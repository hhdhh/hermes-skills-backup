---
name: systematic-debugging
description: "4-phase root cause debugging: understand bugs before fixing."
version: 1.1.0
author: Hermes Agent (adapted from obra/superpowers)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [debugging, troubleshooting, problem-solving, root-cause, investigation]
    related_skills: [test-driven-development, subagent-driven-development]
---

# Systematic Debugging

## Overview

Random fixes waste time and create new bugs. Quick patches mask underlying issues.

**Core principle:** ALWAYS find root cause before attempting fixes. Symptom fixes are failure.

**Violating the letter of this process is violating the spirit of debugging.**

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you haven't completed Phase 1, you cannot propose fixes.

## The Feedback Loop Rule

The feedback loop is the debugging work. Before reading code to build a theory, create or identify a **tight** command that can go red on the user's exact symptom and green when the bug is fixed. A tight loop is fast, deterministic, agent-runnable, and specific enough to catch this bug — not merely "doesn't crash".

When a clean repro is hard, spend disproportionate effort building the loop. Guessing without a red-capable loop is the failure mode this skill exists to prevent.

## When to Use

Use for ANY technical issue:
- Test failures
- Bugs in production
- Unexpected behavior
- Performance problems
- Build failures
- Integration issues

**Use this ESPECIALLY when:**
- Under time pressure (emergencies make guessing tempting)
- "Just one quick fix" seems obvious
- You've already tried multiple fixes
- Previous fix didn't work
- You don't fully understand the issue

**Don't skip when:**
- Issue seems simple (simple bugs have root causes too)
- You're in a hurry (rushing guarantees rework)
- Someone wants it fixed NOW (systematic is faster than thrashing)

## The Four Phases

You MUST complete each phase before proceeding to the next.

## Integration and Installer Failures: Separate the Primary Outcome from Cleanup

For workflows that download artifacts, launch a browser/helper process, or invoke a nested subprocess, classify each stage independently before proposing a fix:

1. **Primary operation:** Did authentication, artifact discovery, download, extraction, or installation actually succeed? Verify with concrete outputs such as counts, file sizes, checksums, and exit status.
2. **Post-operation cleanup:** Did process shutdown, temporary-directory cleanup, or wrapper teardown fail after the primary operation? Do not report the whole operation as failed if its deliverable is intact.
3. **Propagation:** Identify how the cleanup exception became the outer command's non-zero exit (for example, a nested subprocess raising `CalledProcessError`).
4. **Repair at the lifecycle boundary:** Make helper/process termination explicit, wait for child processes or process groups, and make cleanup retry-safe. Avoid merely suppressing cleanup errors unless leaving residue is acceptable and verified.

For installer/license failures, also verify the **package contract** rather than assuming the wizard and package agree. Trace every required input (tool path, generated file, config path) to its producer and compare that contract with the actual artifact contents. If the runtime service computes or logs a value such as a machine identity, treat that as evidence of the service's implementation, but do not silently bypass the intended licensing flow or fabricate a missing signing artifact. A robust diagnostic report should distinguish:

- missing producer/tool versus invalid generated artifact;
- file existence versus semantic validity;
- configuration path versus the path actually read by the service;
- wizard failure versus the service's independent runtime failure.

---

## Phase 1: Root Cause Investigation

**BEFORE attempting ANY fix:**

### Hardware/SDK Layer Separation

When a component name looks like a Linux module (for example, `mod_microphone_main`), first establish which layer owns it. Robot SDK module names are often user-space configuration/registry identifiers, not kernel `.ko` modules; do not infer that `modprobe` is appropriate. Check the service's enabled-module configuration and startup report, then inspect the real device (`/dev`, ALSA/GStreamer/udev) before changing anything.

For device-busy failures, identify the exact device node and its holder, not merely related processes. Use service logs plus `/proc/<pid>/fd` or `fuser`/`lsof` (with authentication available) to map the holder to a command. Stop only the confirmed conflicting process, then restart the dependent service and verify both the service state and the successful device registration. A running service is not enough: verify the functional chain (for example, `GStreamer microphone started`, device registered on the intended `hw:X,Y`, and the higher-level consumer/VAD/chatbot bound to it).

### Distinguish Layers Before Loading or Changing Anything

