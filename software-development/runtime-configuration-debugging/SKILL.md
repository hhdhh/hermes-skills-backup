---
name: runtime-configuration-debugging
description: "Use when runtime behavior disagrees with config files."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [debugging, configuration, python, systemd, runtime]
---

# Runtime Configuration Debugging

## Purpose

Use this skill when a service ignores an apparently correct setting, a configured module never initializes, or multiple copies of similarly named configuration files exist. The central rule is:

> Diagnose the configuration consumed by the running process, not the configuration file that merely looks authoritative.

This complements general systematic debugging with a class-specific workflow for resolving configuration source-of-truth problems.

## Workflow

### 1. Identify the exact runtime entry point

Inspect the service/process launch definition and record:

- executable and arguments;
- interpreter or virtual environment;
- working directory;
- `PYTHONPATH`, `PATH`, and relevant environment variables;
- package location loaded by that interpreter.

For systemd, inspect both the unit and the live process environment. Do not assume an activated interactive shell matches the service.

### 2. Ask the package where its configuration is

Prefer runtime introspection over filename search:

- import the package with the same interpreter used by the service;
- print exported path constants such as `CONFIG_PATH`;
- trace the loader from package initialization to `open()`/parsing;
- print the resolved absolute path and the parsed effective value.

A filename search is useful for discovering candidates, but not for proving which one is active.

### 3. Inventory and compare duplicate candidates

Look for copies in:

- package root versus `configs/`;
- source checkout versus installed `site-packages`;
- examples and templates;
- multiple virtual/Conda environments;
- downloaded wheels versus installed files.

Compare path, mtime, hash, and only the relevant parsed keys. A correct value in an inactive sibling proves nothing.

### 4. Trace gates before drivers

For module/plugin/hardware failures, verify the complete gate chain:

1. feature/module appears in the **effective** enable list;
2. normalization/filtering preserves it;
3. the dispatcher receives it;
4. the registry/config map contains it;
5. the driver branch is entered;
6. construction and readiness checks execute;
7. producer resources are created;
8. consumers attach.

Do not start with driver or hardware theories if the module is filtered out before dispatch.

### 5. Classify logs by control-flow evidence

Distinguish:

- **Skipped initialization:** no registration attempt, no module-specific issue, no device handles/resources.
- **Attempted failure:** traceback, explicit initialization issue, bus/driver error, or readiness failure.
- **Registered but unusable:** registration succeeds but frames/resources never become healthy.
- **Consumer-only failure:** a consumer reports missing IPC/SHM, but this says only that the producer resource is absent—not why.

A hardware report that omits a configured-looking module can itself be evidence that the module never entered discovery.

### 6. Account for stale producer artifacts

Shared memory, sockets, files, and cached registrations may outlive a configuration edit until restart, cleanup, or reboot. This can create a delayed failure pattern:

```text
producer removed from effective config
→ old resource remains temporarily usable
→ service/reboot removes old resource
→ new producer is never started
→ consumers begin failing
```

Correlate config mtimes, service restarts, boot boundaries, producer registration logs, and resource disappearance.

### 7. Use side-effect-free probes

When source is compiled or logs are silent, validate control flow without touching hardware:

- substitute a fake driver/class in a fresh diagnostic process;
- call the discovery function with a minimal enable list;
- confirm constructor, readiness call, registration, and return report;
- avoid starting/stopping the production service or opening real devices.

A successful fake-driver probe proves dispatcher/config flow, not real hardware health. Label that boundary explicitly.

### 8. Verify before concluding

A grounded conclusion should include:

- exact active configuration path;
- effective parsed value;
- why competing files are inactive;
- positive control-flow evidence;
- resource/process evidence;
- timeline explaining when behavior changed;
- separate primary cause from secondary crash/error-handling bugs.

## Pitfalls

- Editing or diagnosing the first same-named file found.
- Treating “available modules” as equivalent to “enabled modules.”
- Treating a consumer’s “shared memory missing” message as a producer root cause.
- Inferring attempted initialization from a native library merely being mapped into the process.
- Assuming a config edit takes effect immediately while stale IPC survives.
- Changing settings before proving which file is active.
- Collapsing a primary configuration gate bug, exception-handling bug, and cleanup crash into one cause.
- Printing secrets while introspecting a large settings object; emit only relevant keys and redact credentials.

## Verification Checklist

- [ ] Service entry point and interpreter confirmed
- [ ] Package import path confirmed
- [ ] Active config path printed by runtime/package loader
- [ ] Relevant effective key parsed and printed
- [ ] Duplicate candidates compared
- [ ] Enable/normalization/dispatch chain traced
- [ ] Producer registration attempt classified
- [ ] IPC/device/process evidence checked
- [ ] Timeline correlated with restart/reboot
- [ ] Primary and secondary failures separated
- [ ] No production mutation performed during diagnosis

## Reference

See `references/packaged-python-service-config.md` for a condensed case pattern involving installed Python packages, systemd, module enable lists, and stale shared memory.