---
name: cli-black-box-auditing
description: Use when auditing a CLI safely via black-box commands.
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [cli, qa, audit, smoke-test, safety, exit-codes]
    related_skills: [systematic-debugging, dogfood]
---

# CLI Black-Box Auditing

Audit a command-line application from its public interface while preserving a strict side-effect boundary. The deliverable is an exhaustive, reproducible command matrix with actual exit codes, timeout/crash evidence, semantic findings, and proof that forbidden mutations did not occur.

## When to Use

Use this skill for:

- release smoke tests of a CLI or installer;
- safety audits where `--apply`, `--force`, service changes, or production writes are forbidden;
- recursive command/help enumeration;
- verification of documented exit-code contracts;
- dry-run behavior, diagnostic suites, preflight checks, and temporary snapshots;
- distinguishing expected host-environment failures from product defects.

Do not use it as a substitute for white-box review, unit testing, or an authorized destructive acceptance test. Load `systematic-debugging` only after a reproducible anomaly needs root-cause analysis.

## Required Inputs

Record these before execution:

1. Exact working directory and recommended entry point.
2. Exact config or fixture to use.
3. Allowed write roots, normally one dedicated temporary directory.
4. Forbidden flags, verbs, and side effects.
5. Documented exit-code meanings.
6. Host assumptions, such as whether this is the target appliance.
7. Required output schema and counting rules.

If the user forbids an action verb such as `start`, `stop`, or `restart`, do not invoke that verb merely because the CLI claims to dry-run it. Its `--help` page may still be audited because argument parsing exits before dispatch. Invoke a forbidden verb in dry-run mode only when the user explicitly asks for that coverage.

## Safety Invariants

- Never add `--apply`, `--yes`, `--force`, activation, or an equivalent mutation switch unless explicitly authorized.
- Never start, stop, restart, enable, or disable a service unless explicitly authorized.
- Redirect stdin from EOF for noninteractive probes so an unexpected prompt cannot hang.
- Put every allowed artifact and fixture under a dedicated temporary root.
- Set `PYTHONDONTWRITEBYTECODE=1` for Python CLIs to avoid repository `__pycache__` writes.
- Use an isolated `HOME` only when needed to contain default state writes; disclose it because it can alter behavior.
- Give every command an outer timeout and retain the application's own exit code separately from harness failures.
- Use argument arrays, not `shell=True`, for matrix execution.
- Treat the repository as read-only. Do not create audit logs inside it.

## Procedure

### 1. Discover the public command tree

1. Read the root `--help` output and record its exit code.
2. Recurse through every command group and leaf `--help` page.
3. Extract positional choices, required options, defaults, and mutation flags from live help rather than relying only on README examples.
4. Include `--version` when present.

Completion criterion: every command/group visible from live help has one help-matrix row, and all omissions are explicitly justified.

### 2. Define the expected-result matrix before execution

For each actual probe, specify:

- stable ID and exact argument vector;
- class: help, read-only, dry-run, diagnostic, fixture validation, or allowed artifact write;
- expected exit code or narrow set of codes;
- reason for that expectation;
- required output markers and forbidden error markers;
- timeout;
- allowed write root, if any.

Derive expectations from documentation and the stated host context, not from the observed result. If the host is intentionally not the target appliance and the contract says missing runtime/ROS/services returns `2`, expect `2`; do not relabel it as a bug after seeing it.

Completion criterion: every planned command has a predeclared expectation and safety classification.

### 3. Establish a clean execution boundary

- Use the exact project entry point and config.
- Create temporary fixtures outside the repository.
- Capture a baseline repository state when possible. For Git repositories, use `terminal` with `git status --porcelain`; for non-Git directories, rely on explicit temp roots plus a before/after file inventory if mutation risk matters.
- Keep environment overrides minimal and list them in the report.

Completion criterion: the command cannot write outside declared locations without being detected or violating a documented guard.

### 4. Run one authoritative matrix harness

Use `scripts/run_command_matrix.py` for medium or large matrices. It executes locally in one process, captures stdout/stderr, records integer exit codes and durations, applies timeouts, and flags crash markers. This is more reliable than one orchestration-tool call per command.

Run exploratory probes as needed, but do not count them in the final total. After exploration, run one final authoritative matrix from a clean temporary root.

Completion criterion: every authoritative row has a real integer exit code, duration, output, and timeout/crash fields; there are no null or missing results.

### 5. Exercise both failure and success paths with fixtures

A non-target host may block a dry-run before it reaches rendering logic. Build the smallest complete fixture in the allowed temporary root and point a temporary config at it, then run the same public command without mutation flags.

For validators, include at least:

