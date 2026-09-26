---
name: functional-completeness-audit
description: Use when auditing software against docs and safety contra...
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [audit, requirements-traceability, cli, safety, testing]
    related_skills: [github-code-review, systematic-debugging]
---

# Functional Completeness Audit

> 完整描述：Use when auditing software against docs and safety contracts.

Audit whether an implementation, its CLI/API, configuration, tests, and operator documentation form one honest, complete contract. This is especially useful for installers, deployment tools, operations utilities, migration tools, and safety-sensitive automation.

## Use When

- A user asks for an independent functional/completeness audit.
- Behavior must be traced to manuals, specifications, README, RUNBOOK, or an acceptance matrix.
- The review must cover dry-run/apply semantics, safety gates, rollback, exit codes, error paths, or configuration-field implementation.
- The system can mutate hosts, networking, services, credentials, or physical equipment and the audit itself must remain read-only.

For ordinary PR style/quality review, use `github-code-review`. For one known bug, use `systematic-debugging`. Use this skill when the core question is **whether the whole documented product contract is actually implemented and testable**.

## Non-Negotiable Principles

1. **Trace requirements, not just code.** A clean implementation can still be incomplete.
2. **Public fields are promises.** A field in defaults, examples, UI, or docs is not implemented merely because it parses.
3. **Audit the top-level contract.** Helper behavior is insufficient if the CLI emits the wrong exit code or success message.
4. **Rejected operations must be mutation-free.** A safety gate that runs after a write is a critical semantic defect.
5. **Rollback claims require round-trip proof.** Creating an artifact and restoring it must be exercised together.
6. **Expected bad input must fail cleanly.** No traceback, ambiguous partial state, or fabricated success.
7. **Read-only means read-only.** Never run real apply, sudo mutations, network activation, service starts, or motion while auditing.

## Workflow

### 1. Establish the evidence boundary

Inventory:

- CLI/API entry points and all subcommands/actions
- defaults and example configuration
- core actions and mutation boundaries
- README, RUNBOOK, requirement manuals/specifications
- test suite and CI/lint/syntax commands
- current repository baseline when available

If original manuals or links are unavailable, say explicitly that traceability is based on repository summaries/transcriptions. Do not claim independent verification of source documents you could not inspect.

For a live or concurrently edited workspace, capture a stable baseline (commit/status or hashes/timestamps). Re-check it before finalizing and re-read changed files; otherwise line citations and conclusions may describe mixed revisions.

### 2. Build a requirements matrix

Use this shape:

| Requirement/source | CLI entry | Config fields | Core action | Dry-run | Apply | Safety gate | Exit code | Rollback | Tests |
|---|---|---|---|---|---|---|---|---|---|

Enumerate every CLI subcommand and every leaf field in defaults/examples. For each field classify:

- validated
- consumed
- persisted
- reflected in diagnostics/status
- documented
- tested

A field that is only declared, displayed, or saved is **not implemented**. Treat unused safety-looking fields as higher severity because operators may rely on them.

### 3. Run safe baseline verification

Run the full unit suite, syntax/compile checks, shell syntax checks, and configured linters when available. Record actual test counts and failures. Do not summarize a red suite as passing.

Do not write ad-hoc probes into the repository. Use temporary directories, in-memory fixtures, and fake/recording runners. Keep every probe deterministic and inspectable.

### 4. Probe behavior combinations

Cover both sides of each relevant state machine:

- dry-run vs apply
- existing target vs newly created target
- local/LAN-only vs 5G vs Wi-Fi combinations
- local vs remote server mode
- enabled vs disabled feature profiles
- successful child command vs first/middle/last failure
- valid vs malformed config/manifest/report input
- interactive confirmation, `--yes`, missing acknowledgement, EOF, and interrupt

Test observable contracts:

- stdout and stderr
- process exit code
- commands attempted and whether they are mutations
- file tree and permissions
- persisted configuration
- generated manifest/report
- rollback result and final system state

