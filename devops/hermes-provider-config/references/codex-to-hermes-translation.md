# Codex `config.toml` → Hermes translation table

When a user hands you a Codex provider config and asks for the same in Hermes. Verified against real Codex config 2026-08-14.

## Side-by-side example

**Codex (`~/.codex/config.toml`):**
```toml
model_provider = "OpenAI"
model = "gpt-5.5"
review_model = "gpt-5.5"
model_reasoning_effort = "xhigh"
disable_response_storage = true
network_access = "enabled"
windows_wsl_setup_acknowledged = true

[model_providers.OpenAI]
name = "OpenAI"
base_url = "https://sub2api.autolife-robotics.com"
wire_api = "responses"
requires_openai_auth = true

[features]
goals = true
```

**Hermes (`~/.hermes/config.yaml` fallback entry + `.env`):**

```bash
# 1. Key in .env (mode 600)
echo "SUB2API_AUTOLIFE_API_KEY=sk-..." >> ~/.env

# 2. Fallback entry — must use save_config() script (hermes config set doesn't accept list literals)
python3 -c "
import sys; sys.path.insert(0, '/home/kk/.hermes/hermes-agent')
from hermes_cli.config import load_config, save_config
cfg = load_config()
cfg['fallback_providers'] = [{
    'provider': 'custom',
    'model': 'gpt-5.5',
    'base_url': 'https://sub2api.autolife-robotics.com/v1',
    'key_env': 'SUB2API_AUTOLIFE_API_KEY',
}]
save_config(cfg)
"

# 3. Optional alias for direct selection (note: top-level `model_aliases`, NOT `model.aliases`)
python3 -c "
import sys; sys.path.insert(0, '/home/kk/.hermes/hermes-agent')
from hermes_cli.config import load_config, save_config
cfg = load_config()
cfg.setdefault('model_aliases', {})['autolife-gpt55'] = {
    'provider': 'custom',
    'model': 'gpt-5.5',
    'base_url': 'https://sub2api.autolife-robotics.com/v1',
    'key_env': 'SUB2API_AUTOLIFE_API_KEY',
}
save_config(cfg)
"
```

## Field-by-field translation

| Codex field | Hermes equivalent | Notes |
|---|---|---|
| `model_provider = "X"` | `provider: X` (inside an alias or fallback entry) | Same string value, same purpose |
| `model = "X"` | `model: X` | Same |
| `[model_providers.X]` section | The entry dict (`provider`, `model`, `base_url`, `key_env`) | Inline dict instead of named section |
| `name = "X"` | (no separate `name` field) | Provider name = first-level `provider` key |
| `base_url = "https://host"` | `base_url: https://host/v1` | **Add `/v1`** — Hermes always uses OpenAI Chat-Completions path, which lives at `/v1/chat/completions` |
| `wire_api = "responses"` | **DROP — no Hermes equivalent** | See pitfall P2 in SKILL.md. If proxy is Responses-only, Hermes can't use it |
| `requires_openai_auth = true` | **DROP** | Always true for custom provider — implicit |
| `review_model = "X"` | **DROP** | Hermes has no separate review model concept |
| `model_reasoning_effort = "xhigh"` | **DROP** | OpenAI Responses API parameter; Chat Completions path doesn't accept it. If you really need reasoning effort, check the proxy's specific schema |
| `disable_response_storage = true` | **DROP** | OpenAI Responses API feature; Chat Completions path doesn't have it |
| `network_access = "enabled"` | **DROP** | Hermes has its own egress controls (`hermes egress`) — see SKILL.md for the bundled egress reference |
| `windows_wsl_setup_acknowledged = true` | **DROP** | Codex-only setup flag |
| `[features] goals = true` | `goals: true` at top level | Default in Hermes; usually no need to set |
| `OPENAI_API_KEY = "sk-..."` in `~/.codex/auth.json` | Inline `api_key:` OR `key_env:` in alias/fallback entry | **Use `key_env:` and put the value in `~/.env`** — see SKILL.md P4 |

## What the user usually means by "translate"

Three intents, three different outputs:

1. **"I want to use this model in Hermes too"** → add an **alias** (`model.aliases.<name>`), so `hermes chat -m <name>` works
2. **"Set this as my fallback when primary dies"** → add a **fallback entry** (`fallback_providers` list)
3. **"Set this as my default / primary"** → use `hermes model` picker (interactive), or `hermes auth add` for built-in providers

Don't conflate these. A common user mistake is assuming "config the provider" = "make it primary". Confirm with the user before re-pointing the primary.

## Example: user says "把这个给我转成 hermes 的"

If they hand you only the Codex config and say "translate", do:

1. Build the **fallback entry** (least invasive — current primary untouched)
2. Optionally build the **alias** for direct selection
3. Run the **cutover test** (`references/forced-primary-failover-test.md`) to prove it works
4. **Don't touch the primary** without explicit user direction

If they then say "make it primary" → `hermes model` picker, or `hermes config set model.default <name>` if using an alias as primary.