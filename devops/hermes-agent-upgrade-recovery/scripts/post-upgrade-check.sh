#!/bin/bash
# post-upgrade-check.sh
# 跑一遍升级后的健康检查 —— CLI / import / 各依赖 / web UI / 各 gateway PID / doctor
# 命中项标红，OK 标绿
# 退出码：0 = 全 OK，1 = 有命中项

set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

EXPECTED_NEW=${EXPECTED_NEW:-"0.19.0"}
EXPECTED_FASTAPI=${EXPECTED_FASTAPI:-"0.141.1"}
EXPECTED_STARLETTE=${EXPECTED_STARLETTE:-"1.3.1"}
EXPECTED_UVICORN=${EXPECTED_UVICORN:-"0.52.1"}
EXPECTED_OPENAI=${EXPECTED_OPENAI:-"2.24.0"}

ERRORS=0

ok() { echo -e "${GREEN}✓${NC} $1"; }
fail() { echo -e "${RED}✗${NC} $1"; ERRORS=$((ERRORS + 1)); }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }

section() {
  echo
  echo "═══ $1 ═══"
}

# ───────── 1. CLI version ─────────
section "1. CLI 版本"

CLI_VER=$(hermes --version 2>/dev/null | head -1 | awk '{print $3}' | tr -d '(,)' || echo "unknown")
PIP_VER=$(/Users/kk/miniconda3/bin/python3 -m pip show hermes-agent 2>/dev/null | awk '/^Version:/ {print $2}')

if [ "$CLI_VER" = "$EXPECTED_NEW" ]; then
  ok "hermes CLI: $CLI_VER"
else
  fail "hermes CLI: $CLI_VER (期望 $EXPECTED_NEW)"
fi

if [ "$PIP_VER" = "$EXPECTED_NEW" ]; then
  ok "pip metadata: $PIP_VER"
else
  fail "pip metadata: $PIP_VER (期望 $EXPECTED_NEW)"
fi

# ───────── 2. Python 模块版本 ─────────
section "2. Python 依赖版本"

CHECKED=$(/Users/kk/miniconda3/bin/python3 <<EOF 2>&1 | grep -v ANTHROPIC
import sys
results = []
for mod, expected in [
    ('fastapi', '$EXPECTED_FASTAPI'),
    ('starlette', '$EXPECTED_STARLETTE'),
    ('uvicorn', '$EXPECTED_UVICORN'),
    ('openai', '$EXPECTED_OPENAI'),
    ('hermes_cli', '$EXPECTED_NEW'),
]:
    try:
        m = __import__(mod)
        v = getattr(m, '__version__', '?')
        results.append(f'{mod}\t{v}\t{expected}')
    except ImportError:
        results.append(f'{mod}\tMISSING\t{expected}')
for r in results:
    print(r)
EOF
)

while IFS=$'\t' read -r mod actual expected; do
  if [ "$actual" = "$expected" ]; then
    ok "$mod: $actual"
  elif [ "$actual" = "MISSING" ]; then
    fail "$mod: MISSING"
  else
    warn "$mod: $actual (期望 $expected)"
  fi
done <<< "$CHECKED"

# ───────── 3. Gateway PIDs ─────────
section "3. Gateway 进程状态"

declare -A EXPECTED_PROFILES=( [default]=1 [dev]=1 [main]=1 [ops]=1 [qa]=1 [cto]=1 [pm]=1 [security]=1 )

for profile in "${!EXPECTED_PROFILES[@]}"; do
  if [ "$profile" = "default" ]; then
    PID=$(launchctl list 2>/dev/null | awk '$3 == "ai.hermes.gateway" {print $1}')
    LABEL="ai.hermes.gateway"
  else
    PID=$(launchctl list 2>/dev/null | awk -v p="ai.hermes.gateway-$profile" '$3 == p {print $1}')
    LABEL="ai.hermes.gateway-$profile"
  fi

  if [ -n "$PID" ] && [ "$PID" != "-" ]; then
    # 进程启动时间（单位：秒）
    ETIME=$(ps -o etime= -p "$PID" 2>/dev/null | tr -d ' ')
    ok "$profile (PID $PID, uptime: $ETIME) ✓"
  else
    fail "$profile ($LABEL) — not running"
  fi
