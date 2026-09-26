# rclone transfer tuning cheat sheet

The four knobs that actually matter: `--transfers`, `--checkers`, `--bwlimit`, `--retries`.
Everything else is either cosmetic or for very specific scenarios.

## `--transfers` (concurrent file streams)

| Workload | Recommended | Why |
|---|---|---|
| Many small files (< 1 MB) | 16-32 | Latency-bound; more streams = more throughput |
| Mixed (1-100 MB) | 8 (default) | Balanced |
| Few large files (GB+) | 4-8 | Bandwidth-bound; > 8 streams queue on the same socket |
| Cross-region / high latency | 2-4 | Don't let the server's connection table fill up |

## `--checkers` (concurrent directory listings)

Default 8. Raise to 16 for huge shallow trees (e.g. flat log dirs); lower to 4
when you see `429 Too Many Requests` from the S3-compatible server.

## `--bwlimit` (bandwidth cap)

Format: `10M`, `500K`, `1G`. Use for:
- Sharing a link with other workloads
- Avoiding peak-hour billing on metered connections
- Multi-day transfers where you want headroom

`--bwlimit "08:00,1M 18:00,off"` schedules: 1 MB/s during business hours, unlimited after 6 PM.

## `--retries` + `--retries-sleep`

For S3-compatible stores with flaky metadata APIs (rustfs sometimes hiccups on listing):
- `--retries 10 --retries-sleep 5s` = 10 retries with 5s between (max ~50s of retry time)
- For long-haul links, add `--low-level-retries 10` (default is usually 3)

## Backgrounding without losing output

```bash
# Pure nohup
nohup rclone copy src dst -P > /tmp/rclone.log 2>&1 &
echo "PID: $!"

# With setsid (detaches from controlling terminal)
setsid rclone copy src dst -P </dev/null > /tmp/rclone.log 2>&1 &

# Follow progress
tail -f /tmp/rclone.log

# Find the process if you forgot the PID
pgrep -af rclone
```

## Spotting whether you're CPU, network, or API bound

Add `-vv --log-file rclone.log` for one minute, then grep:

| Symptom | Bottleneck | Fix |
|---|---|---|
| Many `429 Too Many Requests` | API rate limit | Lower `--checkers` |
| Transfer rate stuck at < 10% of link capacity | Disk I/O or checkers | Lower `--checkers`, raise `--transfers` |
| Transfer rate matches link but high CPU on local box | Checksum overhead (md5) | Add `--checksum` only if needed; default uses mtime+size |
| Random `connection reset` mid-stream | NAT timeout or aggressive firewall | Add `--timeout 5m --contimeout 10s` |

## Common copy-vs-sync-vs-move mistakes

| Command | Adds | Updates existing | Deletes in dst | Use when |
|---|---|---|---|---|
| `copy` | yes | yes | **no** | Default. Safe. |
| `sync` | yes | yes | **yes** | You own the entire destination prefix and want exact mirror |
| `move` | yes | yes | yes (after copy) | You want to free local disk after upload |
| `moveto` | yes | yes | yes | Same as `move` but accepts different dst name |

**Default to `copy`. Tell the user explicitly when you use `sync` or `move`** because
"delete in destination" is irreversible on object storage with versioning disabled.
