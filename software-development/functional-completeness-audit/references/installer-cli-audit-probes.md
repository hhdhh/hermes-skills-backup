# Installer and CLI audit probe recipes

These recipes are session-derived details for `functional-completeness-audit`. Adapt names and paths; keep all execution inside temporary directories and fake runners.

## 1. Recording runner

Create a runner with:

- `apply` state
- a `calls` list containing command plus mutation/sudo/check/timeout flags
- deterministic `CommandResult` fixtures selected by command pattern

Important: if production code relies on `Runner.run(..., check=True)` raising, the fake must reproduce that behavior. A fake that merely returns nonzero can reveal a separate top-level bug, but do not mistake it for the exact production path. Test both:

1. a faithful runner that raises on checked failure;
2. a deliberately non-raising dependency seam to verify the dispatcher does not blindly return success from nested failed results.

## 2. Gate-before-mutation probe

For a remote-session or motion gate:

1. Enable the forbidden context in a patched environment.
2. Invoke the apply path with a recording runner.
3. Assert the expected controlled error/exit.
4. Assert **zero** mutation calls, backup creation, temp install, reload, generation, or service start.

This catches guards placed after configuration writes.

## 3. New-target rollback round trip

Run two variants:

### Existing target

- Seed target bytes and mode.
- Apply a mutation.
- Assert manifest points to a contained backup.
- Roll back.
- Assert byte-for-byte content and permission restoration.

### New target

- Ensure target does not exist.
- Apply a mutation.
- Assert manifest has `created=true` (and privilege metadata when applicable).
- Roll back.
- Assert target no longer exists.

A backup helper returning `None` for a nonexistent target must trigger `record_created`; otherwise the apply action is not reversible.

## 4. Hostile manifest probes

Construct manifests covering:

- malformed JSON
- top-level non-object
- `items` non-list
- item non-object or missing fields
- source outside approved roots
- backup outside selected backup directory
- `..` and symlink escapes
- source `/`, home root, or backup root itself
- duplicate and parent/child source pairs
- type mismatch between source and backup
- `created=true` with conflicting backup
- forged `sudo=true`

Assertions:

- validation completes before mutation;
- CLI returns a controlled input-error exit with no traceback;
- no victim changes;
- manifest paths are canonicalized and containment-checked.

## 5. Partial-commit probe

For a multi-file deployment, inject failure at each stage:

1. missing late template/prerequisite;
2. second or later copy/write;
3. final daemon reload or service readiness check;
4. persistence of the tool's own config.

After each failure assert either:

- the file tree equals its initial snapshot, or
- an explicit partial state and usable rollback artifact are returned.

Prefer prevalidating all templates, IDs, destinations, and unit structure before the first copy.

## 6. Exit-code propagation probe

Mock child operations to return or raise failures and call the public CLI dispatcher/main. Assert:

- configuration/input/runtime error → documented error exit;
- check-state failure → documented check-failure exit;
- interrupt → 130 when promised;
- stdout never says “written/started/restored” when a child failed;
- stderr identifies the failing command/item.

Inspect nested JSON: a top-level status calculation that only looks for `item.status == FAIL` can miss `item.result.ok == false`.

## 7. Field-consumption matrix probe

Enumerate every leaf of defaults and example config. For each field:

1. produce a valid alternate value;
2. run validation;
3. call relevant render/action/diagnostic code;
4. compare output, planned commands, persisted state, or check result.

Classify fields with no observable effect as:

- derived/UI-only (document clearly),
- reserved (reject until supported), or
- missing implementation.

Pay particular attention to schema versions, feature flags, route profiles, safety flags/thresholds, environment names, and automatic-enable controls.

## 8. Requirements/diagnostics parity probe

For each manual completion standard, create a row mapping it to an automated check or explicit manual gate. Typical false coverage:

- hardware listed, but model/firmware/function not verified;
- GPU enumerated, but no real compute smoke test;
- at least one ROS topic, but required topics absent;
- recording directory exists, but streams/metadata not validated;
- service unit exists, but readiness or business endpoint not checked;
- manual acceptance is mentioned in prose but cannot block release status.

Use parameterized fixtures where each required signal is individually absent; applicable mandatory checks should become FAIL or explicit INCOMPLETE.

## 9. Documentation parity

Extract or enumerate:

- parser subcommands/options
- public config leaves
- exit-code definitions
- backup/snapshot artifacts
- safety acknowledgements

Compare with README/RUNBOOK command tables and workflow matrix. Newly added CLI/UI features should not silently escape documentation, and documentation must not call an evidence snapshot restorable unless a round-trip test proves it.

## 10. Concurrent-workspace caution

If files change during the audit:

- stop treating earlier reads/tests as the final baseline;
- identify changed files and re-read them;
- rerun affected deterministic probes and the full suite once stable;
- cite lines from the final inspected version;
- disclose that conclusions are scoped to that revision.

Do not edit the audited repository during a read-only review, even to add probes.