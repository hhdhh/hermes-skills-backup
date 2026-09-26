---
name: remote-incident-diagnosis
description: Use when diagnosing a remote host or robot incident.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ssh, remote-debugging, network, robots, incident-response]
---

# Remote Incident Diagnosis

> 完整描述：Use when diagnosing a remote host or robot incident. Gate transport before credentials and code claims.

## Purpose

Diagnose incidents on a remote machine without confusing a local connectivity failure with a remote application failure. The workflow is evidence-first: establish that the target is reachable, inspect the actual remote state, then form and test a root-cause theory.

## Workflow

1. **Record the target literally.** Preserve the supplied IP/hostname, username, and port. Do not silently substitute a nearby host or normalize identifiers.
2. **Check local transport prerequisites.** Inspect `ip -brief address`, `ip route get TARGET`, and the relevant interface state. For private LAN targets, verify the robot-facing NIC/cable/VLAN is actually up.
3. **Probe before authenticating.** Use a bounded `ping` where ICMP is meaningful and a bounded TCP probe (`nc -vz -w 3 TARGET 22` or an equivalent connect test). Only attempt SSH authentication after TCP connects.
4. **Authenticate without claiming success prematurely.** A timeout means the password was not tested. A refused connection means the host/path answered but the service is unavailable. An authentication failure means transport succeeded and credentials or account policy need investigation.
5. **Inspect remote state after login.** Gather process state, artifact/download state, service logs, exact source locations, and relevant environment/configuration. Read the implementation around the traceback and trace callers before editing.
6. **Build a tight reproduction or verification probe.** Prefer a command that fails on the reported path and turns green after the repair. For cleanup races, capture process lifetime, open files, and directory changes rather than guessing.
7. **Classify findings.** Label each statement as observed from the report, locally verified, remotely verified, or hypothesis. Never call a source-level theory verified when the remote source/runtime was inaccessible.
8. **Finish with an actionable handoff.** If blocked by reachability, state the exact blocker and provide the smallest commands the operator can run on a host that is actually on the target LAN. Do not imply that credentials were tried when the TCP handshake never completed.

## Network/SSH Gate

The minimum gate for `ssh user@TARGET` is:

```bash
ip -brief address
ip route get TARGET
ping -c 3 -W 2 TARGET
nc -vz -w 3 TARGET 22
```

Interpret the result before proceeding. A route through a general Wi-Fi gateway to a robot-only subnet is not evidence that the robot is reachable. If the robot-facing interface is `DOWN`, fix physical/link/routing access or run the probe from the correct jump host; do not keep retrying SSH.

## Dual-Homed Robot Notes

Robots often expose separate management and device LANs. The target may be reachable only through `lan0`/`lan1` or a host physically connected to one of them. Check the local source address selected by `ip route get`; it should match the intended network. A successful SSH connection to another robot address does not prove the requested address is reachable.

## Evidence Discipline

- Preserve full traceback paths and line numbers.
- Separate download/login success from post-processing/cleanup failure.
- If a download completed but cleanup failed, verify files and checksums before recommending another full download.
- Avoid destructive cleanup or process killing until the target process/profile is identified; do not kill unrelated user sessions.
- Do not edit remote code without first reading the relevant function and its process-launch/teardown paths.

## Pitfalls

- Treating a timeout as a bad password.
- Diagnosing remote Chrome, SSH, or application state from a traceback alone.
- Assuming a default route can reach a private device subnet.
- Reporting a likely root cause as confirmed when no remote inspection occurred.
- Asking the operator to run a long list of commands before identifying the transport blocker; keep the handoff focused.

## Supporting Detail

See `references/dual-homed-robot-ssh-gate.md` for the reusable probe interpretation and the evidence boundary used in the incident that motivated this skill.

## Verification Checklist

Before finalizing a remote diagnosis:

- [ ] Target, port, and username preserved exactly.
- [ ] Local interface and selected route checked.
- [ ] TCP transport result recorded.
- [ ] Credential status not overstated.
- [ ] Remote inspection performed, or explicitly marked blocked.
- [ ] Claims categorized as observed, verified, or hypothesized.
- [ ] Next action is executable from the operator's actual network position.
