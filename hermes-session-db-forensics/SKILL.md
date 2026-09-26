---
name: hermes-session-db-forensics
description: Use when prior file/skill content is lost, a staged chang...
---

# Hermes Session DB Forensics

> 完整描述：Recover past-session work artifacts by mining the Hermes state DB (~/.hermes/state.db) directly — full tool-call payloads (write_file/skill_manage arguments), originals of truncated reply quotes, and session boundaries. Use when prior file/skill content is lost, a staged change never landed, session_search scroll is rejected, or a "[Replying to …]" quote is truncated and you need the original.

Recover or verify past-session artifacts from `~/.hermes/state.db` (SQLite, WAL mode — read-only queries are safe while the gateway runs; never write to it).

## When to go to the DB directly

- session_search scroll is rejected ("anchor lives in the current session lineage") but you need messages from the conversation's own history.
- You need the RAW tool-call payload — the exact content a past `write_file`/`skill_manage` wrote — not the rendered reply text.
- A user message references a prior message via `[Replying to: "…"]` — the quote is a truncated preview; always locate the full original before acting on instructions like "按你的建议改进…", because the actual suggestion list lives in that original.

## Schema that matters

- `sessions`: id, title, source, started_at / last_activity_at (epoch floats), message_count.
- `messages`: id, session_id, role, content, tool_calls, timestamp.
- `messages.tool_calls` is a JSON list of `{id, function: {name, arguments}}` where `arguments` is itself a JSON **string** — parse twice.

## Procedure

1. Locate the session: `SELECT id, title, last_activity_at FROM sessions WHERE title LIKE '%<关键词>%' ORDER BY last_activity_at DESC`; or match on message text (see CJK pitfall below).
2. Read the tail: select the last N messages by id for that session_id; convert epoch floats with `datetime.fromtimestamp` to sanity-check ordering and pick the window.
3. For lost file/skill content, scan `messages.tool_calls` where role='assistant': parse each call, filter by function name (`write_file`, `skill_manage`) and argument markers (target path or skill name); the `content` / `operations[].content` field holds the exact bytes previously written.
4. Re-land recovered content with `write_file` to its destination (or a workspace staging path first). If the destination is a skill directory and `skills.write_approval` is on, `skill_manage` only STAGES the change — `write_file` lands immediately; leave any duplicate staged op for the user to reject rather than re-submitting it.

## Pitfalls

- CJK text in FTS: `messages_fts MATCH '中文短语'` can silently return 0 rows — use `WHERE content LIKE '%中文短语%'` on the messages table instead.
- session_search hydration renders reply text but hides tool-call payloads; only direct SQL on `messages.tool_calls` exposes them.
- Quote fragments inside replies are escaped/mangled (markdown tables flattened to `\|`); match on a short distinctive substring, never the whole quote.
- One chat thread spans multiple session rows (a new session id per gateway restart). If the "original" message is not in the session you found, search neighboring sessions by timestamp window before concluding it is gone.