In robotics/Linux incidents, first identify whether the named component belongs to the kernel, a user-space SDK, a ROS node, or a systemd service. Names such as `mod_microphone_*`, `mod_camera_*`, and `mod_battery_*` may be SDK/configuration modules, not kernel `.ko` modules. Do not infer that `modprobe <name>` is appropriate from a module-like name. Verify with the service's startup logs, active configuration, package contents, and `/lib/modules/$(uname -r)` before proposing kernel-module changes.

For a service that remains `active`, separate startup health from feature health: verify `ActiveState/SubState/Result/ExecMainStatus/NRestarts`, then inspect the feature's registration/initialization lines and its real data path (for ROS, topic list/info/hz). A successful process does not prove every feature works, and a quiet `journalctl -f` does not prove a hang; `-f` only waits for new log lines.


### 1. Read Error Messages Carefully

- Don't skip past errors or warnings
- They often contain the exact solution
- Read stack traces completely
- Note line numbers, file paths, error codes

**Action:** Use `read_file` on the relevant source files. Use `search_files` to find the error string in the codebase.

### 2. Build a Tight Feedback Loop

- Can you trigger the user's exact symptom with one command?
- Does the command fail for this bug and only pass once the bug is fixed?
- Is it fast enough to run repeatedly?
- Is it deterministic? For flaky bugs, can you raise the reproduction rate high enough to debug?
- If not reproducible → gather more data, don't guess.

**Ways to construct a loop — try in roughly this order:**

1. **Failing test** at the seam that reaches the bug: unit, integration, or end-to-end.
2. **HTTP script / curl** against a running dev server.
3. **CLI invocation** with fixture input, diffing stdout/stderr against expected output.
4. **Headless browser script** (Playwright/Puppeteer) asserting on DOM, console, or network.
5. **Replay a captured trace**: HAR, request payload, event log, queue message, or webhook body.
6. **Throwaway harness** that boots the smallest useful slice of the system and calls the failing path.
7. **Property / fuzz loop** when the bug is intermittent wrong output over a broad input space.
8. **Bisection harness** suitable for `git bisect run` when the bug appeared between two known states.
9. **Differential loop** comparing old vs new version, two configs, two providers, or two datasets.
10. **Human-in-the-loop script** only as a last resort: script the human steps and capture their result so the loop stays structured.

**Tighten the loop once it exists:**

- Make it faster: cache setup, narrow scope, skip unrelated initialization.
- Make the signal sharper: assert the exact symptom, not generic success.
- Make it more deterministic: pin time, seed randomness, isolate filesystem, freeze network.

For non-deterministic bugs, the immediate goal is a higher reproduction rate, not perfection. Run the trigger 100x, parallelize, add stress, narrow timing windows, or inject sleeps. A 50% flake is debuggable; a 1% flake usually is not.

**Action:** Use the `terminal` tool to run the tight loop:

```bash
# Run a specific failing test
pytest tests/test_module.py::test_name -v

# Or run a scripted repro
python scripts/repro_bug.py

# Or run a high-repetition flaky repro
for i in {1..100}; do pytest tests/test_flake.py::test_name -q || break; done
```

### 3. Check Recent Changes

- What changed that could cause this?
- Git diff, recent commits
- New dependencies, config changes

**Action:**

```bash
# Recent commits
git log --oneline -10

# Uncommitted changes
git diff

# Changes in specific file
git log -p --follow src/problematic_file.py | head -100
```

### 4. Gather Evidence in Multi-Component Systems

**WHEN system has multiple components (API → service → database, CI → build → deploy):**

**BEFORE proposing fixes, add diagnostic instrumentation:**

For EACH component boundary:
- Log what data enters the component
- Log what data exits the component
- Verify environment/config propagation
- Check state at each layer

Run once to gather evidence showing WHERE it breaks.
THEN analyze evidence to identify the failing component.
THEN investigate that specific component.

### 5. Trace Data Flow

**WHEN error is deep in the call stack:**

- Where does the bad value originate?
- What called this function with the bad value?
- Keep tracing upstream until you find the source
- Fix at the source, not at the symptom

**Action:** Use `search_files` to trace references:

```python
# Find where the function is called
search_files("function_name(", path="src/", file_glob="*.py")

# Find where the variable is set
search_files("variable_name\\s*=", path="src/", file_glob="*.py")
```

### Phase 1 Completion Checklist

