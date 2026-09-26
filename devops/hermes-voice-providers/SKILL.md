---
name: hermes-voice-providers
description: Use when adding or validating custom Hermes STT/TTS provi...
version: 1.0.0
author: hermes-agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, voice, stt, tts, command-provider, speech]
    related_skills: [hermes-agent]
---

# Hermes Voice Providers

> 完整描述：Use when adding or validating custom Hermes STT/TTS providers.

Configure, adapt, and verify speech-to-text (STT) and text-to-speech (TTS) providers in Hermes, especially APIs that are not natively supported but can be wrapped as command providers.

## Trigger

Use when the user asks to:

- configure a TTS or STT model for Hermes;
- use an OpenAI-compatible or vendor-specific speech API;
- add a custom command-backed voice provider;
- diagnose voice input/output after an upgrade;
- validate an STT↔TTS voice loop.

For ordinary built-in providers, consult the bundled `hermes-agent` configuration reference first. This skill covers the adapter and verification layer.

## Safety and secret handling

1. Never repeat an API key in output, logs, generated config snippets, or process arguments.
2. Store credentials in the Hermes environment file reported by `hermes config env-path`; do not assume `~/.env` and `~/.hermes/.env` are interchangeable.
3. Set the environment file to mode `600` on POSIX systems.
4. If a key was pasted into chat, configure it if authorized, but advise rotation afterward.
5. Put provider behavior in `config.yaml`; put only secrets in the environment file.

## Workflow

### 1. Inspect the live schema

Run before editing:

```bash
hermes --version
hermes config get stt
hermes config get tts
hermes config env-path
```

Confirm command-provider support from the installed version rather than relying on memory. Custom provider entries normally use:

```yaml
stt:
  provider: vendor
  providers:
    vendor:
      type: command
      command: "python3 /absolute/adapter.py --input {input_path} --output {output_path}"
      output_format: txt
      timeout: 120

tts:
  provider: vendor
  providers:
    vendor:
      type: command
      command: "python3 /absolute/adapter.py --input {input_path} --output {output_path}"
      output_format: wav
      timeout: 120
```

STT command providers may also receive `{model}`, `{language}`, `{format}`, and `{output_dir}`. Use only placeholders verified in the installed source/docs.

### 2. Verify the API protocol before configuring Hermes

A base URL being “OpenAI-compatible” for chat does **not** prove it supports `/audio/speech` or `/audio/transcriptions`.

Probe the exact speech endpoint with a tiny request, without printing the key. Treat HTTP 404 as protocol mismatch, not authentication failure. Consult `references/dashscope-qwen-speech.md` for the validated DashScope split between TTS and ASR.

### 3. Build a narrow adapter

The adapter should:

- accept absolute `--input` and `--output` paths;
- load the credential from the environment file;
- use a bounded network timeout;
- emit only the expected artifact (plain UTF-8 text for STT, valid audio for TTS);
- return non-zero on API errors or malformed output;
- create the output parent directory;
- avoid dependencies when the standard library is sufficient;
- never print secrets or full signed result URLs.

### 4. Configure additively

Add the named command provider first, verify it directly, then switch `stt.provider` or `tts.provider`. Do not delete working providers. Preserve an easy fallback such as local/Edge STT/TTS.

### 5. Verify in three layers

**Adapter:**

```bash
python3 adapter.py --input fixture.wav --output transcript.txt
python3 adapter.py --input text.txt --output speech.wav
```

**Artifact:**

```bash
file speech.wav
stat -c '%s bytes' speech.wav
```

Require non-empty text and a plausible audio size/format.

**Closed loop:** synthesize a known sentence, transcribe the generated audio, and compare semantic content. This proves credentials, networking, serialization, media handling, and both adapters together.

Finally invoke Hermes's own TTS/STT surface if available; a direct adapter pass alone does not prove Hermes loaded the provider.

### 6. Apply configuration lifecycle

Config changes may require a new CLI process or gateway restart. Never restart the gateway from inside its own process; instruct the user to run `hermes gateway restart` from a separate shell, or use the product's safe restart path.

## Upgrade survival

Before a Hermes update:

- back up `config.yaml`, the actual env file, adapters, and current Git state;
- use `hermes update --backup`;
- after migration, confirm provider entries still exist;
- rerun the closed-loop voice test;
- run `hermes doctor` and verify gateway health.

Do not declare success from version output alone.

## Pitfalls

- Chat-compatible endpoint assumed to support speech routes.
- `AI initialized` or provider-object creation mistaken for a successful WebSocket/session connection.
- API key placed in command line or YAML.
- TTS returns JSON containing a temporary audio URL, but adapter writes the JSON as if it were audio.
- STT command returns JSON while Hermes expects plain text.
- Provider switched before adapter verification, destroying the known-good path.
- Gateway restart attempted from inside the gateway process.
- Upgrade verified without re-testing custom adapters.

## References

- `references/dashscope-qwen-speech.md` — validated Qwen TTS/ASR endpoint shapes, models, and tests.
