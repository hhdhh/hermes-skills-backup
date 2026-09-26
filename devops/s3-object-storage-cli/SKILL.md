---
name: s3-object-storage-cli
description: Use when user mentions rustfs, MinIO, S3 bucket, or needs...
version: 1
author: hermes-agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [s3, rustfs, minio, rclone, object-storage, data-transfer, cross-platform]
    related_skills: [lark-feishu-cli, linux-desktop-system-config, hermes-agent]
---

# S3-compatible Object Storage — CLI Toolkit

> 完整描述：Push/pull files to S3-compatible object stores (rustfs, MinIO, AWS S3, Ceph RGW) from any client. Use when user mentions rustfs, MinIO, S3 bucket, or needs to copy data to/from a custom S3 endpoint.

Drive **rclone** against S3-compatible object stores (rustfs, MinIO, AWS S3, Ceph RGW, SeaweedFS) from any client OS. Build self-contained upload/download scripts that any teammate can run with a one-liner.

## When to use

- User has an S3-compatible endpoint (rustfs, MinIO, etc.) and needs to upload or download data
- Building a cross-platform tool (Win + Linux + macOS) that wraps `rclone`
- Need to bundle a config file with AK/SK that survives file transfer
- User pastes an S3 console URL like `https://rustfs.example.com:8444/.../?bucket=foo` — this is the bucket console, the endpoint hostname:port is the API endpoint
- Verifying an existing AK/SK pair can talk to a given endpoint

**Do not use** for building S3 applications (use AWS SDK / boto3). This is for **humans moving data**.

## Critical facts

1. **`rclone` is the universal tool.** Same binary configures, uploads, downloads, syncs, mounts, serves WebDAV. Avoid building custom HTTP-signed code — rclone handles SigV4, retries, multipart, checksums, resume.

2. **rustfs and MinIO are S3-API clones.** If you have AK/SK + endpoint URL + bucket name, rclone config is 4 lines:
   ```ini
   [name]
   type = s3
   provider = Other           # for rustfs/MinIO; for AWS S3 omit this line
   endpoint = https://host:port
   access_key_id = ...
   secret_access_key = ...
   force_path_style = true   # required for rustfs/MinIO; AWS S3 uses virtual-hosted (false)
   ```

3. **Self-signed / private CA certs are common for internal rustfs/MinIO.** Always pass `--no-check-certificate` to rclone. Don't try to add the CA to the system trust store — that's a yak shave.

4. **PowerShell scripts written in Linux UTF-8 break on Windows default encoding.** See Pitfall P1. This is the #1 source of "first run error" reports for cross-platform .ps1 tools.

5. **S3 "console URL" vs "API endpoint"** are different. Console: `https://host:8444/rustfs/console/browser/?bucket=foo` → API endpoint: `https://host:8444`. Always extract the host:port part, drop the path.

6. **`copy` vs `sync` is a footgun.** `copy` only adds, never deletes on destination. `sync` makes destination identical — anything on the dest not in source gets **deleted**. Default to `copy`; make `sync` opt-in.

## Core workflow

### 1. Discover what the user has

Before writing config, ask:
- Is this rustfs, MinIO, AWS S3, or something else? (affects `provider` line and path-style)
- Do you have the endpoint URL? (extract from console URL if needed)
- Do you have access_key_id + secret_access_key? (or is the user using SSO/OIDC? — different flow)
- Is the cert self-signed? (almost always yes for internal rustfs)
- Where is the data going? (bucket name + optional prefix)

If the user only has a console URL like `https://rustfs.example.com:8444/rustfs/console/browser/?bucket=robot-289`, you can extract `endpoint = https://rustfs.example.com:8444` and `bucket = robot-289` directly. They still need AK/SK.

### 2. Build a self-contained rclone config

Write `rclone.conf` with 600 perms on Linux/macOS, NTFS-restricted on Windows. **Never** put it in a publicly shared path. Treat the secret_access_key as a password.

### 3. Verify before promising anything

```bash
rclone listremotes                          # should show your remote name
rclone lsd <remote>:                       # should list buckets
rclone lsd <remote>:<bucket>               # should list prefixes
rclone size <remote>:<bucket>/<prefix>     # should report size
```

If any of these fail with 403/SSL errors, stop and diagnose before letting the user run 100GB uploads.

### 4. Generate client scripts

See templates/ for the working `rustfs.ps1` and `rustfs.sh` from the 2026-08-17 session. They are battle-tested against:
- Windows PowerShell 5.1+ (default on Win 10/11)
- Linux with apt / yum / dnf / pacman / brew
- macOS

### 5. Bundle as zip for distribution

The zip is the unit of transfer. Don't make the user copy 4 files manually. zip -j produces a flat archive that unzips cleanly anywhere.

## Pitfalls