done

# ───────── 4. Web UI ─────────
section "4. Web UI 状态"

WEBUI_PORT=${WEBUI_PORT:-8648}
WEBUI_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "http://localhost:$WEBUI_PORT/" 2>/dev/null || echo "ERR")

if [ "$WEBUI_STATUS" = "200" ]; then
  ok "Web UI :$WEBUI_PORT → 200"
else
  fail "Web UI :$WEBUI_PORT → $WEBUI_STATUS"
fi

# ───────── 5. Skills inventory ─────────
section "5. Skills 库存"

SKILL_COUNT=$(ls ~/.hermes/skills/ 2>/dev/null | wc -l | tr -d ' ')
if [ "$SKILL_COUNT" -ge 150 ]; then
  ok "Skills count: $SKILL_COUNT"
else
  warn "Skills count: $SKILL_COUNT (期望 ≥ 150)"
fi

# ───────── 6. Doctor ─────────
section "6. Doctor 摘要"

DOCTOR_OUTPUT=$(hermes doctor 2>&1 | grep -vE "Warning|ANTHROPIC|This usually|If auth|provider's|truncated|Notice" || true)
DOCTOR_FATAL=$(echo "$DOCTOR_OUTPUT" | grep -E "(✗|FATAL|critical)" || true)

if [ -z "$DOCTOR_FATAL" ]; then
  ok "Doctor 没有致命问题"
else
  warn "Doctor 报："
  echo "$DOCTOR_FATAL" | head -10
fi

# ───────── 7. Bin entry points ─────────
section "7. Bin entry points"

for bin in hermes hermes-acp hermes-agent; do
  if [ -x "/Users/kk/miniconda3/bin/$bin" ] || [ -L "/Users/kk/miniconda3/bin/$bin" ]; then
    ok "bin/$bin 在位"
  else
    warn "bin/$bin 缺失"
  fi
done

# hermes-agent 测试是否能跑（常见 0.19.0 故障：run_agent 缺）
HERMES_AGENT_TEST=$(/Users/kk/miniconda3/bin/hermes-agent --help 2>&1 | head -3)
if echo "$HERMES_AGENT_TEST" | grep -q "ModuleNotFoundError"; then
  fail "bin/hermes-agent 不可用（已知 0.19.0 entry point 故障：run_agent 包未装）"
elif echo "$HERMES_AGENT_TEST" | grep -qE "usage|Usage|help"; then
  ok "bin/hermes-agent 可用"
else
  warn "bin/hermes-agent 状态未知（输出：$(echo "$HERMES_AGENT_TEST" | head -1)）"
fi

# ───────── 8. 备份路径 ─────────
section "8. 最近 backup"

LATEST_BACKUP=$(ls -td ~/.hermes/backups/*/ 2>/dev/null | head -1)
if [ -n "$LATEST_BACKUP" ]; then
  ok "最近 backup: $LATEST_BACKUP"
  BACKUP_TAR=$(ls -t "$LATEST_BACKUP"*.tar.gz 2>/dev/null | head -1)
  if [ -n "$BACKUP_TAR" ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_TAR" | awk '{print $1}')
    BACKUP_VER=$(echo "$BACKUP_TAR" | grep -oE 'hermes_[0-9.]+_full' | sed 's/hermes_//; s/_full//')
    ok "  backup tar: $(basename "$BACKUP_TAR") ($BACKUP_SIZE) — 版本 $BACKUP_VER"
  fi
else
  fail "没有 backup tar！下次升级前必跑 backup-hermes-site-packages.sh"
fi

# ───────── Summary ─────────
echo
echo "════════════════════════════"
if [ "$ERRORS" -eq 0 ]; then
  echo -e "${GREEN}✓ 全部 OK${NC}"
  exit 0
else
  echo -e "${RED}✗ $ERRORS 项命中${NC}"
  exit 1
fi
