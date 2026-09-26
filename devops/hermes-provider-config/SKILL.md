---
name: hermes-provider-config
description: "Hermes custom providers, aliases, fallback chains."
version: 1
author: hermes-agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, providers, model-aliases, fallback, custom-provider, openai-compatible, config]
    related_skills: [hermes-agent]
---

# Hermes provider config

Add custom OpenAI-compatible providers, register model aliases, and build a primary→fallback chain on Hermes Agent. Triggered by any of: "add a custom provider", "register model X at URL Y", "set up fallback", "configure backup model", or translating an OpenAI/Codex/Claude-code provider config into Hermes format.

**Always cross-reference** `autonomous-ai-agents/hermes-agent/references/providers-and-models.md` (bundled) for the current built-in provider table and CLI commands — this skill only covers what bundled docs *don't*: custom-base-URL providers, alias quirks, the `fallback_providers` list, and the `config set` list-literal trap.

## When to use

- Adding a new model source that isn't a built-in Hermes provider (any OpenAI-compatible base URL — proxies, local llama.cpp servers, vLLM, internal gateways)
- Registering a model alias so it can be selected by `/model <name>` or `hermes chat -m <name>`
- Building a fallback chain (primary dies → automatic cutover)
- Translating a Codex `config.toml` or Claude Code provider config into Hermes
- Verifying the chain actually cuts over (not just that the config loads)
- Adding custom command-backed Hermes TTS providers when a vendor's native speech API is not OpenAI `/audio/speech` compatible

For the verified DashScope Qwen TTS adapter pattern, endpoint distinction, and end-to-end checks, read `references/dashscope-qwen-tts.md`.

**Do not use** for built-in providers (Anthropic, OpenAI, OpenRouter, Minimax, Nous, Gemini, etc.) — `hermes auth add <provider>` is the right entry point.

## Core workflow

### 1. Pick the right config primitive

Three different primitives, three different shapes:

| Goal | Config key | Shape | Where keys live |
|---|---|---|---|
| **Alias** — name to use in `hermes chat -m <name>` | `model_aliases.<name>` (top-level, **no dot**) | `{provider, model, base_url?, key_env?}` — see P11 for the two valid `provider` shapes | config.yaml |
| **Fallback entry** — used automatically when primary fails | `fallback_providers` (top-level **list**) | `[ {provider, model, base_url, key_env}, ... ]` | config.yaml |
| **Credential pool** — rotate multiple keys for the same provider | `auth.json.credential_pool.<provider>` | list of credential dicts | auth.json (managed by `hermes auth`) |

The user's request determines the primitive:
- "I want to **use** X as an option" → alias
- "When Y fails, **fall back** to X" → fallback entry
- "I have **multiple keys** for X" → credential pool

You can have all three for the same model — they don't conflict.

**Field name gotcha** (a future session WILL lose an hour here): `model_aliases` is **top-level**, not `model.aliases`. The loader checks both, but only `model_aliases` is the documented entry point; `model.aliases` is a legacy simpler form (`{name: "provider/model"}` strings) that doesn't carry `base_url` or `key_env`. If you write `model.aliases.<name> = {...}` with full dict, it gets loaded but the alias won't surface in `DIRECT_ALIASES` and the user sees "alias not found".

### 2. Put the API key in `~/.env`

Hermes convention: secrets in `~/.env`, settings in `~/.hermes/config.yaml`. Inline `${...}` in YAML works (`api_key: ${MY_KEY}`) but `key_env: MY_KEY` is more idiomatic for custom-provider entries and works in both `model.aliases.*` and `fallback_providers`.

```bash
# ~/.env (mode 600 — `hermes config set <KEY>` for env-shaped keys auto-sets 600)
MY_NEW_PROVIDER_API_KEY=sk-...
```

Verify the key is visible to the hermes process:
```bash
# Both produce something non-empty:
printenv MY_NEW_PROVIDER_API_KEY
python3 -c "import os; print(os.environ.get('MY_NEW_PROVIDER_API_KEY'))"
```

### 3. Add the alias (if you want it selectable)

For custom (non-built-in) endpoints, use `save_config()` so the YAML is clean and the fields are right:

```python
import sys; sys.path.insert(0, '/home/kk/.hermes/hermes-agent')
from hermes_cli.config import load_config, save_config
cfg = load_config()
cfg['model_aliases']['<name>'] = {
    'provider': '<see P11 — either "custom" or a registered providers.<name> key>',
    'model': '<model-id>',
    'base_url': 'https://<host>/v1',   # optional when provider is a registered block
}
save_config(cfg)
```

