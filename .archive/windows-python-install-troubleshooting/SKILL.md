---
name: windows-python-install-troubleshooting
description: 排查并修复 Windows 上 Python 项目 pip install 失败类问题——覆盖 Microsoft Store 占位 Python 占坑、Windows ARM64 + GBK 代码页、cryptography 46.x 改用 Rust + maturin 编译、--no-build-isolation 切断 maturin 查找路径、清华源 --only-binary 找不到老版、hermes-agent 装好后 --no-deps 缺 17 个依赖需选择性补齐。触发词：Windows pip install 失败、py command not found、winget 报已装但没 python、GBK codec can't decode、maturin BackendUnavailable、cryptography Rust 编译、PyJWT[crypto] 装不上、Windows ARM64 pip 失败、清华源找不到 cryptography、hermes-agent 装上但缺依赖、ModuleNotFoundError No module named dotenv。
---

# windows-python-install-troubleshooting

> Class-level skill：在 Windows 上 pip install Python 项目失败时触发。同类对照 macOS 端的 `hermes-agent-upgrade-recovery`（devops 类），本 skill 是**首次部署 + 跨平台**那条线，差异在 OS + ARM64 + GBK + Rust 编译。

## 8 个实战陷阱（2026-08-07 / Mac → Windows ARM64 部署 Hermes 沉淀）

### 陷阱 1：winget 报"已装"但 `py`/`python`/`pip` 全 not found

**症状**：

```powershell
> winget install Python.Python.3.12
Found an existing package already installed. Trying to upgrade the installed package...
No available upgrade found.

> py --version
py: command not found
```

**根因**：Windows 10/11 自带一个 `Python Software Foundation` 的 **Microsoft Store 占位"应用"**——winget 看到它就报"已装"，但**实际没装 Python 解释器**。`py` / `python` / `pip` 全是空气。

**验证**：递归搜 `C:\` 找 `python.exe`，5 层深无结果 = 真没装。

**修复（任选一档）**：

| 档 | 命令 | 耗时 |
|---|---|---|
| A. 官网安装包 | 下载 `python-3.12.x-amd64.exe` 双击装 ⚠ **第一个勾选框"Add python.exe to PATH"必须勾** | 1 分钟 |
| B. winget 强装 | `winget uninstall Python.Python.3.12` 再 `winget install --id Python.Python.3.12 --source winget --accept-package-agreements --accept-source-agreements --force` | 30 秒 |
| C. Anaconda | `winget install Anaconda.Anaconda3`，`conda install python=3.12` | 3 分钟 |

**修完后永远用 `py -m pip`** 而不是 `pip`——Windows 上 `py -m pip` 永远稳，`pip` 偶尔因 PATH 抽风。

### 陷阱 2：Windows ARM64 + GBK 代码页 → pip 子进程编译 setup.py 炸

**症状**：

```
UnicodeDecodeError: 'gbk' codec can't decode byte 0x93 in position 1740: illegal multibyte sequence
ERROR: Failed to build 'ruamel.yaml.clib' when getting requirements for build wheel
```

**根因**：Windows 默认代码页 = GBK（936）。pip 创建**临时隔离 build 环境**跑 setup.py，那个临时环境的代码页**不继承** PowerShell 的 `chcp 65001`。setuptools 用 GBK 读源码 → 读到非 GBK 字节（0x93）→ 炸。

**修复层级（按强度）**：

```powershell
# Level 1：当前 PowerShell 会话改 UTF-8（chcp 影响 cmd.exe 子进程）
chcp 65001
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONUTF8="1"

# Level 2：永久改系统代码页（写入注册表）
reg add "HKLM\SOFTWARE\Microsoft\Command Processor" /v Autorun /t REG_SZ /d "chcp 65001 > nul" /f
setx PYTHONIOENCODING "utf-8" /M
setx PYTHONUTF8 "1" /M