- missing input;
- structurally invalid input;
- structurally valid and semantically valid input;
- deceptive input that satisfies names/references but has invalid content when practical.

Fixtures must be genuinely valid. For example, do not call a text file with a `.png` suffix a valid image fixture. Such a deceptive fixture is useful only as a negative test for shallow validation.

Completion criterion: prerequisite failures and the deepest safe success path are both observed through the public CLI.

### 6. Classify behavior, not just exit numbers

A command is expected only when all applicable conditions hold:

- actual exit is in the predeclared set;
- output contains required status markers;
- output does not contain a traceback, crash, or contradictory error marker;
- a success claim is semantically justified by the fixture;
- any artifact is complete, parseable, and correctly permissioned;
- no forbidden side effect occurred.

Useful consistency checks:

- exit `0` plus `FAIL`, `error`, or traceback text is suspicious;
- nonzero exit without a corresponding failure marker is suspicious;
- timeout exits (`124`, forced-kill variants) are harness-visible hangs, not ordinary application failures;
- setup/configuration errors and check-result failures may intentionally use different codes;
- a validator returning `0` for malformed content is an unexpected false positive even if its process exit is technically “expected.”

Completion criterion: each authoritative row is assigned exactly once to expected or unexpected, with evidence-based rationale.

### 7. Verify allowed artifacts and repository immutability

For snapshots/reports written to a temporary directory, verify:

- the reported path exists;
- expected files exist and no unexplained files appear;
- JSON or other structured outputs parse;
- sensitive directories/files use restrictive permissions where required;
- the artifact contains a warning when it may include secrets;
- repository state matches the baseline.

Completion criterion: artifact correctness and read-only scope are proven by separate checks, not inferred from exit `0`.

### 8. Aggregate mechanically

Use code to deduplicate, count, and format the authoritative results. Enforce:

- `total == expected + len(unexpected)` when every unexpected item represents one matrix row;
- `crashes` and `timeouts` name exact commands and are consistent with row data;
- exploratory reruns are excluded;
- every unexpected item includes command, actual exit, and a specific reason;
- the final response validates against the user's schema with no surrounding prose when required.

Completion criterion: counts are generated from the result file, never reconstructed from memory.

## Exit-Code Interpretation

Classify exits using the project's contract. A common pattern is:

- `0`: command completed and no failing check exists;
- `1`: usage, config, permissions, prerequisite, or execution error;
- `2`: the command ran correctly but one or more checks failed;
- `130`: user interruption;
- `124` or forced-kill code: timeout/hang imposed by the harness.

These meanings are not universal. Quote or summarize the target CLI's documented contract before classifying results.

## Pitfalls

1. **Counting exploratory duplicates.** Keep a separate authoritative result file and count only it.
2. **Broad expected sets.** Do not use `[0, 2]` when the documented host context predicts exactly one.
3. **Harness failures masquerading as product failures.** Assert every result has an integer exit code; rerun the authoritative matrix if orchestration was incomplete.
4. **Help-only confidence.** `subcommand --help` proves parser reachability, not dispatch behavior.
5. **Dry-run overreach.** A dry-run may still read the live network, services, filesystem, or credentials and may validate prerequisites before rendering.
6. **Literal safety violations.** A forbidden verb remains forbidden unless the user explicitly permits its dry-run invocation.
7. **Shallow-validator false positives.** File existence and a matching reference do not prove content validity.
8. **Temporary HOME distortion.** Isolation is useful, but it may change user-service or config discovery; disclose and, when material, compare with the real HOME read-only.
9. **Exit `0` as the only oracle.** Validate output semantics, artifacts, and side effects independently.
10. **Repository cache writes.** Python bytecode, test caches, and generated reports violate a strict read-only audit unless redirected or disabled.

## Verification Checklist

- [ ] Live help tree recursively enumerated
- [ ] Expectations declared before execution
- [ ] Forbidden verbs/flags absent from actual probes
- [ ] Each command protected by EOF stdin and timeout
- [ ] Every result has an integer exit code
- [ ] No unclassified timeout or crash marker
- [ ] Expected environment failures match documented exit semantics
- [ ] Valid and invalid fixture paths exercised
- [ ] Semantic false positives checked
- [ ] Allowed artifacts parsed and permission-checked
- [ ] Repository unchanged
- [ ] Authoritative rows deduplicated and mechanically counted
- [ ] Final output matches the requested schema exactly

## Supporting Files

- `scripts/run_command_matrix.py` — reusable stdlib harness for deterministic CLI matrices.
- `references/command-matrix-format.md` — matrix schema, expectations, and invocation example.
- `references/appliance-installer-audit-lessons.md` — condensed lessons from a read-only installer audit, including fixture and false-positive patterns.
