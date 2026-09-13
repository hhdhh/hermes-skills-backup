# Identity mode decision (bot-only vs user-default)

When a user asks to bind the Lark/Feishu CLI to their agent, you must ask which identity mode they want. This file explains the trade-offs so you can present them honestly.

## The two modes at a glance

| | `bot-only` | `user-default` |
|---|---|---|
| Identity | Bot | User (you) |
| Scopes | Only bot-scoped + IM | All personal scopes (calendar, mail, drive, docs, etc.) |
| Personal data access | ❌ No | ✅ Yes |
| Send messages in groups | ✅ As bot | ✅ As you |
| Risk if shared | Low — bot data only | High — leaks your personal data to anyone the bot is shared with |
| Upgrade path | `config strict-mode` or re-bind with `--force` | (already at max) |

## When to recommend `bot-only`

Default to this. Recommend it when:

- The user is just connecting Feishu for the first time and wants to "see how it works"
- The use case is sending/receiving messages, group chat, bot data only
- The user expressed security caution
- You're uncertain what the user actually wants — `bot-only` is the safer error

`bot-only` can be upgraded to `user-default` later with `config bind ... --identity user-default --force`. So starting with `bot-only` is reversible.

## When to recommend `user-default`

Recommend it when the user explicitly says:

- "I want to read my calendar"
- "I want to search my messages"
- "I want to access my mail / drive / docs"
- "Use my account" / "as me" / "impersonate me" / "with my permissions"

`user-default` is the only way to access user-scoped data. If the user expects the CLI to read their calendar/email/Drive and you bind with `bot-only`, every personal-data call will return a scope error.

## Scope decisions per use case

If the user mentions specific use cases, suggest the minimum scope set:

| Use case | Required scopes |
|---|---|
| Send/receive messages | `im:message`, `im:message.group_at_msg` |
| Read calendar | `calendar:calendar`, `calendar:calendar.event:readonly` |
| Read mail | `mail:user_mailbox`, `mail:user_mailbox.message:readonly` |
| Read drive | `drive:drive`, `drive:file:readonly` |
| Read docs | `docs:document`, `docs:document:readonly` |
| Read contacts | `contact:user`, `contact:user.basic` |

Start with `im:message` (always needed for any agent context), then add per use case. `--recommend` mode asks for the "auto-approve" subset — usually just `im:message` plus a couple of basics. Add more via `--domain` flag if `--recommend` is too restrictive.

## The CLI's safety prompts — what they mean

The CLI prints specific warnings during bind. They're not boilerplate:

- **"请勿将此机器人分享给他人或拉入群聊中使用"** — For `user-default`, the bot IS you. Adding it to a group means everyone in the group can read your data through it. Heed this.
- **"--force is required to switch from bot-only → user-default"** — Means your previous bind was safer; upgrading is irreversible without re-binding.
- **"DO NOT bind without user confirmation"** — Means the agent should not just run `bind` without asking. Always ask first.

## Decision tree

```
User wants Lark/Feishu connected
│
├─ Are they accessing personal data?
│  ├─ No  → bot-only
│  └─ Yes → user-default (warn about not sharing the bot)
│
├─ Did they say "first try / see how it works / test"?
│  └─ Yes → bot-only (reversible)
│
└─ Are they a developer setting up a workspace bot for team use?
   └─ bot-only (probably; user-default is wrong for team bots)
```

When in doubt, ask. The bind step is a one-line `clarify` call away, and the CLI itself refuses to proceed without confirmation.