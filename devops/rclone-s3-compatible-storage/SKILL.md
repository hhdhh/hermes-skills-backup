---
name: rclone-s3-compatible-storage
description: Use when connecting to an internal S3-compatible endpoint...
version: 1
author: hermes-agent
license: MIT
metadata:
  hermes:
    tags: [rclone, s3, rustfs, minio, object-storage, upload, download, cross-platform]
---

# rclone + S3-compatible object storage

> 完整描述：Configure rclone for S3-compatible object storage (rustfs/MinIO/Ceph RGW/Wasabi) and ship cross-platform (Linux/macOS/Windows) upload/download scripts. Use when connecting to an internal S3-compatible endpoint, distributing scripts to a second machine, or moving large data between a local disk and a bucket.

End-to-end workflow for connecting to an S3-compatible object store (rustfs, MinIO, Ceph RGW, Wasabi, etc.) and shipping self-contained upload/download scripts to other machines. The pattern emerged from a real session where the user needed to copy 250+ GB between a local Ubuntu box and an internal rustfs endpoint, then package the same flow for a Windows colleague and another Linux box.

## When to use

- The remote is **not AWS S3** — it's an S3-compatible endpoint (rustfs, MinIO, internal Ceph, etc.) reached by a custom URL, often with a self-signed certificate
- You need to **distribute the configuration + a runnable script** to a second machine (Linux/Windows/macOS) without having shell access there
- The user has given you a console URL like `https://rustfs.example.com:8444/.../browser/?bucket=<name>` — the bucket name is in the URL, but you still need AK/SK to actually call the API
- You're about to issue `rclone copy` to a bucket and want to be sure you understand the bucket's layout (snapshot-vs-collection traps below)

## Don't use this skill for

- Plain AWS S3 — use the AWS CLI / native rclone S3 provider with IAM keys; no need to hand-roll config
- One-off downloads from a public S3 URL — just curl, no rclone needed
- GitHub release downloads — that's `github-release-asset-download`

## Step 1: identify the endpoint

From a console URL like `https://rustfs.gz.autolife.ai:8444/rustfs/console/browser/?bucket=robot-289`, you get **three of the five fields for free**:

| Field | From the URL | Example |
|---|---|---|
| `endpoint` | `scheme://host:port` | `https://rustfs.gz.autolife.ai:8444` |
| `bucket` | `?bucket=<name>` | `robot-289` |
| TLS | URL is `https` but `--no-check-certificate` is required | self-signed / internal CA |

The two you still need from the user: **`access_key_id`** and **`secret_access_key`**. The console login is usually (but not always) the same pair — SSO logins use a separate static credential set, ask the bucket admin.

## Step 2: minimum rclone.conf

```ini
[rustfs]
type = s3
provider = Other
env_auth = false
access_key_id = <AK>
secret_access_key = <SK>
endpoint = https://<host>:<port>
force_path_style = true
```

- `provider = Other` for any non-AWS endpoint. Pick a named provider (Ceph, Minio, Wasabi) only when you have a reason — `Other` works everywhere.
- `force_path_style = true` for almost all self-hosted S3 (rustfs, MinIO, Ceph RGW). AWS uses virtual-hosted style; setting this on AWS breaks it.
- `no_check_certificate = true` is optional but matches the CLI's `--no-check-certificate` flag. Add it when the endpoint is internal/self-signed.
- `chmod 600` the file. The SK is full write access to the bucket.

## Step 3: verify before bulk transfer

Always run these **before** any large `rclone copy`:

```bash
# 1. Endpoint reachable at all (expect 403, not connect failure)
curl -k -sS -o /dev/null -w "HTTP %{http_code} | TLS=%{ssl_verify_result}\n" \
  --max-time 5 "https://<host>:<port>/"

# 2. rclone sees the remote
rclone listremotes

# 3. List all buckets
rclone lsd <remote>: --no-check-certificate

# 4. Drill into the bucket
rclone lsd <remote>:<bucket> --no-check-certificate
```

If step 1 returns 403 + `TLS=20`, the endpoint is up and the cert is untrusted (the expected case for self-signed). If step 3 returns nothing or auth errors, the AK/SK is wrong — don't proceed.

## P1: bucket layout traps — read this before `rclone copy`

Three traps that bit hard in real sessions:

### Trap 1: "top-level date ≠ collection date"

A bucket called `robot-289` with top-level paths `2026-08-12/`, `2026-08-13/`, `2026-08-14/` almost certainly does **not** mean "data collected on that date". The top-level is usually the **archive/upload day**, and inside each one is a sub-tree of **actual collection dates**, often with gaps (no data on Sundays, no 2026-08-02, etc.).

**Always dump the full sub-tree** before assuming what's in there:
```bash
# Shows all subdirs under 2026-08-13/, no truncation
rclone lsd <remote>:<bucket>/2026-08-13 --no-check-certificate | awk '{print $NF}'
```

If the user says "give me August 13", they're almost never asking for what was collected on Aug 13 — they're asking for "the 2026-08-13/ top-level directory" or for the data they expect to find in that era. **Confirm before copying 250 GB.**

### Trap 2: snapshot duplicates

Many pipelines re-upload the same dataset daily as a snapshot. `2026-08-12/`, `2026-08-13/`, `2026-08-14/`, `2026-08-15/`, `2026-08-16/` may all be **byte-identical** (modulo additions). Compare before downloading each:

```bash
for d in 2026-08-12 2026-08-13 2026-08-14 2026-08-15 2026-08-16; do
  echo "=== $d ==="
  rclone size "<remote>:<bucket>/$d" --no-check-certificate | grep "Total size\|Total objects"
done
```

Identical size + identical object count = identical content. Copy once, not five times.

### Trap 3: `rclone size` returning 0B is unreliable

`rclone size` on a prefix sometimes reports 0B / 0 objects even when the prefix is full of data — observed on rustfs. Trust `lsd` + a recursive `ls` over `size` for sizing. If you need a real number, sum individual subdirs or do a dry-run copy with `--dry-run --stats-one-line -P` (rclone still scans, so the stat is accurate).

### Trap 4: misfiled objects

A bucket is named after a robot (`robot-shanghai-yuyu`) and someone dropped a directory called `290/` inside it that contains `sii_office/close_microwave_oven/...` — obviously the wrong robot's data, or a mis-piped upload. Before assuming the bucket is "clean", dump the top level and eyeball it. If you spot a mismatch, **ask the user before deleting or overwriting** — they may want to preserve it for forensics.

## P2: avoid quoting the first lsd output

`rclone lsd` paginates / truncates output by default in some shells. If you only read the first 10 lines, you'll give the user wrong information about what's in the bucket. Always pipe through `awk '{print $NF}'` to get the full list of names, or add `--max-depth` deliberately.

## P3: agent PTY can't sudo

`sudo -v` in a Hermes agent PTY fails with "A terminal is required to authenticate". `echo pw | sudo -S` is security-blocked. **For sudo tasks, write a one-shot `.sh` to `/tmp` and let the user run it.** This matches the broader user preference for "give me a self-contained script" instead of back-and-forth installs.

## P4: rclone already installed?

Before running the official install script, check the existing version:
```bash
which rclone && rclone version | head -1
```
The official install script re-downloads and overwrites without checking. If the version is already current (v1.75+ as of 2026), the user is wasting 30 MB of bandwidth. The script in `templates/install-rclone.sh` does check + backup before overwriting.

## Step 4: ship the script to a second machine

The user pattern is "give me a complete self-contained script, not five back-and-forths." The `templates/` directory has three ready-to-go files:

| File | Target | What it does |
|---|---|---|
| `templates/install-rclone.sh` | Linux | Check version, backup if upgrading, install official latest |
| `templates/setup-rustfs-upload.sh` | Linux | Install rclone + write `rclone.conf` + optionally copy a path in one shot |
| `templates/upload-rustfs.ps1` | Windows | Auto-download `rclone.exe` from official zip + run `rclone copy` |
| `templates/download-rustfs.ps1` | Windows | Mirror of upload: auto-download rclone + `rclone copy` from remote |

### Editing the templates

All four templates have a small "edit these 3 variables" block at the top:

```bash
# Bash
SRC="/path/to/local"
DST="rustfs:bucket/prefix/"
```

```powershell
# PowerShell
$LocalPath     = "D:\data\..."        # local
$RemotePath    = "rustfs:..."          # remote (upload) OR
$RemotePath    = "rustfs:..."          # remote (download)
$LocalPath     = "D:\downloads\..."   # local (download)
$RcloneConf    = "$PSScriptRoot\rclone.conf"
```

For Windows: the script auto-detects whether `rclone.exe` is next to it; if not, downloads from `https://downloads.rclone.org/rclone-current-windows-amd64.zip` and extracts. No manual rclone install on the Windows side.

### Distributing the package

```bash
# Local LAN
scp templates/setup-rustfs-upload.sh user@target:/tmp/
ssh user@target "bash /tmp/setup-rustfs-upload.sh /data/to/upload"

# Or as a zip
zip -j -r rustfs-bundle.zip upload-rustfs.ps1 download-rustfs.ps1 rclone.conf
# Hand-carry / WeTransfer / Feishu
```

## Recommended transfer command

```bash
rclone copy "$SRC" "$DST" -P \
  --no-check-certificate \
  --retries 10 --retries-sleep 5s \
  --transfers 8 --checkers 16
```

- `-P` for live progress
- `--retries 10` + `--retries-sleep 5s` because self-hosted endpoints drop connections
- `--transfers 8` for parallel uploads (good for many small files; raise to 16 if disk/network can handle)
- `--checkers 16` so the parallel hash check doesn't bottleneck
- **No `--no-traverse`** by default; you want rclone to skip already-uploaded files, which is how the retry/resume works

Ctrl+C mid-run + re-run the exact same command = resume from where it stopped. Safe.

## Verification after bulk transfer

```bash
# Sizes match
rclone size "$SRC"   # local
rclone size "$DST"   # remote

# File counts match
rclone ls "$SRC" | wc -l
rclone ls "$DST" | wc -l

# Spot-check a checksum on a big file
md5sum /path/to/local/bigfile
# (rustfs has no md5 CLI but you can re-download a single file to verify)
```

## Reference

- `references/session-rustfs-robot-289.md` — the session this skill was extracted from. Includes the full transcript showing the layout-trap mistakes, the AK/SK delivery from a console URL, and the cross-platform zip packaging.
