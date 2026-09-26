---
name: safety-critical-configuration-orchestration
description: "Use when designing safe one-click system configuration."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [orchestration, safety, dry-run, resume, rollback, testing]
    related_skills: [requesting-code-review, test-driven-development, systematic-debugging]
---

# Safety-Critical Configuration Orchestration

Design and review “one-click” configuration for robots, appliances, networked hosts, and other systems where convenience must not bypass existing safety gates.

## Core Architecture

1. Add a **thin orchestrator** over existing typed action functions. Do not duplicate action logic and do not recursively invoke the CLI through shell strings.
2. Model an explicit, fixed stage DAG. A safe default is:
   - validation/preflight
   - identity
   - network preparation
   - manual network confirmation
   - application settings
   - read-only verification
3. Keep validation/preflight and final verification mandatory even when users select only some mutation stages.
4. Treat disruptive activation and all physical/motion operations as manual checkpoints. “One click” may prepare them, but must not silently cross them.
5. Reuse the established confirmation system. Apply mode must remain explicit; motion acknowledgements must never be weakened or inherited from a non-motion confirmation.

## Dry-Run Contract

Dry-run is a behavioral guarantee, not just skipped subprocesses:

- No target writes, config saves, backup creation, state mutation, service changes, privilege prompts, or network activation.
- Produce the same ordered stage plan, intended targets, commands, risks, and manual next steps as apply mode.
- Read-only probes are allowed only when clearly represented. If preview must be deterministic/offline, mark deferred verification rather than pretending it ran.
- Verify zero mutation with a before/after tree manifest, excluding known generated caches.

## Checkpoint and Resume Model

Persist each run under a private state directory with atomic `0600` state files and a `0700` directory. Record:

- run ID and timestamps
- tool/schema version
- configuration and plan hashes
- host fingerprint
- selected stages and dependencies
- per-stage status and evidence
- backup session ID/directory
- pending manual checkpoint instructions

Recommended stage states:
`PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `INTERRUPTED`, `WAITING_MANUAL`, `SKIPPED`.

Resume rules:

1. Acquire a cross-process lock before inspecting or changing state.
2. Reject resume when tool version, plan, config, or host identity changed; start a new run instead.
3. Never trust a stale `RUNNING` marker as success. Verify the stage postcondition, then either mark succeeded or rerun idempotently.
4. Reconfirm apply privileges and safety acknowledgements on every resumed process.
5. Do not resume past a manual checkpoint until its postcondition is independently verified.

## Failure and Rollback

- Preflight failure must occur before privilege validation, backup creation, or target mutation.
- Share one signed backup session across an orchestration run.
- Register newly created targets as created; back up only targets that already existed.
- Every mutation target must be restorable by the rollback allowlist. Test this bidirectionally: if an action backs it up, rollback must accept it.
- Default to fail-stop with an explicit recovery report. Automatic rollback is safe only before irreversible/manual checkpoints and only when all mutated targets are covered by verified backups.
- Preserve the original failure and separately report rollback success/failure; never replace one with the other.

## Read-Only Review Under Concurrent Changes

A review can be corrupted by another process modifying the tree even when the reviewer itself writes nothing.

1. Capture a source manifest (path, size, `mtime_ns`, SHA-256) before reading/testing.
2. Recompute after every test/lint batch.
3. If it changed, identify and re-read changed files, then rerun affected tests. Never mix findings from different snapshots.
4. If the tree keeps drifting, issue only a point-in-time/blocked verdict.
5. In a non-Git directory, the manifest is the audit baseline; absence of Git does not justify skipping review.

See `references/review-and-test-matrix.md` for a condensed verification matrix.

## Testing Strategy

Use vertical tests from safety invariants outward:

1. Stage order, selection, dependency closure, invalid combinations.
2. Dry-run zero-mutation and complete plan/report output.
3. Preflight FAIL means zero calls to mutation/backup/privilege functions.
4. Fault injection before and after every stage; no later stage runs after failure.
5. SIGINT/SIGKILL recovery, truncated state, stale `RUNNING`, concurrent-run locking.
6. Apply twice to prove idempotence; rollback to prove byte-for-byte restoration and deletion of newly created targets.
7. Network sandbox/VM tests with fixed MACs and a console fallback; SSH activation must fail before any mutation.
8. Safety regression: orchestration cannot start motion services, calibrate, reset hardware, or run network activation.
9. State/report permissions, secret redaction, signed-manifest tamper rejection, symlink/path traversal cases.
10. Run the complete suite and lint against one stable source snapshot before reporting success.

## Common Pitfalls

- Calling the CLI as a subprocess instead of reusing action APIs.
- Reporting `PREVIEW` for verification that was never run without marking it deferred.
- Saving config after partial apply without including that save in recovery semantics.
- Treating idempotent rerun as sufficient checkpoint recovery without postcondition checks.
- Adding an action target to backup code but not to rollback allowlists.
- Calling a workflow “one-click” while omitting stage selection, resume/status, locks, or explicit manual checkpoints.
- Claiming a clean review after tests ran against files that changed concurrently.
