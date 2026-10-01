---
name: sub2api-proxy-wiring
description: Wire Claude Code / Codex / Hermes onto a sub2api LLM gate...
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [sub2api, llm-gateway, claude-code, codex, provider-config, api-key]
    related_skills: [hermes-provider-config]
---

# sub2api proxy wiring

> 完整描述：Wire Claude Code / Codex / Hermes onto a sub2api LLM gateway; verify by group.

Connect CLI coding agents (Claude Code, Codex) to a **sub2api** self-hosted multi-protocol LLM gateway. sub2api routes by **key group**, not by model string — most configuration failures that look like auth errors are actually group mismatches. This skill covers the verification ladder that avoids them.

## When to Use

- User provides a sub2api (or similar multi-protocol gateway) URL + an API key and asks to "configure Claude Code / Codex with this"
- A configured agent reports `401 INVALID_API_KEY` or `model not supported by any configured account in this group`
- Translating a teammate's agent config snippet to this machine — the snippet's model may belong to a different key group
- Any task mixing `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN` env config with a non-Anthropic upstream (GLM, MiniMax, ...)

Don't use for direct Anthropic/OpenAI official endpoints, or for Hermes' own provider config (see `hermes-provider-config` — the Hermes-specific aliases/fallback pitfalls live there).

## Core workflow

### 1. Enumerate the key's group models BEFORE writing any config

A key from the GLM group gets `model_not_found` for any Claude/GPT model even though the gateway globally serves them. Ten seconds here prevents a wrong-model config:
```bash
curl -s https://<host>/v1/models \
  -H "Authorization: Bearer $KEY" | python3 -c "import json,sys; print([m['id'] for m in json.load(sys.stdin)['data']])"
```
Pick the newest model **from this list**. If the user's snippet names a model absent here, their key is from a different group — ask for the right key or use a model from the list.

### 2. Prove the protocol path with a 10-token ping

`/v1/messages` speaks Anthropic wire format even for non-Anthropic models (the gateway translates). Verify before touching agent config:
```bash
curl -s https://<host>/v1/messages \
  -H "x-api-key: $KEY" -H "anthropic-version: 2023-06-01" \
  -H 'content-type: application/json' \
  -d '{"model":"<id-from-step-1>","max_tokens":20,"messages":[{"role":"user","content":"ping"}]}'
```
A response containing `"content":[...]` proves key + model + protocol end-to-end. `model_not_found` → back to step 1 (group mismatch, not an auth problem).

### 3. Write the agent config

**Claude Code** — `~/.claude/settings.json` (chmod 600 — holds the token). No `/v1` suffix in the base URL (the client appends the path); set `model` to the gateway id from step 1:
```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "env": {
    "ANTHROPIC_BASE_URL": "https://<host>",
    "ANTHROPIC_AUTH_TOKEN": "sk-...",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"
  },
  "model": "<id-from-step-1>"
}
```
Back up any existing settings.json first — it may carry unrelated user preferences (theme, attribution header) worth consciously preserving or dropping, not silently overwriting.

**Codex** — `~/.codex/config.toml` with `base_url = "https://<host>"`, `wire_api = "responses"`; key in `~/.codex/auth.json` as `{"OPENAI_API_KEY": "sk-..."}` (chmod 600).

**Hermes** — same pattern via `model.aliases.<name>` with `base_url: https://<host>/v1` (Hermes DOES want the `/v1`); see `hermes-provider-config`.

### 4. Verify the running agent, not just the files

Launch the CLI, confirm the model line shows the gateway id, and run one real prompt. A session that starts but 401s on first message means step 1/2 were skipped — re-run the smoke ladder before debugging the agent.

## Pitfalls

### P1: group mismatch masquerades as auth failure
`401 INVALID_API_KEY` or `"not supported by any configured account in this group"` with a key that passes `GET /v1/models` means the **model id** is outside the key's group — not that the key is wrong. Fix the model, not the key.

### P2: base URL suffix differs per client
Claude Code: NO `/v1`. Hermes aliases: WITH `/v1`. Codex: no `/v1` (paths are per-provider). When a config translated between clients fails, check the suffix first.

### P3: shadowed binaries lie about version
An npm-installed CLI (e.g. `codex` in `~/.npm-global/bin`) shadows the apt one (`/usr/bin`) on PATH and reports a different version than `dpkg -s` claims. When behavior doesn't match the installed package, run `type -a <cli>` and test each binary by absolute path. Keep exactly one install per CLI.

### P4: codex 0.157 已废弃的顶层键与 env_key 提供方
`disable_response_storage` 和 `network_access` 在 codex 0.157+ 被忽略并报 unrecognized setting 警告——直接删掉，不要照抄旧配置。用 `env_key = "SUB2API_API_KEY"` + `requires_openai_auth = false` 的提供方时，密钥从环境变量读，必须导出（写进 ~/.bashrc），auth.json 可同步留一份作 fallback。`model_catalog_json` 指向的文件必须真实存在，否则自定义模型不生效；目录文件可仿照 ~/.codex/models.json 的字段（slug/context_window/supported_reasoning_levels 等）手写。冒烟命令：`codex exec --skip-git-repo-check "1+1"`，确认输出头 provider/model 行正确且无 warning。

### P5: token-bearing config files need 0600 and no backup copies in synced dirs
`settings.json` / `auth.json` hold live keys: chmod 600, keep backups outside any synced/git directory, and never paste the token into chat logs or reports.
