# Bulk alias registration on a multi-model gateway

Worked recipe for "register every usable model on an OpenAI-compatible gateway as a Hermes
alias, without touching the existing default". Generalized from a real session.

## Situation shape

- User pastes a provider config (Codex `config.toml`, Claude Code settings, ...) and asks to
  "configure a new model, coexisting with the existing one".
- The base_url + API key turn out to be **identical** to an already-registered custom provider.
- So the real task = add aliases for additional **model IDs** on the existing provider.
  See P13 in SKILL.md — confirm this interpretation out loud.

## Sequence

### 1. Read current state (don't assume)

```python
from hermes_tools import read_file
print(read_file("/home/kk/.hermes/config.yaml")["content"])
```

Note: existing `model.aliases`, `model.default*`, `fallback_providers`, `custom_providers`,
`mcp_servers`. These are your invariants for the post-change audit.

### 2. Enumerate what the gateway advertises

```bash
curl -s -m 25 -H "Authorization: Bearer $KEY" https://<host>/v1/models
```

Some gateways serve the same payload at `/models` and `/v1/models`. Expect the list to include
models **newer than what the user's pasted config pins** — that's the useful finding.

### 3. Probe every candidate for real availability

Listing ≠ working (P7). Send a real minimal completion per model and record HTTP status +
content. Drop anything non-200 and report which ones you dropped.

Observed failure shape for a dead upstream:
```json
{"message": "Upstream request failed", "type": "upstream_error"}   // HTTP 502
```

### 4. Ask the user for scope before writing

Per P10, don't assume how many to add. Offer: all / one newest / a strong+cheap pair / explain
the variants first. (A user who answers "全部都要" wants the comprehensive option — favor
layered solutions for them thereafter.)

### 5. Back up, then register with dotted leaf paths

```bash
cp ~/.hermes/config.yaml /tmp/config.yaml.bak.$(date +%s)
```

Loop 4 `hermes config set` calls per alias (provider / model / base_url / key_env), asserting
`✓` in each result. See SKILL.md step 3 for the loop.

Naming: prefix by gateway/owner (`autolife-gpt56`, `autolife-gpt56-luna`) so nothing collides
with Hermes' built-in alias catalog (P9).

### 6. Verify each alias end-to-end + audit invariants

Sentinel-token loop over every new alias (SKILL.md step 5), then YAML audit proving default,
fallback, MCP servers, and custom_providers are unchanged. Run the user's shell picker if they
have one.

## Reporting template

Lead with the table of what now exists, then:

- **Explicitly list what was NOT touched** (default model, fallback, MCP servers, existing
  aliases) and where the backup is.
- **Name any model you dropped and why** (e.g. listed but 502) so it doesn't read as an omission.
- **Flag the user's stale source config** if the gateway offers newer models than it pins, and
  offer a minimal opt-in upgrade.
- **Restate your interpretation** if the key/host matched an existing provider (P13), inviting
  correction if they meant a genuinely different provider.

## Gotchas hit in practice

| Symptom | Cause | Fix |
|---|---|---|
| `patch`/`write_file` refuses config.yaml | Security guard on Hermes config | Use `hermes config set` (SKILL.md step 8) |
| `hermes config: error: invalid choice: 'alias'` | There is no `config alias` subcommand | Only `show/edit/get/set/unset/path/env-path/check/migrate` exist |
| `unrecognized arguments: -p ...` | Wrong non-interactive flag | Use `-q` for the query, `-Q` for quiet (P12) |
| Model listed but every call 502s | Dead upstream behind the gateway | Probe first; omit and report (P7) |
| `hermes chat` exits 0 despite argparse error | argparse error still yields exit 0 through the pipe | Assert on a sentinel token in stdout, not exit code |
