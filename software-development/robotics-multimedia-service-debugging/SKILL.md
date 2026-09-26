---
name: robotics-multimedia-service-debugging
description: Use when debugging robot vision, audio, face, or AI servi...
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [robotics, vision, audio, systemd, ros2, shared-memory, debugging]
    related_skills: [systematic-debugging]
---

# Robotics Multimedia Service Debugging

> 完整描述：Use when debugging robot vision, audio, face, or AI services.

## Purpose

Diagnose robot services that combine cameras, microphones, ROS 2, shared memory, realtime AI, and systemd supervision. Treat each user-visible feature as an end-to-end data path rather than inferring health from a single process or configuration flag.

## Core rule

A service showing `active (running)` is not proof of health when `Restart=always` is configured. Establish process stability before debugging higher-level behavior.

## Read-only investigation order

When the user says “先不作改动”, do not restart, stop, patch, or rewrite anything. Use read-only inspection only.

1. **Confirm machine identity**
   - Read hostname, boot ID, boot time, addresses, and robot ID.
   - This is essential when the same IP is reused by different robots.

2. **Prove service stability**
   - Inspect `ActiveState`, `SubState`, `Result`, `MainPID`, `ExecMainStatus`, `NRestarts`, and timestamps.
   - Read the systemd start/stop timeline.
   - Correlate status 139 with kernel segfault records and native child process names.
   - A repeatedly restarting service can appear healthy at the instant of inspection.

3. **Read the effective configuration**
   - Resolve the actual imported package path before choosing the settings file.
   - Inspect feature flags, provider selection, interface names, microphone selection, and credential *presence only*.
   - Never print API keys or tokens; report set/unset and optionally length/fingerprint.

4. **Trace each feature independently**

   **Realtime conversation**
   - Feature enabled → provider selected → required key present → audio device registered → event loop started → WebSocket session created/updated → transcript/response activity.
   - Distinguish local signaling `WebSocket Connected` from the AI provider WebSocket.
   - If provider is Qwen, confirm the code’s actual key lookup (`QWEN_API_KEY` and any TTS-specific fallback such as `ALIYUN_API_KEY`) rather than assuming one key feeds all components.

   **Face detection**
   - Feature enabled → camera hardware enumerated → intended camera module registered → producer created expected SHM objects → consumer attached → face callback registered → face events/topics emitted.
   - `face_detection_enabled=true` and callback registration do not prove image input exists.
   - Enumerate `/dev/shm` and compare actual names with attachment errors.

5. **Check interface-name drift**
   - Compare configured interface lists with `ip -brief addr`.
   - Report invalid aliases separately from the primary fault unless they directly break the data path.

6. **Separate root causes from secondary noise**
   - Credential initialization failures, missing SHM, a camera capture failure, logger exceptions, and cleanup segfaults may coexist.
   - Build a timestamped causal sequence and assign a repair priority.
   - Conda warnings or unrelated camera failures should not displace a proven service-crash cause.

## Repair priority

1. Stop deterministic crash/restart loops.
2. Restore missing producers and data sources (camera/SHM/audio).
3. Supply or correct provider credentials.
4. Correct network-interface mappings and secondary device issues.
5. Verify with stable uptime, zero new restarts, expected session/callback logs, and a real user-level interaction.

## Verification standard

A fix is complete only when all applicable checks pass:

- `NRestarts` does not increase during the observation window.
- No new native segfault or status 139 appears.
- Required SHM objects exist and consumers attach.
- AI logs show provider-specific session creation/update, not merely local signaling.
- A real spoken utterance or face event traverses the full pipeline.

## Pitfalls

- Do not diagnose from a single `systemctl status` snapshot.
- Do not equate hardware enumeration with usable frames.
- Do not equate callback registration with functioning detection.
- Do not treat every `WebSocket Connected` line as the cloud AI connection.
- Do not enable a configured proxy without first proving a listener exists and the robot can reach it.
- Do not expose credentials in diagnostics or summaries.

See `references/autolife-vision-service.md` for a concrete evidence map and command checklist derived from an Autolife vision-service investigation.
