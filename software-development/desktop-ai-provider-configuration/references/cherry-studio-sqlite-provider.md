# Cherry Studio SQLite provider reference

Observed in Cherry Studio 2.0.10 on Linux:

- Data directory: `~/.config/CherryStudio`
- Database: `Data/cherrystudio.sqlite`
- Provider table: `user_provider`
- Model table: `user_model`
- Provider endpoint JSON: `endpoint_configs`, keyed by `openai-chat-completions`, with `baseUrl`
- Provider API keys JSON: `api_keys`, entries shaped as `{id, key, label, isEnabled}`
- Provider defaults used by the app: `default_chat_endpoint = openai-chat-completions`, `is_enabled = 1`
- Model IDs are provider-scoped in the DB, e.g. `<provider_id>::<model_id>`
- Model endpoint declaration: JSON array `["openai-chat-completions"]`

Safe inspection:

```python
import sqlite3
c = sqlite3.connect('/home/USER/.config/CherryStudio/Data/cherrystudio.sqlite')
print(c.execute('pragma table_info(user_provider)').fetchall())
print(c.execute('pragma table_info(user_model)').fetchall())
```

Verification must redact the key:

```python
import hashlib, json
row = c.execute("select endpoint_configs,api_keys from user_provider where provider_id=?", (provider_id,)).fetchone()
keys = json.loads(row[1])
print('api_key_present=', bool(keys and keys[0].get('key')))
print('key_sha256_prefix=', hashlib.sha256(keys[0]['key'].encode()).hexdigest()[:12])
```

A real gateway check should query `<base_url>/models` with `Authorization: Bearer <key>`, report only HTTP status and model IDs, and then send a minimal completion request. Do not put the key in command output, shell history, backups shared with others, or the final response.
