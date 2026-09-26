---
name: remote-linux-service-debugging
description: Use when diagnosing remote Linux services and hardware pi...
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [linux, systemd, ssh, debugging, hardware, services]
    related_skills: [systematic-debugging]
---

# Remote Linux Service Debugging

> 完整描述：Use when diagnosing remote Linux services and hardware pipelines.

## Purpose

Diagnose remote user/system services that look active but have unavailable features, crash loops, hardware pipelines, shared-memory dependencies, or external AI/provider connections. Favor read-only evidence gathering until the user authorizes changes.

## Workflow

1. Verify the remote host identity, boot ID, addresses, and uptime before reusing earlier conclusions. An IP may now identify another machine.
2. Inspect the unit definition and lifecycle properties. Never equate `active (running)` with healthy when `Restart=always` is configured.
3. Capture one complete service generation from `Started` through failure/exit/restart.
4. Split the system into independent fault chains: service lifecycle, provider session, audio/VAD, camera producer, shared-memory transport, feature consumer, and secondary devices.
5. Trace every hardware feature as producer → transport → consumer. Registration or enumeration alone is not end-to-end success.
6. Use isolated differential probes for provider/network clients, but require integrated-service stability and user-visible behavior before claiming a fix.
7. Rank root causes by causality. A deterministic Python exception before shutdown normally outranks a later native cleanup segfault.
8. Before changing anything, state the proposed scope. Back up config, change one variable, restart, and verify exact success criteria.

## Core commands

```bash
hostname
cat /proc/sys/kernel/random/boot_id
uptime -s
ip -brief addr

systemctl --user cat SERVICE --no-pager
systemctl --user show SERVICE \
  -p ActiveState -p SubState -p Result -p MainPID \
  -p ExecMainStatus -p NRestarts -p ActiveEnterTimestamp

journalctl --user -u SERVICE --since '...' --no-pager -o short-precise
```

Re-read `MainPID` immediately before inspecting `/proc/$pid`; restart loops make saved PIDs stale.

## Verification standard

A service repair is complete only when:

- restart count stops increasing over a meaningful observation window;
- the original error signature disappears;
- required producers and transports exist;
- the consumer attaches or receives data;
- the external provider session is established when applicable;
- the user-visible feature works.

See [references/remote-restarting-services.md](references/remote-restarting-services.md) for detailed signatures, shared-memory diagnosis, ROS logger pitfalls, and reporting guidance.
