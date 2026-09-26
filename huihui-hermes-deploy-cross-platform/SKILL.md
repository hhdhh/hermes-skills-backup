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
| `references/migration-zip-recipe.md` | Mac → 新机器打包 + 解压 + 验证一条龙（含排除清单 + 大件决策点） |
| `references/ssh-migration-preflight.md` | SSH 迁移前连通性判定：LAN/virbr 地址、SSH 启用、分阶段审批与可恢复同步 |
| `references/hermes-windows-config-quirks.md` | hermes 0.19.0 on Windows 配置侧坑：custom_providers / config & .env 实际位置 / built-in provider / dashboard auth（K22-K26） |
| `scripts/migration-zip.sh` | Mac 端打 zip 脚本（soul/memory/skills/scripts 全打，symlink 展开） |
| `scripts/windows-deploy.ps1` | Windows 端从零到能对话的一键脚本 |

**Linux → Windows 专属**：zip 排除 + scp 路径 + pwsh 解 UTF-8 + SSH 隧道 + Task Scheduler 一条龙 inline 在档 2.5 文字里；未单独抽出 reference/script 文件（避免一文件一坑）。

## 何时用

| 触发 | 动作 |
|------|------|
| 主人说"在另一台 Windows 部署" / "配置好新电脑" | 走本 skill，5 档按需选 |
| `pip` / `py` / `python` 报"未识别" | 走 §1 诊断（先判是 Python 没装 vs PATH 没刷） |
| 主人说"全部交给你" | 5 档全部列，等同全包 |
| 跨机器迁移 soul/memory/skills | 先走 SSH 连通性预检，再走 §6 打包 + §7 解压路径 |
| 目标 IP 可 Ping 但 SSH 报 `Connection refused` | 主机在线、SSH 未监听；先启用 Remote Login/OpenSSH，不排查密码 |
| 主人说"用 netbird 连 X 电脑配置" | 走 `references/ssh-migration-preflight.md` §NetBird 段：先看本机 `Peers count X/167 Connected`——X 远小于 167 表示未与目标直连；目标机器 netbird SSH Server 默认 Disabled |
| minimax API key 在新机器报 401 | §8 凭证处理 |

## 迁移前置：先打通 SSH，再生成迁移包

跨机器迁移必须按以下顺序执行：

1. 核对目标当前局域网 IP，并检查路由是否走正确接口。
2. 分别验证 Ping、TCP 22 和 SSH 认证；不要把“主机在线”“SSH 服务在线”“凭证正确”混为一层。
3. **主人报"IP 改了"时不直接信任新 IP 覆盖记录**——先确认连的是同一台机：TTL 指纹（Windows≈128、Linux≈64）+ 探测该机已知服务端口（如 22 运维机 / 8748 Ekko Studio）+ SSH 进去取 hostname 三方对齐，确认是原机搬迁而非被别的机器占了 IP，才更新记忆/连接信息。
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

| 源（Mac/Linux） | 目标（Windows） |
|---|---|
| `~/.hermes/SOUL.md` | `C:\Users\<你>\.hermes\SOUL.md` + `%LOCALAPPDATA%\hermes\SOUL.md` |
| `~/.hermes/memories/MEMORY.md` | `C:\Users\<你>\.hermes\memories\MEMORY.md` |
| `~/.hermes/memories/USER.md` | `C:\Users\<你>\.hermes\memories\USER.md` |
| `~/.hermes/IDENTITY.md` | `C:\Users\<你>\.hermes\IDENTITY.md` |
| `~/.hermes/AGENTS.md` | `C:\Users\<你>\.hermes\AGENTS.md` |