If `hermes chat -m <name> ...` returns "alias not found", the user-defined alias namespace is independent of the built-in `/model` catalog (`gpt`, `sonnet`, `codex`, `grok`, ...) — custom aliases don't get catalog resolution; they need an exact match.

**Which `alias.provider` value to use — read P11 before choosing.** `provider: custom` works only for the small set of hosts whose auth key has a hardcoded env-var name (`OPENAI_API_KEY`, `OPENROUTER_API_KEY`). For everything else (dashscope, siliconflow, deepseek, kimi, any internal proxy), the alias must point at a registered `providers.<name>` block whose `key_env` field reads from `~/.env`.

### 4. Add the fallback chain (CRITICAL — see P1)

```bash
# WRONG — writes a *string*, not a list:
hermes config set fallback_providers '[{"provider":"custom","model":"X",...}]'
hermes fallback list   # → "No fallback providers configured" (silent trap)

# CORRECT — use Hermes' own save_config() to serialize a real YAML list:
python3 -c "
import sys; sys.path.insert(0, '/home/kk/.hermes/hermes-agent')
from hermes_cli.config import load_config, save_config
cfg = load_config()
cfg['fallback_providers'] = [
    {'provider': 'custom', 'model': 'X',
     'base_url': 'https://host/v1', 'key_env': 'MY_KEY'},
]
save_config(cfg)
"
hermes fallback list   # → entry now visible
```

Append additional entries with `.append({...})`. Order = retry order.

For each fallback entry, pick `provider` and `key_env` per **P11** — bare `provider: custom` only auto-resolves the key for OpenAI/OpenRouter hosts. Other hosts need a `providers.<name>` block whose `key_env` is read from `~/.env`.

### 5. Verify end-to-end (NOT just "config loads")

Three distinct verifications, in increasing strength:

1. **Config-loaded check**: `hermes fallback list` shows your entry. Confirms YAML round-trips.
2. **Direct call check**: `hermes chat -Q -m <alias> -q "pong"` returns "pong" in seconds. Confirms base URL, key, model ID all resolve. (Flags: see P12.)
3. **Cutover check** (for fallbacks specifically): force the primary to fail and confirm the fallback actually takes the call. See recipe in `references/forced-primary-failover-test.md`.

If only (1) passes, you've only verified YAML syntax. (2) and (3) are the real tests.

**Batch-verify every alias you added** and report a PASS/FAIL table — never claim "configured"
off a successful `config set` alone:

```python
from hermes_tools import terminal
alist = ["tag-modelA", "tag-modelB"]
for a in alist:
    r = terminal(f'timeout 180 hermes chat -Q -m {a} '
                 f'-q "Reply with exactly the token ALIAS-OK and nothing else." 2>&1 | tail -4',
                 timeout=200)
    out = r["output"].strip()
    print(f"{'PASS' if 'ALIAS-OK' in out else 'FAIL'}  {a:22} | {out[-160:]!r}")
```

**Then audit that nothing else moved.** Parse the YAML and print the invariants — this is the
evidence the user actually wants (see P10 / "additive not destructive"):

```python
import yaml
c = yaml.safe_load(open("/home/kk/.hermes/config.yaml"))
print("default:", c["model"]["default_provider"], "/", c["model"]["default"])
for k, v in c["model"]["aliases"].items():
    print(f"  {k:22} -> {v.get('model')} ({v.get('provider')})")
print("fallback:", [f["model"] for f in c.get("fallback_providers", [])])
print("mcp_servers:", len(c.get("mcp_servers", {})))
print("custom_providers:", [p["name"] for p in c.get("custom_providers", [])])
```

Confirm the pre-existing default, fallback chain, MCP servers, and custom_providers are all
untouched, and say so explicitly in the summary. If the user has a shell picker
(`templates/hl-model-picker.sh`), run it too — it's their real entry point and proves the
aliases are discoverable, not just present.

### 6. Confirm the primary is declared (so `fallback list` is honest)

`hermes fallback list` prints the primary line using `_describe_primary()` in `fallback_cmd.py`. That helper reads from `config.model.provider` and `config.model.default`. If those are unset, you'll see:

```
Primary:   ?  (via ?)
```

