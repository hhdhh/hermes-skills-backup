# Autolife vision-service evidence map

Use this as a concise checklist, not as a claim that every robot has the same failure.

## Machine identity

Before comparing with another robot, collect:

- hostname and boot ID
- boot time
- interface names and addresses
- systemd unit `ROBOT_ID`
- installed `autolife-robot-vision` and SDK versions

The same address may later refer to a different robot, so never carry conclusions across machines based on IP alone.

## Conversation path

Relevant effective settings commonly include:

- `ai_chatbot_enabled`
- `realtime_api_provider`
- `start_conversation_on_launch`
- `ai_audio_input_device`
- `enable_hybrid_vad`, `enable_input_vad`
- provider key presence and region
- `TTS_PROVIDER`

Evidence hierarchy:

1. microphone and speaker registered
2. AI manager initialized without key/model errors
3. provider-specific session log (`Qwen session.created`, `session.updated`, etc.)
4. transcript/response events from a real utterance

A local signaling log such as `Registration ACK received` proves only the robot’s local signaling path.

## Face path

Evidence hierarchy:

1. intended camera is visible under `/sys/class/video4linux`
2. camera module registers and captures frames
3. expected color/depth/JPEG SHM producer objects exist under `/dev/shm`
4. face or RGBD consumer attaches without `No shared memory exists`
5. face callback is registered
6. face events/topics are emitted during a real test

If callback registration succeeds but RGBD SHM attachment fails, detection still has no input.

## Crash-loop signature

A misleading snapshot may show:

- `ActiveState=active`
- `SubState=running`

while the timeline shows repeated:

- application exits
- systemd status 139
- `Restart=always` launches it again
- kernel logs identify a native child segfault

Always inspect `NRestarts` plus the timeline. Build a causal sequence from the first application exception through cleanup and native crash; do not assume the final segfault was the initiating error.

## Common independent faults

Keep these separate unless evidence links them:

- AI provider selected but required key absent
- TTS reading a different key field than the realtime provider
- RGBD hardware enumerated but SHM producer absent
- one peripheral camera unable to capture
- configured `lan0`/`lan1` names absent on machines using predictable names such as `enp171s0`
- application logger exception followed by cleanup segfault

## Safe reporting

- State explicitly whether any changes or restarts were made.
- Never print key values; report only set/unset and possibly a short hash.
- Rank root causes and repair order.
- If repair has not been executed and verified, label it as a proposed next step rather than a proven fix.
