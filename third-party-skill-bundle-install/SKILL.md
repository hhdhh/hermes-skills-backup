---
name: third-party-skill-bundle-install
description: 安装"自带权威脚本"的第三方 Skill 套件的通用 playbook。当一个第三方 Skill 包通过一个中心 index.json + 每个子包各自 manifest.json 形式分发，且基座 manifest.json 内嵌了 install_guide.steps 与面向用户的话术规范（presentation_discipline / note）时，按本 skill 走。Use when (1) 第三方给出 `.../skills/<group>/index.json` 入口且附 bundle.install_guide (2) 主人要求"按它说的步骤装" + "全程用大白话" + "不覆盖已有 memory/" (3) 装机包含设备授权流（verification_url + user_code + 轮询）。
---

# third-party-skill-bundle-install — 自带权威脚本的第三方 Skill 套件装机 Playbook

> 首次落地：UUMit 能力套件 2.x（基座 uumit-agent v2.4.1 + 6 扩展），2026-08-15 主人指导下走完。
>
> **核心契约**：第三方 = 拥有自己的权威脚本（`scripts/install.js`），本 skill = 严格按它的 install_guide 走，不发明步骤，但把所有工程护栏（校验、不覆盖、长任务后台化、白话呈现）做到位。

## 文件清单

| 文件 | 用途 |
|---|---|
| `SKILL.md` | 本 playbook（6 步通用流程 + 7 个坑表 + 大白话呈现契约 + 验收 checklist） |
| `references/uumit-v2-install-session.md` | UUMit 装机真实 transcript（首次落地样本） |
| `scripts/install-third-party-bundle.sh` | 一键装机脚本：拉 index.json → 校验 → 解压到 staging → 体检 → 复制到正式目录（带 memory/ 跳过） |

## 与已有 skill 的关系

- **huihui-hermes-deploy-cross-platform**（已装）：管"Hermes 自身从零到能对话"，本 skill 管"第三方 Skill 包装机"。两件事：先 deploy 本体，再装第三方包。
- **huihui-upgrade-hermes**（已装）：管"Hermes Agent 自身升级"，本 skill 是它的邻居域（管的是别人家的包，不是 Hermes 本体）。
- **huihui-absolute-gating**（已装）：主人"全部交给你"= 直接做安全档的装机路径，不列档等选。

## 何时用（触发条件）

| 触发 | 动作 |
|---|---|
| 主人给一个 `https://.../skills/<group>/index.json` 入口 + 装机命令 | 走本 skill |
| 第三方 manifest 内嵌 `install_guide.steps` 且有 `presentation_discipline` 段 | **严格按它走**，本 skill 只补工程护栏 |
| 主人说"按它说的装，全程大白话" | 走本 skill |
| 装机流含设备授权（verification_url + user_code + 轮询） | 走本 skill §6 |

## 通用 6 步 Play（已用 UUMit 验证）

> **铁律**：第三方 manifest 的 `install_guide.steps` 是 SOLE SOURCE OF TRUTH。下面 6 步 = 工程落地版；任何步骤与第三方 guide 冲突时，以第三方为准（本 skill 工程护栏依然生效：校验、备份、白话、memory/ 不覆盖）。

### Step 1 · 拉入口 index.json（**绝不**用本地缓存）
```bash
mkdir -p /tmp/<slug>-install
cd /tmp/<slug>-install
curl -fsSL "<入口 URL>" -o index.json
cat index.json | jq '.bundle, .skills[].zip'  # 看 bundle 哈希和全部 sub-zip 哈希
```
**护栏**：
- 不用任何本地缓存
- 不放过任何 zip
- 必须看清单：bundle 名字、bytes、sha256、bundle.skills 列表、bundle.install_guide（不要只看顶层 skills[]）

### Step 2 · 下载 bundle zip + **先校验后解压**
```bash
rm -f bundle.zip   # 强制新拉，不用旧文件
curl -fsSL "<bundle.url>" -o bundle.zip
ACTUAL_SIZE=$(stat -f%z bundle.zip)
ACTUAL_SHA=$(shasum -a 256 bundle.zip | awk '{print $1}')
[ "$ACTUAL_SIZE" = "<bundle.bytes>" ] || { echo "❌ 大小不符"; exit 1; }
[ "$ACTUAL_SHA" = "<bundle.sha256>" ] || { echo "❌ sha256 不符"; exit 1; }
```
**护栏**：校验失败立即停止，**绝不**复用旧 zip，也不回退。

