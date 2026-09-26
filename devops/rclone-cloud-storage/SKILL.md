---
name: rclone-cloud-storage
description: Move files to/from S3-compatible object storage via rclone.
metadata:
  hermes:
    tags: [rclone, s3, object-storage, file-transfer, cross-platform, rustfs, minio]
    related_skills: [linux-desktop-system-config]
---

# rclone + S3-compatible object storage

Self-hosted S3-compatible stores (RustFS, MinIO, Ceph RGW, SeaweedFS) all expose
the same S3 API surface. rclone talks to them with the `s3` backend and `provider=Other`.
The repeated traps — self-signed certs, AK/SK sourcing, path-style vs virtual-host,
multi-bucket naming conventions that don't mean what they look like — are not unique
to any one product. This skill is the class-level workflow, with the user's
RustFS deployment at `gz.autolife.ai:8444` as the worked example.

## When to use

- User has a `name:` / `bucket:` style address and says "copy from X to Y" / "upload to X" / "download from X"
- `rclone: didn't find section in config file` or `Failed to create file system` — remote not configured
- Cross-platform transfer needed (Linux server ↔ Windows workstation ↔ Mac)
- Bucket contents need to be inspected before/after a transfer (size, top-level layout)
- AK/SK pair available, endpoint is HTTPS (self-signed common on internal infrastructure)

**Don't use for:**

- HTTP(S) file downloads from a known URL → `curl` / `wget` directly
- S3-native (AWS) work where the official `aws` CLI is already configured → use that
- Single tiny file sync under 100 MB → the overhead of setting up rclone isn't worth it
- GCP / Azure blob — rclone has native backends, but the config dance is different

## Prerequisites

```bash
# Linux: rclone is usually pre-installed (Ubuntu 22.04+)
which rclone && rclone version | head -1

# Windows: download from https://rclone.org/downloads/ (windows-amd64 zip)
#   Or: winget install Rclone.Rclone  (Windows 10+)
#   Or: choco install rclone  (Chocolatey)
#   Or: scoop install rclone  (Scoop)

# macOS: brew install rclone
```

If rclone is missing on Linux:
```bash
# User-side (agent can't sudo interactively in PTY — write a script for the user)
curl -fsSL https://rclone.org/install.sh | sudo bash

# Or sudo apt install rclone (Ubuntu 22.04 ships 1.50+; Ubuntu 26.04 ships 1.75)
sudo apt update && sudo apt install -y rclone
```

**Verify before assuming installed.** Existing installs may be older than current (1.69+); the official script reinstalls the same version if it's already current, so this is idempotent. Don't trust package-manager versions blindly.

## Core workflow

### 1. Identify the remote and the bucket

Most "didn't find section in config file" errors come from the user typing `<name>:bucket/...` where `<name>` isn't in `~/.config/rclone/rclone.conf`. Three recovery paths:

```bash
# A. What remotes are already configured?
rclone listremotes

# B. Where is the config file? (rclone knows the canonical path)
rclone config file
# → Configuration file is stored at:
# → /home/<user>/.config/rclone/rclone.conf

# C. Does the user have a hint about the protocol? (URL, console, etc.)
#    RustFS: https://<host>:<port>/rustfs/console/browser/?bucket=<bucket>
#    MinIO console:  https://<host>:<port>
#    The URL exposes: endpoint host:port, bucket name, scheme (HTTP vs HTTPS)
```

If the URL is HTTPS on a non-public host (e.g. `*.gz.autolife.ai`), **assume self-signed cert** and pass `--no-check-certificate` to every rclone call until proven otherwise. Verify with:
```bash
curl -k -sS -o /dev/null -w "HTTP %{http_code} | TLS=%{ssl_verify_result}\n" \
  --max-time 5 "https://<host>:<port>/"
# TLS=20 means the cert chain didn't validate (the expected result for self-signed).
# HTTP 403 on root is fine — auth is required, but the endpoint is reachable.
```

### 2. Source the AK/SK

Three patterns, in order of likelihood:

| Source | Where to look |
|---|---|
| Web console login | The S3 console login is often the same credentials as the AK/SK pair (RustFS, MinIO default). Try `access_key_id = <console-username>`. |
| Web console → Access Keys | "Users" → select user → "Access Keys" tab → "Create access key". MinIO and RustFS both have this. |
| Asked for them | If SSO/OIDC is configured, the S3 API uses a separate static credential. Ask the operator. |

