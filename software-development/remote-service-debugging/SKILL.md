---
name: remote-service-debugging
description: Use when remote system services run but a feature fails.
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    tags: [systemd, ssh, remote-debugging, services, configuration, networking]
---

# Remote Service Debugging

> 完整描述：Use when remote system services run but a feature fails. Diagnose systemd-backed application chains layer by layer.

## Purpose

Diagnose remote Linux applications whose systemd unit appears healthy while an internal feature—AI, audio, camera, provider API, database, or another optional subsystem—does not work.

The governing rule is: **service health is not feature health**. `active (running)` proves that a process exists, not that every subsystem initialized or that the user-facing path works.

## Investigation sequence

1. Confirm host reachability; capture hostname and time so journal evidence has an anchor.
2. Inspect all involved user/system units and failed units, not only the service named by the user.
3. Read bounded journal history around startup and the reported failure. Search for subsystem initialization, authentication, connection, timeout, traceback, and retry lines.
4. Read the complete effective unit with paging disabled. Inspect `ExecStart`, environment, environment files, dependencies, restart policy, and stop timeout.
5. Locate the package and configuration actually loaded by the running interpreter/process. Do not infer it from a similarly named checkout or shell environment.
6. Trace the feature through each boundary: process → subsystem initialization → local IPC/device → DNS/TCP/TLS/HTTP/WebSocket → provider authentication/session → user-visible result.
7. Build the tightest repeatable probe for the failed boundary before changing anything.

For command patterns and interpretation details, read `references/systemd-feature-chain.md`.

## Configuration forensics

When logs suggest configuration changed recently:

- Compare modification times and timestamped backups before editing.
- Parse TOML/YAML/JSON with its native parser where possible.
- For credentials, inspect only presence and character length. Never print values into logs, tool output, or chat.
- Make a fresh timestamped backup of the current file before repair.
- Restore only a confirmed bad field from a known-good local backup; preserve unrelated current settings.
- Re-parse after writing and prove that the owning process loaded the corrected source.

Do not persist environment-specific credential values or conclude that a particular provider/tool is generally broken.

## Layered diagnosis

Treat sequential errors as separate layers. For example:

- missing credential;
- credential restored, but network connection reset;
- provider session established, but application callback crashes;
- backend works, but audio/input path still fails.

Fixing one layer may reveal the next. Never report the entire feature as fixed merely because the earlier error disappeared.

Generic logging exceptions can mask an earlier root error. Preserve chronological context around both rather than treating the final logger exception as the only fault.

## Verification ladder

Verify in this order:

1. unit is active and stable;
2. target subsystem reports successful initialization;
3. required local resource or IPC path works;
4. external provider endpoint/session succeeds;
5. application request produces the expected internal response;
6. end-to-end user interaction succeeds.

A lower rung does not imply a higher one. If host reachability is lost, stop and report the highest rung actually verified plus the exact remaining check.

## Reporting

State concisely:

- confirmed root cause and evidence timestamp;
- exact field/component repaired, without secret values;
- verification rung reached after repair;
- any next blocking layer;
- whether end-to-end verification ran or was prevented.

Do not call unresolved work complete.