---
name: runbook-automation-safety-review
description: Classify runbook steps and audit automation safety.
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [runbooks, automation, safety, release-engineering]
    related_skills: [systematic-debugging, requesting-code-review]
---

# Runbook Automation Safety Review

Classify operational instructions against the real implementation, then recommend the smallest reversible improvement. This skill is for analysis and design review; it does not turn a runbook into an installer by copying shell commands.

## When to Use

- A new deployment, update, migration, driver, or hardware guide must be compared with an existing tool.
- The user asks which steps are safe to automate, preview-only, or necessarily manual.
- A manifest-driven updater is being extended beyond its current artifact or rollback domain.
- The user requires a read-only audit with concrete implementation gaps.

Do not use this as permission to execute a runbook. If the user asks for implementation, complete this review first, then use the appropriate coding and testing workflow.

## Classification Model

Classify **each atomic action**, not each document chapter. A chapter may contain all three classes.

### Safe to automate

Use only when all of these are true:

1. Inputs and targets are explicit and machine-validated.
2. Artifact provenance and integrity are established independently of the artifact itself.
3. Preconditions fail closed before the first mutation.
4. The mutation is narrow, deterministic, non-interactive, and idempotent where practical.
5. Backup and rollback cover the same state domain being changed.
6. Postconditions test the effective or runtime state, not merely path existence.
7. The action does not require physical identity, human judgment, robot motion, or acceptance of an interruption.

A human may still need to approve the plan or supply a validated value. In that case, state: “human confirms value; write can be automated.”

### Verification or preview only

Use when useful evidence can be collected safely, but mutation is not yet safe. Common cases:

- Template-to-live configuration comparison.
- Package, archive, dependency, version, unit, device, or effective-environment checks.
- Exact diff generation for a future narrow patch.
- Simulation such as package-manager dry-run.
- Missing provenance, incomplete rollback, conflicting requirements, or uncertain semantics.

Preview-only is not a weak PASS. Return explicit PASS/WARN/FAIL or READY/BLOCKED criteria and explain what still requires approval.

### Must be manual

Keep the action manual when it involves any of the following without a purpose-built, independently reviewed workflow:

- Credentials, licensing, access grants, or publisher identity decisions.
- Physical cabling, device identity, serial/bus mapping, calibration, motion, or safety monitoring.
- Kernel/DKMS, firmware, ABI-compatibility shims, bootloader, partitioning, or Secure Boot decisions.
- Unknown installer scripts, database migration prompts, destructive deletion, network cutover, or reboot.
- Choosing machine-specific values that cannot be inferred safely.
- Business or operational acceptance that cannot be proven by software alone.

“Manual” does not prohibit automation of prerequisites, evidence collection, backups, or validation.

## Read-Only Discipline

When the user says not to modify files:

1. Read the named source document first and record its title/revision.
2. Inspect the exact implementation path and version the user named.
3. Do not write reports, plans, patches, caches, downloads, or generated artifacts into either workspace.
4. Do not run installers, package managers, daemon reloads, service actions, or commands with hidden mutation.
5. Run tests only when they are known to use temporary directories and project bytecode/cache writes are disabled; otherwise rely on source inspection and say why.
6. Use Git status/diff when the directory is a repository. If it is not, do not treat that as a blocker or claim Git-based cleanliness; rely on captured start/end metadata or hashes for files actually inspected.
7. If files change during the audit, re-read relevant changed files, separate the requested baseline from the live state, and do not attribute concurrent edits to yourself or another actor without evidence.
8. Report “files modified: none” only for actions performed by this review. Mention concurrent drift separately.

## Procedure

### 1. Establish both baselines

Capture the document revision, stated tool version, actual live version, repository/workspace location, and relevant file list. If the stated and live versions differ, preserve both in the report rather than silently switching baselines.

Completion criterion: the report can distinguish “requested baseline,” “files inspected,” and “live state at completion.”

### 2. Atomize the runbook

Split compound instructions into separate actions such as:

- discover/select artifact;
- download or transfer;
- inspect and authenticate;
- install or copy;
- migrate configuration;
- reload/restart/reboot;
- verify version, effective configuration, runtime, and hardware.

Completion criterion: every command and every prose-only decision in the runbook maps to a row or a clearly named sub-step.

### 3. Inspect real implementation boundaries

Read the code, schema, CLI, tests, and documentation. Identify:

- allowed artifact kinds and target environments;
- completeness requirements for a release;
- archive and metadata validation;
- trust root or external signature/checksum;
- dry-run and confirmation gates;
- service quiescence and interruption handling;
- backup contents and rollback domain;
- exact post-install verification;
- tests that prove the safety claim.

Do not infer support from a CLI label or README claim when the execution path does less.

Completion criterion: each claimed capability cites a concrete implementation behavior or is marked absent.

### 4. Build a state-domain matrix

