---
name: hermes-custom-provider-setup
description: Add an OpenAI-compatible custom provider (OpenRouter, Das...
version: 1
author: operator-agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, providers, custom-provider, openai-compatible, openrouter, alias]
---

# Hermes custom provider setup — verified procedure

> 完整描述：Add an OpenAI-compatible custom provider (OpenRouter, DashScope, vLLM, llama.cpp, internal proxy) to Hermes — alias + fallback chain, with the field-name quirks that the bundled skill misses.

Add a third-party / proxy / aggregator OpenAI-compatible endpoint to Hermes and make it selectable via alias and/or backup via fallback chain. Triggered by any of: "add my X key to Hermes", "register <platform> as a provider", "set OpenRouter / DashScope / proxy in Hermes", "give me a backup model", "translate this Codex provider into Hermes".

This skill **supersedes the bundled `hermes-provider-config` for actual wiring**. That bundled skill is field-name-wrong in several places; this one is what works on real Hermes builds. Cross-reference for context only.

## When to use

- Adding any non-built-in OpenAI-compatible endpoint: OpenRouter, DashScope, Together, Fireworks, vLLM, llama.cpp server, OpenCode Zen, internal corporate proxy, third-party aggregator (gptsapi / tu-zi / 302.ai), etc.
- Translating a Codex `config.toml` `[model_providers.X]` block into Hermes form
- Wiring a backup chain (primary dies → automatic cutover)

**Do not use** for built-in providers (`hermes auth add anthropic` / `hermes auth add openai` / etc.) — those have first-class auth flows.

## The four field-name traps (read these BEFORE editing config)

The bundled `hermes-provider-config` skill writes `model.aliases.<name>` and `api_key_env` in many places. **Both are wrong** on real Hermes builds (verified by reading `hermes_cli/model_switch.py` and `hermes_cli/runtime_provider_custom.py`).

| You write | Hermes actually reads | Effect of the mistake |
|---|---|---|
| `model.aliases.<name>: ...` | **`model_aliases.<name>: ...`** (top-level, plural) | alias silently never registered; `hermes chat -m <name>` → "alias not found" |
| `providers.<name>.api_key_env: X` | **`key_env`** (not `api_key_env`) | provider block lookup finds no key; falls through to host-gated env |
| alias `provider: custom` | expects a real provider name if you also registered a block | bypasses your `providers.<name>` block entirely, only uses host-gated env names |
| inline `api_key: sk-...` in yaml | works, but **the key ends up in the YAML file** — leak risk | secrets belong in `~/.hermes/.env` (mode 600) referenced by `key_env` |

**Always check `~/.hermes/hermes-agent/hermes_cli/model_switch.py` and `runtime_provider_custom.py`** before assuming a field name — these are the canonical sources and the bundled docs lag behind them.

## Core procedure

### 1. Verify the key + identify the real platform

Before touching config, **disambiguate which platform the key actually belongs to**. Many "千问 key" / "GLM key" / "DeepSeek key" given to you are actually OpenRouter aggregator keys. The way to tell: hit `/v1/models` with `Authorization: Bearer <key>` and see which host returns 200.

```bash
key="sk-..."   # the key you were given
for url in \
  https://openrouter.ai/api/v1/models \
  https://dashscope.aliyuncs.com/compatible-mode/v1/models \
  https://api.siliconflow.cn/v1/models \
  https://api.deepseek.com/v1/models; do
  code=$(curl -s -o /dev/null -w '%{http_code}' \
    -H "Authorization: Bearer $key" "$url")
  echo "$code  $url"
done
```

The first one that returns **200 with model data** is the real platform. Note: `/v1/models` is often public (no auth required); you cannot tell from `/v1/models` alone. Test `/v1/chat/completions` with a real POST to confirm 401 vs 200.

After identifying, get the **exact model ID string** from `/v1/models` output — aggregators use prefixed IDs:

```bash
curl -s https://<host>/v1/models -H "Authorization: Bearer $key" \
  | jq '.data[].id'
```

