---
name: requirements-coverage-review
description: Review implementations against source requirements.
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Requirements, Coverage, Documentation, UX, Safety]
    related_skills: [document-to-action-items, requesting-code-review]
---

# Requirements Coverage Review

Audit an implementation, README, plan, configuration, and tests against one or more source requirement documents. Preserve source conflicts and safety boundaries instead of flattening them into a feature checklist. This skill is for independent review, not implementation or file modification.

Use `references/coverage-matrix.md` for the working matrix and compact report shape.

## When to Use

- Compare a repository or operational tool with product, process, or field manuals.
- Judge whether coverage supports different user needs, complete workflows, and first-time users.
- Review whether README or plan claims are actually implemented.
- Identify requirements that must remain manual or supervised.
- Reconcile overlapping, versioned, or contradictory source documents.

Don't use for a code diff-only review with no source requirements; use `requesting-code-review` or `github-code-review` instead.

## Prerequisites

- Exact repository and authoritative source paths.
- Requested review scope: documentation, implementation, UX, safety, or all four.
- Mutation policy. If the user says read-only or no side effects, treat that as strict: no file writes, cache generation, report creation, snapshots, setup commands, or tests not proven write-free.

## Procedure

### 1. Freeze the evidence set

Inventory the repository and every source document before analysis. Record exact filenames, document titles, apparent versions/dates, and whether extraction is complete. Detect duplicate or revised copies.

If files appear, disappear, or change during review, re-inventory once and report the snapshot discrepancy. Do not silently continue as though the evidence set were stable.

Completion criterion: every source and reviewed deliverable has an identity and readable provenance.

### 2. Extract requirements with modality

Build a matrix with one row per requirement. Preserve:

- persona or operating profile
- prerequisite and dependency
- mandatory, optional, conditional, or prohibited status
- ordered procedure
- completion/acceptance condition
- recovery or cleanup step
- version/model applicability
- safety and credential boundary
- source `path:line`

Do not turn “may,” “recommended,” “only when,” or “can skip” into an unconditional requirement.

Completion criterion: each material source section is represented or explicitly marked out of scope.

### 3. Model variants and contradictions

Group requirements by scenario rather than forcing one linear happy path. Typical branches include base/local/remote, hardware present/absent, old/new software generation, and combinations such as remote plus voice.

For each contradiction, record both source locations, likely discriminator, and one of:

- newer source wins, with evidence
- model/version-specific branch
- operator choice
- unresolved; requires owner decision

Never pick a side silently.

Completion criterion: every detected conflict has an explicit disposition or unresolved marker.

### 4. Inspect all delivery layers

Review these independently:

1. README promises and onboarding.
2. Plan/catalog workflow steps.
3. CLI/menu discoverability and command existence.
4. Configuration schema and wizard choices.
5. Implementation behavior, writes, backups, exit codes, and readiness checks.
6. Tests and what they actually prove.

A keyword appearing in a plan or test is not workflow coverage. Trace each requirement through the layers that are supposed to satisfy it.

Completion criterion: the matrix distinguishes documented, implemented, verified, manual, deferred, and missing states.

### 5. Run three trace passes

- **Requirement → deliverable:** Is every mandatory requirement represented?
- **Claim → behavior:** Are promises such as “dry-run,” “complete plan,” “automatic backup,” and “acceptance” true for every relevant command?
- **Surface → implementation:** Does every advertised command exist, and is every user-facing config field consumed by behavior?

Specifically inspect:

- commands named in plans but absent from the parser
- config fields only defined or validated but never applied
- printed `FAIL` results paired with exit code 0
- WARN states that should block acceptance
- fixed sleeps presented as service readiness
- template copies that overwrite local settings despite merge claims
- backup coverage for non-file state such as route metrics

Completion criterion: no public promise remains unchecked against code.

### 6. Walk the first-time-user journey

Simulate the journey without relying on expert inference:

