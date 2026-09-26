---
name: ros2-pubsub-diagnostics
description: Use when a ROS 2 publish succeeds but the robot does not...
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [ros2, pubsub, debugging, robotics, diagnostics]
    related_skills: [systematic-debugging]
---

# ROS 2 Pub/Sub Diagnostics

> 完整描述：Use when a ROS 2 publish succeeds but the robot does not react. Trace the topic graph, consumer chain, and runtime preconditions before touching sender code.

Use this skill when a ROS sender logs success but the downstream robot or node does not visibly act.

## Always-on workflow

1. **Separate sender success from system success.**
   - A `publish()` call or local log only proves the sender emitted a message.
   - It does not prove the consumer accepted, parsed, or executed it.

2. **Trace the chain from topic to consumer.**
   - Inspect the topic graph first.
   - Confirm publishers, subscribers, node names, and QoS.
   - Then inspect the real consumer node or service.

3. **Check runtime preconditions before changing code.**
   - Active map, robot ID, mode, service readiness, and config bindings can all block execution while the publish path still looks healthy.

4. **Compare against a working sibling path.**
   - If `go` works but `order` does not, treat that as a routing/consumer problem until proven otherwise.

5. **Fix the consumer chain, not the sender log.**
   - If the graph is healthy but no action occurs, investigate the subscriber, bridge, dispatcher, or service layer before editing the publisher.

## Diagnostic sequence

1. `ros2 topic info -v /topic_name`
2. `ros2 node list`
3. `ros2 node info /node_name`
4. `systemctl --user status <service>.service` when the consumer is a service
5. `ros2 topic echo /topic_name --once` to confirm the message actually appears
6. Inspect service logs or node logs for silent rejection or unmet prerequisites

## What to look for

- A message reaches a bridge node but never reaches the worker.
- The worker exists but is waiting on map or mode state.
- The topic name or payload matches the sender's expectation but not the consumer's parser.
- The downstream node is alive, but its service dependency is not.

## Where to stop

Do not patch sender code until you have identified the boundary where the chain breaks.

## Related reference

- `references/ros-pubsub-diagnostics.md` — topic graph checklist and common failure pattern.
