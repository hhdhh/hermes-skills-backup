#!/bin/bash
# upgrade-hermes.sh — 一键升级 hermes-agent（conda 路线）
# 用法：./upgrade-hermes.sh 0.19.0
# 期望主人已经说"升到 0.19.0"且设了备份目录

set -euo pipefail

NEW_VER="${1:?Usage: $0 <new-version> e.g. 0.19.0}"
PYTHON="${PYTHON:-/Users/kk/miniconda3/bin/python3}"
TS=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="$HOME/.hermes/backups/pre-${NEW_VER}-${TS}"
INDEX="${INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
LOG="$BACKUP_DIR/upgrade.log"

mkdir -p "$BACKUP_DIR"
echo "[$(date '+%H:%M:%S')] upgrade $NEW_VER starting" | tee -a "$LOG"

# 1. 备份
echo "[$(date '+%H:%M:%S')] 备份当前安装..." | tee -a "$LOG"
cd /Users/kk/miniconda3/lib/python3.13/site-packages
tar -czf "$BACKUP_DIR/hermes.tar.gz" \
  hermes_cli hermes_bootstrap.py hermes_constants.py \
  hermes_logging.py hermes_state.py hermes_time.py \
  hermes_agent-*.dist-info/ 2>&1 | tee -a "$LOG" || true
cp ~/.hermes/config.yaml "$BACKUP_DIR/config.yaml.bak"
echo "[$(date '+%H:%M:%S')] 备份完成 → $BACKUP_DIR/$(basename hermes.tar.gz)" | tee -a "$LOG"

# 2. dry-run
echo
echo "[$(date '+%H:%M:%S')] dry-run..." | tee -a "$LOG"
uv pip install --upgrade "hermes-agent==$NEW_VER" --dry-run \
  --python "$PYTHON" --index-url "$INDEX" 2>&1 | tee -a "$LOG"

# 3. 真升
echo
echo "[$(date '+%H:%M:%S')] 真升..." | tee -a "$LOG"
uv pip install --upgrade "hermes-agent==$NEW_VER" \
  --python "$PYTHON" --index-url "$INDEX" 2>&1 | tee -a "$LOG"

# 4. 静态验证
echo
echo "[$(date '+%H:%M:%S')] 静态验证..." | tee -a "$LOG"
"$PYTHON" -c "
import hermes_cli, fastapi, starlette, uvicorn
print(f'hermes_cli={hermes_cli.__version__}')
print(f'fastapi={fastapi.__version__}')
print(f'starlette={starlette.__version__}')
print(f'uvicorn={uvicorn.__version__}')
" 2>&1 | grep -v ANTHROPIC | tee -a "$LOG"

# 5. doctor 末段
echo
echo "[$(date '+%H:%M:%S')] doctor..." | tee -a "$LOG"
hermes doctor 2>&1 | grep -vE 'Warning|ANTHROPIC|This usually|If auth|provider|Notice' | tail -15 | tee -a "$LOG"

echo
echo "============================================================"
echo "  升级完成（静态层）"
echo "  备份：$BACKUP_DIR/"
echo "  下一步（要主人授权）：重启 gateway / web UI"
echo "    → /Users/kk/.hermes/skills/huihui-upgrade-hermes/"
echo "      SKILL.md §6 决策表 + §7 launchctl 路径"
echo "============================================================"
