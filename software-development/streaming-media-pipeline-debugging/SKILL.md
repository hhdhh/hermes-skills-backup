---
name: streaming-media-pipeline-debugging
description: Use when streaming voice/media is connected but silent.
version: 1.0.0
metadata:
  hermes:
    tags: [debugging, audio, voice-agent, streaming, realtime, observability]
---

# Streaming Media Pipeline Debugging

> 完整描述：Use when streaming voice/media is connected but silent. Isolate the first broken boundary with signal probes.

## Purpose

Diagnose realtime voice and media systems boundary by boundary. A healthy WebSocket, session, process, or device is not proof of end-to-end operation. Find the first boundary where valid payload stops flowing, then test one routing or conversion hypothesis at a time.

## When to use

Use when:

- a realtime AI/provider connection is healthy but conversation is silent;
- capture devices exist but VAD/transcription never triggers;
- transcription works but playback is silent;
- shared-memory, RTP, WebSocket, ROS, or queue-based media crosses several processes;
- logs contain many shutdown warnings that may obscure the initiating fault.

For a voice-agent-specific checklist and concrete signal probes, read [`references/voice-agent-pipeline.md`](references/voice-agent-pipeline.md).

## Core model

Map the actual path before diagnosing:

```text
physical source → device driver → capture process → transport/buffer
→ selector/converter → VAD/ASR/model → generated media
→ output transport/buffer → playback process → physical sink
```

Include the control plane separately:

```text
configuration → logical-name resolution → mode/state machine → provider session
```

Control-plane success can coexist with data-plane failure.

## Workflow

### 1. Define a tight red/green probe

Choose an observable assertion for the user's exact symptom. For voice input, deliberate speech must produce nonzero decoded PCM, rising application mic energy, and a VAD/transcription event. For output, a known response must change the playback buffer and reach the sink.

Do not use `service active`, `connected=true`, or `buffer file exists` as the sole pass condition.

### 2. Inventory runtime routing

Record:

- configured logical source/sink;
- resolved runtime module/device;
- modules/devices actually registered;
- owning processes and open descriptors;
- sample format, rate, channels, frame size, and transport;
- current media mode/state.

Treat a name mismatch as a falsifiable hypothesis until the setting and resolver are traced or a controlled switch restores flow.

### 3. Probe each boundary

At each boundary inspect both **liveness** and **payload validity**:

- liveness: process, socket, descriptor, producer/consumer counters;
- validity: changing frames, decoded nonzero samples, RMS/peak, timestamps, sequence progression, expected codec/shape.

A changing hash proves bytes changed, not that useful media exists. Decode or parse the payload whenever possible.

### 4. Locate the first dark boundary

Compare adjacent boundaries. Examples:

- capture buffer has valid PCM, application energy stays zero → investigate consumer attachment, selector, channel/rate conversion, or gating;
- VAD/transcript exists, no response event → investigate model/session request flow;
- response audio exists, playback buffer does not change → investigate output routing;
- playback buffer changes, no sound → investigate sink ownership, mixer, mute/volume, or hardware path.

Focus on the earliest failure; later cleanup exceptions are usually consequences.

### 5. Test one hypothesis

Make the smallest reversible change or read-only probe that distinguishes the leading hypotheses. Re-run the same red/green probe. Do not change provider, microphone, VAD, and output routing together.

### 6. Verify end to end

A fix is complete only when the original interaction succeeds through every required boundary. Re-check service stability and unrelated paths afterward.

## Reporting format

Separate:

1. directly verified healthy boundaries;
2. the first failing boundary;
3. leading hypothesis and confidence;
4. the confirming test;
5. whether a fix was applied and end-to-end verified.

Do not report a plausible mapping mismatch as root cause until configuration/routing has been traced or switching it makes the tight probe green.

## Pitfalls

- Equating AI/provider connectivity with functioning conversation.
- Equating device enumeration or buffer creation with valid media.
- Blaming optional package warnings without evidence that the fallback fails.
- Treating cleanup-time context/destruction errors as the initiating fault.
- Changing persistent configuration through an undocumented API field.
- Declaring success after a restart without producing a real transcript/output event.
