# Voice-agent boundary checklist

## Input and control plane

1. Confirm realtime WebSocket/session creation and configuration completion.
2. Observe the application's own connection/status endpoint or topic.
3. Record the configured logical input and the physical/module name it resolves to.
4. Compare the resolved name with modules actually registered at runtime.
5. Confirm the current media mode routes local microphone audio to AI rather than relay-only, direct playback, or a disabled path.

`connected=true` proves only provider/control-plane health.

## Device and transport

1. Enumerate capture and playback devices.
2. Identify the process owning each expected device descriptor.
3. Verify producer and consumer attachment to shared memory, ring buffers, sockets, or queues.
4. Sample counters or hashes twice over several seconds to establish activity.
5. Decode a window using the declared PCM format; compute nonzero count, RMS, and peak.

Changing bytes alone may be metadata churn, sparse frames, stale data, or silence.

## Application ingestion

During deliberate speech near the intended microphone, observe:

- microphone-energy metric rising above zero;
- VAD `speech_started`/`speech_stopped` events;
- transcription events;
- model response events.

Interpretation:

- valid buffer PCM + zero application energy → break between capture transport and AI ingestion;
- energy present + no VAD → VAD threshold/format/gating hypothesis;
- VAD present + no transcription → provider/input append/commit path;
- transcription present + no response → model/session response path.

## Output

If the model responds but nothing is heard:

1. verify generated-audio events;
2. verify speaker buffer writes or packet counters;
3. verify playback process owns the expected sink;
4. inspect mixer mute/volume and channel routing;
5. play a known local sample through the same sink as a differential test.

## Tight verification

A repeatable end-to-end voice probe should establish:

- provider session connected;
- intended microphone selected;
- plausible nonzero PCM during speech;
- application mic energy rises;
- transcription appears;
- response audio is generated;
- output transport changes;
- response is audible.

Report the earliest failing boundary and distinguish verified fact from the next hypothesis. Never mutate persistent configuration through an undocumented field merely because its likely value is obvious.