**Never** read the AK/SK from a file the user can't point you to. If they paste a URL like `https://rustfs.example.com/console/...`, ask them to log in once and find/create an AK/SK.

### 3. Write the config

```ini
# ~/.config/rclone/rclone.conf  (mode 600, never commit)
[<remote-name>]
type = s3
provider = Other
env_auth = false
access_key_id = <AK>
secret_access_key = <SK>
endpoint = https://<host>:<port>
force_path_style = true
no_check_certificate = true
```

- `provider = Other` for anything that isn't AWS / Cloudflare / GCS / Azure / B2 / Scaleway / DigitalOcean
- `force_path_style = true` for self-hosted S3 (RustFS, MinIO). Virtual-host-style requires wildcard DNS that self-hosted setups don't have.
- `no_check_certificate = true` for self-signed certs (or pass `--no-check-certificate` per call)
- `env_auth = false` unless the user wants to source AK/SK from env vars per call

### 4. Verify before transferring

```bash
# A. List buckets
rclone lsd <remote>: --no-check-certificate

# B. List top-level of a specific bucket
rclone lsd <remote>:<bucket> --no-check-certificate

# C. Size of a prefix (with file count)
rclone size <remote>:<bucket>/<prefix> --no-check-certificate

# D. See the full tree up to depth 2
rclone tree <remote>:<bucket> --max-depth 2 --no-check-certificate
```

**Always read the full `lsd` output before assuming structure.** A bucket named `robot-289` might have top-level entries like `2026-08-12/`, `2026-08-13/`, `2026-08-14/`, `2026-08-15/`, `2026-08-16/` where each is a *snapshot* of the same underlying data — and the snapshot day is **the archive day, not the data collection day**. The actual collection dates are inside, e.g. `2026-08-13/2026-08-11/`, `2026-08-13/2026-08-12/`. See the "naming convention" pitfall in the pitfalls section.

### 5. Transfer with the right flags

```bash
# Pull (remote → local) — most common for backups
rclone copy <remote>:<bucket>/<src-prefix> /local/dest \
  -P \
  --no-check-certificate \
  --retries 10 --retries-sleep 5s \
  --transfers 8 --checkers 16 \
  --stats 10s --stats-one-line

# Push (local → remote)
rclone copy /local/src <remote>:<bucket>/<dst-prefix> \
  -P --no-check-certificate --retries 10 --retries-sleep 5s \
  --transfers 8 --checkers 16 --stats 10s --stats-one-line

# Sync (destructive — destination gets pruned to match source)
rclone sync /local/src <remote>:<bucket>/<dst-prefix> \
  -P --no-check-certificate --retries 10 --retries-sleep 5s
```

Flags explained:
- `-P` / `--progress` — per-file progress; for big jobs
- `--retries N --retries-sleep <duration>` — survive transient errors
- `--transfers N` — concurrent file uploads/downloads (8 is a good default; 16+ on fast links)
- `--checkers N` — concurrent directory listings (helps when bucket has 10k+ objects)
- `--stats 10s --stats-one-line` — single-line progress every 10s, easier to read than the default rolling output
- `--no-check-certificate` — see pitfall P3

### 6. Verify completion

```bash
# Sizes should match (or local is a strict subset of remote for partial copies)
rclone size <remote>:<bucket>/<src-prefix> --no-check-certificate
rclone size /local/dest --no-check-certificate

# File counts (Total objects line)
rclone size <remote>:<bucket>/<src-prefix> --no-check-certificate | grep "Total objects"
rclone size /local/dest | grep "Total objects"

# For a one-off integrity check on a small set, use checksums
rclone check <remote>:<bucket>/<src-prefix> /local/dest --no-check-certificate
# → rclone hashes every file on both sides and compares. Slow but honest.
```

## Cross-platform script packaging

When the user wants the same workflow on Windows, package as a self-contained zip:

```
rustfs-upload/
├── rclone.conf       (chmod 600 / NTFS-restricted — contains AK/SK)
└── upload.ps1        (auto-downloads rclone.exe on first run)
```

Key PowerShell snippets:

```powershell
# Self-downloading rclone (no separate install step for the user)
$RcloneZipUrl = "https://downloads.rclone.org/rclone-current-windows-amd64.zip"
$RcloneExe    = "$PSScriptRoot\rclone.exe"
if (-not (Test-Path $RcloneExe)) {
    $WorkDir = Join-Path $env:TEMP "rustfs-upload-$((Get-Random).ToString())"
    New-Item -ItemType Directory -Path $WorkDir -Force | Out-Null
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $RcloneZipUrl -OutFile (Join-Path $WorkDir "rclone.zip") -UseBasicParsing
    Expand-Archive -Path (Join-Path $WorkDir "rclone.zip") -DestinationPath $WorkDir -Force
    $ExeInZip = Get-ChildItem -Path $WorkDir -Recurse -Filter "rclone.exe" | Select-Object -First 1
    Copy-Item $ExeInZip.FullName -Destination $RcloneExe -Force
}

# Use rclone from the same directory
& $RcloneExe copy $LocalPath $Remote --config="$PSScriptRoot\rclone.conf" `
    --no-check-certificate --retries 10 --retries-sleep 5s --transfers 8 -P
```

**Three parameters the user must change every time** — keep them at the top of the script as a clearly-marked block:

```powershell
$LocalPath     = "D:\data\2026-08-17"   # what to upload
$Bucket        = "robot-289"             # target bucket
$RemotePrefix  = "2026-08-17/"           # sub-path inside bucket; MUST end with /
```

**Default-allow script execution** (one-time per user):
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

The full template is in `templates/upload-rustfs.ps1`.

## Pitfalls

### P1: "didn't find section in config file" — remote name not in rclone.conf

The error `Failed to create file system for "<remote>:<bucket>...": didn't find section in config file` means the `<remote>` part of the path is not a section header in `~/.config/rclone/rclone.conf`. Either:
- The config file doesn't exist (first-time setup) → `rclone config file` shows the path, create the file
- The config exists but the section is missing or misspelled → `rclone listremotes` shows what's actually registered
- The user typed `s3:` / `s3compat:` / `oss:` etc. as a generic protocol name — those aren't real rclone remote names

The fix is to write the config (see step 3), not to debug rclone itself.

### P2: rclone already installed but is the right version — don't reinstall

Always `rclone version | head -1` before "installing." On Ubuntu 22.04+ rclone is in the default repos at 1.50+ and gets updated through normal apt upgrades. The official install script (`curl -fsSL https://rclone.org/install.sh | sudo bash`) re-downloads the same binary if the version matches — wasted time and a 30 MB download. The `linux-desktop-system-config` skill's "Driver pattern" approach is the right handoff if a real upgrade is needed.

### P3: self-signed certs require `--no-check-certificate` on every call

Internal infrastructure (RustFS on `*.autolife.ai`, MinIO behind a corp VPN, Ceph RGW with the default cert) almost never has a cert that resolves through the public CA chain. The error looks like:
```
Failed to create file system for "rusts:...": Get "https://...": x509: certificate signed by unknown authority
```

Three options:
- **`--no-check-certificate` on every rclone call** (simplest, fine for closed networks)
- **`no_check_certificate = true` in rclone.conf** (same effect, no per-call flag)
- **Install the corp CA cert in the system trust store** (only if the user wants it system-wide)

Don't try the third unless the user is on the corp network and you have the CA cert to install. Options 1 and 2 are equivalent.

### P4: top-level "date" prefix is the archive day, not the data day

On data-collection pipelines (robot fleets, observability buckets, log archives), the top-level date subdir is usually **when the snapshot was uploaded**, not when the data was generated. The user thinks they're asking for "2026-08-13" but the snapshot from 2026-08-16 contains strictly more data than 2026-08-13 (every later snapshot supersedes earlier ones).

**Before transferring, run `rclone lsd` on every plausible prefix** and check whether the *contents* are different. If 8-13, 8-14, 8-15, 8-16 all show the same internal subdirectories, pick the latest one — copying all four is a 4× waste.

Verify the pattern is consistent, not assumed. Some pipelines genuinely do collect by day; check the `manifest.jsonl` or `task_meta.json` timestamps inside one leaf file before declaring the pattern.

### P5: missing subdirectory days aren't bugs — they're real gaps

If a bucket's `2026-08-13/2026-08-02/` doesn't exist, the data for 8-02 was either never collected or never uploaded. Don't synthesize a placeholder or skip silently. Tell the user "8-02 isn't there" so they can verify with the upstream pipeline. If the user says "ignore it," proceed; otherwise investigate.

### P6: `rclone copy` is not destructive on the source but IS on the destination for `sync`

- `rclone copy` — copies source → dest, leaves both alone, never deletes. Safe default.
- `rclone sync` — copies source → dest AND deletes dest files not in source. Destructive.
- `rclone move` — copies then deletes source. Destructive on source.