- [ ] Error messages fully read and understood
- [ ] A tight loop command exists and has been run at least once
- [ ] Loop is red-capable: it asserts the user's exact symptom, not a nearby failure
- [ ] Loop is deterministic, or a flaky bug has a high enough reproduction rate to debug
- [ ] Recent changes identified and reviewed
- [ ] Evidence gathered (logs, state, data flow)
- [ ] Problem isolated to specific component/code
- [ ] Root cause hypotheses can be stated and tested

**STOP:** Do not proceed to Phase 2 until you understand WHY it's happening.

---

## Phase 2: Pattern Analysis

**Find the pattern before fixing:**

### 0. Minimize the Reproduction

Once the loop is red, shrink the repro to the smallest scenario that still goes red. Cut inputs, callers, config, data, and steps **one at a time**, re-running the loop after each cut. Keep only what is load-bearing for the failure.

Done when removing any remaining element makes the loop go green. A minimal repro narrows the hypothesis space and often becomes the cleanest regression test.

### 1. Find Working Examples

- Locate similar working code in the same codebase
- What works that's similar to what's broken?

**Action:** Use `search_files` to find comparable patterns:

```python
search_files("similar_pattern", path="src/", file_glob="*.py")
```

### 2. Compare Against References

- If implementing a pattern, read the reference implementation COMPLETELY
- Don't skim — read every line
- Understand the pattern fully before applying

### 3. Identify Differences

- What's different between working and broken?
- List every difference, however small
- Don't assume "that can't matter"

### 4. Understand Dependencies

- What other components does this need?
- What settings, config, environment?
- What assumptions does it make?

---

## Phase 3: Hypothesis and Testing

**Scientific method:**

### 1. Form Ranked Falsifiable Hypotheses

- Generate 3–5 plausible hypotheses before testing any single one.
- Rank them by likelihood and cheapness to falsify.
- State the prediction each hypothesis makes: "If X is the cause, then changing or observing Y should make Z happen."
- Discard or sharpen any hypothesis that does not make a testable prediction.

If the user is present, show the ranked list before testing. They may have domain knowledge that instantly re-ranks it. If the user is AFK, proceed with your ranking.

### 2. Test Minimally

- Test the highest-ranked hypothesis with the smallest possible probe.
- Change one variable at a time.
- Don't fix multiple things at once.
- Prefer debugger/REPL inspection when available; one breakpoint beats ten logs.
- If you add logs, tag every temporary line with a unique prefix such as `[DEBUG-a4f2]` so cleanup is a single search.

### 3. Verify Before Continuing

- Did it work? → Phase 4
- Didn't work? → Form NEW hypothesis
- DON'T add more fixes on top

### 4. When You Don't Know

- Say "I don't understand X"
- Don't pretend to know
- Ask the user for help
- Research more

---

## Phase 4: Implementation

**Fix the root cause, not the symptom:**

### 1. Create Failing Test Case

- Simplest possible reproduction
- Automated test if possible
- MUST have before fixing
- Use the `test-driven-development` skill

### 2. Implement Single Fix

- Address the root cause identified
- ONE change at a time
- No "while I'm here" improvements
- No bundled refactoring

### 3. Verify Fix

```bash
# Run the specific regression test
pytest tests/test_module.py::test_regression -v

# Run full suite — no regressions
pytest tests/ -q
```

### 4. If Fix Doesn't Work — The Rule of Three

- **STOP.**
- Count: How many fixes have you tried?
- If < 3: Return to Phase 1, re-analyze with new information
- **If ≥ 3: STOP and question the architecture (step 5 below)**
- DON'T attempt Fix #4 without architectural discussion

### 5. If 3+ Fixes Failed: Question Architecture

**Pattern indicating an architectural problem:**
- Each fix reveals new shared state/coupling in a different place
- Fixes require "massive refactoring" to implement
- Each fix creates new symptoms elsewhere

**STOP and question fundamentals:**
- Is this pattern fundamentally sound?
- Are we "sticking with it through sheer inertia"?
- Should we refactor the architecture vs. continue fixing symptoms?

**Discuss with the user before attempting more fixes.**

This is NOT a failed hypothesis — this is a wrong architecture.

---

## Red Flags — STOP and Follow Process