### 5. Audit mutation and rollback boundaries

For every mutation:

1. Validate all prerequisites before the first write, or define automatic rollback.
2. Ensure the safety/remote-session/motion gate runs before backup, write, generate, reload, or start.
3. Existing targets must be backed up.
4. New targets must be recorded as created so rollback removes them.
5. Child-command failure must propagate to the top-level CLI.
6. Partial application must be surfaced and recoverable.

Treat restore manifests as hostile input. Validate their schema/version, item types, source allowlist, backup containment, symlinks, duplicates, nested paths, and privileged entries **before restoring the first item**.

A “snapshot” and a “backup” are different unless the snapshot can actually be consumed by rollback. Documentation must not promise restoration from an evidence-only snapshot.

### 6. Audit diagnostics and acceptance semantics

Map each automated or manual completion criterion to one of:

- concrete PASS/FAIL check
- explicit SKIP with reason
- explicit manual INCOMPLETE gate

Mandatory criteria must not silently become WARN if a zero exit code means “ready.” For hardware or physical workflows, distinguish enumeration from functional validation (for example, GPU listing vs real computation, topic existence vs required topic, directory existence vs recorded-content validation).

### 7. Rank findings by consequence

**Critical** generally includes:

- arbitrary overwrite/delete or privilege-boundary weakness
- safety gate checked after mutation
- motion/network mutation bypassing required acknowledgement
- documented rollback incapable of restoring a safety-critical change

**Major** generally includes:

- public but unused configuration fields
- partial commit on an expected failure
- wrong top-level exit code or false success message
- mandatory requirement missing or downgraded to WARN
- documentation/CLI contract mismatch
- unhandled expected error path
- red regression suite or untestable mutation boundary

Phrase each finding as **cause → observable consequence → violated contract**.

### 8. Specify regression tests precisely

Every suggested test should state:

- fixture/setup
- action invoked
- injected condition or combination
- expected exit code
- expected mutation calls or absence thereof
- expected persisted/final state
- expected rollback behavior when relevant

“Add a test” is not sufficient.

## High-Value Testing Patterns

- **Recording runner:** records commands and mutation/sudo/check flags; returns controlled results.
- **Temporary filesystem:** redirects homes, config, assets, reports, and backup roots without touching host paths.
- **Failure injection:** fail each mutation boundary independently.
- **Round-trip test:** apply → inspect manifest → rollback → byte/permission comparison.
- **Field contract parameterization:** change every public config leaf and assert validation or observable behavior.
- **Docs parity test:** compare parser subcommands/options and public configuration keys with README/RUNBOOK tables.

See `references/installer-cli-audit-probes.md` for concrete probe recipes and pitfalls distilled from a safety-sensitive installer audit.

## Common Pitfalls

- Reviewing only happy paths or only diffs.
- Trusting `check=True` in a fake runner that never raises; top-level propagation must be tested explicitly.
- Treating `returncode=0, skipped=true` as successful execution in dry-run output.
- Checking a remote-session guard only around activation while writing configuration before the guard.
- Assuming a backup helper records a nonexistent target.
- Assuming any snapshot is restorable because docs call it “rollback.”
- Accepting Python truthiness as Boolean schema validation.
- Allowing unknown schema versions or fields to merge silently.
- Citing stale line numbers after concurrent edits.
- Claiming original-manual conformance when only a repository transcription was available.

## Completion Checklist

Before reporting:

- [ ] Every CLI entry and public config leaf is in the matrix.
- [ ] All relevant requirement sources were inspected or the evidence limitation is disclosed.
- [ ] Full tests/syntax checks were run and actual results recorded.
- [ ] No dangerous apply/motion/network action was executed.
- [ ] Each critical/major finding has current `path:line` evidence.
- [ ] Each finding has a deterministic regression-test proposal.
- [ ] Dry-run, apply, failure, and rollback semantics were checked end-to-end.
- [ ] Final output exactly matches any requested machine schema.
