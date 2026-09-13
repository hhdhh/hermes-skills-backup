#!/usr/bin/env bash
# Obsidian CLI bridge for oh/ohmo
# Usage: obsidian_bridge.sh <command> [args...]
# Examples:
#   obsidian_bridge.sh search "openharness"
#   obsidian_bridge.sh read "wiki/memory/openharness-integration.md"
#   obsidian_bridge.sh append "MEMORY.md" "New insight: ..."
#   obsidian_bridge.sh daily  # create today's daily note
set -euo pipefail
VAULT="huihui-wiki"
case "${1:-}" in
  search)
    shift; obsidian vault="$VAULT" search query="$*"
    ;;
  read)
    shift; cat "$(echo "$*" | sed 's|^|~/.openclaw/workspace/wiki/|')"
    ;;
  append)
    shift; FILE="$1"; shift
    obsidian vault="$VAULT" append path="$FILE" content="$*"
    ;;
  create)
    shift; FILE="$1"; shift
    obsidian vault="$VAULT" create path="$FILE" content="$*" overwrite=false
    ;;
  daily)
    DATE=$(date +%Y-%m-%d)
    FILE="daily/${DATE}.md"
    if [ ! -f ~/.openclaw/workspace/wiki/$FILE ]; then
      obsidian vault="$VAULT" create path="$FILE" content="# ${DATE}\n\n## OpenHarness 自动添加\n" overwrite=false
    fi
    echo "$FILE"
    ;;
  backlinks)
    shift; obsidian vault="$VAULT" backlinks path="$*"
    ;;
  *)
    echo "Usage: $0 {search|read|append|create|daily|backlinks} [args...]" >&2
    exit 1
    ;;
esac
