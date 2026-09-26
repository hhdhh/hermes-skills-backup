---
name: hermes-voice-provider-integration
description: "Use when adding custom STT/TTS providers to Hermes."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, voice, stt, tts, command-provider, openai-compatible, dashscope]
    related_skills: [hermes-agent, hermes-provider-config]
---

# Hermes Voice Provider Integration

Integrate and verify custom speech-to-text (STT) and text-to-speech (TTS) backends in Hermes without changing the main chat model. Use this when a service is not covered by Hermes' built-in voice providers, or when a nominally OpenAI-compatible endpoint implements chat but not the standard audio routes.

## Core rule

Do not assume that an OpenAI-compatible base URL supports `/audio/speech` or `/audio/transcriptions`. Probe the exact endpoint with a tiny real request. A provider may expose TTS through a native multimodal endpoint and STT through `/chat/completions` with `input_audio` instead.

## Workflow

1. **Inspect live Hermes capabilities**
   - Load the bundled `hermes-agent` configuration reference.
   - Run `hermes config get tts` and `hermes config get stt`.
   - Inspect command-provider support if the requested provider is not built in.

2. **Verify the provider contract**
   - Check current official provider documentation.
   - Probe the exact model, endpoint, request shape, and voice/language with a short request.
   - Never print API keys or full signed result URLs.
   - A successful HTTP status is insufficient: validate returned audio or transcript content.

3. **Choose the integration primitive**
   - Built-in backend: configure `tts.<provider>` or `stt.<provider>`.
   - Unsupported/native backend: add `tts.providers.<name>.type: command` or `stt.providers.<name>.type: command`.
   - Store credentials in `~/.env`; store behavioral settings in `~/.hermes/config.yaml`.

4. **Implement a small adapter**
   - TTS command receives `{input_path}` and `{output_path}` and must write a valid audio file.
   - STT command receives `{input_path}` and `{output_path}` and must write plain transcript text.
   - Accept model/language placeholders when useful.
   - Use timeouts, explicit errors, and output sanity checks.

5. **Configure additively, then switch**
   - Register the named provider first.
   - Verify its adapter directly.
   - Only then set `tts.provider` or `stt.provider` to the new name.
   - Preserve the previous provider config so rollback is a one-key change.

6. **Exercise the real Hermes path**
   - For TTS, verify file type, size, and invoke Hermes' TTS tool/provider.
   - For STT, transcribe a known generated clip and compare the returned sentence.
   - Restart the CLI or gateway after configuration changes; tool/config changes are not guaranteed to affect an already-running process.

## Security

- Never embed credentials in adapter scripts or `config.yaml`.
- Keep `~/.env` mode `0600`.
- If a key was pasted into chat, advise rotation after setup.
- Reports should name the credential variable and whether it is set, never reveal its value.

## Pitfalls

- **False compatibility:** `/compatible-mode/v1` may support chat completions but return 404 for audio routes.
- **Wrong success signal:** a provider object being initialized does not prove its remote session is connected; require provider-specific session/response evidence.
- **Signed URL leakage:** native TTS responses may return temporary signed audio URLs. Download them in the adapter; do not expose them in logs.
- **STT output shape:** Hermes command STT consumes text from `{output_path}` or stdout. Extract the transcript in the adapter rather than returning raw JSON.
- **Remote audio constraints:** some ASR endpoints accept only public URLs. Prefer a documented inline data URL/base64 route when Hermes supplies a local file.

## Provider notes

See [references/dashscope-qwen-voice.md](references/dashscope-qwen-voice.md) for a verified DashScope/Qwen pattern, including endpoint asymmetry and model choices.
