# ROS 2 topic graph checklist

## Use case

A sender prints that it published a message, but the robot does not react.

## Checklist

- `ros2 topic info -v /topic_name`
  - Confirm publisher count, subscriber count, node names, and QoS.
- `ros2 node list`
  - Identify bridge nodes versus worker nodes.
- `ros2 node info /node_name`
  - Confirm what the consumer actually subscribes to.
- `systemctl --user status <service>.service`
  - Use when the consumer is managed by systemd.
- `ros2 topic echo /topic_name --once`
  - Confirm the message appears on the wire.

## Interpretation

If the topic graph is healthy but no action occurs, the bug is usually in one of these places:

1. The downstream consumer is offline.
2. The consumer silently rejects the payload.
3. A map/mode/ID precondition blocks execution.
4. A bridge forwards the message, but the worker never receives it.

## Good next probe

When `go` works but `order` does not, compare their consumer chains and preconditions before changing the sender.