If you catch yourself thinking:
- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "Add multiple changes, run tests"
- "Skip the test, I'll manually verify"
- "It's probably X, let me fix that"
- "I don't fully understand but this might work"
- "Pattern says X but I'll adapt it differently"
- "Here are the main problems: [lists fixes without investigation]"
- Proposing solutions before tracing data flow
- **"One more fix attempt" (when already tried 2+)**
- **Each fix reveals a new problem in a different place**

**ALL of these mean: STOP. Return to Phase 1.**

**If 3+ fixes failed:** Question the architecture (Phase 4 step 5).

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Issue is simple, don't need process" | Simple issues have root causes too. Process is fast for simple bugs. |
| "Emergency, no time for process" | Systematic debugging is FASTER than guess-and-check thrashing. |
| "Just try this first, then investigate" | First fix sets the pattern. Do it right from the start. |
| "I'll write test after confirming fix works" | Untested fixes don't stick. Test first proves it. |
| "Multiple fixes at once saves time" | Can't isolate what worked. Causes new bugs. |
| "Reference too long, I'll adapt the pattern" | Partial understanding guarantees bugs. Read it completely. |
| "I see the problem, let me fix it" | Seeing symptoms ≠ understanding root cause. |
| "One more fix attempt" (after 2+ failures) | 3+ failures = architectural problem. Question the pattern, don't fix again. |

## Quick Reference

| Phase | Key Activities | Success Criteria |
|-------|---------------|------------------|
| **1. Root Cause** | Read errors, reproduce, check changes, gather evidence, trace data flow | Understand WHAT and WHY |
| **2. Pattern** | Find working examples, compare, identify differences | Know what's different |
| **3. Hypothesis** | Form theory, test minimally, one variable at a time | Confirmed or new hypothesis |
| **4. Implementation** | Create regression test, fix root cause, verify | Bug resolved, all tests pass |

## Remote systemd --user Service Diagnostics

For production-like Linux services reached over SSH, distinguish the log-following command from the service itself: `journalctl --user -u NAME -f` attaches to the journal and `Ctrl+C` only exits the follower; it does not stop or restart the unit. After a restart, verify the unit independently with:

```bash
systemctl --user is-active service-a.service service-b.service
systemctl --user show service-a.service -p ActiveState -p SubState -p Result -p ExecMainStatus -p NRestarts -p MainPID
journalctl --user -u service-a.service --since '15:55:00' --no-pager -o short-precise
```

For multiple services, collect status, restart count, exit status, process identity, and recent logs in one SSH command. Separate startup-success evidence (`initialized`, `ACK`, `active/running`, `Result=success`, `ExecMainStatus=0`) from warnings and functional errors. A warning in a dependency scanner (for example, a missing optional media plugin) is not proof that the service failed; prioritize explicit runtime failures such as a sensor/serial reader connection error. If the service is active but the user reports missing data, the next probe should test the data path (topics, sockets, devices, or registrations), not repeatedly restart the unit.

## Hermes Agent Integration

### Investigation Tools

Use these Hermes tools during Phase 1:

- **`search_files`** — Find error strings, trace function calls, locate patterns
- **`read_file`** — Read source code with line numbers for precise analysis
- **`terminal`** — Run tests, check git history, reproduce bugs
- **`web_search`/`web_extract`** — Research error messages, library docs

### With delegate_task

For complex multi-component debugging, dispatch investigation subagents:

```python
delegate_task(
    goal="Investigate why [specific test/behavior] fails",
    context="""
    Follow systematic-debugging skill:
    1. Read the error message carefully
    2. Reproduce the issue
    3. Trace the data flow to find root cause
    4. Report findings — do NOT fix yet

    Error: [paste full error]
    File: [path to failing code]
    Test command: [exact command]
    """,
    toolsets=['terminal', 'file']
)
```

### With test-driven-development

When fixing bugs:
1. Write a test that reproduces the bug (RED)
2. Debug systematically to find root cause
3. Fix the root cause (GREEN)
4. The test proves the fix and prevents regression

## Service-Orchestration Pitfall: Distinguish Canceled Jobs from Root Failures

When debugging a `systemctl --user restart` that reports `Job ... canceled`, inspect the dependency graph and the journal of the prerequisite service before treating the target service as the root cause:

