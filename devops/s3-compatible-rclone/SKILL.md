---
name: s3-compatible-rclone
description: Use when user mentions rustfs, S3 endpoint, AK/SK, bucket...
version: 1
author: hermes-agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [rclone, s3, rustfs, minio, object-storage, upload, download, cross-platform]
---

# rclone + S3-compatible object storage

> 完整描述：Use rclone against any S3-compatible object storage (rustfs, MinIO, SeaweedFS, etc). Use when user mentions rustfs, S3 endpoint, AK/SK, bucket, or wants cross-platform upload/download scripts.

A complete pattern for upload/download/copy against any S3-API-compatible object store (rustfs, MinIO, SeaweedFS, Ceph RGW, etc) from Linux, macOS, or Windows. The user often has a Web console URL, an endpoint, an `access_key`/`secret_key` pair, and a bucket name.

## When to use

- User mentions `rustfs:`, `S3 endpoint`, `bucket`, `AK/SK`, or any object-storage product
- "How do I upload files from Windows to rustfs"
- "Set up rclone for `<brand>` storage on another Linux box"
- "Download data from rustfs to my local machine"
- "Build a self-contained upload/download script for a colleague"

**Do not use** for general AWS S3, GCS, or Azure Blob — those have native tools and different rclone providers. This skill targets the S3-compatible sub-tree (provider = `Other`).

## Critical facts

1. **rclone v1.60+ required for current S3 providers.** Always check `rclone version` first. The 1.60.1 Ubuntu/Debian package is from 2022 and is severely outdated. Install the official latest via the install script:
   ```bash
   curl -fsSL https://rclone.org/install.sh | sudo bash
   ```
   See "Install on a remote box you don't have sudo for" below for the agent-PTY workaround.

2. **S3-compatible stores almost always need `provider = Other` + `force_path_style = true`.** Without `force_path_style`, rclone uses virtual-host style URLs (`<bucket>.<endpoint>`) which works for AWS but breaks for most self-hosted S3.

3. **Self-signed certs need `no_check_certificate = true`** (config) and `--no-check-certificate` (CLI flag, both required). Forget the CLI flag = silent TLS failure.

4. **rclone.conf contains AK/SK = full control of the bucket.** Treat it like a private key. Never put in git, never email, never share via public link. Permission `chmod 600` it.

## Core workflow

### 1. Locate the config file

```bash
rclone config file
# Output: /home/<user>/.config/rclone/rclone.conf
mkdir -p ~/.config/rclone
chmod 700 ~/.config/rclone
```

### 2. Write a remote entry

```ini
[rustfs]
type = s3
provider = Other
env_auth = false
access_key_id = YOUR_AK
secret_access_key = YOUR_SK
endpoint = https://host:port
force_path_style = true
no_check_certificate = true   # only if self-signed
```

The `[name]` (e.g. `rustfs`) becomes the rclone remote alias. Reference it as `<name>:<bucket>/<prefix>/`.

### 3. Verify connectivity before any copy

```bash
# List buckets (tests AK/SK + endpoint + network + TLS)
rclone lsd <name>: --no-check-certificate

# List a specific bucket
rclone lsd <name>:<bucket> --no-check-certificate

# See total size before pulling
rclone size <name>:<bucket>/<prefix>/ --no-check-certificate
```

If `lsd` returns empty buckets or 403, debug in this order: **network → TLS → AK/SK → bucket exists → prefix path**.

### 4. Copy (always prefer `copy` over `sync`)

```bash
rclone copy <src> <name>:<bucket>/<prefix>/ -P \
  --no-check-certificate \
  --retries 10 --retries-sleep 5s \
  --transfers 8 --checkers 16
```

- `-P` = real-time progress (transfer stats + ETA)
- `--transfers N` = concurrent files. 8 is safe; bump to 16-32 for many small files, drop to 4 for big files
- `--retries/--retries-sleep` = resilience on flaky links
- `Ctrl+C` mid-run is safe — re-run the same command, rclone skips what's already done (checks size + mtime + md5)

## Pitfalls

### P1: PowerShell scripts with Chinese comments break on Windows

This is a **silent gotcha that wasted a full user round-trip**. If you write a `.ps1` script on a Linux/macOS box with UTF-8 encoded Chinese comments, and the user runs it in Windows PowerShell (which reads the file using the system default codepage — GBK on Chinese Windows), every Chinese character in a comment becomes a 2-3 char sequence of garbage. If that garbage happens to contain `=`, `,`, `(`, `)`, etc., PowerShell's parser treats the comment line as malformed syntax and refuses to load the file.

