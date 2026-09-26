---
name: object-storage-rclone
description: Use when the user references an rclone remote by name, me...
---

# object-storage-rclone

> 完整描述：Use rclone to connect to S3-compatible object storage (rustfs, MinIO, SeaweedFS, Garage, Ceph RGW, etc.) — config template, TLS pitfalls, bucket layout gotchas, copy/sync recipes. Use when the user references an rclone remote by name, mentions rustfs/MinIO/S3-compatible buckets, or gets "didn't find section in config file" / TLS errors.

Connect to and operate S3-compatible object storage through rclone. Covers
rustfs, MinIO, SeaweedFS, Garage, Ceph RGW, and any other store that speaks
the S3 API. The recurring failure mode is a missing or wrong `[remote]`
section in `rclone.conf`; the recurring success mode is a 4-line stanza.

## When to load this skill

- User mentions an rclone remote by name (`rustfs:`, `minio:`, `s3:`, ...) and gets `didn't find section in config file`.
- User wants to download/upload a large amount of data to/from an S3-compatible bucket.
- User pastes a Web console URL like `https://host:port/.../console/browser/?bucket=NAME` — this is rustfs (or a rustfs-style UI). Endpoint host + port are right there in the URL; you only need to ask for AK/SK.
- User gets TLS errors against a corporate/internal S3 endpoint (self-signed cert).
- User says "this bucket has directories like 2026-08-13/ and inside those 2026-08-12/" — the data layout is **archival snapshots**, not date-ranges.

## Step 1 — gather the 4 facts

You need exactly four things. Everything else has a safe default.

| Field | How you find it | Safe default |
|---|---|---|
| **endpoint** | Web console URL (host:port), or admin/ops handoff, or the original `rclone` error if it named a host | none — must be provided |
| **access_key_id** | rustfs/MinIO console → Access Keys, or same as the Web console login | none — must be provided |
| **secret_access_key** | same as above | none — must be provided |
| **bucket** | already in the user's command/path, or obvious from the Web console URL `?bucket=X` | — |

**Don't ask for these one at a time** — bundle them in a single clarify or hand the user a checklist. They almost always come from the same person.

## Step 2 — write the config stanza

File: `~/.config/rclone/rclone.conf` (Linux/macOS) — discover with `rclone config file`.

```ini
[<remote>]
type = s3
provider = Other
env_auth = false
access_key_id = <AK>
secret_access_key = <SK>
endpoint = https://<host>:<port>
force_path_style = true
```

