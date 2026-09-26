# Hermes Agent upgrade runbook

Use the live CLI as authority because updater options evolve.

## Read-only preflight

```bash
hermes --version
hermes update --help
hermes update --plan
hermes config check
git -C ~/.hermes/hermes-agent status --short --branch
df -h "$HOME"
```

For a Git install, the tree should be clean or any local changes must be explicitly understood before proceeding. The update plan identifies running Hermes services and how they will restart.

## Safe update

```bash
hermes update --backup --yes
```

`--backup` forces both the quick pre-update snapshot and full `HERMES_HOME` archive. Capture the updater’s printed backup path and restore command. Do not use `--no-backup`, `--force`, or `--force-venv` for a routine update.

## Post-update verification

```bash
hermes --version
hermes config check
hermes doctor
hermes gateway status
git -C ~/.hermes/hermes-agent status --short --branch
```

Only check `gateway status` when the update plan showed the gateway as running; similarly verify any other planned service restarts. Confirm the backup file exists and has nonzero size. A successful outcome includes:

- new version reported and updater says up to date;
- config schema migration completed and validation passes;
- Git branch synchronized and clean for Git installs;
- all previously running Hermes services are running again;
- `hermes doctor` passes core checks (optional unconfigured integrations may remain warnings);
- full backup artifact exists, with the exact `hermes import <archive>` rollback command retained.

## Important interpretation

Hermes update output has intermediate successes such as “Code updated.” Continue through dependency syncing, Web UI build, bundled-skill sync, config migration, and service restart. Treat only the final completion plus independent post-update checks as success.
