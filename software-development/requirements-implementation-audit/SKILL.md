---
name: requirements-implementation-audit
description: "Use when auditing requirements against an implementation."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Audit, Requirements, Gap-Analysis, Safety, Traceability]
    related_skills: [codebase-inspection, document-to-action-items, requesting-code-review]
---

# Requirements-to-Implementation Audit

Compare an authoritative manual, specification, runbook, or policy with a live implementation and produce an actionable gap matrix. This skill owns traceability, automation-boundary decisions, prioritization, and read-only verification. It does not implement the recommendations unless the user separately asks for changes.

## When to Use

- Audit an installer or operations tool against a deployment manual.
- Determine which documented steps are implemented, partially implemented, plan-only, missing, or unsafe.
- Separate safe automation from guarded automation and mandatory human work.
- Produce prioritized recommendations tied to real functions, CLI commands, configuration keys, and tests.

Do not use this as a generic LOC inventory. Load `codebase-inspection` only when code-size/language metrics materially help.

## Deliverable Contract

The final audit should contain:

1. an executive coverage conclusion;
2. a requirement-to-implementation matrix or equivalent grouped list;
3. explicit automation classes and manual boundaries;
4. prioritized, implementable recommendations naming concrete CLI/function surfaces;
5. verification evidence and an honest file-modification statement;
6. unresolved dependencies, such as referenced release tables that were not supplied.

Never treat README claims, planned tests, or menu text as proof that behavior is implemented. Actual parser/dispatch wiring and callable implementation are the minimum evidence; successful tests strengthen but do not replace that evidence.

## Procedure

### 1. Establish authoritative inputs

Identify the exact document export and implementation tree. Record enough version evidence to detect drift: document metadata or checksum, repository revision/status when Git exists, and key-file hashes when it does not.

If the source document references an external spreadsheet, release manifest, image-only value, or permission-gated system that is absent, mark the corresponding requirement `unresolved`; do not infer the missing value.

### 2. Preserve a read-only baseline

When the user requests audit-only work:

- do not patch project files;
- avoid commands that create build artifacts or caches;
- for Python tests, set `PYTHONDONTWRITEBYTECODE=1` where practical;
- hash or inventory relevant source files before and after verification;
- use Git status/diff only if the directory is actually a Git repository;
- if no VCS exists, say so and rely on hashes/file inventories instead of claiming the tree is clean.

Tests and diagnostic commands can still have side effects. Account for them explicitly.

### 3. Extract a normalized requirement inventory

For each requirement, capture:

- source section or line range;
- action/configuration item;
- condition (always, first install, optional hardware, recovery only, image-build only);
- inputs and secrets;
- privilege and connectivity requirements;
- physical or visual judgment required;
- rollback path;
- documented success criterion.

Preserve contradictions and uncertainty. A screenshot-dependent value is not automatically a machine-readable requirement.

### 4. Map the real implementation surface

Inspect, in parallel where possible:

- CLI parser and dispatch;
- public functions and orchestration layers;
- configuration schema/defaults/validators;
- backup and rollback mechanisms;
- diagnostic and report generation;
- service profiles and safety gates;
- tests;
- README/runbook/UI claims.

Search both domain terms and likely implementation primitives. For example, a manual may say “stable NIC names” while code uses `render_netplan`, `nmcli`, or `set-name`.

For each match, verify the complete path:

`CLI or API entry -> dispatch -> implementation -> confirmation/backup -> postcondition check -> test`

A broken link means partial coverage, not full coverage.

### 5. Build the traceability matrix

Use these coverage states consistently:

- **Full** — executable path exists, safety controls fit the risk, and success is verified.
- **Partial** — some configuration or checks exist, but prerequisites, rollback, or verification are incomplete.
- **Plan-only** — the tool documents steps but performs no action.
- **Missing** — no meaningful implementation surface exists.
- **Intentionally manual** — automation would require physical judgment, privileged approval, subjective validation, or unacceptable risk.
- **Unsafe/contradictory** — implementation or source guidance should not be automated as written.

Recommended matrix columns:

| Requirement | Source | Automation class | Coverage | Existing CLI/function | Gap | Priority | Acceptance test |
|---|---|---|---|---|---|---|---|

### 6. Classify the automation boundary

#### Safe automation

