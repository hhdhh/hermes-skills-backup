---
name: robot-service-diagnostics
description: Diagnose Linux robot services, ROS topics, sensors, and s...
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [robotics, ros2, systemd, serial, diagnostics, sensors]
    related_skills: [systematic-debugging]
---

# Robot Service Diagnostics

> 完整描述：Diagnose Linux robot services, ROS topics, sensors, and serial peripherals end to end.

## When to use

Use when a robot's systemd service appears stuck, starts without useful data, emits sensor/serial errors, or a user cannot tell whether a ROS/vision/control pipeline is actually working.

## Core rule

Separate **process health**, **initialization health**, and **data-plane health**. A service can be `active (running)` and still have a failed battery reader, an empty output topic, or a disconnected consumer. Never infer functional success from `systemctl status` alone, and never infer failure merely because `journalctl -f` stopped printing.

## Workflow

1. **Capture the exact symptom and time.** Preserve service names, topic names, device paths, robot ID, and timestamps literally.
2. **Check systemd without a pager.** Use `systemctl --user --no-pager --full status SERVICE`, then query `ActiveState`, `SubState`, `Result`, `ExecMainStatus`, `NRestarts`, and `MainPID` with `systemctl --user show`. A healthy process normally has `active/running`, `Result=success`, exit status 0, and no restart loop.
3. **Read the complete startup journal.** Use `journalctl --user -u SERVICE --since ... --no-pager -o short-precise` or `-o cat`. Classify messages as successful initialization, warnings, or functional errors. `journalctl -f` means follow; it waits silently when the process has no new log lines, and Ctrl-C stops only journalctl.
4. **Verify the process and initialization milestones.** Look for explicit evidence such as WebSocket connected, shared-memory camera opened, ROS node initialized, executor spin started, registration ACK received, and sensor readers registered. Use `pgrep -af` only as supplemental evidence because wrappers such as conda can create multiple PIDs.
5. **Verify the ROS data plane.** Source the same ROS setup and reproduce the service's `ROS_DOMAIN_ID`, RMW implementation, and DDS configuration. Run `ros2 topic list -t`, `ros2 node list`, `ros2 node info NODE`, `ros2 topic info TOPIC -v`, and bounded `ros2 topic hz TOPIC`. Check both topic existence and actual rate. A topic with `Publisher count: 0` means no publisher for that topic; it does not mean a subscribing node failed to start.
6. **Verify serial peripherals independently.** Check `/dev/ttyUSB*`, `/dev/ttyACM*`, and expected stable aliases. Resolve symlinks with `readlink -f`, inspect identity with `udevadm info -q property -n DEVICE`, and inspect matching rules under `/etc/udev/rules.d`. Confirm permissions and check contention with `sudo fuser -v DEVICE` and `sudo lsof DEVICE`. USB enumeration proves only that the adapter enumerated, not that the downstream sensor/BMS responds.
7. **Trace configuration to the installed runtime.** Read the actual unit file (`systemctl --user cat SERVICE`) and the installed package/config files used by the running environment. Do not rely on the source wizard or a config template; verify paths, driver version, port, baud rate, and enabled module in the deployed config.
8. **Only then propose a fix.** Prefer a reversible diagnostic or additive configuration change. After any restart or edit, re-check the exact target and data-plane evidence.

## Common interpretations

- `active/running` + successful init milestones + nonzero topic rate: service is operational for that path.
- `active/running` + `Connection to ... reader failed`: degraded functionality, not a service startup failure.
- GStreamer plugin missing-library warnings: may affect video/WebRTC while leaving core ROS/SHM startup healthy; determine relevance from the requested data path.
- DDS loopback/deprecated-element warnings: may be harmless for same-host communication but can break cross-host discovery; test the required network path.
- Missing module messages must be compared with the robot model's enabled-module list; do not treat every optional module absence as an error.

## Pitfalls

- Always add `--no-pager`; otherwise `systemctl status` can consume the terminal in a pager and hide later commands.
- Do not use a live-follow log as a liveness test.
- Do not call a service broken because one unrelated output topic has no publisher; first inspect node subscriptions/publications and the actual output channel.
- Do not change serial aliases, driver versions, baud rates, or DDS interfaces before checking deployed configuration and device contention.
- Treat passwords and tokens as secrets; use interactive SSH authentication and do not persist credentials in scripts or logs.

## Reference

See `references/robot-293-vision-gv-diagnostics.md` for a condensed, session-tested example of the evidence and interpretations above.