**两处都要拷**：hermes 读 `HERMES_HOME`（即 `%LOCALAPPDATA%\hermes\`），但 `~/.hermes/SOUL.md` 是文档/IDE/外部工具的查找路径；任何一处缺都会被默认模板覆盖。

**关键陷阱（K17）**：解压+`hermes setup` 首次启动后，**`hermes doctor` 会自动 seed 默认 SOUL.md 到 `HERMES_HOME`**，把用户灵魂覆盖成"我是 Hermes Agent, Nous Research 创建的..."。**必须在 doctor 跑完后重新覆盖一次 SOUL.md**，再跑 `hermes chat "你是谁"` 端到端验证回答是慧慧/灰灰身份。

验证（用字节数硬验证，不用文本软验证）：

```powershell
# 字节数对齐才算成功——不信任 head -1，cp936 编码下乱码可能让默认模板看起来也像
$src = "C:\path\to\source\SOUL.md"   # 本机 SOUL.md
$dst = "$env:LOCALAPPDATA\hermes\SOUL.md"
if ((Get-Item $src).Length -ne (Get-Item $dst).Length) {
    Write-Error "SOUL.md byte mismatch - copy failed"
}
```

最后跑 `hermes --cli -m <model> -z "你是谁"` 看回答是不是匹配灵魂身份（不是 Hermes Agent 默认模板）。

### 档 2.5 · Linux 源路线（专属，与 Mac 不同）
**走这条路如果源是 Linux（Ubuntu/Debian/Arch），不是 Mac**：要点差异（全部 inline 在本节，未抽 reference/script，避免一文件一坑）：

- **Linux 没有 symlink 展开步骤**（直接 cp -R）—— 但**有 `.venv / node_modules / __pycache__` 排除**（用 rsync，1.4G → 1.1G 节省 30%）
- **走 NetBird VPN** 而不是 LAN 直连：本机 `Peers count X/167 Connected`，目标 P2P Connected 之后才传；不要赌 Relay 带宽
- **scp 路径必须 `C:/Users/...`** 不是 `/c/Users/...`（Win OpenSSH SFTP 不认 MSYS 路径）
- **Windows 解压必须 `pwsh` (PowerShell 7+)** 不是 PowerShell 5.1——后者默认 GBK 解 UTF-8 文件名会炸
- **hermes 0.19.0 配置变了**：provider id 是 `minimax`（built-in，不是 custom），env_vars 自动读 `MINIMAX_API_KEY + MINIMAX_BASE_URL`；`.env` 在 `%LOCALAPPDATA%\hermes\.env`，不是 `~/.hermes/.env`（K21）；顶层 `custom_providers` 段才能让 `provider: custom` 真生效（K20）
- **Web UI 不是 `hermes-web-ui`**（Windows 装的是 npm 包 0.4.0，可装；hermes-agent 自带 `hermes dashboard` 占 9119）。**两者并存**：Ekko Studio（hermes-web-ui）→ 8648，Hermes Agent Dashboard → 9119
- **0.0.0.0 bind 被 6 月硬化阻止**——走 127.0.0.1 + SSH 隧道（`ssh -L 18648:127.0.0.1:8648 jk@<ip>`）
- **Task Scheduler 注册后用 `Start-ScheduledTask` 验证**——避免真重启后再断连
- **跨 shell 传 PowerShell 代码走 base64+UTF-16LE+`-EncodedCommand`**（K18）；**长跑进程用 `cmd /c start /B <bat>` 间接启**（K19）
- **解压后必须重推 SOUL.md 一次 + icacls 锁权限 + ReadOnly 属性**——防 doctor 自动覆盖（K17）
- **`pip install hermes-agent` 撞 WinError 32 文件占用**（certifi/pillow/packaging 同时被 Python 进程锁）—— 用 `--user --no-build-isolation`，绕开系统 site-packages（K22）

**同一台机器部署多套灵魂（multi-soul deployment）**：当目标机器要承担**两个或更多不同身份**（如"私人慧慧/灰灰" + "运营助手"），不拷多份完整 hermes，只**改 SOUL/IDENTITY/USER 三件套**：
- `~/.hermes/SOUL.md` / `IDENTITY.md` / `memories/USER.md` 是**单槽位**——一次只装一个身份；切换身份 = 重写这三个文件
- 切换流程：解锁（`Set-ItemProperty IsReadOnly false` + `icacls /grant:r`） → scp 新文件 → 重锁 → `hermes chat "你是谁"` 端到端验证身份切换
- **绝不能共用同一份 SOUL.md**——私人灵魂有"主人""永远在你身边"等亲密表达，公司灵魂要专业简洁。共用会泄露私人印记
- 知识库 `~/.hermes/skills/` 和 `~/.hermes/knowledge/` 是**身份无关**的共享资源，按场景加载特定 skill 即可
- 模型 `model.default` 也是身份无关，但**不同身份的 SYSTEM 行为偏好靠 SOUL.md 而非 model 配置**——切模型不切灵魂没意义

**本地 skill 加载方式（关键事实）**：拷过去的 `~/.hermes/skills/` 下 200+ 目录，**hermes 默认不自动加载**。验证方法：`hermes skills list` 输出 "0 hub-installed, 0 builtin, 0 local"。本地 skill 通过 `hermes --skills <名字>` 按需加载进 chat context；Ekko Studio (hermes-web-ui) 的 web UI 在配置 session 时让用户勾选。**部署后不要假定 skill 自动可用**——必须 `hermes --cli --skills <关键skill名> -m <model> -z "<触发问题>"` 实测才能验证 skill 真生效。

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
**两个不同的东西，别混**：

| 来源 | 命令 | 默认端口 | 适用 |
|---|---|---|---|
| npm 全局包 `hermes-web-ui` | `hermes-web-ui start` | **8648** | macOS / Ubuntu 主化身常用 |
| hermes-agent 内置 web UI | `hermes serve --host 127.0.0.1 --port 9119` | **9119** | Windows / pip 装的 hermes-agent |

```bash
# macOS / Linux（npm 路线）
npm install -g hermes-web-ui --registry=https://registry.npmmirror.com
hermes-web-ui start
# 浏览器：http://localhost:8648
```

```powershell
# Windows（hermes-agent pip 路线）
hermes serve --host 127.0.0.1 --port 8648
# 浏览器：http://localhost:8648
# 局域网访问见 K26 —— 绑 0.0.0.0 必配 auth
```

**端到端联通验收**：`Test-NetConnection -ComputerName 127.0.0.1 -Port 8648 -InformationLevel Quiet` 必须 `True`；`Invoke-WebRequest http://127.0.0.1:8648 -UseBasicParsing` 必须返回 200。

