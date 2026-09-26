# Remote TTS/model diagnostics

## Case pattern

A ROS vision service successfully initialized cameras, microphones, speaker, WebSocket registration, and ROS, but produced no speech. The journal showed:

```text
Failed to initialize TTS model: PytorchStreamReader failed reading zip archive: failed finding central directory
RuntimeError: PytorchStreamReader failed reading zip archive: failed finding central directory
```

The installed Kokoro extension used a default local directory of `Documents/kokoro`. For service user `ubuntu`, the effective location was `/home/ubuntu/Documents/kokoro`, not `/home/ubuntu/.kokoro`.

The model at that location was 2,883,584 bytes and had a PyTorch ZIP header, but was truncated. A Hugging Face cache contained a same-model blob of about 327,247,856 bytes. The decisive test is successful `torch.load(..., weights_only=True)` or successful model construction; a valid-looking header is not enough.

## Reusable probes

```bash
find "$HOME/Documents/kokoro" -maxdepth 2 -type f -printf '%p %s bytes\n' | sort
stat -c '%n %s bytes' "$HOME/Documents/kokoro/kokoro-v1_1-zh.pth"
xxd -l 32 "$HOME/Documents/kokoro/kokoro-v1_1-zh.pth"
/home/USER/miniconda3/envs/robot_env/bin/python - <<'PY'
import torch
p='/home/USER/Documents/kokoro/kokoro-v1_1-zh.pth'
obj=torch.load(p, map_location='cpu', weights_only=True)
print(type(obj).__name__, len(obj))
PY
```

Replace `USER` and paths with values discovered from the unit/traceback. Do not print credentials while collecting service environment.

## Separate errors

- `OpenAI API key not found` disables the AI chatbot path; it does not explain a corrupted Kokoro archive.
- ROS `publisher's context is invalid` during cleanup after `stop`/`SIGTERM` is teardown noise unless it also appears during normal active operation.
- Conda plugin/pydantic warnings and missing `zstandard` support do not establish whether the TTS model is valid.
