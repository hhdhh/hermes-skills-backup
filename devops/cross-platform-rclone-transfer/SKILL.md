---
name: cross-platform-rclone-transfer
description: "Use when packaging rclone transfers for Windows/Linux."
version: 1
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [rclone, s3, powershell, bash, upload, download]
---

# Cross-platform rclone transfer bundles

Build and verify portable upload/download bundles for S3-compatible remotes. The deliverable should be a working artifact, not just scattered commands.

## Bundle shape

Prefer one class-level bundle:

- `rclone.conf` — credentials and remote definition; keep separate from scripts.
- `rustfs.ps1` or equivalent — Windows upload/download entry point.
- `rustfs.sh` or equivalent — Linux/macOS setup/upload/download/inspection entry point.
- `README.md` — quick start.
- `DOCS.md` — complete usage and troubleshooting.

Never embed access keys in reusable scripts. Scripts may locate a bundled config next to themselves and install/merge it into the platform default location. Treat the config as sensitive and redact it in logs and reviews.

## PowerShell rules

1. Keep Windows PowerShell 5-compatible scripts ASCII-only when the file may be opened under a legacy Chinese code page. Put Chinese instructions in Markdown, not executable source.
2. When invoking a native executable with a PowerShell argument array, pass raw argument values:
   ```powershell
   $args = @("copy", $LocalPath, $RemotePath, "--config=$RcloneConf")
   & $RcloneExe @args
   ```
   Do **not** inject literal quote characters such as ``"`"$LocalPath`""``. Array splatting already preserves spaces.
3. Do not pipe a native verification command to `Select-Object -First N` before checking `$LASTEXITCODE`; the pipeline can obscure the native result or stop it early. Redirect to `Out-Null`, then check `$LASTEXITCODE`.
4. Downloaded `.ps1` files may carry a Mark-of-the-Web marker. Document both:
   ```powershell
   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
   Unblock-File .\tool.ps1
   ```
   Use one-shot `-ExecutionPolicy Bypass` only as a fallback, especially under managed enterprise policy.
5. With `rclone copy`, a single-file download still takes a destination **directory**, not a renamed destination file. Document this explicitly.

## Bash rules

1. Start with `set -euo pipefail` and quote every local and remote path.
2. Resolve the script directory portably and require the bundled config beside the script:
   ```bash
   SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
   BUNDLED_CONF="$SCRIPT_DIR/rclone.conf"
   ```
3. Never overwrite an existing non-empty rclone config merely because it lacks the desired remote. Preserve existing remotes and append the new section. If the section already exists, leave it unchanged unless replacement was explicitly requested.
4. Set the installed config to mode `600`.
5. Provide safe read-only probes (`lsd`, `size`) alongside `upload`, `download`, and `setup`.
6. Use `copy`, not `sync`, by default. Explain that `sync` can delete destination-only files.

## Verification gate

Before delivery:

1. Inventory actual filenames and compare them against every filename mentioned in README/DOCS. Remove stale names.
2. Run `bash -n` and ShellCheck when available.
3. Test Bash argument boundaries with a mock `rclone`, including spaces in source, destination, remote prefix, and config path.
4. Run a read-only live smoke test such as `rclone lsd` when credentials/network are available.
5. Parse PowerShell with `pwsh` when available. If unavailable, state that limitation and at minimum verify encoding, NUL absence, argument-array construction, and absence of legacy non-ASCII source.
6. Verify credential-file permissions without printing credentials.
7. Keep full instructions synchronized with actual script behavior.

## Documentation style

Lead with copy-paste commands. Separate first-time setup from routine upload/download. State which files must remain together. Include interruption/resume behavior, path-with-spaces examples, and a concise security section.

## References

- `references/portable-bundle-review.md` — condensed review checklist and proven failure modes from a Windows/Linux S3 transfer bundle.