# Level 3：PowerShell profile 自动设
notepad $PROFILE
# 末尾加：
# chcp 65001 | Out-Null
# $env:PYTHONIOENCODING="utf-8"
# $env:PYTHONUTF8="1"
```

**重要**：Level 1-2 设了**仍然可能撞 GBK**——因为 pip 创建的临时隔离环境有自己的 cmd.exe 子进程。看错误最后一行是不是 "subprocess-exited-with-error" 区分。如果还是炸 → 跳到陷阱 3 / 4 绕开编译。

### 陷阱 3：`cryptography==46.x` 改用 Rust + maturin 编译，老套路全废

**症状**：

```
pip._vendor.pyproject_hooks._impl.BackendUnavailable: Cannot import 'maturin'
ERROR: Failed to build 'cryptography' when getting requirements for build wheel
```

**根因**：cryptography 从 46.0 起把 C 扩展改成 **Rust + PyO3 + maturin**。Windows 上要 Rust 工具链（rustc + cargo）。

**修复路线**：

```powershell
# A. 装 Rust（一次装好，后续所有 Rust 包都顺）
winget install Rustlang.Rustup
# 重启 PowerShell，让 cargo 进 PATH
rustc --version
cargo --version
py -m pip install hermes-agent -i https://pypi.tuna.tsinghua.edu.cn/simple
# 这次编译 3-5 分钟（Rust 慢），但一路绿灯
```

**反例**：
- ❌ `py -m pip install maturin` 然后 `--no-build-isolation`——隔离环境里 maturin 找不到，子进程没 maturin
- ❌ `--only-binary=:all:` 找老 cryptography——清华源**只镜像 46.x 系列**，老版没有

### 陷阱 4：`--no-build-isolation` 切断 maturin 查找路径

**症状**：装了 Rust，但 hermes-agent 装时还是 `Cannot import 'maturin'`。

**根因**：pip 的 `--no-build-isolation` 强制用主环境的包，但 hermes-agent 的 build system 是声明要 maturin 在**临时隔离环境**里——主环境装了 maturin 没用。

**修复**：**不要带 `--no-build-isolation`**——让 pip 用默认隔离环境，隔离环境会**自动装 maturin 到 build 上下文里**。

```powershell
# ✅ 对的
py -m pip install hermes-agent -i https://pypi.tuna.tsinghua.edu.cn/simple

# ❌ 错的
py -m pip install hermes-agent -i https://pypi.tuna.tsinghua.edu.cn/simple --no-build-isolation
```

### 陷阱 5：清华源 `--only-binary` 找不到老版 cryptography

**症状**：

```
> py -m pip install "cryptography<44" --only-binary=:all:
ERROR: Could not find a version that satisfies the requirement cryptography<44
(from versions: 46.0.0, 46.0.1, 46.0.2, 46.0.3)
```

**根因**：清华源**只镜像最新 major 版本**——46.0.x 系列完整，43.x/44.x/45.x 全没。

**应对**：**别指望降 cryptography 绕 Rust**——直接装 Rust（陷阱 3）。

### 陷阱 6：hermes-agent 装上但 `--no-deps` 缺 17 个依赖

**症状**：

```
Successfully installed hermes-agent-0.19.0
> hermes --version
ModuleNotFoundError: No module named 'dotenv'
```

**根因**：用 `--no-deps` 绕开 cryptography 编译问题 → hermes-agent 装上但 17 个依赖没装（python-dotenv、fire、prompt_toolkit、psutil、pathspec、python-multipart、pillow、Markdown、PyJWT、tzdata、websockets、fastapi、uvicorn、ruamel.yaml、pyyaml、httpx、openai、pydantic、jinja2、requests、tenacity）。

**修复（一键补齐）**：

```powershell
py -m pip install python-dotenv fire prompt_toolkit psutil pathspec python-multipart pillow Markdown PyJWT certifi croniter packaging rich tenacity tzdata websockets fastapi "uvicorn[standard]" ruamel.yaml pyyaml httpx openai pydantic jinja2 requests -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**关键选择**：
- **不带 `cryptography`** —— 装不上（陷阱 3）
- **不带 `[crypto]` 后缀** —— PyJWT[crypto] 依赖 cryptography，会反向撞 Rust
- **不带 `pywinpty<3`** —— Windows 编译依赖，可能撞 maturin/GBK，hermes-agent 主流程用不到
- **不带 `urllib3`** —— 用 requests 自带版本即可

