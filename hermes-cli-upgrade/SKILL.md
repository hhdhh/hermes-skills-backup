---
name: hermes-cli-upgrade
version: 1.0.0
description: Hermes Agent CLI（hermes-agent Python 包）升级流程。在 conda site-packages 里升级 hermes_agent + 依赖，处理 launchd 守护的 7 个 gateway 进程 + web UI bridge 的 mmap 不刷新问题。先备份后装，不擅自动进程层。
tags:
  - hermes
  - hermes-agent
  - python
  - pip
  - conda
  - upgrade
  - runtime
  - devops
triggers:
  - "hermes --version 显示有新版"
  - "升 hermes"
  - "升 hermes-agent"
  - "upgrade hermes-cli"
  - "hermes pip 升级"
  - "升到 0.X.Y"
category: devops
related_skills:
  - node-version-upgrade        # 同形态不同栈（Node 软链切换 vs Python pip 升级）
  - openclaw-gateway-upgrade-recovery  # OpenClaw gateway 而非 Hermes
---

# Hermes Agent CLI 升级

**主人 ABSOLUTE 授权下**升级 `hermes-agent` Python 包到指定版本。**class-level**：未来任何"升 hermes"类任务都走这个。

---

## 🚨 启动前 4 件事（必做）

升级是**程序层改动**，触三类边界：

1. **pip 升级 → 改 site-packages 实际文件**（可逆，有备份方案即可做）
2. **gateway 进程仍跑旧 mmap 库**（要重启才生效 = 撞"不擅自重启服务"边界 → **必须等主人拍板**）
3. **依赖连带升级**（fastapi/starlette/uvicorn 都是 gateway 栈，可能 breaking change）

**主人的话术特征**：
- "升到 X.Y.Z" = 可以动手
- "不要把自己整没了" = 强护栏指令（备份必须做、动文件前先听主人确认到哪一档）
- "做决定" = ABSOLUTE 模式

---

## 流程（6 步 · 8 命中）

### 1️⃣ 体检升级前状态

```bash
# 1A. CLI 版本
hermes --version 2>/dev/null | head -1

# 1B. gateway 状态（含 7 profile + PID + plist stale 提示）
hermes gateway status 2>&1 | grep -E "(PID|supervised|stale)"
# 期望看到：default gateway + cto/dev/main/ops/qa/security 7 进程 + 偶尔有 plist stale warning

# 1C. doctor 体检（过滤 ANTHROPIC_API_KEY ellipsis warning 噪声）
hermes doctor 2>&1 | grep -vE "(Warning|ANTHROPIC|This usually|If auth|provider's|truncated|Notice)" | tail -40

# 1D. Web UI 健康
curl -s -o /dev/null -w "status=%{http_code} time=%{time_total}s\n" --max-time 3 http://localhost:8648/

# 1E. skill 数（升级不应丢）
ls ~/.hermes/skills/ 2>/dev/null | wc -l

# 1F. 找出跑 hermes_agent 的所有关键 PID
ps aux | grep -E "hermes_cli.main|hermes-bridge|hermes-web-ui" | grep -v grep
```

**记录 6 项基线**——后面"5️⃣ 升级后体检"要逐项比对。

---

### 2️⃣ 备份（不留底牌就是整没了）

**两件必备份**：

```bash
# 备份目录
mkdir -p ~/.hermes/backups/pre-{MAJOR}-{MINOR}-{PATCH}/

# 2A. 备份整个 hermes_agent 包（一行包全部真模块）
cd /Users/kk/miniconda3/lib/python3.13/site-packages
tar -czf ~/.hermes/backups/pre-{MAJOR}-{MINOR}-{PATCH}/hermes_{OLD_VER}_full.tar.gz \
    hermes_cli \
    hermes_bootstrap.py \
    hermes_constants.py \
    hermes_logging.py \
    hermes_state.py \
    hermes_time.py \
    hermes_agent-{OLD_VER}.dist-info/ 2>&1 | tail -3

# 2B. 备份 config / env
cp ~/.hermes/config.yaml ~/.hermes/backups/pre-{MAJOR}-{MINOR}-{PATCH}/config.yaml.bak
[ -f ~/.hermes/.env ] && cp ~/.hermes/.env ~/.hermes/backups/pre-{MAJOR}-{MINOR}-{PATCH}/.env.bak

ls -lh ~/.hermes/backups/pre-{MAJOR}-{MINOR}-{PATCH}/
```

