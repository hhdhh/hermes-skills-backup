# Sub2API Responses authentication pattern

## Sanitized symptom

Codex returned:

```text
unexpected status 401 Unauthorized
{"code":"API_KEY_REQUIRED","message":"API key is required in Authorization header (Bearer scheme), x-api-key header, or x goog-api-key header"}
url: https://<relay-host>/responses
```

Two independent clues were present:

1. The request URL ended in `/responses` instead of the known-good `/v1/responses` route.
2. `API_KEY_REQUIRED` said no accepted authentication header was present, rather than saying a supplied key was invalid.

## Faulty configuration shape

```toml
[model_providers.OpenAI]
base_url = "https://<relay-host>"
wire_api = "responses"
requires_openai_auth = false
```

The credential already existed in `~/.codex/auth.json` and matched the intended relay key, but Codex was instructed not to use OpenAI-style authentication.

## Corrected shape

```toml
[model_providers.OpenAI]
base_url = "https://<relay-host>/v1"
wire_api = "responses"
requires_openai_auth = true
```

No key rotation or duplication was required.

## Credential comparison without disclosure

Compare presence, lengths, and digests inside a short script. Output only booleans and lengths. Never print either value.

```python
import hashlib
import json
import os
from pathlib import Path

stored = json.loads((Path.home() / ".codex/auth.json").read_text()).get("OPENAI_API_KEY", "")
intended = os.environ.get("PROVIDER_API_KEY", "")
print("stored_present", bool(stored))
print("intended_present", bool(intended))
print("same_secret", bool(stored and intended and hashlib.sha256(stored.encode()).digest() == hashlib.sha256(intended.encode()).digest()))
```

## Acceptance test

A real ephemeral Codex request returned the exact sentinel and exit code 0:

```text
provider: OpenAI
model: <configured model>
CODEX_AUTH_OK
```

This was stronger evidence than `codex doctor`; its route probe still displayed an HTTP 401 even though the actual authenticated Responses request succeeded. Use `doctor` to inspect effective state, not as the sole pass/fail gate.

## General lesson

When an OpenAI-compatible relay works in one client but Codex reports `API_KEY_REQUIRED`, verify routing and auth injection separately:

- Routing: Does `base_url` produce the documented final Responses URL?
- Injection: Is Codex configured to load and send its stored API key?
- Credential: Does the stored key match the intended key without exposing it?
- Proof: Does a fresh minimal `codex exec` call succeed?