**Rule: any PowerShell script you author cross-platform must have ZERO non-ASCII characters in its source. Put all Chinese/extended text in a separate `.md` documentation file.** The user can read the `.md` separately, and the script parses cleanly on any Windows locale.

This applies to comments AND string literals. Even `Write-Host "配置完成"` will break the parser on en-US Windows where "配" has no GBK mapping.

### P2: PowerShell execution policy blocks unsigned scripts

The user's first attempt at running `.\rustfs.ps1` failed with `未对文件进行数字签名 / UnauthorizedAccess`. This is the default policy on Windows client SKUs. Three solutions, in order of preference:

```powershell
# 1. Per-user policy (one-time, persists for that user)
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
# Then type Y at the prompt

# 2. Per-process policy (only the current window)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 3. Single-command bypass (cleanest UX, no state change)
powershell -ExecutionPolicy Bypass -File "C:\path\to\rustfs.ps1" -Mode download -RemotePath "rustfs:bucket/" -LocalPath "D:\out"
```

**Best UX for handing a script to a colleague: ship a `run.bat` wrapper** in the same directory that always uses bypass:

```bat
@echo off
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0rustfs.ps1" %*
```

Then the user just double-clicks `run.bat` or runs `run.bat -Mode download ...` from `cmd`. Zero policy setup needed.

### P3: `--content @/absolute/path` is rejected by lark-cli and similar tools

Many CLI tools that accept file content via `@file` syntax reject absolute paths. They want relative paths "within the current directory". Workaround: pipe via stdin with `-` placeholder.

```bash
# WRONG (most tools)
lark-cli docs +create --content @/home/me/doc.md ...

# RIGHT
cat /home/me/doc.md | lark-cli docs +create --content - ...
```

Always check `--help` for the `(supports @file, -)` hint.

### P4: rclone's `sync` DELETES files in the destination

`rclone sync A B` makes B look exactly like A — anything in B not in A gets **deleted**. This is dangerous for S3-compatible stores where the destination might have other users' data. **Default to `copy` (only adds, never deletes).** Tell the user explicitly when you use `sync`.

### P5: Don't add `--update` blindly

`--update` skips files where the destination is newer than the source. If the user re-runs a transfer and the source has been edited, those edits will be silently skipped. Only use it when re-uploading the same logical snapshot to an existing destination.

### P6: Cross-machine file transfer — pick the right channel

For a 6 KB script the user wants on another box, options in order of preference for the user's environment (Autolife internal):

```bash
# A. scp (if SSH is open between the two machines)
scp /local/rustfs.sh user@host:/tmp/

# B. LAN HTTP serve (if not, fast and no auth)
cd /local/dir && python3 -m http.server 8000
# On the other box:
curl http://<lan-ip>:8000/rustfs.sh -o rustfs.sh

# C. U盘 / 飞书 / 钉钉 — fine for text scripts, NEVER for .conf with real AK/SK
```

**Never** put `rclone.conf` (with real AK/SK) on a public share. U盘 is fine; Slack public channel is not.

### P7: The 8 vs 16 transfer tuning rule

| File size | Recommended `--transfers` |
|---|---|
| < 1 MB (logs, JSON, small images) | 16-32 |
| 1 MB - 100 MB (typical data) | 8 (default) |
| > 100 MB (videos, archives) | 4-8 |

For high-latency cross-region transfers, also add `--checkers 4` to avoid hammering the listing API.

## The cross-platform script template

A script that hands off cleanly to a colleague's machine (any OS) needs these properties:

1. **Self-installing** — first run downloads rclone if missing
2. **Idempotent config** — doesn't overwrite an existing `rclone.conf` (re-runs are safe)
3. **Verify before copy** — `lsd` first, fail fast with a clear error if remote is unreachable
4. **Real-time progress** — `-P` with `--stats 10s --stats-one-line`
5. **Resumable** — `--retries`, sensible defaults so `Ctrl+C` and re-run works
6. **Excludes as a parameter** — `-Exclude "*.log","*.tmp"` (Windows PowerShell array syntax)
7. **No non-ASCII in PowerShell** (P1)
8. **Documented troubleshooting table** in a separate `.md`

The Linux/macOS shell version and the Windows PowerShell version share the same flag set; the only difference is argument syntax.

## Reference recipes

- `references/windows-powershell-script.md` — annotated PowerShell template, encoding pitfall deep-dive, run.bat wrapper
- `references/linux-shell-script.md` — annotated bash template, multi-distro install detection, environment variable overrides
- `references/transfer-tuning.md` — when to bump transfers/checkers, when to use bandwidth limits, when to run backgrounded
