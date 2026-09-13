# Windows Python 环境恢复 — 完整 session 笔记

> 2026-08-07 真实部署 Windows 触发，从"pip command not found"到真正修好的完整路径。

## 触发场景

主人在新 Windows 电脑跑：
```powershell
pip install hermes-agent -i https://pypi.tuna.tsinghua.edu.cn/simple
# pip : 无法将"pip"项识别为 cmdlet、函数、脚本文件或可运行程序的名称。
```

## 三种"未识别"的真实原因

| 现象 | 真实原因 | 验证方式 |
|---|---|---|
| `pip` 报"未识别" | pip.exe 不在 PATH（Windows 上极常见） | `where.exe pip` 无输出 |
| `py` 报"未识别" | Python 没装 / PATH 没刷 | `py --version` 同样报 |
| `python` 报"未识别" | 跟 py 同因 + Python 3.9 以下没装 launcher | `python --version` 报 |

**最阴险的一档**：`winget install Python.Python.3.12` 输出 "Found an existing package already installed. No available upgrade found"——主人以为装好了，其实 Windows 装的是 **Microsoft Store Python 占位应用**，**没有真的 Python 解释器**。

## 诊断三连

```powershell
# 1. py launcher 在不在？
py --version

# 2. python 解释器在不在？
python --version

# 3. C:\ 下有没有真的 python.exe？
Get-ChildItem -Path C:\ -Filter python.exe -Recurse -ErrorAction SilentlyContinue -Depth 5 | Select-Object -First 5 FullName
```

第三步**无输出** = 解释器**真的没装**，要重装。

## 修法（按失败档位选）

### 档 A：占位 Python 陷阱（winget 报"已装"但找不到）
**管理员** PowerShell：

```powershell
# 1. 卸占位
winget uninstall Python.Python.3.12

# 2. 强装（--force 跳过"已装"判断）
winget install --id Python.Python.3.12 --source winget `
  --accept-package-agreements `
  --accept-source-agreements `
  --force

# 3. 关掉 PowerShell 开新的
# 4. 验证
py --version
# 应输出: Python 3.12.x
```

### 档 B：PATH 没刷（Python 装了但 py 不在）
**手动加 PATH**（一行救命）：

```powershell
# 找 python.exe
$pythonPath = (Get-Command py -ErrorAction SilentlyContinue).Source
# 通常: C:\Users\kk\AppData\Local\Programs\Python\Python312\python.exe

# 加 Scripts 目录到 PATH（pip.exe 在这里）
$scriptsPath = Split-Path $pythonPath
[Environment]::SetEnvironmentVariable("Path", `
  $env:Path + ";" + $scriptsPath + ";" + $scriptsPath + "\Scripts", `
  "User")

# 重启 PowerShell 生效
```

### 档 C：彻底没装（官网安装包，最稳）
1. 浏览器：https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe
2. 双击 → **第一个勾选框** `Add python.exe to PATH` **必勾**
3. Install Now
4. 关 PowerShell 开新的
5. `py --version`

## 装好后第一件事

**永远用 `py -m pip`**——不要直接 `pip`：

```powershell
py -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
py -m pip install hermes-agent -i https://pypi.tuna.tsinghua.edu.cn/simple
hermes --version
```

## 坑总结（这次 session 真实碰到）

1. **"已装"是假的**——Microsoft Store 占位 Python 没有任何可执行文件
2. **`pip` 单跑比 `py -m pip` 容易挂**——Windows PATH 机制问题
3. **`Get-ChildItem -Path C:\`** 在 PowerShell 5.x 巨慢但能找到——这是诊断真理
4. **关窗口才能生效**——PowerShell 不刷 PATH 是老毛病
5. **`refreshenv` 不是万能的**——新装 Python 要重开窗口才稳

## 后续衍生坑（soul 装完后才出现）

- **minimax API key**：从 Mac 拷 `auth.json` 到 Windows，新机器上 `last_status: exhausted` + `invalid api key` 401
  - 解法：`hermes config set providers.minimax.api_key "新key"`，**不拷 auth.json**
- **symlink 失效**：Mac skills/ 里 50+ symlink，Windows 不识别
  - 解法：Mac 端 `cp -RL` 展开再 rsync
- **launchd 不存在**：Mac 的 `~/Library/LaunchAgents/*.plist` 在 Windows 全部失效
  - 解法：Windows 用 Task Scheduler

---

_2026-08-07 真实 session · 主人还没装上 Python 时沉淀_