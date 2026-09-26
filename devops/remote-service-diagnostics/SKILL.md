---
name: remote-service-diagnostics
description: "Use when diagnosing remote Linux services read-only."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [ssh, systemd, networking, diagnostics, websocket, proxy]
---

# Remote Service Diagnostics

## Purpose

Diagnose Linux services over SSH while preserving an explicit **inspect-only / do-not-change** boundary. Establish which component and network channel failed before recommending changes.

## Read-only workflow

1. **Confirm the target and scope**
   - Verify hostname after login.
   - If the user says not to change anything, do not restart/stop/enable/reload services, edit files, install packages, or create files on the remote host.
   - Prefer one-shot noninteractive SSH commands for reproducible capture. Never expose the supplied password in output or persist it in scripts beyond the active session.

2. **Capture service identity and state**
   - Read `systemctl --user status`, `cat`, and `show` (or system equivalents).
   - Capture `FragmentPath`, `ExecStart`, `WorkingDirectory`, `Environment`, `MainPID`, `ActiveState`, `SubState`, `Result`, `NRestarts`, `ExecMainCode`, and `ExecMainStatus`.
   - Read a bounded journal window around the incident.

3. **Map each log line to its channel**
   - Do not merge similarly named WebSocket connections. A local signaling socket may be healthy while a cloud realtime-AI socket times out.
   - Record endpoint, component, timing, and result separately for every channel.

4. **Trace proxy gates end to end**
   - Inspect the configured proxy URL, the feature-enable flag, runtime process environment, and a listener at the configured address.
   - Distinguish:
     - configured but disabled;
     - enabled but not injected into runtime;
     - injected but no proxy listener;
     - listener present but upstream route failing.
   - Interpret application wording carefully: “variable not set” may describe effective runtime state, not absence from a config file.

5. **Probe the smallest useful network layers**
   - Inspect interfaces, routes, and resolver state.
   - Test DNS, TCP 443, TLS/HTTP, and the exact WebSocket endpoint when discoverable.
   - A successful generic HTTPS request to a provider domain proves basic reachability only; it does not prove a specific realtime WebSocket handshake or authentication path.

6. **Separate primary and secondary findings**
   - Hardware/VAD/audio buffer messages may be downstream noise rather than the connection root cause.
   - Package warnings and unrelated dependency errors should be labeled secondary unless the failing call path actually depends on them.

7. **Re-check state before reporting**
   - If service state changed during diagnosis, correlate journal timestamps and systemd result fields.
   - `signal=TERM` plus a `Stopping ...` journal entry and `Result=success` usually indicates an external explicit stop, not an application crash. Do not attribute the stop to the investigation without evidence.

8. **Report evidence before fixes**
   - State what is confirmed, what is ruled out, and what remains unknown.
   - Do not recommend enabling a configured proxy until a listener is confirmed at that address.
   - Redact API keys, tokens, passwords, secrets, and credential-bearing proxy URLs.

## Reference

See `references/systemd-websocket-proxy-checklist.md` for a compact command and interpretation checklist.
