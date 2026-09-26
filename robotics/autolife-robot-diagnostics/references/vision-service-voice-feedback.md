# Vision-service no voice feedback: robot-271 evidence pattern

This reference captures a recurring Autolife diagnostic pattern: `vision-service` restarts successfully but user hears no voice feedback.

## Observed machine identity

- SSH target was `ubuntu@192.168.10.2`, but the host identified as `autolife-robot-271`, not the previous robot-255.
- `ROBOT_ID=271`, Ubuntu 24.04.3, user-level `vision-service`.

## Decisive logs

Vision itself was running and stable:

```text
ActiveState=active
SubState=running
NRestarts=0
VisionService Core initialized
VisionService core initialized successfully
WebSocket Connected
Registration ACK received
```

Audio hardware initialized:

```text
Found speaker device: sysdefault:CARD=PCH
Speaker registered on sysdefault:CARD=PCH
Microphone registered on hw:1,0
Microphone registered on hw:0,0
```

ALSA showed the Vision Python PID owning capture/playback devices:

```text
/dev/snd/pcmC0D0p: ubuntu <vision-python-pid> python
/dev/snd/pcmC0D0c: ubuntu <vision-python-pid> python
/dev/snd/pcmC1D0c: ubuntu <vision-python-pid> python
```

Conversational voice was disabled upstream because the AI Chatbot did not initialize:

```text
[INFO] Initializing AI Chatbot...
[INFO] Successfully loaded system prompt from: .../assets/prompt/prompt.txt
[ERROR] Failed to initialize AI chatbot: OpenAI API key not found.
```

Network-dependent model/TTS resources were unreachable or slow:

```text
HTTPSConnectionPool(host='huggingface.co', port=443) ...
Failed to establish a new connection: [Errno 101] Network is unreachable
Temporary failure in name resolution
```

A fixed TTS phrase could fail independently because the wav asset was missing:

```text
[INFO] TTS_LIST command received: 智动未来简介
[ERROR] 文件 .../autolife_robot_vision/assets/tts/wav/智动未来简介.wav 不存在
```

But other TTS backends/assets could still initialize:

```text
[INFO] Kokoro TTS initialized with model: hexgrad/Kokoro-82M-v1.1-zh, voice: zf_001
[INFO] Local Piper TTS initialized
[INFO] Wav TTS initialized successfully
```

## Interpretation

Do not summarize this class as “audio broken.” The diagnostic split is:

1. ALSA/GStreamer speaker and mic registration were OK.
2. Vision service was active and registered to its local websocket/signaling service.
3. Conversational voice feedback could not work because OpenAI API key was missing.
4. Some predefined phrase playback could not work because selected `.wav` files were absent.
5. HuggingFace/OpenAI network unreachability can delay or break online Kokoro/OpenAI paths.
6. PipeWire being masked is not decisive on this machine because Vision uses ALSA/GStreamer directly.

## Read-only probes to run next time

```bash
systemctl --user show vision-service.service \
  -p ActiveState -p SubState -p MainPID -p NRestarts -p Result -p ExecMainStatus
journalctl --user -u vision-service.service -b --no-pager \
  | grep -Ei 'OpenAI|API key|chatbot|Kokoro|TTS|speaker|microphone|audio|huggingface|network|unreachable|WebSocket|Registration ACK'
cat /proc/asound/cards
aplay -l
arecord -l
fuser -v /dev/snd/*
ip -br addr
ip route
resolvectl status
timeout 12 curl -I https://api.openai.com
timeout 12 curl -I https://huggingface.co/hexgrad/Kokoro-82M-v1.1-zh/resolve/main/voices/zf_001.pt
```

If the user requested read-only, stop at diagnosis and do not add keys, copy assets, alter service env, restart services, or change network/proxy settings.
