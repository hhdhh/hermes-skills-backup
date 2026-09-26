---
name: skill-readiness-audit
description: 'Class-level workflow to audit an agent skill stack after install — verify SKILL.md presence, parse frontmatter `requires` (bins / python_packages / env), smoke-test each skill actual capability (not just enabled), and identify gaps (missing packages, dead symlinks, empty skill dirs). Use when user says 检查技能 / 技能 OK 吗 / skill audit / verify my skills / 依赖齐不齐 / after a large skill install/upgrade batch, or before declaring everything works. Triggers: check skill, skill broken, missing dependency, skill not loading, verify skill, skill environment.'
---

# skill-readiness-audit

Class-level workflow: given a skill stack (e.g. `~/.hermes/skills/` or `~/.claude/skills/`), produce a per-skill readiness report — not just `hermes skills list` enabled count.

> **Authoritative skill mgmt**: `hermes skills list` / `inspect` / `check` is the registry view. This skill is the **execution view** — actually run the imports and binaries the SKILL.md claims it needs.

## When to Use

- After a large skill install batch (装了 50 个 skill)
- Before declaring the skill stack OK to the user
- When a skill seems enabled but does not actually work (silent fallback)
- Periodic audit (e.g. monthly via cron) — drift detection
- Before a critical task that depends on a specific skill (我要用 ljg-card 铸图 → 先 audit)

## Anti-pattern: trusting enabled = OK

`hermes skills list` shows "270 enabled" — but `enabled` only means the **registry knows about it**. It does NOT mean:
- SKILL.md exists and is parseable
- All `requires.bins` are on `$PATH`
- All `requires.python_packages` are installed
- All `requires.env` env vars are set
- The skill actual code runs without import errors

**2026-07-04 灰灰实测**: 主人说检查技能是否完全 OK — `hermes skills list` 报 270 enabled, 0 broken。但实际跑 `chromadb` 导入 = ModuleNotFoundError。**enabled ≠ ready**.

## 5-Step Audit

### Step 1: Symlink integrity

```bash
# 找断链
for l in $(find -L ~/.hermes/skills/ -maxdepth 1 -type l 2>/dev/null); do
  [ ! -e "$l" ] && echo "BROKEN: $l"
done

# 找完全空的 skill 目录（源头就空 — 是 ClawHub 元数据登记，不是 broken）
for d in ~/.hermes/skills/*/; do
  [ -z "$(ls -A "$d" 2>/dev/null | grep -v '^\.')" ] && echo "EMPTY: $d"
done
```

**判定**: BROKEN = `hermes skills audit` 提示的; EMPTY = 源端装的（**不是 broken**——功能可能在别处）.

### Step 2: SKILL.md presence

```bash
# deref symlink (重要 — skills 多数是 symlink)
find -L ~/.hermes/skills/ -maxdepth 3 -name "SKILL.md" 2>/dev/null | wc -l
```

期望: ~95% 的 skill 目录有 SKILL.md. 少量是 namespace/parent（不计数）.

### Step 3: Parse `requires` from all SKILL.md

```bash
# 找 requires 段
for f in $(find -L ~/.hermes/skills/ -maxdepth 3 -name "SKILL.md" 2>/dev/null); do
  NAME=$(grep -E "^name:" "$f" | head -1 | sed 's/name: //' | tr -d '"')
  REQS=$(grep -E "python_packages|bins|requires" "$f" 2>/dev/null | head -3)
  if [ -n "$REQS" ]; then
    echo "=== $NAME ==="; echo "$REQS"
  fi
done
```

聚合: 列**所有 skill 需要的 bins + python packages**（去重）.

# Step 4: Bin check

```bash
# 关键 6 bin（多数 skill 的底座）—— 2026-07-04 加 deno (smart-memory-manager 要)
for b in lark-cli node python3 nano-pdf obscura deno; do
  which $b 2>/dev/null && echo "✓ $b" || echo "✗ $b MISSING"
done
```
# Skill 特定的 bin（按需）
for s in <skill1> <skill2>; do
  # 从 SKILL.md 抠出 requires.bins
  for b in $(yq '.metadata.openclaw.requires.bins[]' ~/.hermes/skills/$s/SKILL.md 2>/dev/null); do
    which $b 2>/dev/null || echo "✗ $s needs $b"
  done
done
```

**坑**: `lark-cli` 在 brew, `nano-pdf` 在 `~/.local/bin/`, **$PATH 不同位置都装上**才稳.

### Step 5: Python package check (清华源)

```bash
# 扫所有 SKILL.md 提到的 python_packages
# 然后用当前环境解释器挨个 import 测
"$(command -v python3)" -c "
import importlib
for pkg in ['chromadb', 'pyyaml', 'lancedb', 'playwright']:
  try:
    importlib.import_module(pkg)
    print(f'✓ {pkg}')
  except ImportError as e:
    print(f'✗ {pkg}: {e}')
"
```

**装法**（清华源）:

```bash
# Use the active project/Hermes Python. On PEP 668 Linux, create a venv
# instead of mutating the system interpreter.
"$(command -v python3)" -m pip install \
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple <pkg>
```

**不要**:
- ❌ `pip install`（conda base 没 pip 入口）
- ❌ `pip install -e .[all]`（会破坏 conda 双轨 — 见 hermes-gateway-admin）
- ❌ `pip install chromadb` 走 PyPI 默认源（卡顿）

### Step 6: Smoke test critical skills

抽 3-5 个核心 skill 做实际 smoke test:

```bash
# 1. 读 1 个 skill 的 SKILL.md frontmatter（验 frontmatter 解析）
head -20 ~/.hermes/skills/huihui-core/SKILL.md

