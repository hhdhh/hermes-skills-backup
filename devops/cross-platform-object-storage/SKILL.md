---
name: cross-platform-object-storage
description: Build upload/download tooling for S3-compatible object st...
version: 1
author: hermes-agent
license: MIT
metadata:
  hermes:
    tags: [rclone, s3, rustfs, minio, object-storage, windows, powershell, cross-platform, encoding]
    related_skills: [linux-desktop-system-config]
---

# Cross-platform object storage tooling (rclone + .ps1/.sh)

> 完整描述：Build upload/download tooling for S3-compatible object storage (rustfs, MinIO, etc.) that runs on both Linux and Windows, using rclone + PowerShell/Bash scripts authored from a Linux agent environment.

Author rclone-based upload/download scripts from a Linux agent that work on both Linux and Windows. Most relevant for S3-compatible stores (rustfs, MinIO, Ceph RGW, SeaweedFS) that need TLS + custom endpoint + AK/SK auth.

## When to use

- User needs to upload/download files between local disk and an S3-compatible object store
- The local environment may be **Linux** (Ubuntu/etc.) or **Windows** — often both
- The agent is running on **Linux** but must produce a script the user will run on Windows
- Single-tool solution preferred (rclone beats s5cmd/aws-cli for self-contained cross-platform: same CLI binary, same config format, same operations on both OSes)
- The "user keeps asking for new variants" pattern: upload only → download only → combined with `-Mode` switch → etc. Consolidate into ONE parameterized script early (see Pitfall P1).

## Core workflow

### 1. Verify connectivity before writing any script

```bash
# Can the agent reach the endpoint? (--no-check-certificate is normal for self-signed)
curl -k -sS -o /dev/null -w "HTTP %{http_code} | TLS=%{ssl_verify_result}\n" \
  --max-time 5 "https://<endpoint>:<port>/"

# Can rclone list buckets? (use whatever rclone is already on the agent)
rclone lsd <remote>: --no-check-certificate 2>&1 | head -20
```

If the agent can't reach the endpoint but the user can, that itself is useful info — write the script anyway, the user runs it, and tell them what to expect on the first invocation.

### 2. Author the script in English, with the config in a sidecar file

Even if the conversation is in Chinese and the user prefers Chinese, the **script body and config file must be pure ASCII or English** (see P1 — encoding). Put Chinese (or any non-ASCII) text in a separate `README.md` or in chat output, not in the .ps1 file.

Minimum file layout for a self-contained kit:

```
<kit-name>/
├── rustfs.ps1                  # Windows: combined upload/download via -Mode
├── setup-rustfs-upload.sh      # Linux: install rclone + write config + (optional) upload
├── rclone.conf                 # sidecar config: AK/SK + endpoint (chmod 600)
└── README.md                   # all human-facing instructions, can be Chinese
```

The user copies the directory to the other machine, runs the right script, done.

### 3. For Windows .ps1 scripts, follow the encoding-immune template

The template at `templates/rustfs.ps1` is the verified-working version. Key rules:

- **No non-ASCII characters anywhere in the .ps1 file** — not in comments, not in `Write-Host` strings, not in error messages. PowerShell on Win-CN reads the file in GBK by default; UTF-8 CJK chars become 2-byte sequences that look like syntax tokens (`=`, `,`, `(`) to the parser, causing `MissingExpressionAfterToken` errors.
- **Verify before shipping**:
  ```bash
  # On the Linux authoring machine, this MUST return 0
  grep -P '[\x{4e00}-\x{9fff}]' /path/to/rustfs.ps1 | wc -l
  ```
- Use `[ValidateSet("upload", "download")]` + `param()` block for parameter handling
- Use `& $RcloneExe @rcloneArgs` (splatting) to avoid backslash-escaping hell with quoted paths
- For rclone arg lists, build them as `@(...)` arrays and append conditionally (e.g. `--exclude`) — much cleaner than inline string interpolation
- Pre-download rclone.exe in the script itself (`Invoke-WebRequest` + `Expand-Archive` to script dir), so the user doesn't need a separate install step

### 4. The combined upload/download pattern (preferred for "集成" requests)

When the user asks to "combine" or "integrate" upload and download, don't ship two separate files — one parameterized file is cleaner:

```powershell
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("upload","download")]
    [string]$Mode,
    [string]$LocalPath = "",
    [string]$RemotePath = "",
    [string]$Bucket = "",
    [string]$RemotePrefix = "",
    [string[]]$Exclude = @(),
    [int]$Transfers = 8
)

# Auto-build RemotePath from Bucket+Prefix if RemotePath is empty
if ($Bucket -and -not $RemotePath) {
    if ($RemotePrefix -and -not $RemotePrefix.EndsWith("/")) { $RemotePrefix += "/" }
    $RemotePath = "rustfs:${Bucket}/${RemotePrefix}"
}

# ... rclone call is identical for both modes except copy-direction
& $RcloneExe @rcloneArgs
```

This is the pattern that the user explicitly requested ("集成到同一个脚本"). Bake it in.

### 5. Package as zip for handoff

```bash
cd /path/to/kit-dir
rm -f /tmp/kit.zip
zip -j -r /tmp/kit.zip . 2>&1 | tail -5
unzip -l /tmp/kit.zip   # verify contents
unzip -t /tmp/kit.zip   # verify integrity
```