1. Read the target unit with `systemctl --user cat` and check `Requires=`, `BindsTo=`, `PartOf=`, and `After=`.
2. Query both units with `systemctl --user show ... -p ActiveState -p SubState -p Result -p MainPID -p NRestarts`.
3. Read the prerequisite's journal around the restart window, not only the target's status.
4. If the target is killed during `ExecStartPre` (often a deliberate sleep), interpret `status=15/TERM` as dependency-driven cancellation.
5. Follow the prerequisite's first application-level exception. Ignore non-fatal startup warnings until the first exception that causes the process to exit.
6. For `Restart=always`, verify stability by checking that `NRestarts` stops increasing and the unit reaches `active/running`; `Result=success` alone may only describe a stop/restart operation, not application health.

For Python packages used by services, distinguish missing runtime configuration assets from missing code: inspect the installed package directory and `pip show -f`/wheel contents. If code opens files such as `settings.toml` or `robot_action.json`, `.example` files are templates, not valid production replacements. Search for a verified device-specific backup and version match before copying; do not fabricate configuration or blindly rename templates.

## Remote systemd service and hardware-module diagnosis

When diagnosing a remotely managed robot or Linux service, separate **process health** from **feature health**. A unit can be `active (running)` while one module (for example, a battery reader) is unusable.

1. Connect to the target and collect evidence in one non-interactive command where possible. Use `systemctl --user show` for machine-readable fields: `ActiveState`, `SubState`, `Result`, `ExecMainStatus`, `NRestarts`, and `MainPID`. Also inspect recent journal output with `--no-pager -o short-precise`.
2. Search logs by the affected subsystem, but do not treat every warning as the root cause. Classify messages into startup success, dependency/plugin warnings, configuration warnings, and functional errors.
3. For serial or USB hardware, verify the full chain: configured logical path (such as `/dev/ttyBattery`), symlink target, underlying `/dev/ttyACM*` or `/dev/ttyUSB*` node, permissions, `udevadm` vendor/product/path properties, and `lsusb` enumeration. A matching USB device and udev symlink prove enumeration, not that the downstream device is responding.
4. Inspect the actual deployed unit (`systemctl --user cat`) and the installed runtime configuration/package files. Do not infer the active configuration from a wizard source tree or from the intended robot model alone.
5. Before changing configuration, check whether the device is held by another process (`fuser -v` and `lsof`). Then verify protocol/driver version, port, and baud-rate settings against the installed module configuration. Restart only after evidence narrows the cause, and re-read the exact target state and fresh logs afterward.
6. When SSH requires a password, use an interactive PTY and submit the password through the process tool; do not put credentials in shell command text or claim a diagnosis from a failed non-interactive attempt.

Common pitfall: `journalctl -f` follows logs, and `Ctrl+C` exits the follower but does not stop the service. Another pitfall is a terminal pager (`systemctl status`) hiding later commands; use `--no-pager` for diagnostic batches.

## Service Health vs Functional Readiness

For daemonized robotics and multimedia services, do not equate `systemctl ... active/running` with the user-visible feature working. Treat startup as a staged pipeline and verify each stage:

1. Process/supervisor state: `ActiveState=active`, `SubState=running`, `Result=success`, `NRestarts=0`.
2. Initialization milestones: inspect logs for explicit success markers (connections, registrations, device attachment, executor spin).
3. Runtime data path: inspect ROS node/topic graph and measure actual rates; a subscribed topic with `Publisher count: 0` means the topic has no producer, not that the subscriber is down.
4. Output path: verify the downstream consumer, shared-memory/audio sink, socket, or UI receives data.
5. Feature-specific readiness: search logs for partial initialization errors. A component such as Piper TTS can initialize while its chatbot/event producer fails due to a missing resource, resulting in no speech despite healthy audio hardware.

A quiet `journalctl -f` is not evidence of a hang: `-f` follows new records, and a healthy idle process may emit none. Use status, process inspection, topic/data probes, and feature-specific logs instead.

When diagnosing missing speech, separate the chain explicitly:
`event/input -> chatbot/text generation -> TTS engine -> audio SHM/socket -> speaker device -> playback`.
Find the first failed stage before changing restart order or hardware configuration. Missing packaged assets (for example, a prompt file) can produce a partial-start state and should be checked alongside TTS/audio initialization messages.

## Real-World Impact

From debugging sessions:
- Systematic approach: 15-30 minutes to fix
- Random fixes approach: 2-3 hours of thrashing
- First-time fix rate: 95% vs 40%
- New bugs introduced: Near zero vs common

**No shortcuts. No guessing. Systematic always wins.**
