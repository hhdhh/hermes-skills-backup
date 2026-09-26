---
name: robot-runtime-diagnostics
description: Use when robot commands publish but tasks do not execute.
---

# Robot Runtime Diagnostics

> 完整描述：Use when robot commands publish but tasks do not execute. Trace ROS reception, behavior-tree lifecycle, and AI readiness without causing motion.

## Scope and safety

Diagnose remote ROS robots by separating transport, task execution, and hardware readiness. Start with read-only inspection. Before recovering a task loop, establish whether pending orders can be consumed and cause movement; obtain explicit authorization for that effect. For a non-motion scope, do not publish orders, reset shared execution state, restart services, or start an order-waiting tree. Keep candidate files outside watched runtime directories so hot reload cannot activate them.

## Procedure

1. **Establish a usable remote shell.** Confirm the hostname and prompt. Execute remote filesystem reads through the SSH session, not local file tools. Use bounded probes such as `timeout 10s ros2 topic echo <topic> --once`. After any foreground probe, verify return to the shell before sending the next command. If it is still waiting, interrupt the probe and confirm the prompt; text submitted to a waiting process is not evidence of command execution. Read the process log when a poll only returns a preview instead of rerunning the same extraction.
2. **Resolve the actual command path.** Read the installed publisher script and distinguish navigation topics from business-order topics. Record message type, payload, robot namespace and domain from the live setup. A `Published` print proves only the publisher call returned, not delivery or execution.
3. **Inspect three independent states.** Check process health with `systemctl --user show <unit> -p ActiveState -p SubState -p MainPID`; inspect discovery with `ros2 topic info -v <topic>`; then inspect business execution using timestamped logs. Subscription counts show discovered endpoints, not that a particular order was handled. Use receive logs to prove reception.
4. **Build the timeline around the user's command.** Fetch `journalctl --user -u <unit> --since <start> --until <end> --no-pager -o short-iso`. Correlate receiver events, flow run IDs, initialization, node failures, and flow termination. Include startup events before the order: a ROS node can remain alive after its behavior tree has exited. Filter output before returning it and preserve short surrounding context; avoid dumping full feedback trees or configuration objects that may contain secrets.
5. **Trace the first failed prerequisite.** Check whether initialization reached the order-waiting node. Separate service discovery from internal readiness: a callable service may still lack a constructed model/API object. Follow the dataset root actually loaded by the running AI process rather than assuming that the directory containing a navigation waypoint is a product dataset.
6. **Validate products without movement.** Check the exact product identifier, active dataset, configuration schema, mesh and reference assets. Distinguish files present, basic schema valid, service-readable product, and physically validated grasp. Never invent arm parameters to silence a schema failure.
7. **Prepare and validate within scope.** Back up the exact files before editing. If activation is not authorized, create a separate candidate and report it as not deployed. Generic XML parsing and a fake-node retry test validate only syntax and the modeled retry rule; require the vendor parser, actual node semantics and approved runtime checks before claiming startup recovery. Do not turn an arbitrary delay/retry count into a proven fix.
8. **Report the failure boundary and remaining gate.** Lead with the evidence-backed root cause, then what was changed and tested. State separately whether the candidate was deployed, task execution resumed, and physical behavior was verified. Do not call preparation a completed repair.

## Interpretation rules

- Inspect business nodes beneath a successful top-level result: a selector can return success because its error-handling branch succeeded, while the order itself failed.
- Distinguish persistent order-waiting flows from one-shot flows. A one-shot flow needs its required input/blackboard fields; receipt of a prior topic message does not establish those fields for a later run.
- Treat compiled-module strings as symbol-discovery hints, not proof of callback logic. Prefer exposed schemas, installed readable scripts and correlated runtime logs.
- Correct an earlier unsupported conclusion explicitly when new evidence arrives; service status, message discovery, and business completion are different assertions.