Prefer automation when the operation is deterministic, locally observable, idempotent, reversible, and does not require physical interpretation. Examples: schema validation, rendering previews, bounded config updates, read-only diagnostics, status reports, and checksums.

#### Guarded automation

Privileged, network-affecting, service-affecting, or destructive operations require:

1. complete preflight before the first mutation;
2. dry-run/preview;
3. explicit scoped confirmation;
4. backup of every affected state, not only files;
5. atomic or staged application where possible;
6. rollback that is itself validated before it starts;
7. postcondition verification;
8. a nonzero or `needs-attention` result when manual activation remains.

Do not call an orchestration run “complete” if a required local confirmation or reboot has not happened.

#### Mandatory human work

Keep work manual when it depends on:

- physical cable/port identification, insertion, orientation, clearance, or emergency-stop supervision;
- OAuth, administrator approval, license issuance, or device enrollment;
- subjective audio/display/visual inspection;
- firmware flashing or irreversible hardware operations;
- robot motion, calibration, mapping, grabbing, or acceptance testing;
- choosing a security policy rather than applying an already-approved one.

Automation may prepare, validate, and record these tasks, but must not fabricate completion.

#### Never automate source guidance verbatim when it embeds

- passwords, setup keys, tokens, or reusable credentials;
- `curl | sh` without artifact verification;
- broad process killing;
- unconditional machine identity resets;
- disabling security updates globally;
- unbounded wildcard package installation;
- destructive disk/swap changes without topology checks and recovery.

Report exposed credentials without reproducing their values and recommend rotation.

### 7. Prioritize gaps

Use impact and implementation order, not document order:

- **P0** — credential exposure, safety-gate bypass, partial-apply risk, incomplete rollback, overly broad mutation scope, or false success reporting.
- **P1** — missing semantic verification, incomplete version/config coverage, idempotency, source validation, service enablement state, and diagnostics needed for reliable operation.
- **P2** — convenience orchestration, UI polish, optional hardware helpers, and low-risk workflow acceleration.

Each recommendation should name:

- the proposed CLI/API;
- the function/module to add or change;
- prerequisites and safety gate;
- postcondition or acceptance test;
- whether it belongs in the default workflow or an opt-in profile.

### 8. Reconcile a changing implementation

A repository may change while the audit is running. If a hash, mtime, test import, or CLI surface changes unexpectedly:

1. do not blend old and new observations;
2. identify the files that changed;
3. re-read the final parser, dispatch, implementation, tests, and docs;
4. rerun verification on a stable final hash set;
5. report concurrent modification as an audit limitation, not as a product defect unless it remains in the final state.

The durable lesson is to rebaseline, not to preserve a transient failing test as a finding.

### 9. Verify and report

Before finalizing:

- run the existing test suite in read-only mode when feasible;
- exercise key CLI help/preview paths without applying changes;
- verify source hashes did not change during the final test run;
- distinguish current coverage from recommendations;
- state exactly which files were created or modified;
- state whether Git evidence was available.

Lead with outcomes and prioritize concise bullets over a replay of the investigation.

## Common Pitfalls

- Marking a requirement “implemented” because a workflow plan mentions it.
- Treating a test that references a not-yet-wired CLI as proof of current capability.
- Ignoring rollback for non-file state such as hostname, linger, connection properties, or service enablement.
- Applying writes before all later-stage prerequisites have been validated.
- Deriving motion risk only from a profile name instead of the units/actions it contains.
- Calling a route-table read a semantic network verification.
- Copying credentials from the source into findings, examples, tests, or references.
- Turning a manual safety decision into an unattended default.
- Claiming a clean repository when the target is not under version control.

## Verification Checklist

- [ ] Every important source requirement has a coverage classification.
- [ ] Full coverage is backed by a real entry-to-postcondition path.
- [ ] Manual and unsafe boundaries are explicit.
- [ ] P0 items address safety/security/transactionality before convenience.
- [ ] Recommendations name concrete functions or CLI surfaces and acceptance checks.
- [ ] Missing external sources remain unresolved rather than guessed.
- [ ] Final conclusions reflect a stable final implementation snapshot.
- [ ] Audit-only mode left project sources unchanged.

## References

- `references/robot-installer-case-study.md` — sanitized example of applying this method to a robot deployment installer and a large operational manual.
