---
name: huihui-hermes-deploy-cross-platform
description: Hermes Agent 在新机器上从零部署到能对话的完整 playbook。覆盖 Mac/Win/Linux 前置环境、Python PATH 坑、minimax API key 失效处理、soul/skills/scripts 跨机器迁移、launchd/Task Scheduler 守护差异。Use when (1) 主人在新机器上要装 Hermes (2) 主人说"在 Windows 部署"/"在另一台电脑跑" (3) `py --version` / `pip` / `python` 报"未识别" (4) 主人要"配置好一切" 的新机器环境。
---

# huihui-hermes-deploy-cross-platform — Hermes 跨平台部署 Playbook

> 背景：2026-08-07 主人在另一台 Windows 上部署 Hermes，触发 Python 占位/PATH/missing pip/symlink 不可移植 4 大坑的真实路径。

## 与已有 skill 的关系

- **huihui-upgrade-hermes**（已装 v0.19.0）：管"已装 Hermes 的 macOS 升级"，本 skill 管"从零到能对话的首次部署"。两者是上下游（先 deploy，再 upgrade）。
- **huihui-cli-upgrade**（已装）：管 Hermes CLI 本身升级，跟首次部署不重叠。
- **huihui-absolute-gating**：本 skill 假设主人在 ABSOLUTE 模式——主人说"给我全部命令" = 直接 5 档全列，不要反问选档。

## 文件清单

| 文件 | 用途 |
|---|---|
| `SKILL.md` | 本 playbook（5 档部署 + 跨平台坑表） |
| `references/windows-python-env-recovery.md` | Windows Python 占位/PATH 全套修复 session 笔记 |
| `references/migration-zip-recipe.md` | Mac → 新机器打包 + 解压 + 验证一条龙 |
| `references/ssh-migration-preflight.md` | SSH 迁移前连通性判定：LAN/virbr 地址、SSH 启用、分阶段审批与可恢复同步 |
| `scripts/migration-zip.sh` | Mac 端打 zip 脚本（soul/memory/skills/scripts 全打） |
| `scripts/windows-deploy.ps1` | Windows 端从零到能对话的一键脚本 |

## 何时用

| 触发 | 动作 |
|------|------|
| 主人说"在另一台 Windows 部署" / "配置好新电脑" | 走本 skill，5 档按需选 |
| `pip` / `py` / `python` 报"未识别" | 走 §1 诊断（先判是 Python 没装 vs PATH 没刷） |
| 主人说"全部交给你" | 5 档全部列，等同全包 |
| 跨机器迁移 soul/memory/skills | 先走 SSH 连通性预检，再走 §6 打包 + §7 解压路径 |
| 目标 IP 可 Ping 但 SSH 报 `Connection refused` | 主机在线、SSH 未监听；先启用 Remote Login/OpenSSH，不排查密码 |
| minimax API key 在新机器报 401 | §8 凭证处理 |

## 迁移前置：先打通 SSH，再生成迁移包

跨机器迁移必须按以下顺序执行：

1. 核对目标当前局域网 IP，并检查路由是否走正确接口。
2. 分别验证 Ping、TCP 22 和 SSH 认证；不要把“主机在线”“SSH 服务在线”“凭证正确”混为一层。
3. 只有 SSH 可连接后，才盘点并备份远端 `~/.hermes`。
4. 远端备份成功后再即时展开本机 skill 软链接并传输，避免提前生成大型、易过期的迁移包。
5. 详细判定表与 macOS/Windows 启用 SSH 命令见 `references/ssh-migration-preflight.md`。

## 部署 5 档 Play（按需组合）

### 档 0 · 平台前置（必跑）
**Windows**（PowerShell 管理员）：
```powershell
winget install Python.Python.3.12     # 关键陷阱见 §1
winget install Git.Git
winget install OpenJS.NodeJS.LTS
refreshenv
```