Never use `sync` or `move` on a destination the user doesn't fully own (e.g. a shared bucket with other people's data). Default to `copy` unless the user explicitly asks for destructive behavior.

### P7: rclone's `lsd` truncates output to ~10 entries unless you grep

When checking bucket contents, `rclone lsd rustfs:robot-289/2026-08-16` can return 10-12 subdirs and you'll assume that's "all of them" if you don't `wc -l` or `tail`. Real bug surface: a bucket with a typo-prefix dir like `290/` mixed in among dates — easy to miss if you only read the first page. Always pipe through `awk '{print $NF}' | sort` and compare against an expected count when the user says "this bucket should have N top-level entries."

### P8: secrets in rclone.conf are world-readable by default

`rclone.conf` contains the AK/SK in plaintext. rclone does not set restrictive permissions on a fresh config — it's whatever umask gives, usually 644. After writing, `chmod 600` immediately:

```bash
chmod 600 ~/.config/rclone/rclone.conf
```

When packaging the config into a zip for Windows transfer, the file lands with NTFS default ACLs (inherited from the parent dir, often "Users" can read). Restrict to owner-only:
```powershell
$acl = Get-Acl $RcloneConf
$acl.SetAccessRuleProtection($true, $false)  # disable inheritance
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    $env:USERNAME, "FullControl", "Allow")
$acl.SetAccessRule($rule)
Set-Acl $RcloneConf $acl
```

### P9: S3 403/400 errors are often a *path-style* mismatch, not a credentials issue

If rclone gets `403 Forbidden` or `400 Bad Request` on every call but the AK/SK is right, the bucket is rejecting virtual-host-style URLs (`<bucket>.<endpoint>/...`) and you need `force_path_style = true` in the config. This is the default for RustFS and MinIO, but some providers (Cloudflare R2, AWS with `s3-accelerate`) want the opposite. When in doubt, set it explicitly.

### P10: rclone `size` on a large prefix can take minutes

`rclone size` walks every object in the prefix to sum bytes and count. On a 250 GB / 35k-file prefix this is 30+ seconds and can hit a list-objects pagination limit. The `Total objects: 35.420k` and `Total size: 253.109 GiB` lines are the output you want. If `size` hangs, fall back to a single `lsd` of one level and let the user decide.

### P11: user already understands the script — just answer the question

When the user asks a targeted follow-up after a script handoff ("only change `Bucket = robot-shanghai-yuyu`?"), **answer the literal question, then stop.** Don't re-explain what the script does, don't re-summarize the workflow, don't offer to make the change yourself. The user has read the script. They're confirming the diff before they edit it. See `linux-desktop-system-config` P-pitfalls for the broader script-handoff etiquette.

## Reference recipes

- `references/rustfs-worked-example.md` — full walkthrough of the autolife RustFS setup (`gz.autolife.ai:8444`, robot-289 / robot-shanghai-yuyu buckets, the 8-12 → 8-16 archive-day trap, the 250 GiB transfer with `--transfers 8`).
- `references/multi-bucket-hygiene.md` — patterns for managing many parallel buckets (one per robot / per project): naming, AK rotation, capacity monitoring, per-bucket vs per-prefix Rclone remotes.

## Templates

- `templates/rclone.conf` — minimal working config for a self-hosted S3-compatible store with self-signed cert.
- `templates/upload-rustfs.ps1` — Windows PowerShell upload script with auto-download, progress, resume, and the three `$LocalPath / $Bucket / $RemotePrefix` parameters at the top.
- `templates/copy-289.sh` — Bash one-liner expansion: loop over date subdirs and copy each with progress (the user's "07-30 to 08-03 subset" pattern from the worked example).

## Verification

A transfer is verified when:

1. `rclone size` on source and destination match exactly in `Total objects` and `Total size` (modulo the user's explicit subset)
2. For a spot check: `rclone check <remote>:<bucket>/<prefix> /local/dest` returns no diff lines
3. The user has confirmed at least one random file opens / parses correctly post-copy

A config is verified when:

1. `rclone listremotes` lists the new remote
2. `rclone lsd <remote>:` returns ≥1 bucket without error
3. `rclone lsd <remote>:<bucket>` returns the expected top-level structure
4. `~/.config/rclone/rclone.conf` has mode 600 (Linux) or owner-only ACL (Windows)
