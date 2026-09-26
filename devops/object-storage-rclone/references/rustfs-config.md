# rustfs deployment reference

Working configuration captured from a real session (2026-08-17) against
the rustfs instance at autolife.ai.

## Endpoint

```
https://rustfs.gz.autolife.ai:8444
```

HTTPS, non-default port 8444. Certificate returned TLS verify error 20
on probe (self-signed or internal CA), so the user always passes
`--no-check-certificate` on the CLI. The deployment accepted the
connection anyway — no auth challenge issue.

## Web console URL pattern

```
https://<host>:<port>/rustfs/console/browser/?bucket=<bucket-name>
```

The bucket name is in the URL query string — parse it before asking the
user. Same URL also works as a sanity check that you're hitting the
right deployment.

## Working rclone.conf stanza

```ini
[rustfs]
type = s3
provider = Other
env_auth = false
access_key_id = <from console → Access Keys or same as login>
secret_access_key = <from console → Access Keys or same as login>
endpoint = https://rustfs.gz.autolife.ai:8444
force_path_style = true
```

User omitted `no_check_certificate` from the stanza and used the
`--no-check-certificate` flag on the CLI instead. Both work; the flag
is per-invocation, the stanza option is sticky.

## Bucket layout observed

The instance is shared across multiple robots/vehicles. Each robot gets
its own top-level bucket:

```
rustfs:/
  apt/
  audit-archive/
  autolife-data-upload-test/
  autolife-robot-packages/
  robot-001/
  robot-234/
  robot-239/
  robot-248/
  robot-289/             ← this user's bucket
  ...
```

Each data-collection bucket follows the **archival-snapshot** convention
(see SKILL.md P2):

```
robot-289/
  2026-08-12/            ← snapshot taken 8-12, contains 7-30..8-10
    2026-07-30/
    ...
    2026-08-10/
  2026-08-13/            ← snapshot taken 8-13, contains 7-30..8-12 (cumulative)
    2026-07-30/
    ...
    2026-08-12/          ← new data added this snapshot
  2026-08-14/ .. 2026-08-16/  ← identical content to 8-13
```

To get the most-recent cumulative dataset, copy the **latest** snapshot
directory (here `2026-08-16/`), not the date range.

## Sizes seen (for context, not as a benchmark)

- `robot-289/2026-08-16/` total: 35 420 objects / 253 GiB
- 8-13 through 8-16 snapshots: identical content (so 8-16 alone is enough)
- 8-12 snapshot: ~225 GiB / 27 000 objects (the delta of 8-13 over 8-12)

## Permission on the config file

`chmod 600 ~/.config/rclone/rclone.conf` after writing — the file
contains plaintext AK/SK. The rclone binary will warn but not refuse
to read world-readable configs.
