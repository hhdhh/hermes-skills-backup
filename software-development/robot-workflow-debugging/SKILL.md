---
name: robot-workflow-debugging
description: Use when debugging ROS robot workflows.
version: 1.0.0
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [ros2, robotics, behavior-tree, navigation, grasping, systemd, diagnostics]
---

# Robot Workflow Debugging

> 完整描述：Use when debugging ROS robot workflows. Trace services, configs, and physical outcomes safely.

Use this class-level workflow for ROS 2 robots whose navigation, perception, manipulation, or business-order flow behaves unexpectedly.

## Operating procedure

1. **Gate the test before touching motion.** Confirm the area is clear, the emergency stop is accessible, no flow is already running, and the intended test is limited to one controlled execution. Start with no-motion checks: service availability, request/response payloads, configuration loading, and behavior-tree validation.
2. **Identify the active runtime.** Record the robot address, ROS domain, robot ID, relevant systemd units, PIDs, restart counters, and the exact log time window. Inspect the installed package/version used by the service; do not assume a source checkout is the runtime.
3. **Trace every boundary.** For topic-based flows, inspect topic type and publisher/subscriber counts. For services/actions, inspect endpoint names, request/response types, goal acceptance, result status, and feedback. Capture both the input and output at each boundary.
4. **Find the actual workflow source.** Search local package directories, service working directories, management-server payloads, and generated artifacts. A local XML can be valid while a server-delivered workflow still fails. Do not edit the first matching file without proving it is the active source.
5. **Compare schema to runtime.** Instantiate or inspect the installed behavior node and list its declared ports/parameters. Compare those declarations with workflow attributes. Source code that supports a parameter does not prove the installed binary/runtime supports it.
6. **Validate product configuration end to end.** Compare the on-disk product JSON with the live product-service response after dataset reload. Check field nesting, scalar/list types, and required assets. Test one field at a time against the real node; preserve a known-good product as the differential reference.
7. **Separate software success from physical success.** Treat action/node `SUCCESS` as an acknowledgement of the software path only. For grasping, require evidence for perception pose, arm trajectory, gripper command completion, force or object-hold feedback, and post-action object presence. `force feedback NOT triggered` means the grasp is unverified even if `GraspOrder` reports success.
8. **Never overlap flows.** If an action reports `flow is already running`, inspect and follow the active run rather than launching another request. Use the stop/emergency path only when needed for safety; do not mask an active result with a second test.
9. **Modify minimally and reversibly.** Back up service units and configs before editing. Change one variable at a time, validate syntax, reload only the affected unit, and avoid whole-stack restarts unless required. After each external change, read back the exact file/unit/state and verify the intended effect.
10. **Report the real terminal condition.** Distinguish navigation success, perception success, grasp-command success, verified physical grasp, placement success, and final business result. Do not call an error-handler success or a motion-command success a completed order.

## High-value probes

```bash
systemctl --user show UNIT -p ActiveState -p SubState -p MainPID -p NRestarts
journalctl --user -u UNIT --since 'YYYY-MM-DD HH:MM:SS' --until 'YYYY-MM-DD HH:MM:SS' --no-pager -o short-iso
ros2 topic info -v TOPIC
ros2 service list -t
```

Use a short-lived ROS client for read-only service checks. For motion-capable action tests, prefer a minimal preflight XML that stops after configuration and product validation; only add navigation or manipulation after the prior stage succeeds and the user has explicitly cleared the site.

## Durable pitfalls

- **Do not equate `active/running` with ready.** A systemd service can be alive while its ROS node is repeatedly failing or its internal model/dataset is not initialized.
- **Do not infer a dropped object from a successful place call.** Place completion can mean only that the arm motion finished; check force feedback and physical presence.
- **Do not flatten every nested array globally.** Product fields have different schemas; validate the specific consumer's expected shape before changing a configuration.
- **Do not trust logs that summarize a selector as success.** A behavior-tree error branch may succeed while the main process branch failed; inspect the child node that performed the work.
- **Do not edit a source checkout to fix an installed-version mismatch.** First prove which artifact the service loads, then make the smallest compatible workflow or package change.
- **Do not expose credentials in diagnostic output.** Redact passwords, tokens, and connection secrets while preserving endpoint hostnames and non-sensitive identifiers.

## References

- For reusable ROS boundary and behavior-tree checks, see `references/ros-boundary-checks.md`.
- For manipulation-specific evidence and stop criteria, see `references/grasp-verification.md`.