# 2. 实际 import + 实例化
"$(command -v python3)" -c "
import sys
sys.path.insert(0, '<skill_module_path>')
import <module>
print('✓ import OK')
inst = <module>.<ClassName>()
print('✓ instantiate OK')
print('  state:', inst.<key_state_attr>)
"

# 3. CLI bin 实际能跑
<bin-name> --version
<bin-name> --help | head -5
```

**测什么**:
- fluid-memory: `HAS_CHROMA = True`（向量搜索激活）
- lark-cli: 输出版本号
- 关键 lark-* skill: `lark-cli <subcmd>` 不报错
- 自家 huihui-core 11 个模块目录全在

### Step 7: Empty / placeholder skill 标注

```bash
# 4 类源头就空（**不是 broken**）
# 1. ClawHub 元数据登记（`.clawhub/origin.json`）
# 2. GitHub bare LICENSE.txt（部分 skill 仓库就这样）
# 3. 软链目标不存在（broken — 真要修）
# 4. 装失败半成品（.tmp / .partial）
```

**判定原则**:
- 源头就空 = 主人装的源就是这样 → 报账说已知空, **不修**
- 装失败 = 重新 `hermes skills install` 一次
- 软链 broken = `hermes skills repair` 修

## Output Format (报账模板)

```
🩺 SKILL READINESS REPORT — ~/.hermes/skills
═══════════════════════════════════════
Symlinks: 163  /  Broken: 0  /  Empty dirs: 4
SKILL.md present: 156/163
═══════════════════════════════════════
CRITICAL BINS:
  ✓ lark-cli 1.0.14       (/opt/homebrew/bin/)
  ✓ node v26.3.0
  ✓ python3 3.13.12
  ✓ nano-pdf
  ✓ obscura

CRITICAL PYTHON PACKAGES:
  ✓ chromadb 1.5.9        (just installed — fluid-memory vector on)
  ✓ pyyaml 6.0.3
  ✗ deno                  (smart-memory-manager 走 fallback)

SMOKE TESTS:
  ✓ fluid-memory 端到端 import+实例化
  ✓ lark-cli --version
  ✓ huihui-core 11/11 modules
═══════════════════════════════════════
KNOWN GAPS (主人有意不装 / 装不到):
  • deno (smart-memory-manager fallback OK)
  • playwright (ljg-card 等主人网络慢)
  • OPENAI_API_KEY (elite-longterm-memory 主人有意)
  • FEISHU_APPSECRET (占位符, 主人已知)

EMPTY SKILLS (源端就空, 不是 broken):
  • github/.clawhub
  • ros2-skill/.clawhub
  - `skill-creator/LICENSE.txt only`

  ═══════════════════════════════════════
  KNOWN UPSTREAM BUGS（2026-07-04 实测）:
    • smart-memory-manager: add/list/search 全活,但 summarize 报"暂无记忆内容"
      (即使 list 看到数据) —— Deno 端 in-memory store 读取问题,
      不归 agent 管. 装好 deno 也不能修,等上游修.
  ═══════════════════════════════════════
  VERDICT: ✅ Ready (with documented gaps)
  ```

## Pitfalls

1. **`hermes skills list` = OK ≠ 实际 OK** — registry view ≠ execution view. 永远要跑一次 import / which.
2. **`find` 不带 `-L` 找不到 symlink 里的 SKILL.md** — 多数 skill 是 symlink, 不加 `-L` 会误报 missing SKILL.md.
3. **安装包必须跟随当前平台环境** — 先确认 `command -v python3`；conda 使用该解释器的 `-m pip`，PEP 668 Linux 则新建 venv，不能照抄 macOS `/Users/kk` 路径。
4. **`pip install -e .[all]` 修 venv 入口会破坏 conda 双轨** — 见 `hermes-gateway-admin`.
5. **装 chromadb / deno / playwright 这类大包要清华源** — 默认 PyPI 在国内卡顿.
6. **空 skill 目录不要删** — 是 ClawHub 元数据登记或 GitHub bare LICENSE, 源头就这样.
7. **deno / playwright 没装 = skill 走 fallback** — 验 skill 的 fallback 模式（fluid-memory 用 `try: import chromadb except: HAS_CHROMA=False`）. **装了更好, 不装不一定坏**.
8. **不要验 credential 类 skill**（elite-longterm-memory 要 OPENAI_API_KEY）— 主人有意不配的不动.

## 关联资源

- `scripts/audit.sh` — 7 步一气跑完的 audit 脚本（清华源装包 + 写报告）
- `templates/report.template.md` — 上面的报账模板拷来即用

## Scope

This skill ONLY:
- Audits the agent own skill stack
- Verifies imports / bins / frontmatter
- Reports gaps (without fixing — fixing needs user intent)

This skill NEVER:
- Installs packages without user intent (建议 + 等批)
- Deletes broken skills（先报账）
- Touches `~/.hermes/skills/_external/` 或 `~/.hermes/skills/_sources/`（hub-installed / external — 见下）
- Modifies SKILL.md 内容（只读）

## Related Skills

- `skill-vetter` — 装前安全审核（before install）
- `darwin-skill` — SKILL.md 评分（quality）
- `hermes-gateway-admin` — Hermes 平台层 admin（含 hermes-web-ui / launchd）
- `workspace-hygiene` — 工作区磁盘 / 长期记忆清理


## 补充（patch，审批积压恢复）

# Use the active Hermes/project Python; on PEP 668 Linux, create a venv instead of mutating system Python.
"$(command -v python3)" -m pip install \
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple <pkg>


## 补充（patch，审批积压恢复）

4. **安装包必须跟随当前平台环境** — 先确认 `command -v python3`; conda 用该解释器的 `-m pip`，PEP 668 Linux 则新建 venv，不能照抄 macOS `/Users/kk` 路径。