### P1: UTF-8 .ps1 breaks on Windows PowerShell — **the #1 first-run failure**

When you write a PowerShell script on Linux (UTF-8 default) with Chinese comments, then ship it to Windows PowerShell (which opens .ps1 as system codepage, often CP936/GBK on Chinese Windows), the Chinese bytes get decoded as garbage characters. Sometimes the garbage contains `,` `(` `)` `=` — which PowerShell parses as **syntax errors**, not warnings. The error message looks like:
```
所在位置 ...ps1:35 字符: 32
+     [int]$Transfers        = 8,                       # 骞跺彂涓婁紶/...
+                                ~
","后面缺少表达式。
```
"骞跺彂" is "并发" misdecoded.

**Fix:** .ps1 files distributed cross-platform must be **English-only** in code AND comments. Put Chinese in a separate `DOCS.md` / `README.md` that PowerShell never parses. Verify with:
```bash
grep -P '[\x{4e00}-\x{9fff}]' script.ps1 | wc -l   # must be 0
```

User corrections in 2026-08-17 session triggered this finding — they reported the parse error and we diagnosed it together.

### P2: PowerShell execution policy blocks unsigned scripts

By default, Windows blocks `.ps1` files. Common user mistakes:
- Running `Set-ExecutionPolicy -Scope CurrentUser` in a **non-admin** PowerShell → effective
- Running it in an **admin** PowerShell → the CurrentUser scope may not apply to the current process; use `-Scope LocalMachine` from admin, or `-Scope Process` for a one-shot

**Workaround that always works** (no policy change needed): provide a `run.bat` that calls PowerShell with `-ExecutionPolicy Bypass`:
```bat
@echo off
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0script.ps1" %*
```
Double-click `run.bat` or call it from cmd. Bypasses all policy issues.

### P3: Endpoint vs console URL confusion

User pastes `https://rustfs.gz.autolife.ai:8444/rustfs/console/browser/?bucket=robot-289`. They think this is the endpoint. It's the **web UI**. Strip the path:
- Endpoint: `https://rustfs.gz.autolife.ai:8444`
- Bucket: `robot-289`

### P4: Don't assume `sync` is safe

`rclone sync` is "make destination identical to source" — it **deletes files in destination that don't exist in source**. If the user syncs their laptop's `~/data` to a shared bucket, then deletes a file locally, the next sync **deletes it from the bucket too**. Default scripts to `copy`. If user explicitly wants sync, force them to type `--sync` flag and confirm.

### P5: Path-style vs virtual-hosted

rustfs/MinIO require `force_path_style = true` (URLs look like `https://host/bucket/key`). AWS S3 prefers virtual-hosted (`https://bucket.s3.amazonaws.com/key`). Wrong setting = 403 errors that look like auth failures.

### P6: Don't auto-create Windows scheduled tasks or shortcuts

Users get spooked when scripts silently install things. Always surface what the script will do (download rclone, write config, etc.) before running.

### P7: rclone.conf contains secrets — handle like SSH keys

The file's `secret_access_key` line = full account takeover if leaked. Don't:
- Commit to git
- Email as attachment
- Paste into public chat

Do:
- `chmod 600` on Linux/macOS
- Use private transfer (WeChat 1-on-1, USB stick)
- Sanitize before sharing scripts (use `***` placeholders in any example)

### P8: 1.60.x is 2022-era. Newer is better

Anything before rclone 1.65 (mid-2023) is missing S3-compatible store improvements. 1.75+ is current as of 2026-08. The user accepted a "reinstall" earlier in the session when we discovered the pre-installed version was actually already current — that's fine, but always check `rclone version` before assuming an upgrade is needed.

## Reference recipes

- `references/rustfs-2026-08-17-session.md` — full session log: how the rustfs tool was built, what failed, what worked
- `references/endpoint-discovery.md` — extracting endpoint + bucket from various console URL shapes
- `references/troubleshooting.md` — error → fix table for the most common issues

## Templates

- `templates/rustfs.ps1` — Windows PowerShell upload/download all-in-one (English-only, no encoding issues)
- `templates/rustfs.sh` — Linux/macOS bash with download/upload/lsd/size/setup subcommands
- `templates/rclone.conf` — minimal S3-compatible config
- `templates/DOCS.md` — Chinese user-facing documentation template

## Scripts

- `scripts/bundle-zip.sh` — rebuild the distribution zip from a source dir

## Verification

After building the tool, always run:
```bash
rclone listremotes              # config is loaded
rclone lsd <remote>:            # endpoint reachable, AK/SK works
rclone lsd <remote>:<bucket>    # bucket exists
rclone size <remote>:<bucket>/  # user can see actual size before pulling
```
If any of these 4 fail, the user's data is unreachable. Diagnose before letting them start a 100GB transfer.
