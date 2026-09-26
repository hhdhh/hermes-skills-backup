# DashScope Qwen Speech Provider Notes

Validated against the Beijing DashScope endpoints in August 2026. Re-check official docs and model availability before reuse.

## Important protocol split

The general OpenAI-compatible base URL:

```text
https://dashscope.aliyuncs.com/compatible-mode/v1
```

supports Qwen ASR through chat completions with audio input, but the tested route:

```text
POST /audio/speech
```

returned HTTP 404. Do not configure Hermes OpenAI TTS against that path merely because chat completion compatibility works.

## TTS: Qwen3-TTS

Validated HTTP endpoint:

```text
POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
Authorization: Bearer $DASHSCOPE_API_KEY
Content-Type: application/json
```

Minimal body:

```json
{
  "model": "qwen3-tts-flash",
  "input": {
    "text": "这是语音测试。",
    "voice": "Cherry",
    "language_type": "Chinese"
  }
}
```

The response contains `output.audio.url`, a temporary signed URL. The adapter must download that URL and write the returned audio bytes. Do not log the signed URL. A validated response produced PCM WAV, mono, 24 kHz, 16-bit.

Useful defaults:

- model: `qwen3-tts-flash`
- voice: `Cherry`
- language: `Chinese`

Model and voice availability can change; consult current official Model Studio docs.

## STT: Qwen3-ASR

Validated endpoint:

```text
POST https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
Authorization: Bearer $DASHSCOPE_API_KEY
Content-Type: application/json
```

Minimal body shape:

```json
{
  "model": "qwen3-asr-flash",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "input_audio",
          "input_audio": {
            "data": "data:audio/wav;base64,..."
          }
        }
      ]
    }
  ],
  "stream": false,
  "asr_options": {
    "language": "zh",
    "enable_itn": true
  }
}
```

Transcript location:

```text
choices[0].message.content
```

For Hermes command-provider integration, write only that transcript to `{output_path}` as UTF-8 text.

## Closed-loop verification

1. TTS a short distinctive Chinese sentence.
2. Confirm output with `file` and a non-trivial byte size.
3. Feed the result to `qwen3-asr-flash`.
4. Compare the recognized sentence semantically; spacing and punctuation normalization are acceptable.
5. Verify `hermes config get tts.provider` and `hermes config get stt.provider` select the intended command provider.
6. Exercise Hermes's `text_to_speech`/voice surface after restarting the relevant process.

## Credential location

Use `hermes config env-path` and store:

```text
DASHSCOPE_API_KEY=...
```

Set mode `600`. Never hard-code the key in the adapter or commit it to the skill library.