- installation and prerequisites
- first command and configuration creation
- choosing one or combined scenarios
- discovering identifiers, paths, MACs, URLs, and assets
- previewing exact changes
- applying safely
- recognizing success and failure
- recovering or rolling back
- handing off manual/admin/physical tasks

Check edge branches: no optional hardware, missing environment, old version, remote-only access, and multi-feature deployments.

Completion criterion: each step tells a novice what to do, what success looks like, and what comes next.

### 7. Classify automation boundaries

Use five classes:

- **Read-only:** safe inventory and diagnostics.
- **Reversible configuration:** may automate with validation, exact preview, backup, confirmation, and rollback.
- **Physical/admin/manual:** hardware installation, web-console binding, licenses, credentials, and visual alignment; provide a checklist only.
- **Motion/hazard:** calibration, reset, mapping, grasping, navigation, replay, and pressure tests; require a cleared area, emergency stop, present operator, and explicit motion acknowledgement.
- **Destructive/platform policy:** partitioning, firmware, drivers, udev, machine identity, update policy, swap, or audio-stack masking; keep conditional and separately approved.

Do not equate “not automated” with “not documented.” Manual tasks still need prerequisites, owner, sequence, success criteria, and cleanup.

Completion criterion: every requirement has an automation class and safety rationale.

### 8. Verify without violating scope

Before running anything, inspect the dispatch path for writes; do not trust command names or README assurances. Commands such as wizard, snapshot, report generation, tests, and compilation may write even without an apply flag.

Under strict no-side-effects scope:

- prefer static inspection
- avoid `compileall`, snapshot/report commands, setup actions, and unreviewed tests
- use help/plan/config rendering only after confirming their code paths are read-only
- set `PYTHONDONTWRITEBYTECODE=1` for any permitted Python execution
- never run commands against live robot hardware or services

If execution is permitted only in isolation, use a disposable sandbox and verify the repository remains unchanged.

Completion criterion: every executed check is listed and no prohibited mutation occurred.

### 9. Report by decision priority

Lead with a one-sentence verdict. Then separate:

1. **Must fix** — safety gap, broken advertised flow, missing mandatory requirement, misleading acceptance, or novice-blocking dead end.
2. **Optional improvement** — clarity, ergonomics, richer diagnostics, or maintainability.
3. **Must remain manual** — tasks that should not be automated.

For each must-fix item state: requirement, source evidence, current evidence, gap/impact, and concrete remediation. Cite local evidence as `path:line`; cite both sides of a contradiction.

For a subagent handoff, lead with outcomes and top blockers; do not replay the full source narrative.

## Pitfalls

- Treating a list of scenario names as support for scenario combinations.
- Calling a ten-line summary a “complete plan.”
- Counting tests that assert three keywords as requirement coverage.
- Assuming all no-`--apply` commands are read-only.
- Claiming universal backup when only selected files are backed up.
- Copying raw settings into snapshots and calling the artifact redacted.
- Treating service existence, topic count, or TCP connect as end-to-end acceptance.
- Omitting manual web, tablet, licensing, or physical steps because the CLI cannot perform them.
- Hiding version conflicts behind a single default model.
- Continuing after the source set changes without disclosing the evidence snapshot.

## Verification Checklist

- [ ] All source documents inventoried and readable.
- [ ] Every material requirement has `path:line` provenance.
- [ ] Modality, version, persona, and prerequisites preserved.
- [ ] Contradictions surfaced and dispositioned explicitly.
- [ ] README, plan, CLI, config, implementation, and tests reviewed separately.
- [ ] Every advertised command exists.
- [ ] Every public config field is consumed or labeled reserved.
- [ ] Dry-run, backup, rollback, readiness, and exit-code claims checked against behavior.
- [ ] First-time and combined-scenario journeys evaluated.
- [ ] Manual and hazardous tasks classified rather than omitted.
- [ ] Report separates must-fix, optional, and must-remain-manual items.
- [ ] No files or live systems were modified when scope was read-only.
