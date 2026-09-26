---
name: linux-workstation-migration
description: Use when reinstalling Linux or moving to a new workstation.
version: 1
metadata:
  hermes:
    tags: [linux, migration, reinstall, backup, restore, verification]
---

# Linux workstation migration

Plan and verify a Linux reinstall or machine move without losing application state. Treat migration as **backup → independent verification → reinstall → restore → live validation**, not as copying a few visible files.

## Trigger

Use when the user plans to:

- reinstall or replace a Linux distribution;
- format, repartition, dual-boot, or replace a disk;
- move an agent, developer environment, or user profile to another machine;
- preserve an application's identity, history, configuration, credentials, and local automation.

## Core workflow

### 1. Inventory before prescribing

Inspect the live machine first. Establish:

- current username and home directory;
- target OS and whether the username/home path will change;
- disk layout, free space, encryption, and available external backup media;
- application-native backup/export commands;
- state stored outside the application's main directory;
- services that should be stopped or snapshotted consistently.

Do not infer the backup scope from an install directory alone. Separate **reinstallable code/binaries** from **irreplaceable data and credentials**.

### 2. Prefer native, consistent exports

If the application provides a documented backup/export command, prefer it over a raw copy. Native exports can safely snapshot active databases, omit runtime PID/lock files, and preserve the expected restore layout.

Use a manual archive or `rsync` only as a documented fallback. For SQLite-backed applications, do not casually copy only the main `.db` while writers are active: WAL/SHM state may matter. Use the application's backup command, a SQLite backup operation, or stop writers first.

### 3. Put the backup outside the disk being erased

A backup remaining on another partition of the same physical disk is not sufficient when repartitioning or reinstalling. Copy it to one or more of:

- removable USB/SSD;
- NAS or another computer;
- private encrypted cloud storage.

Credentials and tokens make full application backups sensitive. Warn against public links and unencrypted shared storage.

### 4. Verify before destructive work

A backup is not complete until verified:

1. Confirm the archive exists on the external destination.
2. Run the archive format's integrity test.
3. Record a SHA-256 checksum next to the archive.
4. Re-read or copy the archive from the external medium, not merely the source path.
5. Confirm critical categories are represented: configuration, secrets/auth, memory/history, custom extensions, jobs/automation, and user-created workspaces.
6. Keep the old installation intact until restore validation succeeds whenever possible.

Never tell the user it is safe to erase the disk based only on a successful archive-creation exit code.

### 5. Preserve path compatibility when practical

Keeping the same username and home path reduces breakage from absolute paths in configuration, cron jobs, workspaces, launchers, and scripts. If paths change, explicitly search restored configuration for the old home prefix and update only confirmed path fields.

### 6. Restore in dependency order

1. Install the target OS and updates.
2. Install prerequisites and the application's current supported release.
3. Restore/import the application data using its native command.
4. Restore external companion tools and user project data separately.
5. Re-authenticate machine-bound OAuth/device credentials if required.
6. Reinstall or re-enable system services only after configuration is restored.

Do not restore old virtual environments, compiled dependencies, or OS-specific binaries unless the application's documented backup format intentionally includes them. Recreate them on the new OS.

### 7. Validate behavior, not just files

Run both static and live checks:

- version and executable path;
- built-in doctor/config validation;
- expected profiles, histories, memories, skills/plugins, and scheduled jobs;
- one real provider/API request;
- one resumed historical session if continuity matters;
- gateway/service status and one real incoming/outgoing message where applicable;
- any path-sensitive workspace or custom launcher.

Document items that require re-login or path changes. “Import completed” is not equivalent to a successful migration.

## Deliverable pattern

When the user wants the migration handled, provide a small number of self-contained stages rather than scattered commands:

- **Stage A — backup and verify** on the old system;
- **Stage B — install and restore** on the new system;
- **Stage C — validate and report**.

For sudo-requiring setup, acquire credentials once in a user-run script (`sudo -v`) and fail fast (`set -euo pipefail`). Never embed or request the user's sudo password.

## Application references

- Hermes Agent migration: `references/hermes-agent-migration.md`

## Pitfalls

- Backing up to the same physical disk that will be repartitioned.
- Copying only settings while omitting sessions, memory, credentials, or automation.
- Treating a profile-sharing export as a full machine backup when it intentionally excludes secrets.
- Copying an active SQLite database without a consistent snapshot method.
- Restoring an old application code checkout instead of installing fresh code and importing data.
- Claiming success before checksum/archive tests and a real post-restore operation.
- Forgetting companion state outside the main application directory (CLI credentials, custom launchers, local web UIs, project repositories).