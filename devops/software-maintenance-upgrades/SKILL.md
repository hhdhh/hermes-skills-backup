---
name: software-maintenance-upgrades
description: Safely upgrade installed software with backup and verific...
version: 1.0.0
metadata:
  hermes:
    tags: [upgrade, update, backup, rollback, verification, maintenance]
---

# Software Maintenance Upgrades

> 完整描述：Safely upgrade installed software with backup and verification.

Use this skill when the user asks to update or upgrade an installed application, CLI, service, or source checkout and expects a safe, verified result rather than only an upgrade command.

## Core workflow

1. **Identify the installation**
   - Record the current version, executable path, installation method, source/remote when relevant, and whether an update is actually available.
   - Prefer the application's own version and update-check commands over package-name guesses.

2. **Inspect risk before mutation**
   - Read the updater's live `--help` and use a read-only plan/check mode when available.
   - Check for local modifications, active branch divergence, running services, disk space, and current configuration validity.
   - Stop rather than overwrite unexplained user changes. Prefer updater-supported stashing or parking only when its behavior is explicit.

3. **Create a rollback point**
   - Use the application's supported full backup/snapshot facility when available.
   - Record the exact backup artifact and restore command.
   - Verify that the backup artifact exists before calling the operation safely recoverable.

4. **Run the supported updater**
   - Use the official in-place updater for the detected installation method.
   - Enable backup explicitly if the updater supports it.
   - Preserve user customizations and avoid destructive reset/force flags unless required and approved.
   - Allow the updater to migrate config and restart its own services when this is documented behavior.

5. **Verify the resulting state**
   - Confirm command exit status and inspect the complete completion section, not just an early success line.
   - Re-check installed version and upstream status.
   - Re-run configuration validation and the application's health/doctor command.
   - Verify every service the update plan said would restart is actually running afterward.
   - Check source-tree cleanliness/synchronization for Git installs.

6. **Report concise evidence**
   - State old → new version, config migration, service health, source/package status, and health-check result.
   - Link the verified backup artifact and provide the exact restore command.
   - Distinguish harmless optional-component warnings from failed core checks.

## Safety rules

- Never equate “download completed” or “code updated” with a completed upgrade; dependency sync, migrations, asset builds, and service restarts may still fail later.
- Never claim “latest” from local metadata alone; compare against the authoritative upstream release or updater check.
- Do not expose secrets while checking configuration. Report presence/validity, not credential values.
- Do not silently replace user-modified plugins, skills, configuration, or source edits.
- If health verification fails, either repair and re-run it or report the upgrade as incomplete with the rollback path.

## Product references

- Hermes Agent’s validated upgrade sequence and commands are in `references/hermes-agent-upgrade.md`.
