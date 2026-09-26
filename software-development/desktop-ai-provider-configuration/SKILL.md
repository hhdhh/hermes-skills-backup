---
name: desktop-ai-provider-configuration
description: Use when configuring desktop AI clients with OpenAI-compa...
version: 1
license: MIT
metadata:
  hermes:
    tags: [desktop, ai, openai-compatible, sqlite, provider, models]
    related_skills: [autonomous-ai-agents/computer-use]
---

# Desktop AI provider configuration

> 完整描述：Use when configuring desktop AI clients with OpenAI-compatible providers. Inspect app storage, preserve existing data, apply additive provider/model changes, and verify with a real API request.

Configure installed desktop AI clients (especially Electron clients) against an OpenAI-compatible gateway without destroying existing settings.

## Scope and safety

- Treat API keys as secrets. Never print them, place them in a report, or repeat them in chat. If the user pasted a key into chat, recommend rotation after the task.
- Prefer the app's supported UI/API. Use direct local storage only when the app has no documented import/configuration path and the storage schema has been inspected first.
- Make additive changes by default: create a distinct provider ID and leave existing providers/models unchanged.
- Before modifying a database, close the app and create a timestamped backup. Never modify a live SQLite database with active writers.

## Workflow

1. **Discover the installation and state**
   - Confirm architecture, installed version, process state, data directory, and existing provider/model records.
   - Read the project/app documentation or inspect the installed schema; do not infer column names.
   - Check the gateway independently with `GET <base>/models` using the supplied key, but redact the key in all output.

2. **Map provider data**
   - Identify the provider table and model table, foreign keys, required fields, endpoint type, API-key entry format, capability format, and ordering conventions.
   - Use a preset OpenAI provider as a structural reference where possible, but create a separate user provider rather than overwriting the preset.
   - Only register models confirmed by the gateway or explicitly requested by the user. Preserve requested display names and limits, but do not claim limits are server-verified unless the API reports them.

3. **Apply transactionally**
   - Close the application gracefully, then back up the database.
   - Insert/update the provider and its models inside one SQLite transaction.
   - Use a stable provider ID and deterministic model IDs so rerunning the procedure is idempotent: delete/reconcile only records owned by that provider ID.
   - Set endpoint URL, authentication type, enabled state, streaming support, and model metadata explicitly; do not rely on defaults.
   - Never write the secret into shell history or logs. Prefer environment/file-descriptor input when possible.

4. **Restart and verify**
   - Restart the app and confirm its process is running.
   - Read back the exact provider and model records, checking URL, enabled state, model count, and IDs. Report only a masked/presence check for the key.
   - Perform a real minimal chat/completions request through the configured endpoint when feasible. A successful database write alone is not proof the configuration works.
   - Keep the backup path so the user can restore if the client migration changes.

## Cherry Studio notes

Cherry Studio 2.x stores user providers and models in `~/.config/CherryStudio/Data/cherrystudio.sqlite` on Linux. Relevant tables are `user_provider` and `user_model`; the provider endpoint is stored in `endpoint_configs`, and API credentials are stored in `api_keys` as entries with an ID, key, label, and enabled flag. The OpenAI-compatible endpoint type is `openai-chat-completions`.

For a custom OpenAI-compatible gateway, use a separate provider whose endpoint config contains the gateway base URL (usually including `/v1`), set `default_chat_endpoint` to `openai-chat-completions`, and add models with `endpoint_types` explicitly set. See `references/cherry-studio-sqlite-provider.md` for the inspected schema and verification recipe.

## Common pitfalls

- **Live SQLite writes:** Electron may keep WAL/shm files open; close all app processes before the write, then reopen the app.
- **Preset overwrite:** Editing the built-in `openai` row can affect future migrations and existing chats. Use a custom provider ID.
- **Model list mismatch:** A gateway may expose aliases or date-suffixed IDs not present in the user's requested list. Do not silently substitute IDs.
- **False verification:** Seeing a provider in settings proves persistence only. Verify `/models` and make one actual completion request.
- **Secret disclosure:** Never include the full API key in final output; advise rotation if it was pasted into a public/shared conversation.
