# Hermes Agent migration

Use this reference when moving a complete Hermes installation to a freshly installed OS or another machine. Official documentation is the source of truth; confirm command syntax with the installed CLI before execution.

## What carries the agent's continuity

Hermes uses its home directory (normally `~/.hermes`, or `$HERMES_HOME`) for the state that makes an installation feel like the same agent:

- `config.yaml` — settings and model/tool configuration;
- `.env` and `auth.json` — credentials and OAuth/token pools;
- `state.db` — canonical session metadata and message history;
- `memories/` and `USER.md`/memory files — durable user and agent memory;
- `skills/`, plugins, hooks, skins, widgets, and other custom extensions;
- `cron/`, gateway/channel configuration, profiles, and routing state;
- application workspaces stored under the Hermes home.

The `hermes-agent/` source checkout is reinstallable code and is excluded from a normal full backup. Install a fresh current release on the target OS rather than transplanting its old virtual environment.

## Preferred full-machine path

On the source machine, inspect live help first:

```bash
hermes backup --help
hermes import --help
```

Create a **full** backup (not `--quick`) directly on external media:

```bash
hermes backup -o /media/$USER/BACKUP/hermes-full-backup.zip
sha256sum /media/$USER/BACKUP/hermes-full-backup.zip \
  > /media/$USER/BACKUP/hermes-full-backup.zip.sha256
unzip -t /media/$USER/BACKUP/hermes-full-backup.zip
```

The full backup is the correct choice for machine migration because it includes global state, profiles, sessions, API keys, and auth. A quick backup is useful as an additional emergency snapshot but should not silently replace the full archive.

On the target machine:

1. Prefer the same username/home path if practical.
2. Install Hermes using the current official installer/documentation.
3. Verify the copied archive checksum from the destination medium.
4. Import the archive, using `--force` only when intentionally overwriting the fresh Hermes home.
5. Run `hermes doctor`, inspect profiles and cron jobs, and make one real model call.

Typical commands after installing Hermes:

```bash
sha256sum -c hermes-full-backup.zip.sha256
hermes import /path/to/hermes-full-backup.zip --force
hermes doctor
```

## Full backup versus profile export

- `hermes backup`: full machine migration; includes all profiles, global configuration, credentials, sessions, and data; ZIP format.
- `hermes profile export`: moves or shares one profile; credentials are deliberately excluded; tar.gz format.

Do not recommend profile export alone when the user wants the same complete agent on a new OS.

## Manual fallback

If native backup cannot be used, copy the Hermes home while excluding the reinstallable source checkout, preferably after stopping active Hermes/gateway writers:

```bash
rsync -av --exclude='hermes-agent' ~/.hermes/ /external/path/.hermes/
```

Treat this as fallback, not first choice. Confirm SQLite consistency and preserve hidden files.

## External companion state

Ask about and inventory tools outside `~/.hermes`, such as:

- coding-agent credentials (`~/.codex`, etc.);
- custom shell launchers in `~/.local/bin`;
- separately installed local web interfaces;
- user repositories and documents;
- browser profiles or external MCP applications.

Do not claim `hermes backup` includes these.

## Post-restore acceptance checks

- `hermes --version` resolves to the new installation.
- `hermes doctor` reports no blocking problem.
- Model/provider configuration is present without printing secrets.
- Expected profiles, memories, skills, session history, and cron jobs exist.
- A historical session can be found/resumed.
- A real model request succeeds.
- Gateways are reinstalled/restarted and tested if used.
- Absolute paths referencing the old home directory are identified and corrected.
- Machine-bound OAuth logins are refreshed where needed.

Keep the external backup until all checks pass.