**macOS**（terminal）：
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python@3.12 git node
```

**Linux**（apt）：
```bash
sudo apt update && sudo apt install -y python3.12 python3-pip git nodejs npm
```

### 档 1 · 最小可用 Hermes（10 分钟）
**永远用 `py -m pip` 而不是 `pip`**（跨平台最稳）：

```powershell
# Windows
py -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
py -m pip install hermes-agent -i https://pypi.tuna.tsinghua.edu.cn/simple
hermes --version
```

```bash
# macOS（conda 路线，按实际安装位置）
~/miniconda3/bin/python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
~/miniconda3/bin/python -m pip install hermes-agent -i https://pypi.tuna.tsinghua.edu.cn/simple

# Linux（系统 Python 或已有虚拟环境）
python3 -m pip install --user --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
python3 -m pip install --user hermes-agent -i https://pypi.tuna.tsinghua.edu.cn/simple
hermes --version
```

### 档 2 · 灵魂迁移（"灰灰"登场）
**只拷 soul/identity/memory，**不**拷 auth.json**（API key 跟机器指纹绑定）。

| 源（Mac） | 目标（Windows） |
|---|---|
| `~/.hermes/SOUL.md` | `C:\Users\<你>\.hermes\SOUL.md` |
| `~/.hermes/memories/MEMORY.md` | `C:\Users\<你>\.hermes\memories\MEMORY.md` |
| `~/.hermes/memories/USER.md` | `C:\Users\<你>\.hermes\memories\USER.md` |
| `~/.hermes/IDENTITY.md` | `C:\Users\<你>\.hermes\IDENTITY.md` |
| `~/.hermes/AGENTS.md` | `C:\Users\<你>\.hermes\AGENTS.md` |

验证：soul 第 1 行应该是 `# SOUL.md - 慧慧的灵魂（Hermes 化身）`。

### 档 3 · skills 迁移（175+ 项）
**关键**：Mac 上 skills/ 大量是 symlink 到主体 `~/.openclaw/workspace/skills/`，**Windows 不识别 symlink**。

Mac 端先把 symlink 展开：
```bash
cd ~/.hermes/skills
for f in */; do
  if [ -L "$f" ]; then
    cp -RL "$f" "$f.real"
    rm "$f"
    mv "$f.real" "$f"
  fi
done
```

然后打包拷到 Windows 对应路径。

### 档 4 · 后台守护（平台差异）

| 平台 | 机制 | 启动 |
|---|---|---|
| macOS | launchd | `~/Library/LaunchAgents/ai.hermes.gateway-*.plist` + `launchctl load` |
| Windows | Task Scheduler | 见 `scripts/windows-deploy.ps1` |
| Linux | systemd user unit | `~/.config/systemd/user/hermes.service` |

### 档 5 · Web UI
```bash
# 全平台通用
pip install hermes-web-ui -i https://pypi.tuna.tsinghua.edu.cn/simple
hermes-web-ui start
# 浏览器：http://localhost:8648
```

## ⚠️ 跨平台坑表（必读）