Provide the absolute path in chat as a `[link](path)` so the user can grab it. Always include `unzip -l` and `unzip -t` output to prove the zip is sound (the user's first instinct will be "is the zip broken?" — answer that proactively).

## Pitfalls

**P1: PowerShell encoding trap — the #1 reason "first run fails"**

When the agent is on Linux and writes a .ps1 with Chinese comments or error messages, the file is UTF-8. When the user runs it on Windows-CN, PowerShell reads it in the system default codepage (GBK / cp936). Every Chinese character becomes a 2-byte sequence that doesn't match any valid GBK glyph, producing mojibake like `閰嶇疆`, `澶辫触`, `骞跺彂`. Worse, some of those garbled bytes happen to be `=`, `,`, `(`, `)` — the parser sees them as **syntax errors** (`MissingExpressionAfterToken`), not as encoding complaints. The user pastes a parse error and the agent thinks it's a logic bug.

**The rule is absolute: the .ps1 file contains zero non-ASCII characters.** Verify with `grep -P '[\x{4e00}-\x{9fff}]' file.ps1 | wc -l` returning 0 before handoff. If the user needs Chinese, put it in a separate `README.md` or in the chat reply.

Symptom signature from this session (Aug 2026):
```
所在位置 C:\Users\User\Downloads\...\rustfs.ps1:35 字符: 32
+     [int]$Transfers        = 8,                       # 骞跺彂涓婁紶/...
+                                ~
","后面缺少表达式。
```
The `骞跺彂` etc. are mojibake of `并发上传/下载数`. The comma after `8` is actually a UTF-8 continuation byte of a CJK char that survived partial decoding — PowerShell's parser doesn't know it should be a comment delimiter and tries to parse the rest of the line as code.

**P2: agent's rclone vs. target machine's rclone**

The agent can run rclone on Linux and verify the connection. But the user's Windows machine needs its own rclone.exe. The script must download it on first run, not assume the user installed it manually:

```powershell
$RcloneZipUrl = "https://downloads.rclone.org/rclone-current-windows-amd64.zip"
# ... Invoke-WebRequest + Expand-Archive
```

If you skip this, the user will hit "rclone not recognized" and blame your script. ~30MB, takes 20-30s on a typical connection.

**P3: zip integrity complaints on the user's side**

If you skip `unzip -t` verification, the user will. Don't make them ask "is the zip ok?" — proactively show the test result in the chat reply. Same for `unzip -l` (proves the right files are inside).

**P4: hardcoded AK/SK leakage risk**

`rclone.conf` contains a credential with full bucket control. Warn the user every time:
- `chmod 600` on Linux; on Win, set NTFS ACL to "only me can read"
- Never commit to git
- Never send via email / WeChat / Lark attachments
- Provide a "rotate the key" contact in case of compromise

**P5: `rclone copy` vs `rclone sync` — never default to sync**

`copy` = add/update only, never delete. `sync` = make destination identical to source, **deleting anything extra**. If the user has both upload and download in the same script, the default MUST be `copy`. Even on upload, accidentally using `sync` could wipe an existing dataset if the local path is empty (e.g. user pointed at the wrong directory).

If the user asks for "sync", add a `-WhatIf`-style confirmation prompt or at minimum a loud `Write-Host -ForegroundColor Red` warning.

**P6: Windows path with spaces and the quoting layer**

rclone args go through three quoting layers: PowerShell → cmd → rclone. A path like `D:\my data\2026-08-17` needs `"..."` in PowerShell, then `"..."` again for rclone. The cleanest pattern is splatting:

```powershell
$rcloneArgs = @("copy", "`"$LocalPath`"", "`"$RemotePath`"") + $CommonArgs
& $RcloneExe @rcloneArgs
```

Don't try to build the command as a single string with nested escapes — it's not worth the cognitive load.

**P7: `--exclude` as a separate flag per pattern, not comma-joined**

PowerShell's `$Exclude` is `string[]`. rclone wants `--exclude "*.log" --exclude "*.tmp"`, not `--exclude "*.log,*.tmp"`. Build the args with a loop:

```powershell
foreach ($e in $Exclude) { $rcloneArgs += @("--exclude", "`"$e`"") }
```

**P8: `rclone.conf` discovery from script directory**

Use `$PSScriptRoot` (not `$PSCommandPath` or `$MyInvocation.MyCommand.Path`) — `$PSScriptRoot` resolves correctly even when the script is dot-sourced or run via `-File`. Default to `$PSScriptRoot\rclone.conf` so the script "just works" when dropped next to its config.

## Reference recipes

- `references/rustfs-s3-setup.md` — full rclone + S3-compatible remote config recipe, with the verification commands and the S3 quirks (force_path_style, provider=Other, no_check_certificate).
- `references/encoding-debugging.md` — the exact decode ladder for "PowerShell parse error + mojibake" — what to grep for, what the error messages look like, and why the parser thinks the comment is code.

## Templates

- `templates/rustfs.ps1` — combined upload/download .ps1 (encoding-safe, splat-args, auto-download rclone, ValidateSet Mode). Copy and adapt bucket name in rclone.conf.
- `templates/setup-rustfs-upload.sh` — Linux self-installer (apt or curl-install rclone, write rclone.conf, verify, optional upload if path arg given). Same config format as the .ps1.
- `templates/rclone.conf` — minimal S3-compatible config (type/provider/endpoint/auth/no_check_certificate/force_path_style).