For every atomic step, record:

| Field | Meaning |
|---|---|
| Action | Exact operation or decision |
| State domain | Python/Conda, `/opt`, APT/kernel, systemd, app/database, hardware, reboot, etc. |
| Existing support | Full, partial, validation-only, or none |
| Classification | Safe automation, preview-only, or manual |
| Missing controls | Preconditions, provenance, backup, rollback, or runtime proof |
| Minimal change | Smallest safe next capability |

Completion criterion: no mutation is described as rollback-safe using a backup from a different state domain.

### 5. Audit provenance and release selection

An SHA-256 stored inside the same downloaded bundle proves internal consistency, not publisher authenticity. Prefer a signed manifest, trusted release channel, or independently delivered digest. Reject wildcard “latest” selection unless the release policy is explicit and machine-checkable. Require release profiles to enforce mandatory package completeness when the guide names a fixed set.

Completion criterion: integrity, authenticity, version selection, and release completeness are assessed separately.

### 6. Audit configuration migration

Never classify whole-file `.example` replacement as safe merely because `cp` is deterministic. Prefer:

1. parse and validate old/live/new-template files;
2. produce a three-way or semantic diff;
3. preserve machine identity, credentials, calibration, hardware mappings, and unknown keys;
4. patch only approved keys;
5. back up and atomically write;
6. parse again and verify effective state.

URDF, calibration, module lists, USB mappings, licenses, and machine identity normally require human confirmation even if the final narrow write is automated.

Completion criterion: the proposed migration names preserved fields and the exact keys allowed to change.

### 7. Demand evidence at the right depth

Use this evidence ladder:

1. **Existence:** file, directory, command, or unit exists.
2. **Structure:** archive, JSON/TOML/YAML, ELF, package metadata, or unit parses correctly.
3. **Intent:** configured values equal the approved plan.
4. **Effective state:** service manager, linker, package manager, or environment reports the applied value.
5. **Runtime:** plugin loads, service responds, device enumerates, or application performs the expected function.
6. **Operational acceptance:** a human confirms physical behavior, migration correctness, or safe restart.

Do not promote levels 1–2 to a full PASS when the guide’s outcome requires levels 4–6. Parse and compare version thresholds; command exit code alone is insufficient.

### 8. Recommend the minimum safe sequence

Prefer this order:

1. Add read-only checks and a complete plan.
2. Resolve document contradictions and establish trusted release metadata.
3. Automate narrow, reversible file updates with backup and semantic verification.
4. Add state-domain-specific transactions only when rollback is real.
5. Keep kernel, firmware, unknown scripts, database choices, physical mappings, and reboot manual until separately engineered.

Completion criterion: recommendations are small enough to implement independently and do not imply a broader rollback guarantee than exists.

## Critical Pitfalls

- **Rollback-domain mismatch:** `pip freeze` can restore Python packages; it cannot restore `/opt`, APT/DKMS, systemd files, databases, firmware, or hardware settings.
- **Embedded digest trust:** a manifest and payload compromised together can still match.
- **Glob installs:** wildcard selection can install multiple or stale artifacts and cannot prove “latest.”
- **Existence-only validation:** `ls` does not prove archive provenance, ABI compatibility, plugin loading, service effectiveness, or device function.
- **Systemd shell assumptions:** `Environment=` is not a shell; values such as `$LD_LIBRARY_PATH` require explicit effective-state verification and often an `EnvironmentFile=` or complete value.
- **ABI symlink shortcuts:** linking a new SONAME to an older expected name can hide incompatibility. Treat it as manual unless ABI compatibility is demonstrated.
- **Unknown install scripts:** archive path safety does not make `install.sh` or a database migration safe.
- **Conflicting thresholds:** report both requirements, use the stricter threshold for blocking validation, and request source correction.
- **Concurrent drift:** a live tool changing during review invalidates a single-version conclusion; report both snapshots.

## Output Format

Lead with the outcome, then provide:

1. a per-step classification table;
2. concrete implementation gaps tied to code behavior;
3. a numbered list of minimal safety improvements;
4. document contradictions or unsafe assumptions;
5. verification performed, files created/modified, and blockers.

Keep session-specific detail out of this file. For a worked GStreamer/robot update example, read `references/gstreamer-robot-update-case.md`.

## Verification Checklist

- [ ] Every atomic runbook action is classified.
- [ ] Conditional automation names all prerequisites.
- [ ] Current capability is distinguished from proposed capability.
- [ ] Integrity is distinguished from authenticity.
- [ ] Backup/rollback scope matches each mutation domain.
- [ ] Verification depth matches the promised outcome.
- [ ] Machine-specific, physical, disruptive, and unknown-script actions remain manual.
- [ ] Minimal improvements begin with read-only evidence.
- [ ] Requested baseline and live end state are both reported if they differ.
- [ ] No files were modified when the task was read-only.
