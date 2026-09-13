#!/bin/bash
# version-watchdog.sh — Hermes stack version monitor
# 主人 2026-07-04 全权下放 · 化身心跳检查
# 检查 hermes-web-ui / hermes-agent / hermes CLI 是否有新版本
# 有变化 → 写 ticker → 主人下次 session 看到
# crontab: 0 9 * * * /Users/kk/.hermes/scripts/version-watchdog.sh

set -euo pipefail
LOG="$HOME/.hermes/logs/version-watchdog-$(date +%Y%m%d).log"
mkdir -p "$(dirname "$LOG")"

echo "$(date '+%Y-%m-%d %H:%M:%S') === version check ===" >> "$LOG"

# 1. hermes-web-ui (npm)
NPM_LATEST=$(npm view hermes-web-ui version 2>/dev/null || echo "unknown")
NPM_LOCAL=$(npm list -g hermes-web-ui 2>/dev/null | grep hermes-web-ui | awk '{print $2}' | tr -d '[]' || echo "unknown")
echo "  hermes-web-ui: local=$NPM_LOCAL latest=$NPM_LATEST" >> "$LOG"

# 2. hermes-agent (brew formula, optional)
BREW_LATEST=$(brew info hermes-agent --json 2>/dev/null | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['versions']['stable'])" 2>/dev/null || echo "unknown")
BREW_LOCAL=$(brew list --versions hermes-agent 2>/dev/null | awk '{print $2}' || echo "not installed")
echo "  hermes-agent: local=$BREW_LOCAL latest=$BREW_LATEST" >> "$LOG"

# 3. hermes CLI (conda pip package)
HERMES_LOCAL=$(hermes --version 2>&1 | head -1 || echo "unknown")
echo "  hermes CLI: $HERMES_LOCAL" >> "$LOG"

# 4. 比 last-success — 没变就静默退出
TICKER="$HOME/.hermes/cron/version_ticker"
if [ -f "$TICKER" ] && grep -q "$NPM_LATEST" "$TICKER" 2>/dev/null && grep -q "$BREW_LATEST" "$TICKER" 2>/dev/null; then
  echo "  status: no change since last check" >> "$LOG"
  exit 0
fi

# 5. 有变化 → 写新 ticker
cat > "$TICKER" << TICK
hermes-web-ui: $NPM_LATEST
hermes-agent: $BREW_LATEST
hermes-cli: $HERMES_LOCAL
last_check: $(date -Iseconds)
TICK

echo "  status: CHANGE DETECTED → ticker updated" >> "$LOG"
echo "" >> "$LOG"