**Ekko Studio（`hermes-web-ui`，npm 全局包，0.7.x）** vs **Hermes Agent Dashboard**（`hermes dashboard`，Python 内置）**是两套独立的 UI**：
- 端口不冲突：Ekko Studio 默认 8648，Hermes Dashboard 默认 9119，**两套并存各司其职**
- 升级 Ekko Studio：`npm install -g hermes-web-ui@latest`（npm 上 `latest` tag 指向当前 release）
- 0.7.x 警告 EBADENGINE 要求 `node >=23.0.0`，当前 node 22.14 能跑但不优雅——**仅 warning，不阻塞启动**；真出问题再升 Node（`winget install OpenJS.NodeJS.LTS`）
- 验证：`hermes-web-ui version` + `netstat -ano | Select-String :8648` 确认监听 + 浏览器开页面 title 含"Ekko Studio"

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
| K17 | **pip install 触发 WinError 32 文件占用** | `pip install hermes-agent` 报 `WinError 32: 另一个进程正在使用此文件` 指向 `cacert.pem` / Pillow / psutil 等 | 进程里有别的 Python 解释器在跑（旧脚本/服务/资源管理器）；先 `Get-Process python` 看谁在跑；改用 `py -m pip install --user --no-build-isolation <pkg>` 把包装到 `%APPDATA%\Roaming\Python\<ver>\site-packages`，绕过系统 site-packages 的文件占用 |
| K18 | **`--user` 装的 hermes-agent scripts 不在 `py` 启动器 PATH** | `hermes --version` 在 bash 直接调报"command not found"，但 `C:\Users\<u>\AppData\Roaming\Python\Python312\Scripts\hermes.exe` 存在 | 永远先 `where.exe hermes` 或绝对路径调；解决持久化用 `[Environment]::SetEnvironmentVariable("Path", $env:Path + ";<ScriptsDir>", "User")`（用户授权下），新 shell 即生效 |
| K19 | **pip 中断留下 `~xxx` lock 目录** | `py -m pip` 警告 `Ignoring invalid distribution ~ertifi (~sutil / ~il / ~ydantic_core)` | 进程退出后用 PowerShell `Remove-Item "<env>\Lib\site-packages\~*" -Recurse -Force` 清空；运行中删不掉是正常的，等进程退出再清 |
| K20 | **PowerShell 5.1 解压 zip 报"路径中含有非法字符"** | `[System.IO.Compression.ZipFile]::ExtractToDirectory` 在 Windows PowerShell 5.1（默认 GBK/cp936）下解 UTF-8 文件名的 zip 失败 | **装 PowerShell 7+**：`winget install Microsoft.PowerShell`；pwsh 默认 UTF-8 + UTF-16 LE `-EncodedCommand` 干净传递；不用 Expand-Archive 也不用 PowerShell 5.1 + .NET ZipFile 调 UTF-8 zip |
| K21 | **`scp` 到 Windows OpenSSH 路径风格不匹配** | Linux 端 `scp file user@win:/c/Users/...` 报 `dest open: No such file or directory` | Windows OpenSSH 的 SFTP server 不认 MSYS 风格 `/c/Users/...`；用 Windows 风格 `C:/Users/<u>/...`（正斜杠）。Linux `ssh user@host:/c/...` 同样规则 |
| K22 | **hermes 0.19.0 实际写 `AppData\Local\hermes\`，不是 `~/.hermes/`** | `~/.hermes/config.yaml` 改了不生效；`~/.hermes/.env` 设了 env var 不被读 | hermes 把运行数据写在 `C:\Users\<u>\AppData\Local\hermes\`：`config.yaml` / `auth.json` / `.env` 都走这里；灵魂/memory/skills 仍走 `~/.hermes/`。先用 `hermes config env-path` / `hermes config path` 验证实际位置 |
| K23 | **`custom_providers` 是顶级 list，不是 alias 字段** | 写 `model.aliases.X.provider: custom` 配自定义 base_url，chat 报 `No inference provider configured` | 自定义 OpenAI 兼容端点写 `custom_providers:`（config.yaml 顶级 list），每项含 `name` / `base_url` / `api_key` 或 `key_env` / `model` / `api_mode` / `models`；alias 只用于切换模型别名，不要把 endpoint 配置塞进 alias |
| K24 | **优先用 built-in provider（如 `minimax`），不要绕 custom** | 同样 key 配 custom 报 `HTTP 401: invalid api key`；改 built-in 后通 | 自带的 `minimax` / `anthropic` / `openai` / `openrouter` 等 provider 已注册 `PROVIDER_REGISTRY`，env_vars + base_url_env_var 都配好；只要设对应 env var（如 `MINIMAX_API_KEY` + `MINIMAX_BASE_URL`）就行。`hermes auth list` / `hermes fallback list` 看支持的 provider 列表 |
| K25 | **`hermes config set` 用 positional args，不支持 `--value`** | `hermes config set model.aliases.x --value "..."` 报 `unrecognized arguments: --value` | 实际语法 `hermes config set [key] [value]`；复杂 dict 用 Python `hermes_cli.config.save_config(load_config() | update({"...": {...}}))` 直接写 config.yaml；记得 `Copy-Item` 备份原文件 |
| K26 | **`hermes serve` / `hermes dashboard` 绑 0.0.0.0 强制要求 auth** | `Refusing to bind dashboard to 0.0.0.0 — the auth gate engages on non-loopback binds, but no auth providers are registered.` | 三选一：(a) bind `127.0.0.1` + 本地/SSH/NetBird 隧道；(b) 配 basic auth：`dashboard.basic_auth.username` + `dashboard.basic_auth.password_hash`（hash 用 `py -c "from plugins.dashboard_auth.basic import hash_password; print(hash_password('<pw>))"`）；(c) `hermes dashboard register` 走 OAuth。**没有"无 auth 公开 bind"这个选项**——是 2026-06 hardening 后的硬规定 |
| K27 | **MSYS bash 在嵌套 SSH + PowerShell 时吞 PowerShell 反引号/单引号** | `sshpass -p 0 ssh ... 'powershell -Command "Get-Item \`$env:X"'` 报 SyntaxError，PowerShell 看到 `= Stop` 这种残缺 | 永远 `pwsh -NoProfile -ExecutionPolicy Bypass -EncodedCommand <base64>`，base64 = `iconv -f UTF-8 -t UTF-16LE <ps1> | base64 -w 0`；不用反引号、不用单引号 here-string 套反引号 |
| K28 | **hermes-agent PyPI 包装名是 `hermes_agent`，实际包名是 `hermes_cli`** | `py -c "import hermes_agent"` 报 `ModuleNotFoundError`，但 `hermes.exe` 跑得好；找包目录找 `hermes_agent` 子目录不存在 | hermes CLI 入口包名是 `hermes_cli`，源码在 `AppData\Roaming\Python\Python312\site-packages\hermes_cli\`；诊断/grep 错误信息用 `hermes_cli/...` 路径 |
| K17 | **`hermes doctor` 自动 seed SOUL.md 覆盖用户灵魂** | 解压后 SOUL.md 字节数对、内容前几行也像，但实际是 `default_soul.py` 模板；用户跑 `hermes chat "你是谁"` 收到"我是 Hermes Agent, Nous Research 创建的..."而不是"我是慧慧" | 解压+`hermes setup`/首次启动后**重新覆盖 SOUL.md 一次**到 `HERMES_HOME`（即 `%LOCALAPPDATA%\hermes\SOUL.md`）+ `~/.hermes/SOUL.md`，用 `wc -c` 硬验证字节数对齐源；最后跑一次 `hermes chat "你是谁"` 确认回答匹配灵魂身份。**不要信任 `head -1` 单行软验证**——Windows cp936 编码下乱码会让覆盖后的默认模板看起来"也像"灵魂 |
| K18 | **PowerShell here-string 反引号被 bash 吃** | `\`n` / `\`$var` 在 msys bash → Windows pwsh 链路里全部被 shell 解释成换行/命令替换，写出来的文件是 `${}VAR` 而不是 `${VAR}` | 跨 shell 传 PowerShell 代码唯一稳的路线：`iconv -f UTF-8 -t UTF-16LE script.ps1 | base64 -w 0` → `pwsh -EncodedCommand <B64>`，**避免任何 `\`n / \`$ 转义** |
| K19 | **Windows `Start-Process` 启长跑进程卡住** | `Start-Process hermes -ArgumentList ...` 在 SSH + PowerShell 链路上挂死，进程不退出、端口不 listen | 用 `cmd /c start /B <bat>` 间接拉起；bat 里调 hermes；命令行工具接受管道 heredoc，hermes 这种长跑服务走 bat 间接启动 |
| K20 | **`provider: custom` alias 不够，必须有顶层 `custom_providers`** | hermes 0.19.0 的 `model.aliases.*.provider: custom` 不会自动注册 provider；`hermes chat` 报 `No inference provider configured` | 顶层加 `custom_providers: [{name, base_url, key_env, api_mode: chat_completions, model, models: {...}}]`，或者直接用 built-in provider id（如 `minimax`），env_vars 自动从 `.env` 读 |
| K21 | **hermes `.env` 路径 ≠ `~/.hermes/.env`** | hermes `config env-path` 实际是 `%LOCALAPPDATA%\hermes\.env`（Windows）/ `~/.local/share/hermes/.env`（Linux），不是 `~/.hermes/.env` | 把 API key 写到 `hermes config env-path` 显示的路径；或者 `hermes config get model.aliases.X` 反查；写错路径时症状是 `HTTP 401: invalid api key`（因为 hermes 拿到字面 `${ENV}` 当 key） |
| K22 | **Windows `pip install hermes-agent` 撞 WinError 32** | 装到一半 certifi/pillow/packaging 的 .pem / .dist-info 同时被正在跑的 Python 进程锁住（资源管理器、VSCode、hermes 自身），pip 报 `[WinError 32] 另一个程序正在使用此文件` 中断 | 加 `--user --no-build-isolation`，把 hermes-agent 装到 `%APPDATA%\Roaming\Python\Python312\site-packages\`，不碰系统 site-packages；装完用 `Get-FileHash` 验 `hermes.exe` sha，再 `hermes --version` 看能跑 |

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
[  ] (Get-Item $env:USERPROFILE\.hermes\SOUL.md).Length -eq 14580        # 字节数对齐源，不是 head -1
[  ] (Get-Item $env:LOCALAPPDATA\hermes\SOUL.md).Length -eq 14580       # HERMES_HOME 也有，逃过 doctor 覆盖
[  ] ls $env:USERPROFILE\.hermes\skills | Measure-Object | Select Count >= 150
[  ] ls $env:USERPROFILE\.hermes\memories | Should contain MEMORY.md, USER.md  # 没有 .bak/.lock
[  ] hermes --cli -m <model> -z "你是谁" 回答含 "慧慧" 或 "灰灰"  # 端到端验证灵魂加载，不是 Hermes Agent 默认模板
[  ] hermes-web-ui start 看到 :8648 listening
[  ] Task Scheduler 里 "Hermes-Heartbeat" 任务在
[  ] icacls $env:USERPROFILE\.hermes\SOUL.md /inheritance:r /grant:r "${env:USERNAME}:(R,W)"  # 锁权限防 doctor 再覆盖
```