**`provider = Other` is the universal fallback** for any non-AWS S3 clone.
`force_path_style = true` is required by rustfs/MinIO/most S3 clones (AWS
uses virtual-hosted style; clones don't).

If the user is going through a corporate MITM or self-signed cert, also
add `no_check_certificate = true` to the stanza, OR pass
`--no-check-certificate` on every CLI invocation. The config option is
stickier and survives shell history loss.

Then `chmod 600` the file — it contains plaintext secrets.

## Step 3 — verify before copying anything

Never go straight from "config written" to a multi-hundred-GB `rclone copy`.
Three cheap probes first:

```bash
rclone listremotes                          # confirms config parses
rclone lsd <remote>: --no-check-certificate # lists buckets (lsd = dirs only)
rclone lsd <remote>:<bucket> --no-check-certificate # lists top-level in bucket
```

`lsd` returns objects with size `-1` for directories, so don't read the
"size" column on dir listings — it's always `-1`. If you need sizes, use
`rclone size` on a specific path.

## Pitfalls (read these — they bit real sessions)

### P1 — read the FULL `lsd` output before drawing conclusions

`rclone lsd` can return 12+ lines for a bucket. If you only eyeball the
first 10 and say "directory X and Y have the same content", you will be
wrong — the 11th and 12th entries may be the new data the user actually
wants. Always pipe through `wc -l` and read to end, or run `rclone tree
<remote>:<bucket> --max-depth 2` for a complete picture.

**Real failure mode:** claimed `2026-08-12/` and `2026-08-13/` directories
had identical content. Wrong — `2026-08-13/` had two extra subdirectories
(`2026-08-11`, `2026-08-12`) that the partial read missed, and the user's
actual ask was for those two.

### P2 — top-level date is usually archival, not data date

On data-collection buckets (robot/vehicle/sensor logs, etc.) the convention
is almost always:

```
bucket/
  2026-08-12/        ← archival snapshot, taken ON this date
    2026-07-30/
    2026-07-31/
    ...
    2026-08-10/
  2026-08-13/        ← next day's snapshot, cumulative
    2026-07-30/
    ...
    2026-08-12/      ← newest data this snapshot contains
```

So `2026-08-16/` having "no 2026-08-16" inside it is normal. The user
saying "I want 13-16" usually means "the 13-16 snapshots", not "data dated
13-16". Confirm with the user before pulling 200+ GiB of cumulative
backlog.

### P3 — don't reinstall rclone without checking the version first

Run `rclone version | head -1` before assuming rclone is old. Ubuntu
26.04 ships rclone v1.75.0 in apt, which IS the current upstream (as of
2026). If you assume "v1.60 must be old" and run the official install
script, you'll re-download 30 MB and re-install the same version. Waste
of bandwidth and a credibility hit when the user notices.

The only safe upgrade path is:

```bash
rclone version | head -1    # see what's there
sudo rclone selfupdate       # official in-place upgrade, ~10 MB, no script needed
```

`rclone selfupdate` is built into rclone itself — it knows its own latest
version and atomically replaces the binary. It also doesn't need curl
piped to a root shell, which sidesteps the agent-pty sudo problem.

### P4 — agent PTY cannot sudo, user PTY can

If you need to `sudo rclone selfupdate` or `sudo cp rclone /usr/bin/`,
do it from the agent's PTY and it will fail with "A terminal is required
to authenticate". Hand the user a self-contained one-shot `.sh` instead
(in the spirit of `linux-desktop-system-config`), or ask them to run
`sudo rclone selfupdate` directly. Don't try `echo pw | sudo -S` — it's
security-blocked by the harness and probably by sudoers.

### P5 — `--check-first` on huge copies

For any copy where the source is >50 GB or the user might re-run it after
a Ctrl-C, prefer `rclone copy --check-first` once at the start. rclone
default behavior (compare-modtime-or-size) is fast on resume but can
misclassify already-copied-but-truncated files after a kill. The
`--check-first` mode does a full hash comparison on the first pass, then
falls back to fast mode for subsequent runs.

### P6 — disk space math before kicking off

`rclone copy` to local disk: `df -h <dest-parent>` and compare to
`rclone size <src> --json | jq .bytes` (or the human-readable output).
Common failure: user kicks off a 250 GiB copy onto a 100 GiB free
volume, fill disk, copy dies at 60%, partial files in destination,
re-run is a mess. Always check first.

## Recipes

### Copy a whole bucket
```bash
rclone copy <remote>:<bucket>/ "/local/dest" -P \
  --no-check-certificate --retries 10 --retries-sleep 5s --transfers 8
```

### Copy one day's data inside an archival snapshot
```bash
rclone copy <remote>:<bucket>/2026-08-16/2026-08-12 "/local/dest/2026-08-12" -P \
  --no-check-certificate --retries 10 --retries-sleep 5s --transfers 8
```

### Dry-run / see what would copy
```bash
rclone copy <remote>:<bucket>/2026-08-16/ /local/dest \
  --dry-run --no-check-certificate -P
```

### Mount as filesystem (fuse)
```bash
mkdir -p ~/mnt/<bucket>
rclone mount <remote>:<bucket> ~/mnt/<bucket> \
  --no-check-certificate --daemon --vfs-cache-mode writes
```

### Verify config without copying
```bash
rclone lsd <remote>: --no-check-certificate         # buckets
rclone lsd <remote>:<bucket> --no-check-certificate # top-level dirs
rclone size <remote>:<bucket>/<path> --no-check-certificate # bytes
```

## References

- `references/rustfs-config.md` — exact working config for the rustfs
  deployment at `rustfs.gz.autolife.ai:8444` with AK/SK format
  expectations and bucket-discovery patterns.