Common forms: `qwen/qwen3.8-max-0902` (not `qwen3.8-max`), `z-ai/glm-5.3` (not `glm-5.3`), `deepseek/deepseek-v4-pro`, `moonshotai/kimi-k3`, `stepfun/step-3.7-flash`.

### 2. Confirm the env var name Hermes will accept

Hermes's host-gated env lookup (in `_host_gated_env_key_candidates` of `runtime_provider.py`) only recognizes two names for OpenAI-compatible hosts:

```python
_getenv("OPENAI_API_KEY", "") if is_openai else "",
_getenv("OPENROUTER_API_KEY", "") if base_url_host_matches(base_url, "openrouter.ai") else "",
```

If you want your key read by the **direct-alias resolution path** (`provider: custom` with explicit base_url), it MUST be exported as `OPENAI_API_KEY` or `OPENROUTER_API_KEY` depending on the host. Custom names like `QWEN_HUB_API_KEY` are silently skipped, and the request goes out with no Authorization header → 401 "Missing Authentication header".

**Workarounds for non-standard key names:**
- Add a second env var with the same value under one of the recognized names: `OPENROUTER_API_KEY=sk-...` alongside `QWEN_HUB_API_KEY=sk-...`. The original-name callers (your other scripts) keep working; Hermes picks the recognized one.
- Or use the **named-provider-block** path (step 4 below) which reads `key_env` from your registered provider and bypasses the host-gated whitelist entirely.

### 3. Put the key in `~/.hermes/.env` (mode 600)

```bash
echo 'QWEN_HUB_API_KEY=sk-...YOURKEY...' >> ~/.hermes/.env
chmod 600 ~/.hermes/.env
```

Hermes loads `~/.hermes/.env` into subprocess env automatically on `hermes chat` / `hermes run`. Verify with:

```bash
bash -c 'source ~/.hermes/.env && echo "${KEY_NAME:-NOT_SET}"'
```

### 4. Register the provider in `providers:` AND alias in `model_aliases:` (use `save_config`, NEVER `hermes config set`)

`hermes config set` only does scalar coercion — it writes `fallback_providers` and aliases as **strings**, not lists/dicts (see P1 in the bundled skill). Always script the write via `save_config()`.

```python
import sys; sys.path.insert(0, '/home/kk/.hermes/hermes-agent')
from hermes_cli.config import load_config, save_config

cfg = load_config()

# (a) providers block — host-level config, takes `key_env`
cfg.setdefault('providers', {})
cfg['providers']['<name>'] = {
    'api_key_env': '<ENV_VAR>',           # kept for back-compat reads
    'key_env': '<ENV_VAR>',               # THIS is what runtime reads
    'base_url': 'https://<host>/v1',
    'model': '<vendor>/<model-id>',
    'api_mode': 'chat_completions',
    'name': '<Display Name>',
}

# (b) model_aliases — top-level plural, NOT model.aliases
cfg.setdefault('model_aliases', {})
cfg['model_aliases']['<alias-name>'] = {
    'provider': '<name>',                 # points at the providers block above
    'model': '<vendor>/<model-id>',
    'base_url': 'https://<host>/v1',
}

# (c) fallback_providers — top-level list
fb = cfg.get('fallback_providers', [])
fb.append({
    'provider': '<name>',                 # or 'custom' if no providers block
    'model': '<vendor>/<model-id>',
    'base_url': 'https://<host>/v1',
    'key_env': '<ENV_VAR>',
})
cfg['fallback_providers'] = fb

save_config(cfg)
```

Always back up first:

```bash
cp ~/.hermes/config.yaml ~/.hermes/config.yaml.bak-pre-<name>-$(date +%Y%m%d-%H%M%S)
```

`model.default` / `model.provider` stay untouched (P10 in the bundled skill — additive, never replacement, unless the user explicitly tested and asked).

### 5. Verify — and read logs when it fails

```bash
hermes chat -m <alias-name> -q "ping"
```

Three outcomes and what they mean:

