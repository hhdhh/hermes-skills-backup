---
name: codex-custom-provider-troubleshooting
description: Diagnose and repair Codex CLI/Desktop custom OpenAI-compatible provider failures, especially 401/403 authentication errors, wrong Responses API paths, missing Bearer headers, and config/auth drift. Use when Codex reports API_KEY_REQUIRED, Unauthorized, requests /responses instead of /v1/responses, or a custom provider works elsewhere but not in Codex.
version: 1.1.0
---

# Codex Custom Provider Troubleshooting

Use this class-level workflow for Codex CLI/Desktop connections to OpenAI-compatible gateways, relays, and custom Responses API providers.

## Safety rules

- Never print, paste, or diff raw API keys.
- Before editing `~/.codex/config.toml` or `~/.codex/auth.json`, create a timestamped mode-600 backup.
- Do not replace a credential until you have established that it is wrong. Compare length and SHA-256 digests in-process instead of displaying secrets.
- Prefer the smallest config correction. Do not restart Hermes or unrelated gateways for a Codex-only client configuration error.

## Diagnostic loop

### 1. Capture the exact failing URL and response

The URL often identifies the routing defect immediately:

- `https://host/responses` usually means the provider `base_url` is missing `/v1`.
- `https://host/v1/responses` with `API_KEY_REQUIRED` usually means no accepted authentication header was sent.
- A 401 that says the key is invalid means a header was sent but its value is rejected; do not confuse this with a missing-header error.

Preserve the response code/message and request ID, but never credentials.

### 2. Inspect the effective Codex provider configuration

Read `~/.codex/config.toml` and identify:

- top-level `model_provider`
- active `[model_providers.<name>]`
- `base_url`
- `wire_api`
- `requires_openai_auth`
- `env_key` (when set, Codex reads the key from this environment variable and ignores `auth.json`)
- optional static/env HTTP headers

For an OpenAI-compatible Responses endpoint, the common shape is:

```toml
model_provider = "relay"
model = "provider-model-id"

[model_providers.relay]
name = "Relay"
base_url = "https://relay.example.com/v1"
wire_api = "responses"
requires_openai_auth = true
```

Do not assume every provider needs `/v1`; verify against a known-good client configuration or provider documentation. The key invariant is that Codex appends the Responses path to `base_url`.

### 3. Verify credential availability without disclosure

Check:

- `codex login status`
- whether `~/.codex/auth.json` contains `OPENAI_API_KEY`
- whether the intended environment variable is present
- whether stored and intended credentials match by digest, not by printing values

Important: a custom provider can use a non-OpenAI key, but Codex's `requires_openai_auth = true` tells Codex to load its stored API-key credential and send it as `Authorization: Bearer …`. The field name describes Codex's authentication mechanism, not the company that issued the key.

### 4. Rank hypotheses before editing

Typical ranking for `API_KEY_REQUIRED`:

1. `requires_openai_auth = false`, so Codex omits Bearer auth.
2. `base_url` misses the provider API prefix, often `/v1`.
3. Codex's stored key differs from the intended provider key.
4. A profile overlay or `CODEX_HOME` points at another config/auth file.
5. The gateway expects `x-api-key` rather than Bearer auth.
6. The block sets `env_key`, so Codex demands that environment variable and ignores `auth.json` entirely — the signature of a distributed team config: the shipped `auth.json` does nothing until the block drops `env_key` and sets `requires_openai_auth = true`.

Test predictions one variable at a time where possible. If both the URL and error body independently prove two defects, fix both together and document why.

## Repair procedure

1. Back up the active config.
2. Correct the provider URL to the verified API root.
3. Enable `requires_openai_auth = true` when the gateway accepts Bearer authentication.
4. Keep unrelated headers and provider options unchanged.
5. Parse/lint TOML after editing.
6. Run `codex login status` and `codex doctor` as diagnostics.
7. Perform a real ephemeral `codex exec` request; this is the acceptance test.

## Verification standard

A configuration parse and `codex doctor` are not sufficient. Run a minimal, deterministic model call such as:

```bash
codex exec --ephemeral --skip-git-repo-check --ignore-rules \
  --disable hooks --disable goals --disable memories \
  -s read-only -C /tmp -m <model> \
  '只回复：CODEX_AUTH_OK'
```

Success requires all of the following:

- exit code 0
- expected provider/model shown in startup output
- exact sentinel response received
- original 401 no longer appears

`codex doctor` route probes may still be less authoritative than the real request because probes can target a different endpoint or authentication path. Treat the actual `codex exec` model call as the decisive result.

## Desktop/session behavior

`config.toml` is read by newly started requests. If a long-lived Codex Desktop process or an existing conversation retains stale provider state, open a new conversation or reopen the Codex window. Do not restart unrelated services unless a fresh CLI request also fails.

## Rollback

If the real request regresses, restore the timestamped backup and re-run the same deterministic probe. Never leave a partially edited provider block.

## Pitfalls

- Before diagnosing auth, check WHICH codex binary runs: an npm-global `@openai/codex` shadows the apt-installed `/usr/bin/codex` because `~/.npm-global/bin` precedes `/usr/bin` in PATH. `which -a codex` first; `npm uninstall -g @openai/codex` to let apt's version take over (config in `~/.codex/` is untouched).
- Gateway control-plane vs data-plane: if `GET {base_url}/models` returns 200 with a valid key but every completion/images POST returns 503, the gateway is alive and auth is correct — the inference backend is down. Do not edit local config for this.
- 429 body `group requests-per-minute limit exceeded` (type `rate_limit_exceeded`, with `retry-after`) means a shared group quota is exhausted by other consumers — server-side, not your config. Check the body text; a bare status code cannot distinguish this from a bad-key rejection.
- One relay, multiple key groups: `GET /v1/models` lists only THAT key's group. A 404 `Model ... is not supported by any configured account in this group` means the key is valid but the model belongs to another group — swap key or model, do not touch base_url/auth flags. Verify a candidate key's group with a 2-token `/v1/messages` or `/v1/responses` curl before editing any client config.
- Claude Code on an Anthropic-wire relay: `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` alone is not enough — without `ANTHROPIC_MODEL` it requests `claude-sonnet-*` and gets 404 model_not_found on non-Claude relays. Map `ANTHROPIC_MODEL` + `ANTHROPIC_SMALL_FAST_MODEL` (e.g. glm-5.3 / glm-5.3-flash) and verify with `claude -p 'sentinel' --model <m>`; a cosmetic `unrecognized_model` warning about context windows does not block the call.
- Setting a key in the shell while `requires_openai_auth = false` does not guarantee Codex sends it.
- A valid key cannot fix a malformed API root.
- A correct `/v1` path cannot fix a missing Authorization header.
- Do not infer success from HTTP reachability alone.
- `warning: Model metadata for <model> not found. Defaulting to fallback metadata` for a non-OpenAI model (e.g. glm-5.3) via a custom provider is benign; treat the real `codex exec` response as the verdict, not this warning.
- Do not expose credentials in terminal output, patches, reports, or support files.

## References

- `references/sub2api-responses-auth.md` — sanitized reproduction and repair pattern for a Responses-compatible relay requiring Bearer authentication.
