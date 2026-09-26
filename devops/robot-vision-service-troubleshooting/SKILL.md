---
name: robot-vision-service-troubleshooting
version: 1.0.0
description: Use when diagnosing a robot's vision, voice-dialog, AI ch...
---

# Robot vision and voice-service troubleshooting

> 完整描述：Use when diagnosing a robot's vision, voice-dialog, AI chatbot, audio relay, or related systemd services. Inspect logs and package entrypoints, separate hardware/network/backend failures, back up before service changes, and verify recovery.

## Workflow

1. **Connect and identify the target**
   - Verify the target IP, hostname, active interfaces, route, and SSH access before changing anything.
   - Prefer a non-interactive password mechanism that does not print credentials into shell history or logs.
   - Record the current service state and recent logs before restarting or editing anything.

2. **Separate the layers**
   - Check `vision-service.service`, the AI chatbot initialization logs, the realtime provider session, `autolife-relay.service`, and any flow/data-logger units independently.
   - Treat these as separate gates: hardware registration, backend/workspace lookup, provider WebSocket, local chatbot initialization, and frontend relay connection.
   - Do not call a service healthy merely because systemd reports `active`; inspect the application logs for initialization completion.

3. **Validate the audio path without blaming hardware prematurely**
   - Look for explicit microphone registration, shared-memory buffer creation, speaker registration, and audio socket creation in the vision logs.
   - If those succeed, investigate chatbot/provider/relay initialization instead of changing ALSA, PipeWire, or physical devices.
   - `Active Audio Connections (0)` means no relay client is connected; it does not prove the microphone or speaker is broken.

4. **Validate workspace/backend configuration**
   - Distinguish HTTP errors: `409` usually indicates a binding conflict; `404` on the workspace API indicates a missing, invalid, deleted, or wrong-environment workspace resource.
   - Confirm the effective workspace identifier and API endpoint from runtime logs/config, but do not alter workspace ownership or bindings unless the user explicitly directs it.
   - After a workspace correction, restart the vision service only when needed and verify that the old 404/409 is gone.

5. **Inspect local initialization failures**
   - If provider logs show session creation and WebSocket connection succeeded but chatbot initialization still fails, treat the remaining error as a local package/runtime compatibility problem.
   - Capture the exact exception and locate the responsible package/module before changing binaries or reinstalling environments.
   - A logging error such as `info() takes exactly 1 positional argument (3 given)` indicates an incompatible logger call or wrapper; do not misclassify it as an API, workspace, or audio failure.
   - Warnings such as missing wrapper attributes may indicate a package/API mismatch; record them separately from the fatal initialization exception.

6. **Handle broken auxiliary systemd units safely**
   - Inspect the unit's `ExecStart`, installed package tree, importable modules, `Restart`, and `RestartSec` before fixing it.
   - Never invent a replacement Python module path from a similar package name. Prove the entrypoint exists with the target environment's Python/import tooling.
   - If a stale unit repeatedly launches a nonexistent module and another active service already owns the function, back up the unit and disable the stale unit; do not blindly reinstall the environment.
   - Check for duplicate autostart units or wrapper scripts that can re-enable the bad service.
   - Verify the unit is inactive, restart count is stable, no new error logs appear, and the legitimate vision/flow services remain active.

7. **Verify after every state change**
   - Re-check service states, process list, recent journal entries, provider session logs, relay connection counters, and system load.
   - Report what was changed, the backup path, what is fixed, and what remains unresolved.

## Durable pitfalls

- Do not equate `systemctl active (running)` with application readiness; a process can remain alive after chatbot initialization failed.
- Do not conflate a successful provider WebSocket with a successful chatbot; local tool/schema/logging initialization may still fail afterward.
- Do not use `Active Audio Connections (0)` as proof of bad audio hardware; it describes relay clients, not device registration.
- Do not fix a missing module by guessing a similarly named package path; inspect the installed package and import graph first because compiled package layouts frequently move entrypoints.
- Back up service files and wrapper scripts before disabling a restart loop; the backup makes rollback possible without copying secrets or the whole environment.

## User-specific output

- Reply in simplified Chinese, address the user as “主人”, lead with the conclusion, then give evidence and remaining actions.
- When the user asks for direct handling, perform safe internal diagnostics and reversible service cleanup directly; avoid changing workspace bindings or credentials without explicit direction.
- Keep credentials out of logs, reports, backups, and memory.
