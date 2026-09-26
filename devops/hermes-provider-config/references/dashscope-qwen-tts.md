# DashScope Qwen TTS as a Hermes command provider

Use when a user supplies a DashScope API key/base URL and wants Hermes spoken replies.

## Endpoint distinction

DashScope's OpenAI-compatible base URL:

```text
https://dashscope.aliyuncs.com/compatible-mode/v1
```

is suitable for compatible chat APIs, but do **not** assume it implements OpenAI `POST /audio/speech`. Probe the exact route first; a verified test returned HTTP 404. Qwen3-TTS uses the native DashScope multimodal endpoint:

```text
POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
Authorization: Bearer $DASHSCOPE_API_KEY
Content-Type: application/json
```

Example body:

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

The JSON response contains `output.audio.url`; download that URL to the output file expected by Hermes.

## Hermes integration pattern

Hermes supports custom command TTS providers under `tts.providers.<name>`:

```yaml
tts:
  provider: dashscope
  providers:
    dashscope:
      type: command
      command: python3 ~/.hermes/scripts/dashscope_tts.py --input {input_path} --output {output_path}
      output_format: wav
      timeout: 120
      voice_compatible: false
```

Store `DASHSCOPE_API_KEY` in `~/.env` with mode 600, never inline in `config.yaml` or scripts. Make model/voice optional environment settings, e.g. `DASHSCOPE_TTS_MODEL=qwen3-tts-flash`, `DASHSCOPE_TTS_VOICE=Cherry`.

## Verification ladder

1. Probe the native API and confirm HTTP 200 plus a non-empty `output.audio.url`.
2. Run the adapter directly using a temporary UTF-8 input file.
3. Validate the downloaded artifact (`file` should report RIFF/WAVE; size should be meaningfully above a few hundred bytes).
4. Call Hermes `text_to_speech(provider="dashscope", ...)` and require `success: true` plus a real media path.
5. Only then set `tts.provider: dashscope`; restart the CLI/gateway if configuration was loaded before the change.

## Pitfalls

- A chat-compatible base URL does not imply TTS compatibility; verify the exact API route.
- DashScope returns a temporary audio URL, not raw WAV bytes in the first response.
- Never print or repeat a user-supplied API key. If it was pasted into chat, recommend rotating it after setup.
- Do not declare success from config output alone; generate and inspect a real audio file.
