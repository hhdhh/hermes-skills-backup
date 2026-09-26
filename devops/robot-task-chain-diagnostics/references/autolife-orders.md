# Autolife orders: diagnostic boundaries

## Publisher versus executor

Inspect the installed `autolife_robot_gv/scripts/test_pub.py` rather than assuming version compatibility. In the inspected implementation, `go` publishes a String to `/robot_navigation_<domain>_<robot>/go`, while `order` publishes the product identifier to `/robot_order`. Map-derived menu entries establish waypoint names, not valid AI product configuration.

## Lifecycle checks

Inspect the selected flow XML. A capsule flow can execute `InitDataset` before entering a state machine containing `WaitOrder`. If `InitDataset` fails and the root Sequence terminates, `flow-service` may remain active and log `Received robot order` without executing navigation or grasping. Prove this with matching flow-start, failure, finish and subsequent receipt timestamps.

Compare persistent capsule execution with one-shot order actions. A one-shot action may require `order` on its blackboard; topic publication is not proof that the action received that parameter. An `order is empty` result is distinct from a missing product.

## AI data checks

Trace `service_ai_grasp_reinit_dataset_<domain>_<robot>`, preload and product-information boundaries using installed interfaces and logs. An internal-object AttributeError during reinitialization followed later by model initialization is evidence of a readiness race, not evidence that the service is absent.

Use runtime `dataset_root` logs to identify which directory was loaded. The AI package's default dataset may be empty while Flow owns the populated dataset. Loading an empty default after a failed switch explains a later `Product data not found` response. A subsequent successful reinitialization supersedes that historical state but does not itself restart a terminated waiting flow.

Discover product files rather than assuming `config.xml`: installed products may use `config.json`, mesh and reference assets. Separate preload/model success from configuration validation; `invalid product config` requires examination of the product-response schema and consuming node, not guessed coordinate changes.

## Reporting traps

- An error-handling Sequence returning success can cause the parent Selector and overall flow to report success despite `process_order` failure. Show business-node outcomes.
- Keep the original order window separate from later manual recovery attempts. Do not attribute another operator's initialization or action runs to your investigation.
- Diagnose first; dataset reinitialization, restarting an order loop, clearing stages and live order replay are state changes, not passive probes. Pending orders can execute on recovery.