**真包名坑**（2026-08-05 踩）：真实模块名是 `hermes_cli/` + `hermes_bootstrap.py` 等顶层文件，不是 `hermes_agent/` 子目录。`pip show hermes-agent` 显示 Location 是 `site-packages`，但 site-packages 里的目录叫 `hermes_cli`。第一次 tar `hermes_agent/` 就 No such file。

---

### 3️⃣ 查 release 内容（dry-run）

```bash
# 用 uv + 清华源 dry-run（**清华源对 hermes-agent 是稳的**，但 pip 默认走清华源找不到此包）
uv pip install --upgrade hermes-agent \
    --dry-run \
    --python /Users/kk/miniconda3/bin/python3 \
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    2>&1 | tail -30
```

**看 3 个关键点**：

1. **目标版本号** + commit date
2. **会破坏的依赖**（fastapi/starlette/uvicorn 等大跨位 → gateway 栈可能不兼容）
3. **会卸的依赖** + 替换目标（conda 自带的 `xxx (from file:///opt/miniconda3/...)` 会被 PyPI 包顶替）

**owner 拍板点**：碰到 fastapi 0.x→1.x、starlette 0.x→1.x 这种 major 位跳，**风险评估写到报告里给主人**，不要擅自动手。

---

### 4️⃣ 装

```bash
uv pip install --upgrade hermes-agent \
    --python /Users/kk/miniconda3/bin/python3 \
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    2>&1 | tail -30
```

**装完立即验证**：

```bash
hermes --version 2>/dev/null | head -3
# 期望：Hermes Agent v{新版本号} (日期) ... Up to date

/Users/kk/miniconda3/bin/python3 -c "
import hermes_cli, fastapi, starlette, uvicorn, openai
print('hermes_cli', hermes_cli.__version__)
print('fastapi', fastapi.__version__)
print('starlette', starlette.__version__)
print('uvicorn', uvicorn.__version__)
print('openai', openai.__version__)
" 2>&1 | grep -v ANTHROPIC
```

**关键判断**：CLI 命令 + Python import 都通 = 文件层成功 ✅。

---

### 5️⃣ 升级后体检（同 1️⃣ 比对）

跑一次 **1️⃣ 的 6 项命令**，跟升级前快照比对：

| 项 | 期望 |
|---|---|
| `hermes --version` | 新版本号 ✅ |
| `hermes gateway status` | 7 profile PID 仍活 ✅ |
| `hermes doctor` | profiles / skills hub / memory 全 ✅（API key 警告是已知的，不应新增） |
| Web UI :8648 | 200 ✅ |
| skills 数 | 等于升级前 ✅ |
| 关键 PID 仍在 | ✅ 但**进程层的 mmap 还是旧库** |

**最后一项必告诉主人**：
- 升级**文件成功 + 进程仍旧库** 意味着：CLI 命令、Python 一次性 import 都用新版本；**但正在跑的长进程（gateway default / web UI bridge / 6 个 profile gateway）仍用 0.18.2 mmap**
- 这些进程**只有 launchd 重启（崩溃 / logout / 系统升级 / 主人显式 restart）才会切到新库**

---

### 6️⃣ 报告 + 进程层决策点报主人

**绝对不要擅自动 gateway**（AGENTS.md 不擅自重启服务）。给主人列 3 档：

| 档 | 做啥 | 风险 |
|---|---|---|
| A. 全重启 | 8 个进程全 kill 让 launchd 重启 | 最干净。⚠ 万一新版本启动器跟旧 plist 不兼容全挂（备份在，回滚 30 秒） |
| B. 只 web UI bridge（PID 68926） | 只这一个进程重启 | 影响范围最小。gateway default 仍旧库 |
| C. 现在别碰 | 等 launchd 自然重启 / logout | 旧库继续跑，新版本只在 CLI 层就位 |

**默认不擅自选** — 主人 ABSOLUTE 模式不等于 unbounded 风险授权，服务重启属硬边界。

---

## 🛡 回滚（任何档跪了都救得回来）

```bash
# 一行回滚（已验证可行）
tar -xzf ~/.hermes/backups/pre-{MAJOR}-{MINOR}-{PATCH}/hermes_{OLD_VER}_full.tar.gz \
  -C /Users/kk/miniconda3/lib/python3.13/site-packages/ \
&& uv pip install --upgrade --force-reinstall hermes-agent=={OLD_VER} \
   --python /Users/kk/miniconda3/bin/python3 \
   --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 验证
hermes --version 2>/dev/null | head -1
# 应回 OLD_VER
```

---

## ⚠️ 常见坑

