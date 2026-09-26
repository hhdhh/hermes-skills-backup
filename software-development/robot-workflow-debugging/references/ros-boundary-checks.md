# ROS Boundary Checks

Use these checks in order, stopping before any motion if a prior boundary is unhealthy.

1. Record `ROS_DOMAIN_ID`, `ROBOT_ID`, service-unit state, PID, and restart count.
2. Inspect topic/action/service discovery with `ros2 topic info -v`, `ros2 service list -t`, or the action client. A discovered endpoint proves discovery only; it does not prove the consumer accepted the payload.
3. For actions, record goal acceptance, feedback, result status, and any embedded error/message fields. A transport-level result can be successful while the behavior-tree work branch failed.
4. For behavior trees, inspect the leaf node that matters (`ReadOrderDatabase`, `OrderDetection`, `GraspOrder`, `PlaceOrder`) rather than only the root/selector result.
5. For server-delivered workflows, capture the quest/workflow identifier and compare the delivered XML with the installed node's declared ports. Search the management payload source, not only local package XML.
6. After a fix, verify the exact target file or systemd drop-in, then re-query the runtime and run the smallest no-motion preflight possible.

Useful interpretations:

- `flow is already running`: follow the existing run; do not launch another test.
- `active/running` with increasing `NRestarts`: service readiness is not established.
- `goal accepted` followed by an invalid-node error: the transport is healthy; workflow schema/runtime compatibility is the failing boundary.
- `SUCCESS` from an error-handling selector: inspect the failed child branch before calling the flow successful.
