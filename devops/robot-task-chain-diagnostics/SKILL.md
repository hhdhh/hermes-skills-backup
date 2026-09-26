---
name: robot-task-chain-diagnostics
description: Use when robot navigation works but tasks do not execute.
---

# Robot Task-Chain Diagnostics

> 完整描述：Use when robot navigation works but tasks do not execute. Trace ROS receipt, behavior-tree lifecycle, AI readiness, and product data without moving hardware.

## Scope and safety

Diagnose ROS-backed robot orders, navigation, perception and behavior-tree execution. Default to read-only inspection over the user-authorized SSH connection. Do not publish test orders, reset task stages, initialize poses, start behavior trees, or restart services without explicit approval: these can consume pending orders and move hardware. Never invent grasp poses or calibration values to bypass validation.

## Procedure

1. **Establish the remote command channel.** Confirm the remote shell prompt before submitting checks. Bound waiting probes with `timeout`; a topic echo awaiting data is not a shell. If it blocks, interrupt that probe, confirm the prompt, and resubmit only the intended read-only checks. Use the process tool's `log` action for full output rather than repeatedly rerunning commands because `poll` shows only a preview. Remote paths must be read through SSH, not host-local file tools.
2. **Read the publisher implementation.** Extract the exact topic, message type and payload for both the working navigation action and failing order action. Treat a printed `Published` line as local publication only, not delivery or execution evidence.
3. **Inspect discovery and process state.** Use `ros2 topic info -v <observed-topic>` and `systemctl --user show <observed-unit> -p ActiveState -p SubState -p MainPID`. Discovery proves endpoints exist, not that callbacks ran; active service processes do not prove an active business flow. Use the robot's observed ROS and interpreter environment, without assuming local and remote environments match.
4. **Correlate the exact user operation window.** Read `journalctl --user -u <unit> --since '<start>' --until '<end>' --no-pager -o short-iso` across receiver, flow and AI units. Include earlier startup events and preserve timestamps, PIDs and run IDs. Find actual receipt of the submitted product before attributing failure to networking.
5. **Trace the behavior-tree lifecycle.** Find flow start, initialization, `WaitOrder`, first failed business node and flow finish. Read the selected XML to establish whether an initialization failure prevents entering the order loop. Distinguish a persistent waiting flow from a one-shot action requiring explicit order input.
6. **Trace readiness and product-data boundaries.** If initialization or preload fails, compare request time against internal AI initialization completion. Follow runtime dataset-root changes and inspect the actual selected product directory and supported config format. Do not infer product availability from navigation waypoints, package defaults or old documentation.
7. **Reduce evidence before reporting.** Filter logs remotely; parse large JSON tree feedback into timestamp, run ID, node, status and feedback message instead of dumping whole trees. Compare later successful initialization against earlier failures so historical faults are not reported as current state.
8. **Deliver the diagnosis and recovery gates.** Lead with the verified failing boundary, show a short timestamped evidence chain, distinguish confirmed facts from inferred startup races, and state what remains unverified. Separate diagnosis from repair: only claim restoration after checking the waiting flow and performing an explicitly authorized end-to-end test.

## Interpretation rules

- Require task-level success, not merely root-tree success: a Selector's successful error handler can mask failure of the order-processing branch.
- Verify API/internal-object readiness independently of ROS service advertisement: handlers may be reachable before model initialization completes.
- Check whether the receiver survives after its flow terminates: callback logs may continue even though no `WaitOrder` consumer remains.
- Do not replay a real robot order merely to obtain a tight feedback loop. Prefer timestamp-correlated existing logs, static control-flow inspection and verified read-only queries; label live execution untested.

For Autolife-specific boundaries and evidence patterns, see [references/autolife-orders.md](references/autolife-orders.md).