**验**：

```powershell
hermes --version
# → Hermes Agent v0.19.0

hermes chat "你好"
# → 不报 ModuleNotFoundError 即成功
```

### 陷阱 7：decision point —— 装 Rust vs 绕编译（ABSOLUTE 模式专属）

**症状**：cryptography 装不上，agent 卡在 "要不要装 Rust"。

**决策树**：

| 档 | 内容 | 耗时 | 适用 |
|---|---|---|---|
| **A. 装 Rust** | `winget install Rustlang.Rustup` 然后默认装 | 3-5 分钟编译 | 主人 ABSOLUTE 模式 + 后续要装更多 Python 项目 |
| **B. 装老版 cryptography** | 清华源没镜像，PyPI 默认源在中国慢/卡 | 不行 | ❌ 别选 |
| **C. `--no-deps` 绕过** | hermes-agent 装上，缺 17 个依赖选择性补 | 1-2 分钟 | **主人短期使用 / 不装别的项目** |

**正确动作**：直接做 C 档（陷阱 6 的一键补齐命令），并报告"已装 / 缺啥 / 怎么补"。**不主动装 Rust**——除非主人明确说"要长期维护 Windows 上 Python"。

### 陷阱 8（补充）：`uvicorn[standard]` 拖 httptools → MSVC 编译要求

**症状**：装 `uvicorn[standard]` 时报：

```
error: Microsoft Visual C++ 14.0 or greater is required. Get it with "Microsoft C++ Build Tools": https://visualstudio.microsoft.com/visual-cpp-build-tools/
ERROR: Failed building wheel for httptools
```

**根因**：`uvicorn[standard]` 装了 httptools（HTTP 解析 C 扩展）+ uvloop + watchfiles——这些是**性能加速**，Windows ARM64 上 httptools 需要 MSVC 编译。

**修复**：**不带 `[standard]` 标记**——用纯 Python 实现：

```powershell
# ✅ 对的
py -m pip install uvicorn

# ❌ 错的
py -m pip install "uvicorn[standard]"
```

**对主流程影响**：uvicorn 不带 `[standard]` 仍能启动 Hermes Gateway，只是 HTTP 解析略慢（hermes-cli 的 LLM 调用主路径不依赖 httptools）。

### 陷阱 8：Windows 没有 `launchd` —— cron / daemon 替代

**症状**：Mac 上的 `~/Library/LaunchAgents/*.plist` + `launchctl bootstrap` 在 Windows 全废。

**修复**：用 **Task Scheduler**（自带，零依赖）：