| # | 坑 | 表现 | 解法 |
|---|---|---|---|
| K1 | **Microsoft Store Python 占位** | `winget install Python.Python.3.12` 报"已装"，但 `py` / `pip` 全 "command not found" | 卸载占位 → 强装：`winget install --id Python.Python.3.12 --force`；或官网安装包**勾选 Add python.exe to PATH** |
| K2 | **PATH 没刷** | 装完 Python 后旧 PowerShell 窗口里 `py` 找不到 | **关掉 PowerShell 开新的**；或手动 `[Environment]::SetEnvironmentVariable("Path", ..., "User")` |
| K3 | **`pip` 单独命令不在** | `pip` 报未识别，但 `py` 在 | **永远用 `py -m pip`** 而不是 `pip`（Windows 上 pip.exe 不一定在 PATH） |
| K4 | **C:\ 下找不到 python.exe** | `Get-ChildItem C:\ -Filter python.exe -Recurse` 无输出 = Python 解释器没装（不是 PATH 问题） | 走 K1 重装；不要靠 SetEnvironmentVariable 救 |
| K5 | **PyPI 默认源卡顿** | `pip install` 几十秒无响应 | **全程加 `-i https://pypi.tuna.tsinghua.edu.cn/simple`** |
| K6 | **minimax API key 401** | 新机器上 `auth.json` 是从 Mac 拷的，`last_status: exhausted` | **不拷 auth.json**；新机器重新 `hermes config set providers.minimax.api_key "新key"` |
| K7 | **symlink 不可移植** | Mac skills/ 里大量 symlink → Windows 显示"[无法访问]" | Mac 端 `cp -RL` 展开再拷（见档 3） |
| K8 | **launchd ≠ Task Scheduler** | Mac plist 在 Windows 完全无用 | Windows 用 Task Scheduler 走 `scripts/windows-deploy.ps1` |
| K9 | **Conda 不是 venv** | doctor 报 "venv entry point not found" 是**误报** | 跳过，不动 conda 的 site-packages |
| K10 | **Path 长度限制** | Windows MAX_PATH 260 字符，skills 深路径会失败 | Windows 10+ 启用长路径：`Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name LongPathsEnabled -Value 1` |
| K11 | **`~/.hermes/scripts/*.sh`** | macOS 路径里 Windows 上不存在 | Windows 等价：PowerShell 脚本 `*.ps1` 替代 |
| K12 | **SOUL.md 里的路径** | soul 写的 `~/.openclaw/workspace/` 在 Windows 上不存在 | soul 引用主体路径时，要意识到化身 2 在 Windows 是独立身体——主体仍在 Mac 上 |
| K13 | **Linux `fluid-memory` 假绿** | chromadb 已装，但脚本仍写 `~/.openclaw/workspace/database\\...`，wrapper 只找 Windows `python.exe`/PATH `python` | 只改目标机副本：数据根改为 `~/.hermes/memory-data`；wrapper 优先 `sys.executable`；用 Hermes venv 实际跑 `wrapper.py status`，必须返回 `backend: ChromaDB` |
| K14 | **npm 中断后 `ENOTEMPTY`** | `npm install -g` 长时间卡住，中止后重试报 rename/ENOTEMPTY | 先逐个运行目标 bin 判断哪个已完整安装；保留可用包，只对失败包 `npm uninstall -g <pkg>` 后用镜像源单独重装，禁止粗暴清空整个 npm-global |
| K15 | **Linux venv Python 软链接失效** | `~/.local/bin/python -> <venv>/bin/python` 执行时可能回落系统解释器，导致 venv 包 `ModuleNotFoundError` | 改用 shell wrapper：`exec /home/<user>/.hermes/hermes-agent/.venv/bin/python "$@"`，再实际 import 依赖验证 |
| K16 | **Gateway cwd 不在 Hermes home** | Web UI 启动的 gateway cwd 可能是 npm 包目录，`~/.hermes/AGENTS.md` 的知识入口不一定随 cwd 注入 | 在标准 `memories/MEMORY.md` 追加目标机知识索引指针；从 gateway 实际 cwd 启动 oneshot，验证能回答知识目录；不要靠重启碰运气 |

## 主人 ABSOLUTE 模式下的部署话术

主人说"在另一台 Windows 部署"或"给我全部命令"——按以下节奏回：

1. **第 1 句**：列 5 档（档 0 必跑 + 档 1 必跑），让主人看哪档需要
2. **不反问选档**：主人 ABSOLUTE = 默认 5 档全列，等同全包
3. **关键诊断**：如果主人贴"command not found"，先判是 K1/K2/K3 哪一档再给修法
4. **不拷 auth.json**：永远提醒主人 API key 要重配
5. **soul 验证**：拷完 soul 第一时间 `type SOUL.md | head -1` 验证

## 验收 checklist（新机器必跑）

```powershell
# Windows 端
[  ] py --version 输出 Python 3.12.x
[  ] hermes --version 输出 Hermes Agent v0.X.Y
[  ] type $env:USERPROFILE\.hermes\SOUL.md 第一行含 "慧慧的灵魂"
[  ] ls $env:USERPROFILE\.hermes\skills | Measure-Object | Select Count >= 150
[  ] hermes chat "你是谁" 看到灰灰回应
[  ] hermes-web-ui start 看到 :8648 listening
[  ] Task Scheduler 里 "Hermes-Heartbeat" 任务在
```

---

_2026-08-07 真实部署 session 沉淀_
_护栏：永远 py -m pip · 不拷 auth.json · symlink Mac 端先展开 · PATH 刷不开就重装_