| Output | Meaning |
|---|---|
| Real reply, no fallback warning | Wired correctly |
| `⚠️ Model fallback: <model> via custom unavailable (authentication failed)` | Authorization header not reaching the upstream. Check logs. |
| `⚠️ Model fallback: <model> via custom unavailable (model not found)` | Model ID wrong (often missing vendor prefix on aggregators). Hit `/v1/models` to confirm. |
| `alias not found` | alias registered under wrong key (`model.aliases` instead of `model_aliases`). |

**Always check `~/.hermes/logs/agent.log` when chat fails.** It logs the resolved base_url/model in clear text — much faster than rerunning chat:

```bash
grep -E "OpenAI client created.*<alias>" ~/.hermes/logs/agent.log | tail -3
grep -E "API call failed|AuthenticationError" ~/.hermes/logs/agent.log | tail -5
```

### 6. The named-provider-block vs direct-alias fork

There are two completely different code paths in Hermes for resolving a custom provider. Pick deliberately:

- **`provider: <name>` in alias** → resolves through `providers.<name>` block → uses `key_env` from that block → reads your custom env var name. Use this when your env var isn't on the host-gated whitelist.
- **`provider: custom` in alias** → resolves through `_resolve_direct_alias_runtime` → only reads `explicit_api_key` + host-gated env names (`OPENAI_API_KEY` / `OPENROUTER_API_KEY`). Use this only when your key is exported under one of those two names.

If you're unsure, the named-provider-block path is more robust.

## Pitfalls

### P1: Field name `model.aliases` vs `model_aliases`

`model.aliases.<name>` is silently ignored. The actual key is `model_aliases.<name>` at the top level. Reading `hermes_cli/model_switch.py::_load_direct_aliases` line 218 confirms this — only `cfg.get("model_aliases")` is read.

### P2: Field name `api_key_env` vs `key_env`

Both are accepted in some code paths, but `runtime_provider_custom.py::_resolve_named_custom_runtime` line 496 specifically reads `custom_provider.get("key_env")`. Writing only `api_key_env` → key never resolved via the named-provider path.

### P3: Host-gated env whitelist

Only `OPENAI_API_KEY` and `OPENROUTER_API_KEY` are checked by `_host_gated_env_key_candidates`. Custom names are silently skipped. With `provider: custom` alias, this is the only path the request takes — your key MUST be under one of those two names, OR you must use the named-provider-block path with `key_env`.

### P4: 401 "Missing Authentication header" vs "Invalid key"

`Missing Authentication header` from upstream means Hermes sent no Authorization header at all (key resolved to empty string). `Invalid API key` / `Incorrect API key provided` means a header was sent but the key is wrong/expired. The first → check env var name and provider block wiring. The second → re-verify the key against the upstream directly with curl.

### P5: Aggregator model IDs are vendor-prefixed

`/v1/models` returns IDs like `qwen/qwen3.8-max-0902`, `z-ai/glm-5.3`, `moonshotai/kimi-k3`, `stepfun/step-3.7-flash`. The prefix is required. A bare `qwen3.8-max` or `glm-5.3` returns model-not-found on OpenRouter-style aggregators.

### P6: `/v1/models` may be public

Many OpenAI-compatible endpoints expose `/v1/models` without auth (so the catalog is browsable). A 200 from `/v1/models` does NOT mean your key works. Always verify with a real `POST /v1/chat/completions` before trusting the wiring.

### P7: Don't use `hermes config set` for nested dicts/lists

It coerces everything to scalar strings. Use `save_config()` from `hermes_cli.config` instead — this is the only reliable scripted path (the bundled skill documents this in P1; the trap applies equally to `model_aliases`, `providers`, and `fallback_providers`).

### P8: When guessing the platform, check `/v1/models` AND `/v1/chat/completions`

A 200 from `/v1/models` only proves the host is up and serves models publicly. The 401 from `/v1/chat/completions` is the real test of whether your key belongs there. Hit multiple candidate hosts and use the one where both return 200.

### P9: Always read `~/.hermes/logs/agent.log` when chat returns a fallback warning

It contains the exact base_url/model the client was built with, the failure type (401/404/etc.), and which fallback was activated. Iterating blind via `hermes chat` is 10× slower than grepping the log.