### 坑 1：清华源找不到 hermes-agent（走 pip）

`python3 -m pip index versions hermes-agent` 走清华源报"No matching distribution found"。**必须用 `uv pip`**。PyPI 默认源在主人环境下 curl 也会被 shell 防护 block。

### 坑 2：`hermes doctor` 提示 `pip install -e '.[all]'` 是误报

升级完 doctor 末段会建议"重新装 entry point"。这**不需要**——`/Users/kk/.local/bin/hermes` 是软链 → `/Users/kk/miniconda3/bin/hermes`（也是软链/可执行），pip 升级自动刷。

### 坑 3：profile "no .env" ≠ profile 不活

`hermes gateway status` 的 Profiles 段会显示 `pm: no .env`、`cto: gateway running, no .env` 等。**`no .env` 是缺 API key 警告，进程是跑的**。看 PID 那行才是状态。

### 坑 4：进程 mmap 真相

升级完 site-packages 后，**已在内存里的进程不会刷新 import**。新版本只在：
- 下次 `hermes --version` 这种**新进程**生效
- 任何新启动的 Python import hermes_cli 的脚本生效
- 重启了的 gateway 进程生效

已跑的进程继续用旧库直到被 kill。

### 坑 5：shell `--help` 也会被 block

`hermes gateway restart --help` 这种命令会被环境拦下来报"BLOCKED"。**不是真卡**，是 hermes 自家 shell policy 对任何"可能动服务"的命令加确认。
- 解决：跳过 `--help`，直接看 `hermes --version` 这类只读命令验状态
- 想了解命令，先查 `/Users/kk/miniconda3/lib/python3.13/site-packages/heres_cli/` 下的源

### 坑 6：dist-info 自带清理

`hermes-agent==A.B.C` 升级到 X.Y.Z 后：
- `hermes_agent-{A.B.C}.dist-info/` 自动删除
- `hermes_agent-{X.Y.Z}.dist-info/` 自动出现
- 手动备份前先看 `pip show hermes-agent | grep Version` 拿版本号

### 坑 7：ANTHROPIC_API_KEY ellipsis warning 噪声

主人 .env 里 `ANTHROPIC_API_KEY` / `ANTHROPIC_PROXY_API_KEY` 包含 `…`（U+2026），每次 hermes 命令都打 warning。**不影响功能**（strip 自动完成），grep 时要过滤 `Warning|ANTHROPIC|This usually|If auth|provider's|truncated|Notice`。

---

## 🔗 相关 skill（不是替代）

- **`node-version-upgrade`**：Node/npm 升版的对应 skill。同形态不同栈。本 skill 不替代，仅在 Hermes Python CLI 范畴内适用。
- **`openclaw-gateway-upgrade-recovery`**：OpenClaw 自己的 gateway 故障恢复。本 skill 不管 OpenClaw gateway。
- **`workspace-hygiene`**：工作区清理。版本升级 ≠ 清理。

---

## 主人偏好固定（嵌入 skill，不再每次重临场）

| 偏好 | 来源 | 行为 |
|---|---|---|
| ABSOLUTE 授权 | 2026-06-18 "所有任务都继续推进 不要停下来" | 不问"要不要我做 X"——直做可逆动作 |
| "不要把自己整没了" | 2026-08-05 "升到 0.19.0 不要把自己整没了" | 备份必做，不擅自动进程层 |
| "做决定 / 全权" | 2026-06-18 11:25 | trust-but-verify，关键操作先汇报不请示 |
| 不擅自 mass-delete / 不擅自重启服务 | AGENTS.md 三化身共守 | 文件可动 / 进程不动 |
| trust-but-verify 关键操作先汇报 | 2026-06-16 LEARNINGS | 升级涉及进程层必须报主人决策 |

---

## 📎 引用

- `references/hermes-cli-pkg-layout.md` — site-packages 实际文件结构（避开"hermes_agent"目录坑）
- `references/conda-env-paths.md` — ~/miniconda3/env/ 和 system Python 选哪个的判定
- `templates/upgrade-checklist.md` — 每次升级前打印填的检查表
- `scripts/preflight.sh` — 1️⃣ "体检升级前状态" 的封装脚本（可一键跑）

---

**印证会话**：2026-08-05 Hermes 0.18.2 → 0.19.0 升级实战。从体检、备份（含第一次 tar 错路径）、dry-run 看 release content、装、6 项比对、到进程层 3 档报主人，**全走通**。备份 `~/.hermes/backups/pre-019-0/hermes_0182_full.tar.gz` (6.7MB) 在手。