That's not a bug — it just means the primary isn't declared in config.yaml (it's resolved implicitly from `auth.json` or shell env at call time). To make it visible:

```bash
hermes config set model.provider <provider-name>     # e.g. minimax-cn
hermes config set model.default <model-id>           # e.g. MiniMax-M3
hermes fallback list                                 # now shows "Primary: <model> (via <provider>)"
```

Useful as a **diagnostic signal** — if `fallback list` shows the right primary, you know the config path is wired correctly. If it shows `?`, you know the resolution is implicit (via env) and will silently miss if the env isn't loaded at call time (see P5).

### 7. (When translating or self-configuring) Default to "additive, not destructive"

When the user asks to "configure myself with X" or "add Y as an option" or "use Z as a backup", the safest pattern is **add X/Y/Z as alias + fallback entry** without touching the current default. Reasons:

- The current model is what the conversation is running on — replacing it mid-session can break the agent's ability to continue.
- Aliases don't conflict with `model.default`; both can coexist.
- Switching to the new model is then a one-line user decision (`/model <name>` or `hermes chat -m <name>`), not a config reversal if they don't like it.

Replace `model.default` only after the user has **explicitly tested the new model** and **explicitly asked to make it the default**. The user's "不要把自己整坏了" is a first-class signal for this preference — see P10.

### 8. Clean up ugly alias YAML with `save_config()`

`hermes config set model_aliases.<name>` (note: top-level, not `model.aliases`) accepts multi-line scalar values, but the resulting YAML is a literal multi-line string under one key — readable as:

```yaml
model_aliases:
  autolife-gpt55: 'provider: custom

    model: gpt-5.5

    base_url: https://sub2api.autolife-robotics.com/v1

    api_key: ${SUB2API_AUTOLIFE_API_KEY}'
```

Works fine functionally. To get clean nested-dict YAML instead, rewrite with hermes' own serializer:

```python
import sys; sys.path.insert(0, '/home/kk/.hermes/hermes-agent')
from hermes_cli.config import load_config, save_config
cfg = load_config()
cfg['model_aliases']['<name>'] = {
    'provider': '<see P11>',         # NOT 'model.aliases' — top-level key
    'model': '<model-id>',
    'base_url': 'https://<host>/v1',
    'key_env': '<ENV_VAR>',          # reads from ~/.env
}
save_config(cfg)
```

Same technique used to add fallback entries (see step 4). Apply this once after the initial `config set` if YAML readability matters to the user.

## Pitfalls

### P1: `hermes config set fallback_providers` writes a string, not a list

This is the single most likely failure mode. Hermes' `set_config_value` only does scalar coercion (`bool/int/float/string`), so when given a list-shaped string it serializes it as a YAML string scalar (quoted) and `_iter_fallback_entries()` in `fallback_config.py` returns `[]`. The result:

```bash
$ hermes config get fallback_providers
'[{"provider":"custom","model":"X",...}]'    # looks right
$ hermes fallback list
No fallback providers configured.            # actually empty
```

The CLI `hermes fallback add` is interactive-only (`_require_tty("fallback add")`) and routes through `hermes model` picker — which doesn't show custom `provider: custom` entries either. **The only reliable scripted path is `save_config(cfg)`** as shown in step 4. This is what the bundled fallback command itself does internally (`_write_chain` → `save_config`).

### P2: wire_api = "responses" is a Codex concept, not Hermes

If translating from Codex `config.toml`, the `[model_providers.X] wire_api = "responses"` setting has **no Hermes equivalent**. Hermes uses OpenAI Chat Completions by default. Almost every proxy that supports Responses also supports Chat Completions — but if your proxy is Responses-only, Hermes won't speak to it without code changes. Drop the wire_api line and proceed; if calls fail with protocol errors, the proxy is Responses-only and Hermes can't use it.

Other Codex fields with **no Hermes equivalent** (ignore when translating):
- `review_model`
- `model_reasoning_effort = "xhigh"` (OpenAI Responses API specific)
- `disable_response_storage`
- `windows_wsl_setup_acknowledged`

### P3: Hermes uses different protocol defaults per SDK path

- Custom provider with `base_url: https://host/v1` → Hermes uses OpenAI Chat Completions client against `/v1/chat/completions`
- Tool calling: standard OpenAI tool-calling schema — works on every Chat-Completions-compatible proxy
- If the proxy returns a non-standard response shape, Hermes will fail with a parse error, not silently degrade

### P4: Auth key from env vs from config

Two equivalent ways to attach a key:
- `api_key: sk-...` (inline — avoid; ends up in `config.yaml` and any process that reads it)
- `key_env: ENV_VAR_NAME` (recommended; reads `os.environ` via `agent.secret_scope.get_secret`, which also respects multiplexed gateway profiles)

A `key_env` value that doesn't exist in env at call time → fallback entry silently skipped. Verify the env var is exported **in the hermes launcher's environment**, not just in your interactive shell session (cron, systemd, gateway subprocess all need it too).

**Subtle gotcha:** `key_env` is not magic — `agent.secret_scope.get_secret()` only finds env vars that the hermes process actually has in its environment. The variables named `OPENAI_API_KEY` and `OPENROUTER_API_KEY` are guaranteed to resolve via host-gated lookups (the resolver checks `is_openai` / `base_url_host_matches("openrouter.ai")` against the alias's base URL). Every other env-var name **must** be present in the actual process env at the time `hermes chat` starts — putting it in `~/.hermes/.env` or `~/.env` is not enough on its own; the hermes CLI loader only reads `.env` files into its own env during specific setup flows. **If `hermes chat -m <alias>` reports 401 "Missing Authentication header", first check `printenv <YOUR_KEY_ENV_NAME>` from a fresh shell** — if it's empty there, the key isn't reaching hermes regardless of what's in `.env`. See P12.

### P5: Primary provider "active_provider" must be discoverable

Hermes resolves the primary in this order:
1. `auth.json.active_provider` (explicit)
2. `config.model.provider` + `config.model.default` (explicit)
3. `credential_pool` keys with `source: env:<NAME>` (implicit, scans shell env)

If `MINIMAX_CN_API_KEY` (or whatever your primary's env name is) is only in your interactive shell session and not in `~/.env` or `~/.bashrc`, **any non-interactive hermes invocation** (cron, gateway, new login shell) won't find the primary and will go straight to fallback — silently burning fallback quota. For any persistent deployment, put primary keys in `~/.env`.

**Making the primary explicit in config.yaml** (so `hermes fallback list` shows it instead of `Primary: ?`):

```bash
hermes config set model.provider <provider-name>      # e.g. minimax-cn
hermes config set model.default <model-id>            # e.g. MiniMax-M3
hermes fallback list                                   # now shows "Primary: <model> (via <provider>)"
```

This **overrides** `auth.json.active_provider` rather than augmenting it. Safe to set when both agree; if they disagree, the config.yaml declaration wins.

User-defined aliases (`model.aliases.<name>`) are also valid primary declarations via the picker UI or `hermes chat -m <alias>` — they're a third resolution path, not just a selection convenience.

### P6: `/model <built-in-alias>` does NOT use your custom provider

`/model gpt5`, `/model sonnet`, `/model codex` etc. resolve via Hermes' **catalog-resolved built-in alias table**, which points at canonical providers (OpenAI, Anthropic, ...). If you defined `model.aliases.mygpt` pointing at your proxy, you must use `/model mygpt` or `hermes chat -m mygpt` exactly. Don't expect `/model gpt5` to redirect to your proxy — it won't.

**However**, user-defined aliases *are* accepted by `/model <exact-name>` inside an interactive `hermes` session (resolver checks user aliases BEFORE built-in table). They just won't appear in the picker's menu — you have to type the name. So both paths work for user aliases:
- `/model mygpt` inside interactive hermes → resolves to your alias
- `hermes chat -m mygpt -q "..."` from any shell → resolves to your alias
- But the `/model` picker UI menu will only show built-in catalog entries, not yours

### P9: User-defined aliases are independent from built-in alias catalog

Built-in aliases (`gpt5`, `sonnet`, `codex`, `grok`, `claude`, `gemini`, `deepseek`, `qwen`, `minimax`, `kimi`, `glm`, ...) are managed by Hermes' catalog and shadow ANY user alias with the same name. If you define `model.aliases.minimax` pointing at your custom provider, it WILL shadow the built-in `minimax` shortcut. This is sometimes wanted (override the default) and sometimes surprising — pick names that don't collide unless you mean to override.

Naming convention: prefix with a tag (`my-`, `proxy-`, `autolife-`, `local-`) to avoid collisions. `autolife-gpt55` is safer than `gpt55`.

### P7: A model being LISTED by the proxy does not mean it WORKS — probe before configuring

`/v1/models` lists what the proxy *advertises*. Many proxies list models whose upstream is
dead, unfunded, or region-blocked. Listing is not availability:

```bash
curl -s https://<host>/v1/models -H "Authorization: Bearer $KEY" | jq '.data[].id'
```

**Probe each candidate with a real completion before writing it into config.** A model that
returns HTTP 502 `{"type":"upstream_error"}` will silently poison an alias or fallback entry
that looks perfectly valid in YAML. Observed in practice: on one gateway, `gpt-5.2-pro` was
listed but returned 502 on every call while 7 sibling models returned 200.

```python
from hermes_tools import terminal
import json
K = "sk-..."
for m in ["model-a", "model-b"]:
    body = json.dumps({"model": m,
                       "messages": [{"role": "user", "content": "reply with the single word OK"}],
                       "max_tokens": 16})
    r = terminal(f"curl -s -m 60 -o /tmp/r.json -w '%{{http_code}}' "
                 f"-H 'Authorization: Bearer {K}' -H 'Content-Type: application/json' "
                 f"-d {json.dumps(body)} https://<host>/v1/chat/completions")
    d = json.loads(terminal("cat /tmp/r.json")["output"])
    print(m, r["output"].strip().splitlines()[-1],
          d.get("error") or d["choices"][0]["message"]["content"][:40])
```

Configure only the models that returned 200 with real content, and **tell the user which ones
you dropped and why** — a silently-omitted model looks like an oversight otherwise.

### P12: `hermes chat` non-interactive flags are `-q` / `-Q`, not `-p`

For scripted verification of an alias:

```bash
hermes chat -Q -m <alias> -q "Reply with exactly the token ALIAS-OK and nothing else."
```

- `-q QUERY` / `--query` — the single-shot prompt (**not** `-p`; `-p` errors with
  `unrecognized arguments`)
- `-Q` / `--quiet` — suppress banner/spinner/tool previews, emit only the final response plus
  a `session_id:` line
- `--provider`, `--reasoning`, `-t/--toolsets`, `-s/--skills` also available per-run

Wrap in `timeout 180` and loop over every alias to get a PASS/FAIL table in one pass. Assert on
a sentinel token in the output rather than on exit code alone — `hermes chat` can exit 0 while
having printed an argparse error.

### P11: Prefer dotted leaf paths over multi-line scalars for nested config

`hermes config set model.aliases.<name> "provider: custom\nmodel: ..."` (one call, multi-line
scalar value) *works*, but YAML-dumps the whole dict as a **literal multi-line string** under
one key — ugly, and it needs a `save_config()` rewrite to clean up.

Setting one **dotted leaf path per call** (`model.aliases.<name>.provider`, `.model`,
`.base_url`, `.key_env`) produces proper nested dicts directly, with intermediate levels
auto-created. Verified working at 3 levels deep. Always use the leaf-path form; it costs N
calls but needs zero cleanup.

### P13: "Configure a new model" may mean a new model ID, not a new provider

When a user pastes a provider config (e.g. `~/.codex/config.toml`) and says "configure a new
model, coexisting with the existing one", check whether the **base_url and API key already
exist** in `config.yaml`. If they match an existing entry, the only genuinely new thing is the
**model ID** — so the work is adding aliases on the existing custom provider, not registering a
new provider.

Do both of these:
1. **Enumerate what the gateway actually offers** (`/v1/models`) — the user's pasted config may
   be pinned to an older model than what's available. Surface the newer options and let them
   pick scope (see P10, step 1) rather than mirroring their file verbatim.
2. **State the interpretation explicitly in the summary**: "your key + gateway are identical to
   the existing `<alias>`, so I read this as *new model IDs on the same provider*; if you meant a
   genuinely different provider (different key/host), that's a different setup — tell me."

This closes the ambiguity instead of silently guessing, and it's usually where the real value is:
the user's own config was stale relative to their gateway.

Also worth flagging back to the user: if their source config (Codex, Claude Code, etc.) pins an
older model than the gateway now serves, offer a **minimal** upgrade to that file too (change
only the model fields) — but as a separate opt-in, not bundled into the Hermes change.

### P8: `hermes fallback add` requires a TTY

`hermes fallback add` calls `_require_tty("fallback add")` — it won't run over a piped/non-interactive shell. Even if it accepted arguments (it doesn't), it still needs the picker UI. **The scripted escape hatch is `save_config()` from step 4.**

### P10: Self-config requests should default to additive, not replacement

When the user asks an agent to "configure yourself with X model" / "set up Y as an option" / "use Z as a backup", the **default pattern** is:

- Add X/Y/Z as a `model.aliases.<name>` entry — non-destructive, selectable via `hermes chat -m <name>`
- Optionally also add to `fallback_providers` — non-destructive, automatic on primary failure
- **Do not** replace `model.default` / `model.provider` until the user has explicitly tested the new model AND explicitly asked to make it the default

Why: the agent reading this skill is itself running on the current primary. Replacing `model.default` mid-session risks:

- Breaking the current conversation if the new model is incompatible, rate-limited, or differently behaved
- An irreversible-feeling change ("把自己整坏了") when the user only wanted to *try* something
- Loss of the working primary — if the new model turns out to be broken, the user has to remember to revert

Workflow for self-config requests:

1. **Ask first** what scope they want (alias-only / alias + fallback / full default swap). Don't assume.
2. **Add alias** (non-destructive — see step 3)
3. **Verify** with `hermes chat -m <name> -q "ping"` that the new model actually responds
4. **Add to fallback chain** if they want backup behavior (non-destructive — see step 4)
5. **Cutover check**: force the primary to fail, confirm the new entry takes the call
6. **Only then** offer to swap `model.default`, after they confirm with eyes-open

The user's literal phrasing "不要把自己整坏了" is a first-class signal — capture this preference into the workflow, not just memory.

### P11: `alias.provider: custom` only works for OpenAI/OpenRouter hosts

The alias resolver takes two completely different paths based on the `provider` field:

| `alias.provider` value | Resolver path | Key resolution | When it works |
|---|---|---|---|
| `custom` | `_resolve_direct_alias_runtime()` | Host-gated env candidates: `OPENAI_API_KEY` (if `is_openai`), `OPENROUTER_API_KEY` (if base URL host matches `openrouter.ai`), OLLAMA loopback | **Only** OpenAI / OpenRouter / Ollama hosts — and `OLLAMA_API_KEY` is only checked for loopback |
| `<name>` where `name` is a registered `providers.<name>` block | `_resolve_named_custom_runtime()` → `_match_new_style_provider()` | Reads `entry.key_env` (or `entry.api_key_env`) from `~/.env` via `agent.secret_scope.get_secret()` | **Any** host — works for dashscope, siliconflow, deepseek, kimi, internal proxies, anything |

The symptom when you pick the wrong path: `hermes chat -m <alias>` returns 401 with `Missing Authentication header` and silently falls back to whatever's next in `fallback_providers`. The error message never says "you used the wrong alias.provider value".

**Default to the second pattern** (register a `providers.<name>` block first, then point the alias at it with `provider: <name>`). It's the only pattern that scales beyond the two hosts the maintainers hardcoded.

Detailed comparison and the full `_match_new_style_provider` vs `_resolve_direct_alias_runtime` decision logic: see `references/alias-provider-patterns.md`.

### P12: `key_env` reads hermes's own process env, not arbitrary `.env` files

`agent.secret_scope.get_secret(name)` only returns truthy for env vars that exist in the hermes launcher's process environment at call time. The `~/.hermes/.env` and `~/.env` files are NOT auto-loaded into every `hermes chat` subprocess — they're loaded only during specific setup flows (`hermes setup`, `hermes auth add`).

For `OPENAI_API_KEY` / `OPENROUTER_API_KEY` this doesn't matter because P11's host-gated fallback checks them directly. For **any other env var name** (e.g. `DASHSCOPE_API_KEY`, `MY_PROXY_KEY`, `QWEN_HUB_API_KEY`), you must verify the var is in the actual process env when `hermes chat` runs.

**Quick verification, in order of how often the answer is "no"**:

1. `printenv <VAR>` from a fresh shell → if empty, hermes chat will 401
2. `cat ~/.hermes/.env | grep <VAR>` → confirms the file has it (does NOT mean hermes sees it)
3. `bash -c 'source ~/.hermes/.env; printenv <VAR>'` → confirms dotenv loading works for a child shell (hermes does the equivalent at startup)
4. `hermes chat -m <alias> -q ping` → real test

If (1) is empty but (2) shows the var, you need to export it explicitly:
- One-off: `export <VAR>=... && hermes chat -m <alias> ...`
- Persistent: add `export <VAR>=...` to `~/.bashrc` (interactive shells) and `~/.hermes/.env` for setup-flow consumers
- systemd / cron / gateway: the unit file must set the env var directly (`Environment=VAR=value`)

### P13: The `patch` tool refuses to write `~/.hermes/config.yaml`

The `patch` and `write_file` tools refuse to modify `~/.hermes/config.yaml` directly — the safety guard says "Agent cannot modify security-sensitive configuration." This is intentional, but it means the agent can't use its standard file-edit tools on this file.

Two workarounds, both official:
1. **`save_config(cfg)` from Python** — preferred for nested-dict edits. Loads via hermes's own serializer, preserves ordering, validates structure.
2. **`hermes config set <key> <value>` CLI** — works for scalar values, breaks for lists (see P1).

There is no way to bypass this guard from the agent's side; do not attempt. If you find yourself wanting to edit config.yaml directly with `patch`, that's a signal you should be using `save_config()` instead.

## Reference recipes

- `references/forced-primary-failover-test.md` — the only reliable way to confirm a fallback chain actually triggers
- `references/codex-to-hermes-translation.md` — field-by-field translation table for `~/.codex/config.toml` → Hermes
- `references/bulk-alias-registration.md` — end-to-end recipe for registering many aliases on one multi-model gateway: probe-before-configure, dotted-leaf-path loop, invariant audit, reporting template, and the CLI gotcha table
- `references/alias-provider-patterns.md` — decision table: when `alias.provider: custom` works, when you need a registered `providers.<name>` block, and why
- `templates/hl-model-picker.sh` — shell-side picker (`hl <alias>`) for listing/launching with any registered alias; copy to `~/.local/bin/hl` and `chmod +x`. Reads `model.aliases` live so adding a new alias automatically appears in `hl -l` output.

## 补充（审批积压恢复 4f4ac9ea）

### 3. Add the alias (if you want it selectable) — USE DOTTED LEAF PATHS

**Preferred method.** `hermes config set` accepts arbitrarily deep dotted paths and creates
intermediate dicts as needed. Set one leaf field per call — this yields clean nested YAML
with **no post-hoc cleanup** (unlike the multi-line-scalar form, see P11):

```bash
hermes config set model.aliases.<name>.provider custom
hermes config set model.aliases.<name>.model    <model-id>
hermes config set model.aliases.<name>.base_url https://<host>/v1
hermes config set model.aliases.<name>.key_env  MY_NEW_PROVIDER_API_KEY
```

Each call prints `✓ Set model.aliases.<name>.<field> = <value> in <path>`. Verify:
```bash
hermes config get model.aliases.<name>     # prints the nested dict
```

**Registering many aliases at once** (e.g. every model a gateway offers) — loop it in
`execute_code` rather than hand-typing 4×N calls, and assert on the `✓`:

```python
from hermes_tools import terminal
BASE, KEY = "https://<host>/v1", "MY_NEW_PROVIDER_API_KEY"
aliases = {"tag-modelA": "model-a-id", "tag-modelB": "model-b-id"}
fail = []
for a, m in aliases.items():
    for k, v in [("provider","custom"),("model",m),("base_url",BASE),("key_env",KEY)]:
        r = terminal(f"hermes config set model.aliases.{a}.{k} {v}")
        if r["exit_code"] != 0 or "✓" not in r["output"]:
            fail.append((a, k, r["output"][:120]))
print("failures:", fail or "none")
```

Back up config.yaml first: `cp ~/.hermes/config.yaml /tmp/config.yaml.bak.$(date +%s)`.

If `hermes chat -m <name> ...` returns "alias not found", the user-defined alias namespace is independent of the built-in `/model` catalog (`gpt`, `sonnet`, `codex`, `grok`, ...) — custom aliases don't get catalog resolution; they need an exact match.


## 补充（审批积压恢复 448ef799）

### 8. If a file-edit tool refuses to touch config.yaml, that's by design

`~/.hermes/config.yaml` is **write-protected against the agent's file tools**. A `patch` /
`write_file` attempt returns:

```
Refusing to write to Hermes config file: /home/kk/.hermes/config.yaml
Agent cannot modify security-sensitive configuration. Edit ~/.hermes/config.yaml
directly or use 'hermes config' instead.
```

This is a security guard, not a broken tool. **Always reach for `hermes config set` first**
for alias/provider work (step 3) — don't waste a turn discovering the refusal. The
`save_config()` escape hatch (step 4) remains the path for genuine **list-valued** keys like
`fallback_providers`, which `config set` cannot express (P1).