**绝对不能信任**：`type SOUL.md | head -1` 在 Windows cp936 编码下默认 SOUL.md 的中文也"看起来像"灵魂；只看头部文本不能区分。字节数 + chat 端到端是唯一可靠验证。

---

_2026-08-07 真实部署 session 沉淀_
_护栏：永远 py -m pip · 不拷 auth.json · symlink Mac 端先展开 · PATH 刷不开就重装_

## 补充（patch，审批积压恢复）

## Mac 端打 zip

```bash
#!/bin/bash
# scripts/migration-zip.sh
# 用法: bash migration-zip.sh <output-path>
set -e

OUT="${1:-./hermes-migration.zip}"
TIMESTAMP=$(date +%Y%m%d-%H%M)
STAGING="/tmp/hermes-migration-$TIMESTAMP"

mkdir -p "$STAGING"

# 1. 灵魂（必拷）
cp ~/.hermes/SOUL.md "$STAGING/"
cp ~/.hermes/IDENTITY.md "$STAGING/" 2>/dev/null || true
cp ~/.hermes/AGENTS.md "$STAGING/" 2>/dev/null || true

# 2. 记忆（去 .bak / .lock，避免拉历史快照）
mkdir -p "$STAGING/memories"
for f in ~/.hermes/memories/*.md; do
  base=$(basename "$f")
  case "$base" in
    *.bak.*) continue ;;        # 历史 bak 备份，新机器不需要
    *.lock)   continue ;;        # 锁文件，可能跟新机器进程冲突
  esac
  cp "$f" "$STAGING/memories/"
done

# 3. Skills（**先展开 symlink + 排除运行时产物**）
# 排除项是平台专属的运行时产物：Mac 技能里打包的 venv 在 Windows 上是死路径，
# 还会让 zip 内路径超过 Windows MAX_PATH。打包前必须过滤。
mkdir -p "$STAGING/skills"
cd ~/.hermes/skills
for f in */; do
  name="${f%/}"
  if [ -L "$name" ]; then
    cp -RL "$name" "$STAGING/skills/$name"
  else
    rsync -a \
      --exclude='.venv' \
      --exclude='node_modules' \
      --exclude='__pycache__' \
      --exclude='.git' \
      --exclude='.mypy_cache' \
      --exclude='.pytest_cache' \
      --exclude='dist' \
      --exclude='build' \
      --exclude='*.pyc' \
      --exclude='*.wasm' \
      --exclude='*.map' \
      "$name" "$STAGING/skills/$name"
  fi
done

# 4. Knowledge（先报告大件，再决定是否全拷；knowledge/feishu-study 单目录
# 经常 1GB+ 主要是研究资料归档，运营助手场景下是否需要问主人）
mkdir -p "$STAGING/knowledge"
du -sh ~/.hermes/knowledge/* 2>/dev/null | sort -h
# 决策点：knowledge/feishu-study 这种 >500M 的目录，打包前明确问主人——
# "运营助手要不要查研究资料？全拷 / 只拷元数据（180M）/ 不拷"
# 默认全拷但 echo 提醒主人
cp -R ~/.hermes/knowledge "$STAGING/knowledge"

# 5. Scripts（Mac bash 脚本，Windows 等价物单独处理）
mkdir -p "$STAGING/scripts"
cp ~/.hermes/scripts/*.sh "$STAGING/scripts/" 2>/dev/null || true

# 6. 打 zip
cd "$(dirname $STAGING)"
zip -r "$OUT" "$(basename $STAGING)"

# 7. 报告
echo ""
echo "✅ Hermes 迁移包已生成: $OUT"
echo "   大小: $(du -h "$OUT" | cut -f1)"
echo "   内容: soul + memories(.bak/.lock 跳过) + skills(symlink-expanded, 排除 venv/node_modules/cache) + knowledge + scripts"
echo ""
echo "⚠️  不含 auth.json —— API key 在新机器重配"
echo "⚠️  launchd plist 不含 —— Windows 用 Task Scheduler 重建"
echo ""
echo "下一步：把 $OUT 拷到新机器（U 盘 / 网盘 / scp），解压到对应路径"
```