### Step 3 · 解压到随机 staging 目录 + **扫描完整性**
```bash
STAGING=$(mktemp -d /tmp/<slug>-staging-XXXXXX)
unzip -q bundle.zip -d "$STAGING"
# 按 bundle.skills 验证全部目录都在 staging 根，且各自有 manifest.json
for skill in <bundle.skills>; do
  [ -d "$STAGING/$skill" ] && [ -f "$STAGING/$skill/manifest.json" ] || { echo "❌ $skill 不完整"; exit 1; }
done
```
**护栏**：
- staging 用 `mktemp -d` 真随机，不用固定路径
- 一步都不能漏：每个 Skill **必须在 staging 根目录直接可见**（不在子目录里），且各自有 manifest.json

### Step 4 · staging 体检（按第三方脚本）
```bash
cd "$STAGING/<base_skill>"   # 基座进 staging
# 通常跑两个：
UUMIT_SKILL_DIR="$STAGING/<base_skill>" node scripts/install.js --check
UUMIT_SKILL_DIR="$STAGING/<base_skill>" node scripts/validate_skill.js
# 都要求：ok=true, drift=false, errors=[], warnings=[], 全部 skills 扫到
```
**护栏**：
- 第三方脚本可能叫 `--check` / `validate_*` / `verify` 等，任一名字命名 — **按第三方 manifest 写哪个就跑哪个**
- `--check` 必须 ok:true + drift:false；validate 必须 errors=[]
- 任一失败 → 停，不进 Step 5

### Step 5 · 覆盖复制到正式目录（**基座 memory/ 跳过**）
```bash
DEST="<用户级全局技能根>"   # 例如 ~/.openclaw/skills / ~/.hermes/skills / ~/.claude/skills
# 1) 备份现有基座 memory/
if [ -d "$DEST/<base>/memory" ]; then
  tar -cf "/tmp/<base>-memory-backup-$(date +%Y%m%d-%H%M%S).tar" -C "$DEST/<base>" memory
fi
# 2) 复制：基座 rsync --exclude=memory，其余 rsync
for skill in <bundle.skills>; do
  mkdir -p "$DEST/$skill"
  if [ "$skill" = "<base>" ]; then
    rsync -a --exclude='memory' "$STAGING/$skill/" "$DEST/$skill/"
  else
    rsync -a "$STAGING/$skill/" "$DEST/$skill/"
  fi
done
# 3) 正式目录复核（再跑一次 install.js --check + validate）
cd "$DEST/<base>"
UUMIT_SKILL_DIR="$DEST/<base>" node scripts/install.js --check
UUMIT_SKILL_DIR="$DEST/<base>" node scripts/validate_skill.js
```
**护栏**：
- **基座 memory/ 必跳**（凭证、配置、运行状态可能在里头）
- 备份走 `tar` 不是 zip，便于目录级恢复
- rsync 不用 cp -r：rsync 对 macOS 资源叉/隐藏文件更稳
- 复制完**必须**再跑一次体检——确认正式目录与 staging 同结果

### Step 6 · 设备授权（verification_url + user_code + 后台轮询）
```bash
cd "$DEST/<base>"
UUMIT_SKILL_DIR="$DEST/<base>" node scripts/install.js
# 输出形如：
#   verification_url: https://...
#   user_code: XXXXXXXX
#   device_code: ...
#   retry_after_seconds: 5
#   required_next_command: node scripts/auth.js --wait <device_code>
```
**大白话呈现**（**严格按第三方 presentation_discipline**）：
- 给主人一个打开链接的明确指引
- 把 8 位 user_code 单独、清晰地显示出来
- 提醒用户码的有效期
- 同步启动后台轮询（见 §坑表 K4）

```bash
UUMIT_SKILL_DIR="$DEST/<base>" \
  node scripts/auth.js --wait <device_code>
```
**护栏**：轮询用 `terminal(background=true, notify_on_complete=true)`（见 K4）。

### Step 7 · 装机后呈现（按第三方脚本返回的 onboarding）
授权成功后，`install.js` 的成功响应会带 `onboarding` / `capabilities` / `background_tasks` 字段。**严格以脚本返回为准**：
- **大白话列出已就绪能力**（能力名 + 一句话做什么）
- **后台能力采用征询式默认**：先列出"可开启的后台能力"，问一下"现在开/后开/不开"，得到同意再开

