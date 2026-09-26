#!/usr/bin/env bash
# Copy a subset of date-named subdirectories from a remote S3-compatible bucket
# to a local destination.  Shows per-folder progress and disk usage.
#
# Edit the three variables at the top, then run.

set -euo pipefail

# ============== YOU EDIT THESE THREE LINES ==============
REMOTE="rustfs:robot-289/2026-08-16"     # source prefix (parent of the date subdirs)
DEST="/home/kk/289 2026-08-16"            # local destination
DAYS=(2026-07-30 2026-07-31 2026-08-01 2026-08-03)   # subdirs to copy (no 2026-08-02 — confirm with operator)
# ========================================================

# Pre-flight: show sizes and confirm disk
echo "=== per-folder sizes ==="
for d in "${DAYS[@]}"; do
    s=$(rclone size "$REMOTE/$d" --no-check-certificate 2>&1 | grep "Total size" | head -1)
    c=$(rclone size "$REMOTE/$d" --no-check-certificate 2>&1 | grep "Total objects" | head -1)
    echo "  $d: $c | $s"
done
echo ""
echo "=== local disk ==="
df -h "$(dirname "$DEST")" | tail -1
echo ""

mkdir -p "$DEST"

for d in "${DAYS[@]}"; do
    echo "============================================="
    echo "  copying $d ..."
    echo "============================================="
    rclone copy "$REMOTE/$d" "$DEST/$d" -P \
        --no-check-certificate --retries 10 --retries-sleep 5s \
        --transfers 8 --checkers 16 --stats 10s --stats-one-line
    echo ""
done

echo "done."
echo ""
echo "=== local result ==="
du -sh "$DEST"/* 2>/dev/null
