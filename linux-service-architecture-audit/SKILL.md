---
name: linux-service-architecture-audit
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [linux, systemd, audit, services, architecture, operations]
    related_skills: [systematic-debugging, grounded-citations]
description: "Audit Linux hosts: services, deps, data flows, health."
---

# Linux Service Architecture Audit

## Purpose

Use this skill when asked to inspect a Linux machine comprehensively and explain:

- machine/system/hardware/network/runtime baseline;
- all operationally relevant services and their startup commands;
- service-to-service dependencies and startup order;
- IPC, network, database, shared-memory, message-bus, or robotics data flows;
- actual runtime health rather than a superficial service-state snapshot;
- findings in a durable technical report.

The deliverable is an evidence-backed architecture and health audit, not a raw command dump. Default to read-only inspection unless the user separately authorizes changes.

## Audit principles

1. **Identity before inventory.** Confirm hostname, OS, boot ID/time, logged-in account, timezone, and whether the target is the intended host.
2. **Inspect both systemd managers.** `systemctl` and `systemctl --user` are distinct control planes. User services can be the entire application stack, especially when `loginctl show-user ... -p Linger` is enabled.
3. **Unit files describe intent; runtime proves reality.** Read unit contents and `systemctl show`, then inspect processes, sockets, logs, restart counters, and domain-specific graphs.
4. **Dependency order is not readiness.** `After=network.target` only orders startup; it does not guarantee DNS, routes, cloud access, databases, devices, or application readiness.
5. **`active` is not healthy.** `Restart=always` can make a crash loop look intermittently active. Sample `NRestarts` at least twice and inspect `Result`, `ExecMainStatus`, recent journal, and a business-level probe.
6. **Separate primary failure from downstream symptoms.** Trace producer → transport → consumer → error handling → systemd response. Do not blame a missing input if the producer and transport are proven healthy.
7. **Do not leak secrets.** Never copy passwords, tokens, API keys, environment secrets, private config values, or full credential-bearing command lines into reports. Redact at collection time where possible.
8. **Explain scope honestly.** “All services” should mean every custom/business service individually plus system services grouped by operational role. Hundreds of static/template distro units do not need one-by-one prose unless explicitly requested.

## Workflow

### 1. Establish a read-only collection boundary

State that inspection is read-only. Avoid `restart`, `enable`, package installs, edits, database writes, and commands that can activate devices. If SSH requires a password, use the session’s approved mechanism without embedding the password in generated reports or reusable scripts.

Create a task list with these phases:

1. host baseline;
2. system and user service inventory;
3. application/runtime dependency analysis;
4. health and risk assessment;
5. report creation and read-back verification.

### 2. Collect the host baseline

Capture, at minimum:

```bash
hostnamectl
cat /etc/os-release
uname -a
uptime
who -b
id
loginctl show-user "$USER" -p Linger -p State -p Sessions
timedatectl
lscpu
free -h
lsblk -e7 -o NAME,TYPE,SIZE,FSTYPE,FSVER,MOUNTPOINTS,MODEL,SERIAL
df -hT
df -ih
ip -br addr
ip route
ss -lntup
lspci -nn
lsusb
```

Also inspect relevant runtimes: Python/Conda, ROS, Docker/Podman, GPU, databases, language runtimes, package versions, and device nodes. Never assume the user profile describes the remote target.

### 3. Inventory both systemd scopes

```bash
systemctl list-unit-files --type=service --no-pager
systemctl list-units --type=service --all --no-pager
systemctl --failed --no-pager
systemctl list-timers --all --no-pager

systemctl --user list-unit-files --type=service --no-pager
systemctl --user list-units --type=service --all --no-pager
systemctl --user --failed --no-pager
systemctl --user list-timers --all --no-pager
```

Find custom units in `/etc/systemd/system`, `/usr/local/lib/systemd/system`, and the target user’s `~/.config/systemd/user`. Follow symlinks or use `systemctl cat`; a plain file scan can miss enabled units represented through target `.wants/` links.

For every custom/business unit, collect:

```bash
systemctl [--user] show UNIT \
  -p Id -p Description -p LoadState -p ActiveState -p SubState \
  -p UnitFileState -p MainPID -p ExecMainStatus -p Result -p NRestarts \
  -p FragmentPath -p ExecStart -p ExecStartPre -p ExecStop \
  -p Requires -p Wants -p BindsTo -p PartOf -p Before -p After \
  -p WantedBy -p RequiredBy -p Restart -p RestartUSec
systemctl [--user] cat UNIT
systemctl [--user] status UNIT --no-pager -l
journalctl [--user] -u UNIT -b --no-pager -n 50
```

Avoid dumping `Environment=` blindly because it may contain credentials. Extract only known-safe variables or redact values by key name.

