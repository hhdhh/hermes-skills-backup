---
name: llm-provider-key-probe
description: Use when the user gives you an API key and asks 'is this...
version: 1
author: openclaw-curator
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [llm, api-key, probe, verification, openai-compatible, pre-flight, zhipu, openai, anthropic]
---

# LLM provider key probe

> 完整描述：Pre-flight probe for any LLM provider API key — verify availability, list models, distinguish rate-limit from quota/auth errors before wiring the key into a config. Use when the user gives you an API key and asks 'is this usable / does it work / can I call X model / 测试一下这个 key' or before configuring a new provider in Hermes/Codex/Claude Code/any OpenAI-compatible client.

Pre-flight verification for any LLM provider API key, before wiring it into a client. One key in, one diagnostic out: "usable for which models, blocked on which error class, what the next action is."

## When to use

Trigger on any of: "test this API key", "is this key usable", "verify the key works", "test key for X model", "ping the LLM", "测一下这个 key", "key 可用吗", "调通了吗". Also trigger **proactively before** `hermes-provider-config` step 3 (adding an alias) when the user hands you a fresh key — never wire a key without proving it can answer a real call.

**Do not use** for client-side config (alias, fallback chain, env wiring) — that's `devops/hermes-provider-config`. **Do not use** for Codex/Claude-Code specific auth debugging — those are `codex-custom-provider-troubleshooting` and `claude-api`. This skill ends at the moment the diagnostic verdict is delivered; the client-side work is downstream.

## Core workflow

Three phases, in order. Each is independent — if phase 1 fails, fix that before phase 2.

### Phase 1: list models (lowest-cost probe, no quota burn)

The `/v1/models` endpoint (or provider equivalent) returns the catalog the key can see. If it returns 200, the key is **authenticated** — that alone rules out 401/403. The returned IDs also tell you which model names to use in phase 2.

```bash
# OpenAI-compatible default
curl -s "$BASE_URL/models" -H "Authorization: Bearer $KEY" | jq '.data[].id'

# Anthropic (no /models endpoint, use account console or just skip to phase 2)
# Gemini:  https://generativelanguage.googleapis.com/v1beta/models?key=$KEY
```

Always include `-w "\nHTTP:%{http_code}\n"` on curl to capture the status code alongside the body — providers return error info in the body, not the status code alone.

### Phase 2: real call against the cheapest available model

A `/models` 200 doesn't mean the key can **invoke** the listed models — many providers gate the catalog on auth but charge per-call quota separately, and quota exhaustion returns the same 429 the user might mistake for "key invalid". So you need **one real call** to the cheapest model:

```bash
curl -s -X POST "$BASE_URL/chat/completions" \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"'"$CHEAP_MODEL_ID"'","messages":[{"role":"user","content":"ping"}],"max_tokens":5}' \
  -w "\nHTTP:%{http_code}\n"
```

Pick the cheapest model from phase 1. `max_tokens: 5` so the response truncates fast and you pay ~10 tokens instead of 100. If you don't know the cheapest, common safe defaults by provider:

| Provider | Cheapest always-available model |
|---|---|
| OpenAI | `gpt-4o-mini` |
| Anthropic | `claude-3-5-haiku-latest` |
| Zhipu (智谱) | `glm-4-flash` |
| DeepSeek | `deepseek-chat` |
| Gemini | `gemini-1.5-flash` |
| Qwen | `qwen-turbo` |

### Phase 3: classify the error (when phase 1 or 2 fails)

The shape of the error tells you **which class** of failure it is, and that determines the next action. The three error classes are:

| HTTP | Common meaning | What to tell the user |
|---|---|---|
| `401 Unauthorized` / `403 Forbidden` | Key invalid, expired, or wrong header | "Key rejected by provider — paste the exact value again or check expiry" |
| `429 Too Many Requests` with `code` indicating **quota** (e.g. Zhipu `1113`, OpenAI `insufficient_quota`) | Account-level: balance zero OR subscription doesn't include this model | "Key works, but the model isn't covered by your plan / balance is empty. Check the provider's billing page or pick a model the subscription includes" |
| `429 Too Many Requests` with `code` indicating **rate limit** (e.g. OpenAI `rate_limit_exceeded`, Anthropic overloaded) | Provider throttling — sleep and retry, **not** a billing issue | "Provider is rate-limiting — wait a few seconds and try one model at a time, not in a loop" |
| `404 Not Found` | Wrong base URL OR model ID doesn't exist on this provider | "Base URL or model ID is wrong — check `$BASE_URL/models` for valid IDs" |
| `5xx` | Provider outage | "Provider-side issue, retry later" |