## 补充（patch，审批积压恢复）

## 失败模式

| 现象 | 原因 | 修法 |
|---|---|---|
| SOUL.md 第 1 行不对 | zip 解压层级错（多了一层目录） | 用 `-DestinationPath` 指定 $target 直接解压 |
| skills 数量 < 150 | symlink 没展开 | Mac 端重跑 `cp -RL` 步骤 |
| Windows 长路径报错 | MAX_PATH 260 字符限制 | 启用长路径（见 huihui-hermes-deploy-cross-platform SKILL.md K10） |
| PowerShell 5.1 `ExtractToDirectory` 报"路径中含有非法字符" | cp936 + UTF-8 文件名解码失败 | 装 PowerShell 7+：`winget install Microsoft.PowerShell`；用 `pwsh` + `[System.IO.Compression.ZipFile]::ExtractToDirectory` 解压（K20） |
| scp 传 zip 报 `dest open: No such file or directory` | Linux 端用了 MSYS 风格 `/c/Users/...` 路径，Windows OpenSSH SFTP server 不认 | 改 Windows 风格 `C:/Users/<u>/...`（K21） |
| `hermes --cli -m X` 报 `HTTP 401: invalid api key` | `.env` 写在 `~/.hermes/.env`，hermes 实际读 `AppData\Local\hermes\.env` | `hermes config env-path` 看实际位置，把 key 写到那里；或配 built-in provider（K22 / K24） |
