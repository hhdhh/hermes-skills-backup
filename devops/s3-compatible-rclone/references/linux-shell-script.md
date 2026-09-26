# Linux/macOS shell script for rclone + S3-compatible storage

Annotated template — copy and modify for new remotes. The Linux version is simpler
than the Windows one: rclone is usually installable from the OS package manager, and
no encoding pitfalls.

## Annotated template

```bash
#!/usr/bin/env bash
# Upload / download / inspect rclone remote.
# Usage:
#   bash rustfs.sh setup                     # install rclone + write config + verify
#   bash rustfs.sh download <remote> <local> # copy remote -> local
#   bash rustfs.sh upload   <local> <remote> # copy local -> remote
#   bash rustfs.sh lsd      <remote>         # list directories only
#   bash rustfs.sh size     <remote>         # show total size
set -euo pipefail

BUCKET="${BUCKET:-robot-shanghai-yuyu}"          # default bucket
REMOTE_PREFIX="${REMOTE_PREFIX:-290/}"           # default prefix
TRANSFERS="${TRANSFERS:-8}"                       # concurrent transfers
RCLONE_CONF="${RCLONE_CONF:-$HOME/.config/rclone/rclone.conf}"

usage() {
    cat <<EOF
Usage: bash $0 <command> [args]

Commands:
  setup                  install rclone + write config + verify
  download <r> <l>       remote -> local
  upload   <l> <r>       local  -> remote
  lsd      <remote>      list directory
  size     <remote>      show total size
EOF
}

# 1. Install rclone (only if missing) - detects distro
ensure_rclone() {
    if command -v rclone >/dev/null 2>&1; then
        echo "[setup] rclone present: $(rclone version | head -1)"
        return
    fi
    echo "[setup] installing rclone..."
    if   command -v apt-get >/dev/null 2>&1; then sudo apt-get install -y -qq rclone
    elif command -v yum     >/dev/null 2>&1; then sudo yum install -y rclone
    elif command -v dnf     >/dev/null 2>&1; then sudo dnf install -y rclone
    elif command -v pacman  >/dev/null 2>&1; then sudo pacman -Sy --noconfirm rclone
    elif command -v brew    >/dev/null 2>&1; then brew install rclone
    else curl -fsSL https://rclone.org/install.sh | sudo bash
    fi
    command -v rclone >/dev/null 2>&1 || { echo "install failed"; exit 1; }
}

# 2. Write config (only if missing - never overwrite an existing key)
ensure_config() {
    mkdir -p "$(dirname "$RCLONE_CONF")"
    if [ -f "$RCLONE_CONF" ] && grep -q "^\[rustfs\]" "$RCLONE_CONF"; then
        echo "[config] present: $RCLONE_CONF"
        return
    fi
    cat > "$RCLONE_CONF" <<'EOF'
[rustfs]
type = s3
provider = Other
env_auth = false
access_key_id = YOUR_AK
secret_access_key = YOUR_SK
endpoint = https://host:port
force_path_style = true
EOF
    chmod 600 "$RCLONE_CONF"
    echo "[config] written: $RCLONE_CONF"
}

# 3. Verify remote
verify_remote() {
    if ! rclone lsd "rustfs:" --config="$RCLONE_CONF" --no-check-certificate >/dev/null 2>&1; then
        echo "remote unreachable - check network / endpoint / AK / SK"
        exit 1
    fi
    echo "[verify] remote OK"
}

case "${1:-}" in
    setup) ensure_rclone; ensure_config; verify_remote ;;
    lsd)   shift; rclone lsd  "$1" --config="$RCLONE_CONF" --no-check-certificate ;;
    size)  shift; rclone size "$1" --config="$RCLONE_CONF" --no-check-certificate ;;
    download) shift
        REMOTE="$1"; LOCAL="$2"
        ensure_rclone; ensure_config; verify_remote
        mkdir -p "$LOCAL"
        rclone copy "$REMOTE" "$LOCAL" -P \
            --config="$RCLONE_CONF" --no-check-certificate \
            --retries 10 --retries-sleep 5s --transfers "$TRANSFERS" ;;
    upload) shift
        LOCAL="$1"; REMOTE="$2"
        ensure_rclone; ensure_config; verify_remote
        [ -e "$LOCAL" ] || { echo "local path missing: $LOCAL"; exit 1; }
        rclone copy "$LOCAL" "$REMOTE" -P \
            --config="$RCLONE_CONF" --no-check-certificate \
            --retries 10 --retries-sleep 5s --transfers "$TRANSFERS" ;;
    *) usage; exit 1 ;;
esac
```

## Key design choices

- **Auto-detect package manager** — covers apt/yum/dnf/pacman/brew without asking the user
- **Don't overwrite an existing config** — re-running `setup` is idempotent
- **Config via env vars** (`BUCKET`, `REMOTE_PREFIX`, `TRANSFERS`) — user can swap targets without editing the script
- **Quote all paths** — `set -euo pipefail` + quoting prevents silent arg-loss on paths with spaces

## Install on a remote box where the agent has no PTY sudo

If the user asks the agent to "set this up on a colleague's box" and the agent's own
PTY cannot do `sudo` (it usually can't, due to "A terminal is required to authenticate"),
write a self-contained installer script for the user to run manually:

```bash
curl -fsSL https://rclone.org/install.sh | sudo bash
```

Write the command to `/tmp/install-rclone.sh` for the user to execute, with output
they can paste back. Don't try to run `sudo bash` from the agent's own PTY.

## Backgrounding large transfers

```bash
# Run in background, log to file, tail to watch
nohup rclone copy "/src" "rustfs:bucket/dst/" -P \
  --no-check-certificate --transfers 8 > /tmp/upload.log 2>&1 &

# Check progress
tail -f /tmp/upload.log

# Or just non-blocking + return
rclone copy ... > /tmp/upload.log 2>&1 &
disown
```

For multi-day transfers, consider `--bwlimit 50M` to avoid saturating shared links.

## Debug

```bash
# Verbose log
rclone copy <src> <dst> -vv --log-file /tmp/rclone.log --no-check-certificate

# Filter log for errors only
grep -E "ERROR|FAIL" /tmp/rclone.log
```
