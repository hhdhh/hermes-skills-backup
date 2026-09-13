#!/bin/bash
# preflight.sh — Hermes CLI 升级前体检（一键跑完 6 项 + 输出基线）
# 调用：bash ~/.hermes/skills/hermes-cli-upgrade/scripts/preflight.sh [label]
# label 可选，写到输出头便于截图归档

set -uo pipefail

LABEL="${1:-preflight-$(date +%Y%m%d-%H%M%S)}"
TS="$(date '+%Y-%m-%d %H:%M:%S')"

echo "═══════════════════════════════════════════════════════════"
echo "  Hermes CLI Upgrade · ${LABEL}"
echo "  timestamp: ${TS}"
echo "═══════════════════════════════════════════════════════════"
echo

# 过滤 ANTHROPIC_API_KEY ellipsis warning
FILTER='grep -vE "(Warning: ANTHROPIC|This usually means|If authentication|provider'\''s dashboard|truncated|Notice) "'

echo "── 1. hermes CLI 版本"
hermes --version 2>/dev/null | head -3

echo
echo "── 2. gateway 状态"
hermes gateway status 2>&1 | grep -E "(PID|supervised|stale)" | head -15

echo
echo "── 3. doctor 体检（末段 · 过滤 warning 噪声）"
hermes doctor 2>&1 | ${FILTER} | tail -30

echo
echo "── 4. Web UI :8648"
curl -s -o /dev/null -w "  HTTP %{http_code}  响应 %{time_total}s\n" --max-time 5 http://localhost:8648/

echo
echo "── 5. skills 数"
echo "  $(ls ~/.hermes/skills/ 2>/dev/null | wc -l) skill(s)"

echo
echo "── 6. 跑 hermes_cli 的关键 PID"
ps aux | grep -E "hermes_cli.main|hermes_bridge|hermes-web-ui" | grep -v grep | awk '{printf "  PID=%s  CUM=%s\n", $2, $11}' | head -10

echo
echo "── 7. Python 环境"
/Users/kk/miniconda3/bin/python3 -c "
import sys
print(f'  Python {sys.version_info[:2]} @ {sys.executable}')
import hermes_cli
print(f'  hermes_cli {hermes_cli.__version__} @ {hermes_cli.__file__}')
" 2>&1 | ${FILTER}

echo
echo "── 8. 当前 hermes-agent pip 元数据"
/Users/kk/miniconda3/bin/python3 -m pip show hermes-agent 2>&1 | grep -E "^(Name|Version|Location):" | head -3

echo
echo "═══════════════════════════════════════════════════════════"
echo "  baseline OK · 把这段输出存到 ~/.hermes/backups/pre-{VER}/baseline.txt"
echo "═══════════════════════════════════════════════════════════"
