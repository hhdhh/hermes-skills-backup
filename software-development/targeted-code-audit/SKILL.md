---
name: targeted-code-audit
description: "Use when auditing code read-only for high-impact defects."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [code-review, audit, read-only, safety, testing]
    related_skills: [requesting-code-review, systematic-debugging]
---

# Targeted Read-Only Code Audit

Audit a named implementation and its surrounding control flow without modifying the repository. Optimize for a small number of reproducible, high-impact findings rather than general review commentary.

## Use When

- The user says **read-only**, **do not modify**, or asks for an audit rather than implementation.
- Scope is limited to named functions/files plus dispatch, validation, tests, or a governing specification.
- The user defines a severity gate such as false PASS, command crash, unsafe write, security failure, or missed mandatory requirements.

For ordinary pre-commit verification with fixes, use `requesting-code-review` instead.

## Non-Negotiable Boundary

Read-only means no source/test/config edits, formatting, auto-fixes, staging, commits, generated fixtures inside the repository, or commands that mutate application state. Use temporary locations for probes if needed. Do not reinterpret permission to run tests as permission to fix failures.

## Workflow

### 1. Lock the scope and impact gate

Convert the request into an explicit inclusion gate. Typical reportable outcomes:

- false PASS / false readiness;
- CLI or dispatch crash on user-reachable input;
- a write that bypasses preview/apply/confirmation or targets an unsafe path;
- omission or contradiction of a mandatory guide/spec requirement.

Exclude style, naming, generic maintainability, speculative hardening, and low-impact test gaps unless they directly enable an included outcome.

### 2. Read the whole execution slice

Inspect together:

1. named implementation;
2. CLI parser and dispatch branch;
3. configuration loading and validation;
4. runner/process and exception boundary;
5. focused unit/integration tests;
6. authoritative guide/revision and local documentation that claims compliance.

Trace inputs through validation → dispatch → implementation → status/exit code. Do not review the named function in isolation.

### 3. Generate concrete failure hypotheses

Prioritize semantic gaps over superficial checks:

- text present versus directive actually active;
- path exists versus object usable/executable;
- return code zero versus output semantically valid;
- configured value versus effective runtime value;
- custom version ordering versus prerelease/build semantics;
- valid leaf value versus malformed container type;
- passing fixture versus production-faithful fixture.

See `references/high-impact-probes.md` for reusable probes.

### 4. Reproduce candidates read-only

Use focused tests or deterministic temporary probes. Demonstrate the exact bad outcome (e.g., comparator returns true for an old prerelease, commented directive yields PASS, malformed JSON section raises an uncaught exception).

A green full suite is supporting context only. It does not disprove an uncovered boundary defect.

### 5. Re-check freshness and citations

Before reporting, re-read the exact cited regions when files may be changing. Ensure line numbers and behavior refer to the latest file contents. If a user says to converge immediately or stop calling tools, stop exploration and report from evidence already gathered—do not make one more “verification” call.

### 6. Apply the severity gate again

For each candidate, ask:

- Is the bad outcome concrete and user-visible?
- Does it meet one of the user’s allowed categories?
- Is it reproduced or directly provable from current code?
- Can it be explained without speculation?

Drop anything that fails this gate. Explicitly state **no high-impact findings** when none remain.

## Reporting Contract

Lead with findings, ordered by impact. Each finding should contain:

- concise title naming the bad outcome;
- `file:line` citation;
- mechanism;
- concrete consequence;
- relevant missing test only when it explains why the defect escaped.

End with a short verification footer: tests/probes run, whether unsafe writes were found, files modified (**none** for read-only audits), and blockers. Do not replay the investigation or add generic suggestions.

## Pitfalls

- Treating substring matches as proof of effective systemd/config semantics.
- Calling any existing file “ready” when execute permission or content matters.
- Trusting hand-rolled version keys without rc/dev/build boundary probes.
- Testing malformed leaf values but never malformed JSON section types.
- Reporting every missing test instead of only tests tied to a confirmed high-impact defect.
- Continuing tool calls after the user explicitly asks for immediate convergence.
- Auto-fixing because a general code-review skill recommends it; the read-only boundary wins.
