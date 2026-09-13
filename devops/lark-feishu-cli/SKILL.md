---
name: lark-feishu-cli
description: "Lark/Feishu CLI: bind, OAuth Device Flow, identity modes."
version: 1
author: hermes-agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [lark, feishu, larksuite, oauth, device-flow, agent-context, bytedance]
    related_skills: [hermes-agent, hermes-provider-config]
---

# Lark / Feishu CLI

Drive the [@larksuite/cli](https://www.npmjs.com/package/@larksuite/cli) (`lark-cli`) from an AI agent. The CLI handles **both** Lark international (`open.larksuite.com`) and Feishu China (`open.feishu.cn`) via a single binary — only the `--brand` flag and the host URL differ. Triggered by: "connect to Feishu", "bind lark to my agent", "set up Lark OAuth", "send a Feishu message from CLI", "configure lark-cli app", "list Feishu calendar events".

## When to use

- Installing + binding the Lark/Feishu CLI to a user account or AI agent workspace
- Running the OAuth Device Flow with the **agent-handoff pattern** (CLI returns URL, user clicks in their browser, agent polls)
- Choosing between `bot-only` and `user-default` identity modes (impacts what data the CLI can touch)
- Translating an open platform app config (`App ID` + `App Secret`) into a working CLI binding
- Verifying the bind works after a token rotation or app re-publish

**Do not use** for building Feishu apps themselves (this skill is for *consuming* the API). For app creation, go to https://open.feishu.cn/app (CN) or https://open.larksuite.com/app (international) in the user's browser.

## Critical facts

1. **There is no `@feishu/cli` on npm.** The only official CLI is `@larksuite/cli` (verified `npm view @feishu/cli` → 404; `@larksuite/cli@1.0.87` exists with `bin: lark-cli`). The same binary serves both Lark and Feishu — brand is a config option, not a separate package.

2. **The CLI has explicit AI-agent guards.** It detects `OPENCLAW_HOME` / `HERMES_HOME` env vars and changes behavior:
   - `lark-cli config init` inside an agent context **refuses by default** — uses `--force-init` to override, or use `config bind` instead.
   - `config bind` requires **explicit user confirmation** of both intent AND identity preset (`bot-only` or `user-default`). The CLI literally prints "DO NOT bind without user confirmation" in its help.

3. **`lark-cli auth login` is blocking by default** — but `--no-wait --json` returns the verification URL immediately, designed for agent handoff. See "Device Flow handoff" below.

## Identity modes

The bind step **must** ask the user to choose. Don't pick one yourself unless told:

| Mode | What it does | Capability | Risk |
|---|---|---|---|
| **`bot-only`** (default, safer) | Bot identity only | Send/receive bot messages, bot data, group chats | Cannot access user's personal calendar/mail/drive/docs |
| **`user-default`** | Impersonates the user | Everything, including personal data | Powerful; warns at bind time not to share the bot or pull it into groups (it'd leak the user's data) |

The CLI rejects `bot-only → user-default` upgrades without `--force`. Use `lark-cli config strict-mode` to switch identity preset on the **same** app — that's the policy switch and doesn't re-bind.

## Core workflow

### 1. Install

```bash
npm install -g @larksuite/cli
lark-cli --version   # expect 1.0.x
```

Installs to user prefix (`~/.npm-global/bin/lark-cli`) when `~/.npmrc` has `prefix=...` — same pattern as other user-level npm installs.

### 2. Ask the user for App ID + App Secret (or use `--new` for bot-only)

User must create a self-built app at https://open.feishu.cn/app (CN) or https://open.larksuite.com/app (international). Required at creation:

- App name (anything)
- Required scopes (start with `im:message` for messaging; add `calendar:calendar`, `mail:user_mailbox`, `drive:drive`, `docs:document` if using `user-default`)
- A published version (CLI can't call unscoped/unpublished apps)

For **`bot-only`**: `--new` flag can create the app automatically without the user going to the website.

### 3. Bind to the agent context

```bash
# Inside an agent context (HERMES_HOME set):
lark-cli config bind \
  --source hermes \
  --app-id "cli_xxxxxxxx" \
  --identity bot-only        # or user-default
# For user-default upgrade from bot-only, add --force
```

Without `--source`, the CLI auto-detects from env. `--source` values: `openclaw`, `hermes`, `lark-channel`.

Bind writes to `~/.lark-cli/<workspace>/config.json` (default workspace name = source). The bind is a **one-shot sync** — later agent config changes don't auto-update lark-cli. Re-bind if the underlying app changes.

### 4. Device Flow with agent handoff (THE key pattern)

```bash
# Step 1: kick off, get URL, RETURN IMMEDIATELY (do NOT block)
lark-cli auth login --no-wait --json --recommend
# → JSON: {"device_code":"...", "verification_url":"https://accounts.feishu.cn/oauth/v1/device/verify?...&user_code=XXXX-YYYY", "expires_in":600, "hint": "..."}

# Step 2: send URL to user. Tell them to click it / scan QR with Feishu App.
#         END THE TURN HERE. Do not poll in the same turn.

# Step 3: after user confirms (in a later turn):
lark-cli auth login --device-code "<device_code>"
# This blocks until the user has authorized, or 600s expiry, whichever first.
```

The CLI's response JSON **literally instructs** the agent to do this handoff. Don't fight it. Don't try to open the URL yourself with `browser_navigate` or similar — the auth **must** complete in the user's browser.

### 5. Generate QR code (for mobile scan)

```bash
# QR generation is for AI agents to display inline. Required step.
cd /tmp/lark-qr   # must be a relative path target
lark-cli auth qrcode "<verification_url>" -o qr.png --size 512
# Then display the PNG inline in your response (vision_analyze to verify, or just trust it).
```

`qrcode` takes URL as a **positional arg**, not `--url`. Output path must be **relative** (`-o` rejects absolute paths) and within the current working directory. PNG is 512×512 default.

### 6. Verify the binding works

```bash
lark-cli config show      # shows current app id, identity mode
lark-cli auth status      # shows current user, scopes granted
lark-cli auth scopes      # lists enabled scopes for the app
lark-cli calendar +agenda # calls a +shortcut to verify user-data access
lark-cli api GET /open-apis/calendar/v4/calendars  # raw API path as fallback
```

The `+agenda` shortcut (and similar `+<verb>` shortcuts) are the high-level task layer. They're preferred over raw API calls. See `lark-cli <domain> --help` for available shortcuts.

## Pitfalls

### P1: There's no `@feishu/cli`, only `@larksuite/cli`

Stop searching. `@feishu/cli` 404s. The `@larksuite/cli` description literally says "The official CLI for Lark/Feishu open platform". One binary, both brands.

### P2: `lark-cli config init` refuses inside agent contexts

`HERMES_HOME` and `OPENCLAW_HOME` are both detection signals. Inside Hermes: `init` refuses with a hint pointing you at `config bind`. Either:
- Use `config bind` (preferred — binds the existing app, no duplicate)
- Use `init --force-init` only if you really want a separate app inside the agent workspace

### P3: `config bind` requires explicit user confirmation

The CLI prints this in its help. Before running it, confirm with the user:
1. Intent: "bind this app to the Hermes agent workspace"
2. Identity: `bot-only` or `user-default`

Never auto-pick. The CLI also rejects `bot-only → user-default` upgrades without `--force`.

### P4: Blocking auth login in a one-shot agent turn is wrong

`lark-cli auth login` (without `--no-wait`) blocks until the user clicks the URL — which might be minutes or hours later. The CLI provides `--no-wait --json` specifically for agent handoff. Use it. End your turn. Wait for the user to come back. Then `--device-code` to complete.

### P5: QR code generation flags are positional, output is relative-path

```bash
# WRONG:
lark-cli auth qrcode --url "$URL" --output /tmp/qr.png
# RIGHT:
cd /tmp/lark-qr
lark-cli auth qrcode "$URL" -o qr.png
```

The CLI doesn't accept `--url` and rejects absolute `-o` paths. Read the flags from `qrcode --help` before guessing.

### P6: App Secret leakage — sanitize before logging

`config bind` (and `init`) may echo the app secret in error messages or traces. Recommend the user rotate the secret after a bind in a less-trusted environment. The `--app-secret-stdin` flag exists for `init` precisely to avoid `ps` exposure — bind doesn't have it, so treat any bind command as visible to the shell history.

### P7: Scope requests need publishing + user-grant flow

Even after scopes are enabled in the app config and a version is published, the **user** must grant them at the OAuth consent screen. The `--recommend` flag requests only "auto-approve" scopes (CLI sets these). Non-recommended scopes require explicit consent in the browser — pass `--domain` or `--exclude` to customize.

### P8: `+shortcuts` vs raw API — prefer shortcuts

Each domain has shortcuts: `+agenda` (calendar), `+list` (drive), etc. They're higher-level than raw API calls. Inspect any call with:

```bash
lark-cli schema <service>.<resource>.<method>   # shows params, types, scopes
```

before firing raw `api GET /open-apis/...` calls. Risk tier per call shows in `--help`: `read | write | high-risk-write`. The `high-risk-write` tier requires `--yes` only after the user has confirmed.

### P9: Brand flag defaults to `feishu`

`lark-cli config init --brand feishu` is default. For international: `--brand lark`. The choice affects which open-platform URL the CLI contacts (`open.feishu.cn` vs `open.larksuite.com`).

## Reference recipes

- `references/oauth-device-flow-handoff.md` — exact end-to-end sequence (script with `--no-wait --json` URL extraction, QR generation, then `--device-code` polling)
- `references/identity-mode-decision.md` — when to recommend `bot-only` vs `user-default` to the user, with scope-mapping examples