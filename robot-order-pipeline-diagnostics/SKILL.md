---
name: robot-order-pipeline-diagnostics
description: Use when robot orders fail despite working navigation.
---

# Robot Order Pipeline Diagnostics

> 完整描述：Use when robot orders fail despite working navigation. Diagnose ROS, behavior-tree and AI contracts without unintended motion.

## Scope and safety

Use for remote robot order, navigation-to-grasp, and behavior-tree failures. Treat navigation, business execution, and AI readiness as separate layers.

- Start read-only. Distinguish permission to edit configuration, restart a named service, reload AI data, and execute physical motion. A clear floor does not establish software readiness.
- Before starting any test, check current execution state. Never replace an active order with a diagnostic tree; use `force_execute=false` where supported and treat “flow is already running” as a rejected test, not your test's result.
- Do not start a permanent order listener merely to test a fix: it may consume previously queued orders. Prefer a bounded, explicit single test after readiness checks.
- Preserve all physical calibration values. Normalize data shape only after a differential test proves the contract mismatch; never bypass validation by inventing poses.
- Report separately: file changed, live response verified, diagnostic test passed, business branch succeeded, and physical outcome observed. Software grasp success still needs on-site confirmation.

## Procedure

1. **Establish a usable remote shell.** Confirm authentication and prompt before sending commands. Use bounded diagnostics, not an indefinite `ros2 topic echo` or `journalctl -f` in the command shell. If a subscriber is waiting, interrupt that diagnostic and confirm shell return before sending more commands. Use process logs to read complete output rather than repeatedly rerunning commands because poll previews omit their beginnings. Remote paths must be inspected remotely, not with local filesystem tools.
2. **Read the publisher and trace its destination.** A `Published` print only proves the publisher called its send method. Compare direct navigation with business-order topics. Topic subscriber counts do not prove receipt or execution; correlate receiving-node logs with the user's order and time window.
3. **Build an execution timeline.** Read bounded systemd journals for navigation, Flow, Vision and AI. Check MainPID, NRestarts and initialization completion, not just active/running. A live ROS node can receive orders while its behavior tree has already terminated.
4. **Locate the earliest failed business node.** Distinguish parser rejection, initialization, product preload, config read, navigation, recognition, grasp and placement. A Selector's successful error handler can make the root report SUCCESS while `process_order` failed. Require the business branch and relevant leaf nodes to pass.
5. **Inspect the actual installed contract and live payload.** Determine interpreter and package version from the running environment. Compare configured file path, disk JSON, live service response, and consumer expectations. A newer source checkout does not define the installed binary's interface.
6. **Minimize a red/green test.** Capture a real read-only response and replay it through the installed consumer in an isolated process. Change only one field or shape at a time. Use real transport-wrapper code with a stubbed service client rather than guessing callback or result tuple semantics. See [Autolife contracts](references/autolife-contracts.md).
7. **Repair the proven source.** Back up the exact file or Workflow, make the smallest change, validate syntax and unchanged fields, and read it back. For server-supplied XML, correlate allocation logs with the task code and associated Workflow; do not edit an unrelated local XML that happens to contain matching attributes. Check shared-Workflow impact and stop at login walls.
8. **Verify bottom-up.** Reload only the necessary data, query it again, then run a bounded no-motion preflight such as product preload plus config read. Use fresh state before any authorized physical test. Do not claim a candidate file or isolated mock test is a deployed fix.

## Domain reference

Read [Autolife contracts](references/autolife-contracts.md) for product-shape probes, DDS service configuration and server Workflow provenance. Revalidate names and schemas against the installed version before using examples.