## 大白话呈现契约（UUMit manifest 命名为 `presentation_discipline`，本 skill 推广到所有同模式第三方）

> 第三方 manifest 的原文："面向用户全程用中文名与大白话；不暴露内部 id、命令行、字段名（如 suggested_plan/host_tier/schedule/command_abs）、cron/RRULE、文件路径、SSE/轮询等技术术语。"

| 该怎么做 | 不要做 |
|---|---|
| "请在手机打开这个链接..." | 贴 curl 命令 + verification_url= 直接说 |
| "把 8 位用户码 XXXXXXXX 输进去" | 贴 user_code 字段名 |
| "已经准备好这些能力：xxx" | 列 capabilities[] 数组 |
| "要不要帮你把后台能力也开了？" | 直接 `register background_tasks: ...` |
| "已写入你的机器里，重启后还在" | 说 /Users/kk/.openclaw/skills/uumit-agent/ 这种路径 |
| "耗时 30 秒左右，我盯着等" | 暴露 retry_after_seconds / SSE |

**核心原则**：用户不需要懂技术，他只要做"打开链接 → 输入码 → 等我说好"三件事。

## ⚠️ 装机坑表（必读）

| # | 坑 | 表现 | 解法 |
|---|---|---|---|
| K1 | **用本地缓存的 zip** | 网络断了/想加速 → "反正上次下过" | **永远新拉**；每次 `rm -f *.zip` 再 curl |
| K2 | **覆盖了基座 memory/** | rsync 无 --exclude 直接覆盖 → 凭证/会话丢 | **基座必 rsync --exclude=memory**；复制前先 tar 备份 |
| K3 | **staging 与正式目录路径混用** | install.js 看错目录 → check 全绿但装错地方 | staging 时 `UUMIT_SKILL_DIR=$STAGING/<base>`，正式时 `$DEST/<base>`；两边目录**不能混** |
| K4 | **macOS 没 `timeout` 命令** | 授权轮询等不到想加 timeout 报 command not found | 不靠 timeout；用 `terminal(background=true, notify_on_complete=true)` 让后台进程结束后通知 |
| K5 | **前台跑轮询会卡死整个 session** | `timeout 480 node auth.js --wait ...` 在 shell 里跑 8 分钟 | 永远后台化：`background=true, notify_on_complete=true` |
| K6 | **跳过 staging 体检** | 直接复制到正式目录 → 万一 zip 有问题污染生产 | **staging 必须先 install.js --check + validate_skill.js** 两道关 |
| K7 | **装机过程暴露给主人技术细节** | 用户码、verification_url、cron/symlink 等说了一堆 → 主人反感 | **严格按大白话契约**：只说"打开链接 + 输用户码 + 等"三件事 |

## 验收 checklist（装机完成必跑）

```bash
[  ] /tmp/<slug>-install/index.json 是当天联网拉的（不是缓存）
[  ] bundle.zip 大小与 sha256 与 index.json 完全一致
[  ] staging 解压后全部 bundle.skills 子目录在根，且都各自有 manifest.json
[  ] staging 体检：install.js --check = ok:true + drift:false，validate_skill.js = errors:[]
[  ] 正式目录复核：同样两道体检全绿
[  ] 基座 memory/ 没有被覆盖（原文件保留 + tar 备份在 /tmp/）
[  ] scripts/install.js 启动后返回 verification_url + user_code
[  ] 后台轮询用 background=true，notify 模式
[  ] 主人看到的指引纯大白话（不含内部字段名/路径/技术术语）
```

## 快速复用模板（占位符替换）

```bash
SLUG="<第三方代号>"  # 例如 uumit
ENTRY="<入口 index.json URL>"
DEST="<正式目录根>"  # 例如 ~/.openclaw/skills
BASE="<基座名>"     # 例如 uumit-agent
```

详见 `scripts/install-third-party-bundle.sh`（一键实现 Step 1-5）。

---

_2026-08-15 UUMit 装机真实落地沉淀_  
_护栏：第三方 manifest 是 SOLE SOURCE OF TRUTH · 校验先于解压 · 基座 memory/ 必跳 · 大白话先于工程细节_
