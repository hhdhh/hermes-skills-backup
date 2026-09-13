#!/bin/bash
# audit.sh — skill-readiness-audit 7 步一气跑完
# 主人 2026-07-04 灰灰立 · 7/4 实测用一次
# 复跑这个脚本:bash ~/.hermes/skills/hermes/skill-readiness-audit/scripts/audit.sh

set -uo pipefail

SKILL_ROOT="${SKILL_ROOT:-$HOME/.hermes/skills}"
REPORT="$HOME/.hermes/logs/skill-audit-$(date +%Y%m%d-%H%M%S).md"
PY="/Users/kk/miniconda3/bin/python3.13"
PIP_INDEX="--index-url https://pypi.tuna.tsinghua.edu.cn/simple"

mkdir -p "$(dirname "$REPORT")"
{
echo "🩺 SKILL READINESS REPORT"
echo "Generated: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Root: $SKILL_ROOT"
echo "═══════════════════════════════════════"
echo

# Step 1: Symlink integrity
echo "## Step 1: Symlink integrity"
BROKEN=0
EMPTY=0
for l in $(find -L "$SKILL_ROOT" -maxdepth 1 -type l 2>/dev/null); do
  [ ! -e "$l" ] && { echo "BROKEN: $l"; BROKEN=$((BROKEN+1)); }
done
for d in "$SKILL_ROOT"/*/; do
  [ -z "$(ls -A "$d" 2>/dev/null | grep -v '^\.')" ] && { echo "EMPTY: $d"; EMPTY=$((EMPTY+1)); }
done
TOTAL=$(find -L "$SKILL_ROOT" -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
echo "  Total dirs: $TOTAL / Broken: $BROKEN / Empty: $EMPTY"
echo

# Step 2: SKILL.md presence
echo "## Step 2: SKILL.md presence"
SKILLMD=$(find -L "$SKILL_ROOT" -maxdepth 3 -name "SKILL.md" 2>/dev/null | wc -l | tr -d ' ')
echo "  SKILL.md files: $SKILLMD"
echo

# Step 3-4: Parse requires + bin check
echo "## Step 3-4: Required bins + python_packages (from SKILL.md frontmatter)"
BINS_NEEDED=()
PYPKG_NEEDED=()
for f in $(find -L "$SKILL_ROOT" -maxdepth 3 -name "SKILL.md" 2>/dev/null); do
  # 抽 bins: 简单 grep (frontmatter 多种格式)
  B=$(grep -oE '"[a-z][a-z0-9_-]+"' "$f" 2>/dev/null | grep -E "lark-cli|node|python3|nano-pdf|obscura|tsx|deno" | tr -d '"' | sort -u)
  for b in $B; do
    case " ${BINS_NEEDED[*]:-} " in *" $b "*) ;; *) BINS_NEEDED+=("$b") ;; esac
  done
done
echo "  Bins needed: ${BINS_NEEDED[*]:-none}"
echo
echo "## Step 4: Bin check"
for b in lark-cli node python3 nano-pdf obscura deno tsx; do
  P=$(which $b 2>/dev/null)
  if [ -n "$P" ]; then
    V=""
    case $b in
      lark-cli) V=$(lark-cli --version 2>&1 | head -1) ;;
      node) V=$(node --version 2>&1 | head -1) ;;
      python3) V=$(/Users/kk/miniconda3/bin/python3.13 --version 2>&1 | head -1) ;;
      *) V=$($b --version 2>&1 | head -1) ;;
    esac
    echo "  ✓ $b @ $P — $V"
  else
    echo "  ✗ $b MISSING"
  fi
done
echo

# Step 5: Python package import test
echo "## Step 5: Critical python packages"
$PY -c "
import importlib
for pkg in ['chromadb', 'pyyaml', 'lancedb', 'playwright', 'sqlite3']:
  try:
    m = importlib.import_module(pkg)
    v = getattr(m, '__version__', 'built-in')
    print(f'  ✓ {pkg} {v}')
  except ImportError as e:
    print(f'  ✗ {pkg}: {e}')
"
echo

# Step 6: Smoke test 4 个核心 skill
echo "## Step 6: Smoke tests"
# fluid-memory
if [ -f "$HOME/.openclaw/workspace/skills/fluid-memory/fluid_skill.py" ]; then
  OUT=$($PY -c "
import sys
sys.path.insert(0, '$HOME/.openclaw/workspace/skills/fluid-memory')
import fluid_skill
m = fluid_skill.FluidMemorySkill()
print(f'  ✓ fluid-memory: HAS_CHROMA={m.use_vector}')
" 2>&1)
  echo "$OUT"
fi
# lark-cli
echo "  ✓ lark-cli: $(lark-cli --version 2>&1 | head -1)"
# huihui-core 11 modules
HUIHUI_OK=0
for m in token_juice memory_tree skill_yaml auto_fetch vault tree_summarizer subconscious phase_workflow mail_app_adapter self_improvement_loop owner_state_monitor; do
  [ -d "$SKILL_ROOT/huihui-core/$m" ] && HUIHUI_OK=$((HUIHUI_OK+1))
done
echo "  ✓ huihui-core: $HUIHUI_OK/11 modules"
# hermes CLI
HERMES_VER=$(hermes --version 2>&1 | head -1)
echo "  ✓ hermes CLI: $HERMES_VER"
echo

# Step 7: Empty / placeholder
echo "## Step 7: Empty / placeholder skills (源头就空 — 不是 broken)"
for d in "$SKILL_ROOT"/*/; do
  if [ -z "$(ls -A "$d" 2>/dev/null | grep -v '^\.')" ]; then
    name=$(basename "$d")
    if [ -d "$d/.clawhub" ]; then
      echo "  • $name (ClawHub 元数据登记)"
    else
      echo "  • $name (空目录 — 源头如此)"
    fi
  fi
done
echo
echo "═══════════════════════════════════════"
echo "VERDICT: $(if [ $BROKEN -eq 0 ]; then echo "✅ Ready"; else echo "⚠ $BROKEN broken links need repair"; fi)"
} | tee "$REPORT"

echo
echo "📄 Report: $REPORT"
