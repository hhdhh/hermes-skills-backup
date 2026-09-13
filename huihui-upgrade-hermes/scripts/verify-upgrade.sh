#!/bin/bash
# verify-upgrade.sh — 升级后验收脚本
# 用法：./verify-upgrade.sh   (期望看到 [✓] 全绿 + 版本号新)
# 需要：新版本已 `uv pip install`，但还没重启任何 gateway 进程
#
# 退出码：
#   0 = 全绿
#   1 = 静态失败（库没装上 / 版本不对）
#   2 = 进程层失败（gateway 没重启 / web UI 不响应）

set -uo pipefail

EXPECTED_VER="${1:-0.19.0}"
PYTHON="${PYTHON:-/Users/kk/miniconda3/bin/python3}"
TS="$(date '+%H:%M:%S')"

echo "============================================================"
echo "  Hermes Agent 升级验收  ($TS)"
echo "  期望版本: $EXPECTED_VER"
echo "============================================================"
echo

# 1. 静态层：CLI 版本
echo "[1/7] hermes CLI 版本"
HERMES_VER=$("$PYTHON" -m hermes_cli.__init__ 2>&1 | grep -E "^Hermes Agent" | head -1) || true
if [ -z "$HERMES_VER" ]; then
  HERMES_VER=$(hermes --version 2>/dev/null | grep -E "Hermes Agent" | head -1)
fi
echo "    $HERMES_VER"
if echo "$HERMES_VER" | grep -q "$EXPECTED_VER"; then
  echo "    ✓ 通过"
else
  echo "    ✗ 失败 —— 期望包含 '$EXPECTED_VER'"
  exit 1
fi
echo

# 2. pip metadata
echo "[2/7] pip show hermes-agent"
PIP_VER=$("$PYTHON" -m pip show hermes-agent 2>/dev/null | awk '/^Version:/ {print $2}')
echo "    Version: $PIP_VER"
[ "$PIP_VER" = "$EXPECTED_VER" ] && echo "    ✓ 通过" || { echo "    ✗ pip 版本不匹配"; exit 1; }
echo

# 3. import smoke test
echo "[3/7] import smoke test"
IMPORT_OUT=$("$PYTHON" -c "
import hermes_cli, fastapi, starlette, uvicorn
print(f'hermes_cli={hermes_cli.__version__}')
print(f'fastapi={fastapi.__version__}')
print(f'starlette={starlette.__version__}')
print(f'uvicorn={uvicorn.__version__}')
" 2>&1 | grep -v ANTHROPIC)
echo "$IMPORT_OUT" | sed 's/^/    /'
if echo "$IMPORT_OUT" | grep -q "hermes_cli=$EXPECTED_VER"; then
  echo "    ✓ 通过"
else
  echo "    ✗ import version mismatch"
  exit 1
fi
echo

# 4. dist-info
echo "[4/7] dist-info 存在"
DIST_DIR="/Users/kk/miniconda3/lib/python3.13/site-packages"
if ls $DIST_DIR/hermes_agent-${EXPECTED_VER}.dist-info > /dev/null 2>&1; then
  echo "    ✓ $DIST_DIR/hermes_agent-${EXPECTED_VER}.dist-info 在位"
else
  echo "    ✗ 期望 dist-info 不存在"
  exit 1
fi
echo

# 5. web UI 响应
echo "[5/7] web UI http://localhost:8648"
WEB_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://localhost:8648/)
WEB_TIME=$(curl -s -o /dev/null -w "%{time_total}" --max-time 3 http://localhost:8648/)
echo "    status=$WEB_STATUS time=${WEB_TIME}s"
if [ "$WEB_STATUS" = "200" ]; then
  echo "    ✓ 通过"
else
  echo "    ⚠ web UI 未响应（可能还在重启）"
fi
echo

# 6. gateway 进程数量
echo "[6/7] gateway profile 数量"
HERMES_PROCS=$(pgrep -f "hermes_cli.main gateway run" 2>/dev/null | wc -l)
echo "    找到 $HERMES_PROCS 个 hermes_cli gateway 进程"
if [ "$HERMES_PROCS" -ge 5 ]; then
  echo "    ✓ 通过（≥5 个 gateway 进程）"
else
  echo "    ⚠ 偏少（期望 ≥5）"
fi
echo

# 7. 升级前后的对比（提醒主人）
echo "[7/7] 提示：进程层版本检查"
echo "    当前 PID 跑的是新版还是旧版？"
echo "    用法："
echo "      for pid in \$(pgrep -f 'hermes_cli.main gateway run'); do"
echo "        echo \"PID=\$pid \$(ps -p \$pid -o etime,command= | tail -1)\""
echo "      done"
echo "    跑得越久的进程越可能跑着旧库（除非升级后重启过）"
echo
echo "============================================================"
echo "  静态层验收完成（4/7 必过，3/7 警告）"
echo "============================================================"
