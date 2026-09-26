# Log Evidence Recipes for Meta-Questions

Concrete grep / filter recipes for answering "how did Hermes do X" questions. The SKILL.md is the always-on rule; this file is the per-platform lookup.

## Universal: find the active session

```bash
# Most recent gateway session id
grep -oE 'session=[0-9_a-z]+' ~/.hermes/logs/agent.log | tail -1
# Recent sessions (last 5)
grep -oE 'session=[0-9_a-z]+' ~/.hermes/logs/agent.log | sort -u | tail -5
```

Every inbound and outbound in that session will be tagged with that session id in `agent.log` and `gateway.log`. Filter for it before doing anything else — it cuts noise by ~99% on a busy gateway.

## Feishu (飞书)

**Inbound events** carry `sender.open_id`, `chat_id`, `message_id`, and the literal text. The platform line prefix is `[Feishu]`.

```bash
# All inbound DMs in a session
grep "session=<SID>" ~/.hermes/logs/agent.log \
  | grep "Inbound dm message received"

# The "did the bot proactively send" check
grep "session=<SID>" ~/.hermes/logs/agent.log \
  | grep "Sending response"

# If outbound count > 0 but inbound count == 0, the bot did send first.
# If outbound == 0, every response was reactive.
```

**Field reference** (what the log line gives you):

| Field in log | What it proves |
|---|---|
| `id=om_xxx` | Unique message id; same id can appear twice if Feishu webhook re-delivered (de-dup is server-side and imperfect) |
| `chat_id=oc_xxx` | The conversation. The bot used this to send the reply. |
| `sender=user:ou_xxx` | The user's open_id, attached to *every* inbound by the Feishu platform — no API call needed to learn who is messaging |
| `reply_to_id=None` | The outbound did not reference any prior message — the bot replied with a fresh message, not a thread reply |
| `text='...'` | The literal user text. Decoded JSON-unsafe chars appear literally — when a user pastes a code block with `\n` and `\\`, that's exactly what shows up |

**Cold-start check** — was there ever a `Sending response` in this session with no preceding `Inbound dm message received`?

```bash
# Per-session first event
grep "session=<SID>" ~/.hermes/logs/agent.log \
  | grep -E "Inbound dm|Sending response" \
  | head -1
```

If the first event is `Inbound dm message received`, the session was opened by the user. The bot did not cold-message.

## Telegram

Prefix: `[Telegram]` (or platform name in `gateway.platforms.base` log lines).

```bash
# Inbound updates
grep "session=<SID>" ~/.hermes/logs/agent.log \
  | grep -E "update.*message|message received"

# Outbound (sent messages)
grep "session=<SID>" ~/.hermes/logs/agent.log \
  | grep -iE "sendMessage|sending message"
```

`from.id` in the inbound line is the Telegram user id. Field names differ from Feishu; same idea, different label.

## Discord

Prefix: `[Discord]`.

```bash
# Inbound message create events
grep "session=<SID>" ~/.hermes/logs/agent.log \
  | grep "MESSAGE_CREATE"

# Outbound
grep "session=<SID>" ~/.hermes/logs/agent.log \
  | grep -iE "send.*message|created message"
```

`author.id` is the user snowflake. **Privileged Gateway Intents** (Message Content Intent) is a permission concern — if the bot is silent in DMs, check the bot's intent flags in the Discord developer portal, not the logs.

## Slack

Prefix: `[Slack]`. The `message.channels` subscription is what enables public-channel events. If inbound only shows DMs, the bot probably has no `message.channels` scope — that is a config / scope question, not a log-evidence question.

## Config references (when the question is about permission / scoping, not behavior)

| Question class | Look in |
|---|---|
| "Can the bot message me unprompted?" | `~/.hermes/config.yaml` → `messaging.<platform>.proactive` (if present) + the platform app's admin console for granted scopes |
| "What platforms are enabled?" | `~/.hermes/config.yaml` → `messaging.platforms` |
| "What model is the bot using?" | `~/.hermes/config.yaml` → `model.*` and `provider.*`; the live value is in the `API call #N:` line of `agent.log` |
| "Where is the user data stored?" | `~/.hermes/state.db` (canonical session store, SQLite + FTS5); `~/.hermes/sessions/` for gateway routing index |

## Cross-platform invariant

**Every** messaging platform attaches a per-user identifier to every inbound event the bot receives. The bot does not need to look the user up by name, email, or phone to reply — it just echoes the identifier back. This is why the answer to "how do you find me" is almost always "the platform tells me on every message; I don't look you up." This is the same shape across Feishu / Telegram / Discord / Slack / iMessage / Signal — only the field name changes.

## When logs are insufficient

If `agent.log` is rotated and the relevant session is in `agent.log.1` or older, just substitute the file path. If the event is so old it's gone, say so plainly: "the log for that session has been rotated out, so I can't verify the exact event from logs — here's what the general mechanism is, labeled as a principle, not a verified fact about that specific event."

Never reconstruct a "likely" event from general platform knowledge and present it as evidence.