```powershell
# 创建 PowerShell 心跳脚本
$scriptPath = "$env:USERPROFILE\.hermes\scripts\hermes-heartbeat.ps1"
@"
`$log = "$env:USERPROFILE\.hermes\logs\heartbeat.log"
New-Item -ItemType Directory -Path (Split-Path `$log) -Force | Out-Null
Add-Content `$log -Value "$(Get-Date -Format o) heartbeat OK"
hermes gateway status | Out-Null
"@ | Out-File -Encoding utf8 $scriptPath

# 注册到 Task Scheduler
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-File $scriptPath"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName "Hermes-Heartbeat" -Action $action -Trigger $trigger -Description "Hermes 化身心跳"
```

### 陷阱 9：hermes-agent 装完后凭证配置 5 个连环坑（2026-08-07 真实流程）

#### 9.1 `hermes chat "prompt"` 用法错——v0.19.0 用 `-z`

**症状**：

```
> hermes chat "你好"
usage: hermes [-h] [--version] [-z PROMPT] ...
hermes: error: unrecognized arguments: 你好
```

**根因**：Hermes 0.19.0 的 `hermes` 主命令用 `-z "prompt"` 传一次性 prompt（不是子命令 `chat`）。`chat` 子命令存在但用法不同。

**修复**：

```powershell
# ✅ 对的
hermes -z "你好"

# 进交互模式
hermes
```

#### 9.2 `hermes config set providers.X.api_key` 不被 agent 读

**症状**：

```
> hermes config set providers.minimax.api_key "sk-..."
✓ Set providers.minimax.api_key = sk-... in config.yaml

> hermes -z "你好"
agent failed: No usable credentials found for provider 'minimax-cn'. Set MINIMAX_CN_API_KEY.
```

**根因**：Hermes 0.19.0 的凭证系统**只读环境变量**，**不读** `config.yaml` 里的 `providers.<x>.api_key` 字段（config.yaml 里那个字段是占位 / 给其他工具看的，不是 agent 实际取值路径）。

**凭证加载优先级**（按 auth.py 实证）：

1. 环境变量（`MINIMAX_CN_API_KEY` / `MINIMAX_API_KEY` / `OPENAI_API_KEY` 等）
2. `.env` 文件（`~/.hermes/.env` —— 装 Python 的 Hermes 自动加载）

**修复（任选一档）**：

```powershell
# 档 A：设系统环境变量（永久）
setx MINIMAX_CN_API_KEY "sk-..." /M
# ⚠ 关 PowerShell 开新会话才生效；某些 Win 11 ARM64 上 setx /M 不生效（echo 输出空）

# 档 B：写 .env 文件（推荐，稳）
mkdir $env:USERPROFILE\.hermes -Force
$content = "MINIMAX_CN_API_KEY=sk-..."
[System.IO.File]::WriteAllText("$env:USERPROFILE\.hermes\.env", $content, [System.Text.UTF8Encoding]::new($false))
# ⚠ 必须 [System.Text.UTF8Encoding]::new($false) —— 强制无 BOM
#    PowerShell Out-File -Encoding utf8 默认 **UTF-8 with BOM**，dotenv 解析可能炸

# 档 C：走 OAuth（不需要 key 字符串）
hermes model
# 选 minimax-cn → 走 OAuth device code 登录
```

#### 9.3 验证 .env 是否真读了

```powershell
hermes secrets list
```

输出会列每个 provider 的 key 是否被识别、长度、状态。如果 `minimax-cn` 出现但 value 是空 = 文件读到了但解析失败（多半是 BOM 或换行问题）。

#### 9.4 Provider ↔ 环境变量映射表（auth.py:298, 341 实证）

| Provider ID | 环境变量 | Base URL |
|---|---|---|
| `minimax` | `MINIMAX_API_KEY` | `https://api.minimax.io/anthropic` |
| `minimax-cn` | **`MINIMAX_CN_API_KEY`** | `https://api.minimaxi.com/anthropic` |
| `minimax-oauth` | (OAuth device code) | 同上 |
| `anthropic` | `ANTHROPIC_API_KEY` / `ANTHROPIC_TOKEN` / `CLAUDE_CODE_OAUTH_TOKEN` | (Anthropic 默认) |
| `openai` | `OPENAI_API_KEY` | (OpenAI 默认) |
| `glm` | `GLM_API_KEY` / `ZAI_API_KEY` | ... |
| `kimi` | `KIMI_API_KEY` / `KIMI_CODING_API_KEY` | ... |
| `kimi-cn` | `KIMI_CN_API_KEY` | ... |

**配置默认模型 + provider**：

```powershell
hermes config set model.default "minimax/MiniMax-M3"
hermes config set model.provider "minimax-cn"
```

#### 9.5 Key 安全护栏（必读）

⚠️ **每条 PowerShell 命令里的 key 都在聊天记录里**——Windows 部署调试完后**立即去 minimaxi.com 控制台 revoke 这个 key 重新生成**。这是 ABSOLUTE 模式专属风险：主人允许 agent 直接调命令，但 agent 不能保证 chat log 不留底。

**替代**：用 `hermes model` 走 OAuth（key 不经过 chat log），或用临时 key 调试完立刻作废。

## Windows 部署 Python 项目标准流程
1. 验 Python 状态（陷阱 1）
   py --version
   # 报错 → 装 Python（官网 / winget / conda 任选一档）

2. 验 Rust 状态（陷阱 3，可选但推荐）
   rustc --version
   # 不存在 → winget install Rustlang.Rustup

3. 永久改 UTF-8 代码页（陷阱 2 Level 2）
   reg add "HKLM\SOFTWARE\Microsoft\Command Processor" /v Autorun /t REG_SZ /d "chcp 65001 > nul" /f
   setx PYTHONIOENCODING "utf-8" /M
   setx PYTHONUTF8 "1" /M
   # 关 PowerShell 开新的

4. 装项目（默认走清华源 + 默认 build isolation）
   py -m pip install <pkg> -i https://pypi.tuna.tsinghua.edu.cn/simple

5. 撞 Rust 编译 → 评估（陷阱 7 decision point）

6. 撞 GBK → 陷阱 2 Level 1-2 + 重试；还炸 → 陷阱 4 不要用 --no-build-isolation

7. 撞 maturin BackendUnavailable → 陷阱 3 装 Rust

8. 装完验证
   py -m pip show <pkg>
   <pkg> --version
   <pkg> chat "测试"

9. 缺依赖报错 → 陷阱 6 一键补齐
```

## 验证清单

```powershell
# 部署前
py --version                                          # 3.12.x ✓
rustc --version                                       # 1.97.x 可选 ✓
chcp                                                   # 65001 ✓

# 部署中
pip show <pkg> | grep Location                         # site-packages 路径
pip install <pkg> --dry-run -i <mirror>                # 看装什么 + 跨位

# 部署后
<pkg> --version                                        # 期望版本号
hermes --version                                       # Hermes Agent v0.19.0
hermes chat "测试"                                     # 不报 ModuleNotFoundError
py -c "import hermes_cli; print(hermes_cli.__file__)"  # 真在 site-packages
```

## 反例（不该做的事）

❌ **不要相信 winget "已装"** —— Microsoft Store 占位 Python 不算真装，py/python/pip 全 not found
❌ **不要忘了勾"Add python.exe to PATH"** —— 官网安装包第一个勾选框，不勾等于没装
❌ **不要相信 `pip` 命令直接能用** —— Windows 上 `pip` 偶尔 PATH 抽风，**永远用 `py -m pip`**
❌ **不要单靠 `chcp 65001`** —— pip 临时隔离环境的 cmd.exe 子进程不继承，可能撞 GBK
❌ **不要 `--only-binary=:all:` 找老 cryptography** —— 清华源不镜像老版本
❌ **不要 `--no-build-isolation`** —— 切断 maturin 查找路径，子进程没 maturin 仍炸
❌ **不要 `py -m pip install PyJWT[crypto]`** —— 反向引入 cryptography，又撞 Rust
❌ **不要 `pip install hermes-agent` 没看缺啥** —— 装完跑 `hermes --version` 才知道缺 dotenv
❌ **不要 `hermes chat "prompt"`** —— v0.19.0 用 `hermes -z "prompt"`
❌ **不要相信 `hermes config set providers.X.api_key`** —— agent 不读 config.yaml 的 api_key，只读环境变量 + .env
❌ **不要 `setx KEY value /M` 然后不重启 PowerShell** —— 当前会话读不到；某些 Win 11 ARM64 上 setx 静默失败
❌ **不要 `Out-File -Encoding utf8` 写 .env** —— 默认 UTF-8 **with BOM**，dotenv 解析可能炸；用 `[System.IO.File]::WriteAllText` + `UTF8Encoding($false)` 强制无 BOM
❌ **不要把 Mac 上的 `auth.json` 拷到 Windows** —— Mac key 指纹已过期（401），重新配

## 模板

- `templates/setup_hermes_windows.ps1` —— **一站式部署脚本**（9 步，含 Python 验、UTF-8 改、Rust 装/绕、hermes-agent 装、缺依赖补、.env 写无 BOM、provider 选、模型配、对话验证、心跳可选）。下次 Windows 部署让主人在 PowerShell 跑这个，**不再给一行行命令**。

## 联动

- `hermes-agent-upgrade-recovery` —— 同 OS（macOS）端 hermes-agent 升级。差异：本 skill 是**首次部署 + 跨平台**，那个 skill 是**升级 + 同 OS**
- `openclaw-gateway-upgrade-recovery` —— OpenClaw gateway 升级（Node / npm / plist），跨 Windows 时同样要看 Node 路径
- `node-version-upgrade` —— Windows Node 路径坑（`C:\Program Files\nodejs\node.exe` vs `~\AppData\Roaming\npm`），参考 macOS 端写法的 Win 适配
- `workspace-hygiene` —— 备份路径 `~/.hermes/backups/` 跨平台兼容，Windows 上是 `%USERPROFILE%\.hermes\backups\`

## 启动信号

- 主人说"在 Windows 装 hermes" / "Windows 部署" / "迁移到 Win" / "Win 跑 hermes" 任何一个
- Windows PowerShell 报 `py: command not found`
- pip 报 `Cannot import 'maturin'`
- pip 报 `UnicodeDecodeError: 'gbk' codec can't decode`
- `hermes --version` 报 `ModuleNotFoundError: No module named 'dotenv'`
- `hermes-agent` 装上但 `pip check` 报 17 个依赖缺失
- `hermes -z "x"` 报 `No usable credentials found for provider 'X'`
- `hermes config set providers.X.api_key` 写成功了但 agent 报"No usable credentials"
- pip 装 `uvicorn[standard]` 报 `Microsoft Visual C++ 14.0 required`

**会话开始必做**：主人说 Windows 部署 → 第一步 `skill_view('windows-python-install-troubleshooting')` 加载本 skill，**不要凭直觉给命令**——本 skill 8 个陷阱全部沉淀过。

## 必读（执行前）

- 主人 ABSOLUTE 行为模式 = 持续委托，但**跨平台部署涉及"装系统级组件"**（Rust / Python / Node）——首次装前列档，主人在场就列
- 主人 cancel clarify = "你看着办做安全那档"——决策点卡住时（陷阱 7）做 C 档（`--no-deps` + 选择性补齐），等下次主人有时间再升 Rust
- "不要把自己整坏了" = 护栏指令——装 Rust 是**装系统级工具**，不算"整坏"；但 `pip install hermes-agent` 默认走隔离编译是 3-5 分钟 Rust 编译，**会占 CPU**，提前告诉主人
- **跨平台部署反例（2026-08-07 反思）**：本 skill 之前的版本默认"agent 给一行行 PowerShell 命令让主人手敲"——这违反了 USER.md 里"sudo 操作 = 写脚本让主人在 Terminal 跑"的精神。**修正**：Windows 部署涉及多条命令（>5 步）时，**写成 .ps1 脚本让主人在 PowerShell 跑一次**（`hermes-install-windows.ps1`），而不是给 5+ 条独立命令。把调试 + 验 + 回滚写成单个文件，主人一次跑完看到结果。例：`setup_hermes_windows.ps1`（含 Python 装、Rust 装、UTF-8 改、hermes-agent 装、缺依赖补、.env 写、验证）。
- **凭证安全护栏**：Windows 部署调试时 key 会进 chat log——调试完**必须让主人去 provider 控制台 revoke 重发**（陷阱 9.5）。或者直接走 `hermes model` OAuth 流程避开 key 明文。