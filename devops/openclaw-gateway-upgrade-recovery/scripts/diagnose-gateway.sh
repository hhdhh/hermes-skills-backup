#!/bin/bash
# diagnose-gateway.sh — OpenClaw Gateway 升级失败一键诊断
# 走每个陷阱的诊断路径，输出"哪个陷阱命中"的结论。
# 不做任何修改，只读 + suggest。
#
# 用法:
#   bash diagnose-gateway.sh
#   bash diagnose-gateway.sh --deep  # 包含 sqlite/dump 检查

set -u
DEEP=0
[ "${1:-}" = "--deep" ] && DEEP=1

RED="\033[0;31m"; GREEN="\033[0;32m"; YELLOW="\033[1;33m"; NC="\033[0m"

ok()   { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
fail() { echo -e "${RED}❌ $1${NC}"; }
section() { echo -e "\n${YELLOW}═══ $1 ═══${NC}"; }

section "陷阱 1: 版本错位 (CLI vs runtime)"
WHICH=$(command -v openclaw 2>/dev/null || true)
echo "which openclaw → $WHICH"
DEFAULT_VERSION=""
if [ -n "$WHICH" ] && [ -x "$WHICH" ]; then
  DEFAULT_VERSION=$($WHICH --version 2>&1 | head -1)
  echo "  default version: $DEFAULT_VERSION"
fi
REAL_CLI=""
for candidate in /Users/kk/.openclaw/tools/node-*/bin/openclaw; do
  [ -x "$candidate" ] && REAL_CLI="$candidate"
done
echo "runtime CLI: $REAL_CLI"
if [ -n "$REAL_CLI" ]; then
  REAL_VERSION=$($REAL_CLI --version 2>&1 | head -1)
  echo "  runtime version: $REAL_VERSION"
  if [ "$DEFAULT_VERSION" = "$REAL_VERSION" ]; then
    ok "默认 CLI 与 Gateway runtime 版本一致（/opt/homebrew/bin shim 可正常使用）"
  else
    fail "命中陷阱 1: 默认 CLI 与 Gateway runtime 版本错位"
  fi
elif [ -n "$DEFAULT_VERSION" ]; then
  warn "未找到 ~/.openclaw/tools/node-* runtime CLI；只验证了默认 CLI"
else
  fail "未找到可执行的 openclaw CLI"
fi

section "陷阱 2: Node 版本下限"
NODE_BIN="/opt/homebrew/opt/node/bin/node"
if [ -x "$NODE_BIN" ]; then
  NODE_VER=$("$NODE_BIN" --version)
  echo "node ($NODE_BIN): $NODE_VER"
  # OpenClaw 7.1+ 要求 ≥25.9.0 或 ≥24.15.0
  if [[ "$NODE_VER" > "v25." ]] || [[ "$NODE_VER" == "v25."* ]]; then
    ok "Node ≥25.9.0 (OpenClaw 7.1+ requires)"
  elif [[ "$NODE_VER" > "v24.15" ]]; then
    ok "Node 24.15+ - 7.1+ accepts"
  else
    fail "Node $NODE_VER < 24.15 — 7.1+ 需要升级或换路径"
  fi
fi
PLIST=~/Library/LaunchAgents/ai.openclaw.gateway.plist
if [ -f "$PLIST" ]; then
  PLIST_NODE=$(plutil -extract ProgramArguments.3 raw "$PLIST" 2>/dev/null)
  echo "plist ProgramArguments[3]: $PLIST_NODE"
  if [[ "$PLIST_NODE" == *node@24* ]] || [[ "$PLIST_NODE" == *node-v24* ]]; then
    fail "命中陷阱 2: plist 用 node@24 但 OpenClaw 7.1+ 要 ≥25.9.0"
  fi
fi

section "陷阱 3: plist ProgramArguments 脏状态"
if [ -f "$PLIST" ]; then
  COUNT=$(plutil -extract ProgramArguments xml1 -o - "$PLIST" 2>/dev/null | grep -c "<string>")
  echo "ProgramArguments 元素数: $COUNT (期望 8)"
  if [ "$COUNT" != "8" ]; then
    fail "命中陷阱 3: ProgramArguments 脏了,需 remove + insert 重写"
  else
    ok "ProgramArguments 干净"
  fi
fi

section "陷阱 4: env 文件被裁"
ENV_FILE=~/.openclaw/service-env/ai.openclaw.gateway.env
if [ -f "$ENV_FILE" ]; then
  EXPORT_COUNT=$(grep -c "^export" "$ENV_FILE")
  echo "export 数: $EXPORT_COUNT (期望 ≥19)"
  if [ "$EXPORT_COUNT" -lt 5 ]; then
    fail "命中陷阱 7: env 文件只剩 $EXPORT_COUNT 行 export,被裁了"
    echo "  备份候选:"
    ls -t ~/.openclaw/service-env/ai.openclaw.gateway.env.bak-* 2>/dev/null | head -3 | sed 's/^/    /'
  fi
fi

section "陷阱 5: Secret 严格校验"
set -a; source "$ENV_FILE" 2>/dev/null; set +a
SECRETS_IN_CONFIG=$(grep -oE '"id": "[A-Z_]+_API_KEY"' ~/.openclaw/openclaw.json 2>/dev/null | sort -u | sed 's/"id": "//;s/"//')
echo "config 引用的 secret:"
for sid in $SECRETS_IN_CONFIG; do
  v=$(eval echo \$$sid 2>/dev/null)
  if [ -z "$v" ]; then
    fail "  $sid: MISSING"
  else
    ok "  $sid: ${v:0:5}... (${#v})"
  fi
done

section "陷阱 6: Migration gate / lease"
if [ "$DEEP" = "1" ] && command -v sqlite3 >/dev/null; then
  MIGRATION=$(sqlite3 ~/.openclaw/state/openclaw.sqlite "SELECT app_version FROM schema_meta WHERE meta_key='startup-migrations'" 2>/dev/null)
  LEASE=$(sqlite3 ~/.openclaw/state/openclaw.sqlite "SELECT count(*) FROM state_leases WHERE scope='startup-migrations'" 2>/dev/null)
  echo "startup-migrations 标记: $MIGRATION (期望等于 CLI VERSION)"
  echo "startup-migration lease 计数: $LEASE"
  if [ "$LEASE" != "0" ]; then
    warn "命中陷阱 6: 有 lease 残留/有效,可能未过 expiration"
  fi
fi

section "陷阱 7: launchd breaker"
if [ "$DEEP" = "1" ]; then
  STATE=$(launchctl print gui/$(id -u)/ai.openclaw.gateway 2>/dev/null | grep -E "active count|state " | head -2)
  echo "$STATE"
fi

section "健康检查"
HEALTH=$(curl -sS -m 3 http://127.0.0.1:18789/healthz 2>&1)
echo "healthz: $HEALTH"
if echo "$HEALTH" | grep -q '"ok":true'; then
  ok "Gateway 活着"
else
  fail "Gateway 不活 — 检查上面陷阱结论"
fi

echo
echo "════════════════════════════════════════"
echo "完成。命中哪个陷阱看上面 [❌] 行。"
echo "修复步骤见 SKILL.md 陷阱 N。"
echo "════════════════════════════════════════"
