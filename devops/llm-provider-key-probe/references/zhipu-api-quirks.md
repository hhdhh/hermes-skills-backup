# Zhipu (智谱清言) — API quirks

Verified against `https://open.bigmodel.cn` (the public BigModel endpoint, not private deployments).

## Endpoints

| Purpose | Path | Notes |
|---|---|---|
| Chat completions | `POST /api/paas/v4/chat/completions` | **No `/v1/` prefix** — this is the official endpoint, not OpenAI-compatible despite the OpenAI-shaped body |
| List models | `GET /api/paas/v4/models` | Returns all models the key can see; auth-gated, no quota check |
| Embeddings | `POST /api/paas/v4/embeddings` | Same auth as chat |
| Image gen | `POST /api/paas/v4/images/generations` | Same auth |
| Audio (TTS/ASR) | `/api/paas/v4/audio/...` | Same auth |

**Gotcha**: If you use `https://open.bigmodel.cn/api/paas/v4/...` (no `/v1`) it works. If you add `/v1` you get 404. This trips up people who assume Zhipu is OpenAI-compatible — it uses the same JSON shape but a different path scheme.

## Auth

Header: `Authorization: Bearer <key>`

No special header for organization/project — the key alone is the credential. There is no "organization required" header like OpenAI's.

## Error code dictionary

| `error.code` | Meaning | Recoverable? |
|---|---|---|
| `1001` / `1002` | Auth failure (key invalid/expired) | No — user must reissue |
| `1113` | **余额不足或无可用资源包** — balance zero OR subscription doesn't include this specific model | No — recharge or pick a different model |
| `1214` / similar | Parameter validation | Maybe — fix the request |
| `1301` / `1302` | System / rate-limit | **Yes** — sleep 6-10s and retry |
| `429` (no body code) | Generic rate limit | Yes — sleep and retry |

The `1113` error is the **most important one to recognize** — Zhipu returns it for both "your whole account is empty" AND "your balance is fine but you don't have the `glm-5.x` resource pack" (resource packs in Zhipu are per-model-tier). So the user can be paying for `glm-4-flash` happily and still get 1113 on `glm-5.3` because the 5.x resource pack is sold separately.

## Rate limits

Zhipu applies per-second request limits that **trigger on burst**. Looping 5+ requests in rapid succession against the same key will start returning 429 even on models the key can fully use. Add `sleep 6` between probes. The first request after a long pause (8+ seconds) reliably succeeds.

## Model families (as of 2026-01)

Listed via `GET /api/paas/v4/models` with a valid key:

- **glm-4-flash** — cheapest, always available, default probe target
- **glm-4.5** / **glm-4.5-air** / **glm-4.6** / **glm-4.7** — 4.x mainline
- **glm-5** / **glm-5-turbo** / **glm-5.1** / **glm-5.2** — 5.x mid-tier
- **glm-5.3** / **glm-5.3-flash** — 5.x flagship (often sold as separate resource pack)
- **embedding-2** / **embedding-3** — embeddings

**Probing strategy**: list via `/models` first, then test `glm-4-flash` as the smoke test, then test the specific model the user asked about (with `sleep 6` between).

## Worked example — full probe transcript

```bash
KEY="28cd0af0f78242f792f33b88898a44e7.CWR5ySOTUGRDfqNg"
BASE="https://open.bigmodel.cn/api/paas/v4"

# Phase 1: list models
curl -s "$BASE/models" -H "Authorization: Bearer $KEY" | jq -r '.data[].id'
# → 10 model IDs returned → ✅ authenticated

# Phase 2: cheapest call
curl -s -X POST "$BASE/chat/completions" \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"glm-4-flash","messages":[{"role":"user","content":"ping"}],"max_tokens":5}'
# → HTTP 200, 11 tokens used → ✅ quota + model valid

# Phase 3: the model the user actually wants
curl -s -X POST "$BASE/chat/completions" \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"glm-5.3","messages":[{"role":"user","content":"ping"}],"max_tokens":5}'
# → HTTP 429 / code 1113 / 余额不足 → ❌ this model not on user's resource pack
```

Verdict to the user: "Key valid, `glm-4-flash` works, but `glm-5.3` returns 1113 — your account either has no 5.x resource pack or no balance for it. Check the BigModel console."