### 4. Map the runtime, not just systemd

Systemd edges explain lifecycle coupling, not application data flow. Inspect all relevant channels:

- process tree and multiprocessing children: `ps`, cgroups, `systemd-cgls`;
- TCP/UDP listeners and owners: `ss -lntup`;
- local databases/caches and bind addresses;
- `/dev/shm`, POSIX/System V IPC, Unix sockets;
- message buses such as ROS 2/DDS, D-Bus, MQTT, Kafka, Redis streams;
- hardware producers and device consumers;
- generated child processes such as Nav2, browser workers, model servers;
- reverse proxies, relays, web UIs, and remote-access agents.

For ROS 2 systems, use the exact runtime environment from the units before querying:

```bash
source /opt/ros/<distro>/setup.bash
# apply the unit's ROS_DOMAIN_ID, RMW_IMPLEMENTATION, and DDS config
ros2 node list
ros2 topic list -t
ros2 service list -t
ros2 action list -t
```

Build text chains such as:

```text
hardware producer → driver/service → SHM/topic/socket → consumer → controller/action
```

A report must contain a textual equivalent even if it also includes a diagram.

### 5. Determine health with time-based evidence

For each critical unit, record the state tuple:

```text
ActiveState / SubState / Result / ExecMainStatus / NRestarts / MainPID
```

Re-sample restart counters after a short meaningful interval. Treat these as distinct states:

- stable running;
- intentionally disabled/on-demand;
- failed and stopped;
- activating because of `ExecStartPre`;
- crash-looping with automatic restart;
- running but business-unhealthy.

Correlate errors in this order:

1. application traceback/error;
2. missing library/interface/config/input evidence;
3. native crash or cleanup failure;
4. systemd restart/cancellation behavior;
5. dependent units affected by `Requires`, `BindsTo`, or `PartOf`.

Do not infer causality solely from timestamps; verify the dependency or data-flow edge.

### 6. Analyze exposure and operational risk

Classify findings, for example:

- **P1:** continuous crash loop, unavailable core function, unsafe actuator behavior;
- **P2:** failed startup dependency, unbounded restart policy, readiness gap, externally exposed management port;
- **P3:** capacity trend, firmware warning, stale disabled units, documentation gap.

For listeners, distinguish loopback-only from wildcard/public binding. Report the port and role, but do not expose secrets or claim authentication is weak unless it was actually tested.

### 7. Write the report

Recommended structure:

1. scope, timestamp, and read-only declaration;
2. executive summary;
3. machine baseline;
4. networking and exposed interfaces;
5. architecture overview;
6. every custom/business service: purpose, entry point, dependencies, transport, state;
7. key data and control flows;
8. grouped system infrastructure services;
9. current health findings with evidence;
10. prioritized remediation and exact verification criteria;
11. operational commands and config-path index;
12. audit boundaries and facts that may change.

Use tables for inventory and text chains for relationships. Put the most important live failure near the top. Clearly separate verified facts, reasoned interpretations, and recommendations.

### 8. Verify the artifact

If publishing to a document system, parse/validate the local draft, create it in the requested location and identity, then fetch it back. Assert that the returned content includes the title, critical services, main finding, dependency model, and audit boundary. Return the verified document URL.

## Common pitfalls

### P1: Only inspecting system services

Robot, kiosk, desktop, and per-user application stacks often live entirely under `systemctl --user`. Always inspect both scopes and check linger.

### P2: Missing units because they are symlinked

A basic `find` without following links can show only a subset of enabled user services. Use `systemctl --user list-unit-files`, `systemctl --user cat`, and `find -L` for `.wants/` trees.

### P3: Treating `active` as proof of health

Crash loops alternate between `activating`, `active`, and `failed`. The durable signal is a growing `NRestarts` plus repeated journal signatures.

### P4: Confusing transport health with consumer health

If a consumer opens SHM successfully and fails later while creating a message/service type, the producer and SHM path are healthy. Document the later interface/library failure separately.

### P5: Overstating `After=`

`After=network.target` is ordering only. `Requires=` controls activation failure propagation; `BindsTo=` couples active lifetime more strongly; `PartOf=` propagates stop/restart operations. Explain each edge accurately.

### P6: Reporting every distro unit as equal

Group standard OS services by role. Analyze custom units and anomalous system units individually. State this audit boundary explicitly.

### P7: Capturing sensitive config wholesale

Settings files and unit environments frequently contain API keys. Read only safe fields or redact names matching `key|token|secret|password|credential` before saving output.

## Supporting material

- `references/robotics-host-audit.md` — condensed checklist and interpretation guide for ROS 2, shared-memory, camera, navigation, control, and AI-service hosts.