**Critical distinction**: 429 with a `quota`-family code (1113, `insufficient_quota`, `quota_exceeded`) **does not recover with sleep**. 429 with a `rate_limit`-family code **does**. The two look identical on the wire — read the body. Zhipu returns `{"error":{"code":"1113","message":"余额不足..."}}`; OpenAI returns `{"error":{"code":"insufficient_quota","message":"..."}}`. Always echo the body to the user, not just the status.

**Rate-limit cross-test**: when the user reports a 429 and you suspect quota, run **one** request after `sleep 8`. If it returns 200, it was rate-limit, not quota. If it still 429s, it's quota.

### Phase 4: report the verdict

A complete diagnostic in this exact shape, so the user can act without a follow-up question:

```
Key:           <provider name>
Authentication: ✅ (or ❌ 401/403)
Model <X>:     ✅ HTTP 200, N tokens used
               or ❌ HTTP 429 / code 1113 / "余额不足"
Models available: <paste the /models list, or a summary>
Recommendation: <next concrete step>
```

Don't just report "key works" — report **which models** it works for. A key that hits `glm-4-flash` but not `glm-5.3` is half-working; the user needs to know.

## Pitfalls

### P1: Conflating rate-limit (429) with quota exhaustion (429)

Many providers — Zhipu, OpenAI, Anthropic — return HTTP 429 for **both** "you called too fast" (transient) and "your account is empty" (permanent). The body's `code` field is the only differentiator. **Always read the body**, not just the status. Then use the rate-limit cross-test (sleep 8 + retry) to confirm — a transient 429 recovers, a quota 429 does not.

### P2: For-loop model probes trigger rate-limits and produce false negatives

If you naively loop `for m in glm-4.7 glm-5 glm-5.1 glm-5.2 glm-5.3; do curl ... -d "{\"model\":\"$m\"...}"; done`, you'll burn through the provider's per-second request budget and **every subsequent call returns 429**, even on models the key is fully entitled to. After this happens, you can't tell a real "this model isn't on your plan" from a "you got rate-limited because of your own probe loop".

**Always add `sleep 6` (or more) between model probes** in any loop, or better — do **one probe at a time** and stop as soon as you have what you need. The cheapest working model is enough to certify the key.

### P3: A 200 on `/v1/models` doesn't prove call quota

Phase 1 success means the key is **authenticated**. It does **not** mean the account has call quota. Phase 2 (real call) is required to confirm usable quota. Don't tell the user "key works" after phase 1 alone.

### P4: The cheapest-model fallback is the safest probe target

Don't probe with the most expensive model on the plan. If the user says "test if my key can call X" and X is a flagship model, first try the cheapest always-on model in the same family — `gpt-4o-mini` for OpenAI, `glm-4-flash` for Zhipu, `claude-3-5-haiku-latest` for Anthropic. If the cheap one works, the key is valid; then try the flagship separately.

### P5: Don't print the raw key in output, even when verifying

Use `$KEY` in the curl command and let the shell substitute. If the user pasted the key in the conversation, do not echo it back in the report — refer to it as "the key you provided" or "sk-...4e7" (last 4 chars only). The skill's job is to test the key, not to log it.

### P6: Provider-specific quirks live in references, not here

This SKILL.md covers the **generic** probe workflow. Provider-specific endpoint shapes, error code dictionaries, model catalog patterns, and rate-limit policies live in `references/<provider>.md`. The generic workflow is provider-agnostic; the references are not.

## References

- `references/zhipu-api-quirks.md` — Zhipu (智谱清言) specific: `/api/paas/v4/...` paths, `code 1113 = 余额不足/资源包不含`, catalog endpoint, `glm-5.3` family
- `references/openai-api-quirks.md` — OpenAI: `insufficient_quota` vs `rate_limit_exceeded`, organization-required headers, project keys vs user keys
- `references/anthropic-api-quirks.md` — Anthropic: no `/v1/models`, `x-api-key` header, version pinning required
- `references/probe-template.sh` — copy-paste bash template combining all 3 phases with auto-classification
