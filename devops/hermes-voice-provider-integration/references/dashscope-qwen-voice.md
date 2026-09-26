# DashScope / Qwen Voice Provider Notes

Verified integration pattern for Hermes command providers. Model availability and API contracts can change; re-check official Alibaba Cloud Model Studio documentation before reuse.

## Endpoint asymmetry

The generic base URL:

```text
https://dashscope.aliyuncs.com/compatible-mode/v1
```

supports OpenAI-compatible chat completions, but a probe of:

```text
POST /audio/speech
```

returned HTTP 404. Do not configure Hermes' built-in OpenAI TTS against this URL without first proving the audio route exists.

## TTS

A working Qwen TTS request used:

```text
POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
model: qwen3-tts-flash
input.text: <text>
input.voice: Cherry
```

The response contains `output.audio.url`, normally a temporary signed URL. The adapter should immediately download it to `{output_path}` and validate that the result is a real audio file. A verified result was PCM WAV, mono, 24 kHz.

Recommended credential variable:

```text
DASHSCOPE_API_KEY
```

Suggested optional behavioral variables:

```text
DASHSCOPE_TTS_MODEL=qwen3-tts-flash
DASHSCOPE_TTS_VOICE=Cherry
DASHSCOPE_TTS_LANGUAGE=Chinese
```

## STT

A working local-file pattern used the compatible chat endpoint:

```text
POST https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
model: qwen3-asr-flash
messages[0].content[0].type: input_audio
messages[0].content[0].input_audio.data: data:<mime>;base64,<audio>
asr_options.language: zh
asr_options.enable_itn: true
```

Extract:

```text
choices[0].message.content
```

and write it as UTF-8 text to the Hermes command provider's `{output_path}`.

This inline data URL route is useful because Hermes starts from a local voice-message file, while some documented Qwen ASR OpenAI-compatible examples only describe publicly accessible audio URLs.

## Hermes command-provider shapes

TTS:

```yaml
tts:
  provider: dashscope
  providers:
    dashscope:
      type: command
      command: python3 /path/dashscope_tts.py --input {input_path} --output {output_path}
      output_format: wav
      timeout: 120
      voice_compatible: false
```

STT:

```yaml
stt:
  enabled: true
  provider: dashscope
  language: zh
  providers:
    dashscope:
      type: command
      command: python3 /path/dashscope_stt.py --input {input_path} --output {output_path} --model {model} --language {language}
      output_format: txt
      timeout: 120
      model: qwen3-asr-flash
      language: zh
```

## Verification fixture

1. Generate a short known sentence through TTS.
2. Confirm the output is a non-trivial valid WAV/audio file.
3. Feed that same file to STT.
4. Check that the transcript preserves the key words of the sentence.
5. Invoke the Hermes TTS/STT command-provider path, not only the adapter script.

## Security note

Never record API keys or signed audio URLs in a skill. If a user pastes a key into chat, configure it through `~/.env` with mode `0600`, avoid echoing it, and recommend rotation afterward.
