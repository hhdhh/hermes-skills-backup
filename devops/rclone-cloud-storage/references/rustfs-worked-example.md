# RustFS at gz.autolife.ai:8444 — worked example

This is the user's primary cloud object store, hit on 2026-08-17. Use it as a
concrete case study when the same patterns show up elsewhere.

## What was discovered

The URL the user provided — `https://rustfs.gz.autolife.ai:8444/rustfs/console/browser/?bucket=robot-289` — exposed three facts without any login:

| Fact | From URL | Implication for rclone config |
|---|---|---|
| Endpoint | `rustfs.gz.autolife.ai:8444` | `endpoint = https://rustfs.gz.autolife.ai:8444` |
| Bucket | `robot-289` | destination prefix |
| Scheme | `https://` | HTTPS, not HTTP |

The port 8444 + the `.gz.autolife.ai` host + the `rustfs` path = self-hosted
RustFS, almost certainly with a self-signed cert.

Confirmed reachability before doing anything else:
```bash
curl -k -sS -o /dev/null -w "HTTP %{http_code} | TLS=%{ssl_verify_result}\n" \
  --max-time 5 "https://rustfs.gz.autolife.ai:8444/"
# → HTTP 403 | TLS=20
# 403 on root is expected (no auth); TLS=20 = cert didn't validate through the
# public CA chain, which is exactly why --no-check-certificate is needed.
```

## What the user already had on their machine

The user's first attempt was `rclone copy rustfs:robot-289/2026-08-13/ ...`
which failed with `didn't find section in config file` — the symptom of an
empty/missing `~/.config/rclone/rclone.conf`. We wrote the config, did
NOT replace rclone (it was already v1.75.0, the current latest), and verified
the connection.

Lesson for next time: **check `rclone version` before "installing"**. The
official install script is idempotent on a current install but wastes 30 MB
and ~30 s of download. A 1-second `rclone version | head -1` answers the
question.

## The naming convention trap

The bucket `robot-289` had these top-level entries:

```
2026-08-08
2026-08-10
2026-08-11
2026-08-12     ← what the user's first command was sourcing
2026-08-13
2026-08-14
2026-08-15
2026-08-16
```

We assumed these were daily archives and that each top-level was a different
day's data. **That was wrong.** Running `rclone lsd` on each one revealed
that 2026-08-13, 2026-08-14, 2026-08-15, 2026-08-16 all had **identical**
sub-directory structures (7-30, 7-31, 8-01, 8-03, 8-04, 8-05, 8-06, 8-07,
8-08, 8-10, 8-11, 8-12) — same data, just snapshotted on different days.

The top-level date = **archive day** (when the snapshot was uploaded).
Inside, the dates are **collection days**. Picking 2026-08-13 vs 2026-08-16
gives the same data; 2026-08-12 is missing 8-11 and 8-12 because the
pipeline hadn't finished those days yet when the 8-12 snapshot was taken.

This trap is dangerous because `rclone size` of any two "different" archive
days will return the same byte count only if the snapshot is exact, and the
checksum verification is the only way to be 100% sure. The pragmatic check:
`rclone lsd` on the top two archive days; if the sub-dir list is identical,
pick the latest one and don't copy the rest.

## The 250 GB transfer that didn't happen

The user originally asked for `rclone copy rustfs:robot-289/2026-08-13/ "/home/kk/289 2026-08-12"`. We caught:

1. The size: 253.109 GiB / 35,420 files. Would have taken hours and eaten
   250 GB of local disk.
2. The naming trap above: 8-12 and 8-13 contain different sub-day ranges,
   so the destination directory name `2026-08-12` mismatched the source
   contents — but the user wanted the data, not the directory name to match.
3. The user said "不用了我自己来" / "I don't need it, I'll do it myself" —
   correct decision. We gave them the info, didn't push.

When the user came back with a tighter scope — "only 07-30 to 08-03" — we
wrote `/tmp/copy-289.sh` with the right subset (4 days, ~120 GB) and let
them run it.

## What the cross-platform deliverable looked like

For the Windows side, the deliverable was a zipped folder:

```
rustfs-upload.zip  (~2.2 KB)
├── upload-rustfs.ps1    (the script)
└── rclone.conf          (the config, mode-600 on the user's side)
```

The script auto-downloads rclone.exe on first run, so the user didn't need
to install anything separately. Three `$Variable = ...` lines at the top
are the entire user-facing interface. Worked example: `$Bucket = "robot-shanghai-yuyu"`
replacing the default `robot-289` was the entire "what do I change on
Windows" answer when the user asked which line to edit.

## Useful commands for the same store later

```bash
# How big is the bucket overall?
rclone size rustfs: --no-check-certificate

# Top-level of any bucket
rclone lsd rustfs:robot-289 --no-check-certificate

# What's the newest archive day for a given bucket?
rclone lsd rustfs:robot-289 --no-check-certificate | awk '{print $NF}' | grep -E '^20[0-9]{2}-' | sort | tail -3

# Spot-check: are two archive days the same data?
diff <(rclone lsd rustfs:robot-289/2026-08-13 --no-check-certificate | awk '{print $NF}' | sort) \
     <(rclone lsd rustfs:robot-289/2026-08-16 --no-check-certificate | awk '{print $NF}' | sort)
# → empty output = identical contents

# Find stray/non-date directories in a bucket (e.g. accidental 290/ misdrop)
rclone lsd rustfs:robot-shanghai-yuyu --no-check-certificate | awk '{print $NF}' | grep -vE '^20[0-9]{2}-|^19[0-9]{2}-'
```
