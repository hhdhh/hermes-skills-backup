---
name: robot-service-chain-diagnostics
description: Use when robot navigation works but orders fail.
---


# Robot Service-Chain Diagnostics

> 完整描述："Use when robot navigation works but orders fail. Trace ROS services, behavior trees and product contracts without unintended motion."

## Execution order

1. Establish the permitted scope: read-only diagnosis, reversible configuration changes, service restart, and physical execution are separate gates. Before restarting an order consumer or starting a tree, check for pending orders; restoring a consumer may trigger motion without a new publish. Ask the operator to remain near the emergency stop before a physical test.
2. Reconnect and refresh service state before relying on earlier observations. Read relevant unit paths and recent journals; compare MainPID, NRestarts, ActiveState and SubState across observations. A running process is not proof that models, datasets or business loops are ready.
3. Trace the publisher's exact topic and message through the subscriber, business tree and downstream service. Correlate journal timestamps with the user's commands. Topic subscription counts prove discovery, not message handling; a local Published print proves neither delivery nor execution.
4. Check tree lifecycle before changing products. Identify the last start, finish and failure event and the first failing business node. A Selector can return SUCCESS after its error branch succeeds; report business-node results separately from transport/action and top-level tree results.
5. Build a non-motion probe at the failing boundary. Prefer read-only product lookup, then a bounded preflight containing only verified non-motion nodes. Do not restore the whole order loop merely to test a data parser. Never force-preempt another running flow for a diagnostic probe.
6. Capture an actual response and replay it into the installed consumer offline. Preserve the real wrapper/serialization contract; change one field shape at a time and assert both status and output values. See [product contract testing](references/product-contract-testing.md).
7. For service faults, compare the service's effective environment with the SSH shell; sourcing a shell does not configure systemd. Back up the exact unit, prefer an isolated drop-in, validate, reload, and restart only the authorized service. Read back effective settings and verify sustained readiness, not a single active sample. See [DDS and startup readiness](references/dds-startup-readiness.md).
8. Report exactly which layer is fixed: candidate generated, offline test passed, deployed, interface verified, or physical task completed. Never call an offline candidate a live repair. Keep remaining blockers explicit.

## Remote-shell discipline

- Read bounded process logs after commands; a poll preview can omit the evidence needed to diagnose the failure. Do not resend source-reading commands merely because their output is absent from the preview.
- Before submitting another shell command, verify the previous command has returned to a prompt. Bound topic echo and journal following with a timeout; cancel a waiting subscriber before continuing, because queued text is otherwise not executed as shell commands.
- Keep remote paths and local paths distinct. Use SSH-side read-only Python for remote inspection or deliberately copy files locally; a local file search cannot inspect an SSH host.
- Use focused batches with compact summaries and preserve useful fixtures/reports. Avoid giant repeated listings and guessed mock interfaces.

## Safety and interpretation

- Do not flatten arbitrary pose arrays or invent angles to satisfy a validator. Prove singleton shape normalization preserves values and check every consumer before production deployment.
- Do not compensate for startup races with unvalidated indefinite retries. A service may register before its underlying AI object exists; gate on meaningful readiness and bound recovery attempts.
- Do not infer full robot health from a successful product preload. Navigation, recognition, arm motion and placement require their own acceptance evidence.
