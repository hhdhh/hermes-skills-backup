---
name: robotics-multimedia-diagnostics
description: "Use when robot camera/audio SHM pipelines fail or restart."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [robotics, camera, rgbd, shared-memory, systemd, diagnostics]
    related_skills: [systematic-debugging]
---

# Robotics Multimedia Diagnostics

## Purpose

Diagnose Linux robot multimedia pipelines where hardware producers publish frames/audio through shared memory and downstream vision, perception, or recognition services consume them. The workflow separates the first failure from secondary crashes and avoids changing the machine until the effective runtime configuration is proven.

## Core model

Treat the pipeline as ordered layers:

1. **Effective configuration** selects modules and drivers.
2. **Hardware discovery** constructs and registers producers.
3. **Producer runtime** opens USB/V4L2/ALSA devices.
4. **IPC publication** creates SHM data, metadata, and synchronization objects.
5. **Consumers** attach to those objects.
6. **Application logic** processes frames/audio.
7. **Cleanup and supervision** govern crashes and restarts.

A consumer saying “SHM does not exist” proves only that publication is absent. It does not prove that SHM itself is defective.

## Required workflow

### 1. Establish a tight, read-only feedback loop

Use one observation set that can turn green after repair:

- service state and restart counter;
- producer registration line;
- expected SHM object names;
- consumer attachment line;
- relevant hardware node ownership/occupancy.

Do not begin with edits, reinstallations, symlinks, or service rewrites.

### 2. Resolve the effective configuration path

Never infer the active config from filenames or nearby copies.

Determine it from at least one runtime source:

- package constants such as `*_CONFIG_PATH`;
- startup logs that print the loaded path;
- process command line and environment;
- source call chain that opens the file;
- a harmless runtime import that prints the resolved constant.

Then compare the effective file with similarly named copies. Record which copy is active and which copies are decoys. Confirm the target module is present in the actual enabled-module list.

### 3. Trace selection into producer registration

For the target module, verify in order:

- it exists in the available-module catalog;
- it is present in the effective enabled list;
- normalization preserves it;
- discovery receives it;
- the expected driver model/version resolves;
- construction/read/register branches execute.

If logs are silent, use a **non-hardware control-flow probe**: replace the driver class in a disposable Python process with a fake implementation that logs constructor/read/register calls. This validates module-selection logic without opening devices or creating SHM. Never inject the fake into the live service.

### 4. Separate producer absence from hardware failure

Classify evidence:

| Evidence | Interpretation |
|---|---|
| No producer registration and no device FD | initialization skipped or failed before open |
| Producer registration exists, SHM absent | publication/configuration failure |
| SHM exists, consumer attach fails | naming/protocol/permissions/stale-object mismatch |
| Device enumerates in a separate process only | hardware is visible, but live driver path still needs tracing |

Inspect hardware only after selection and registration are understood: USB topology, V4L2/ALSA nodes, permissions, open FDs, supported profiles, firmware, runtime linkage, and kernel errors.

### 5. Check SHM as a contract

Compare producer and consumer contracts exactly:

- data and metadata names;
- protocol (`v1`, ring buffer, etc.);
- slot count and frame geometry;
- pixel format and stream names;
- synchronization object names;
- ownership and permissions.

Also check `/dev/shm` capacity and inodes, but do not mistake abundant free space for proof that a producer ran.

### 6. Read systemd state correctly

`active` can be a transient illusion when `Restart=always` is set. Check together:

- `ActiveState`, `SubState`, `Result`, `ExecMainStatus`;
- `NRestarts` twice with a delay;
- recent `Main process exited` records;
- `Requires`, `BindsTo`, and `PartOf` for dependent services;
- start/stop timeout behavior.

A dependent service whose start job is canceled may merely have been stopped because its bound parent crashed during `ExecStartPre`.

### 7. Build a causal fault tree

Report problems by layer:

- **Primary cause:** earliest condition that prevents intended operation.
- **Secondary application bug:** bad exception/degradation path.
- **Cleanup bug:** hang, timeout, or native crash during shutdown.
- **Environmental noise:** warnings that do not block startup.

Do not promote a later logger exception, cleanup segfault, or network warning to the SHM root cause if the producer was never selected.

## Verification after an authorized fix

Require all of the following:

1. producer registration appears;
2. expected SHM data and metadata objects exist;
3. consumers attach successfully;
4. service remains running and restart count stops increasing;
5. dependent recognition/perception service starts;
6. an end-to-end frame or recognition event is observed.

## Pitfalls

- **Wrong config copy:** package layouts often contain both `package/configs/model.json` and `package/model.json`; only runtime resolution decides which matters.
- **Available is not enabled:** a module printed in “Available modules” can still be omitted from initialization.
- **Loaded library is not active hardware:** an ELF mapping proves import/linkage, not device open or producer registration.
- **Hardware enumeration is not application success:** a standalone SDK may enumerate a camera while the service skips its driver entirely.
- **Do not globally replace repeated flags:** settings such as lazy reading may occur for many cameras; target the exact module path.
- **Do not leak secrets:** when printing resolved settings, redact API keys, tokens, passwords, and app secrets.
- **Do not use ABI symlinks as a guess:** a SONAME mismatch requires compatibility evidence or matched packages.

## Session reference

See `references/rgbd-shm-producer-consumer-case.md` for a condensed real-world case showing effective-config resolution, producer/consumer separation, systemd dependency effects, and verification evidence.