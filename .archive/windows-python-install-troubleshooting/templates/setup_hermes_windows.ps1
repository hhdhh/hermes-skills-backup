# setup_hermes_windows.ps1
# Windows ARM64 + Python 3.12 + Hermes Agent v0.19.0 部署脚本
# 主人一次性跑这个，等完成看底部验证清单
# 用法（PowerShell 管理员）：
#   iex (irm https://raw.githubusercontent.com/...)   # 如果有远程版
#   或：.\setup_hermes_windows.ps1

$ErrorActionPreference = "Stop"
$hermesDir = "$env:USERPROFILE\.hermes"
$scriptsDir = "$hermesDir\scripts"

Write-Host "=== Hermes Windows 部署脚本 ===" -ForegroundColor Cyan
Write-Host "OS: $env:OS | Arch: $([System.Environment]::Is64BitOperatingSystem) ARM:$([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture)"
Write-Host ""

# === 步骤 1：验 Python（覆盖陷阱 1：winget 占位 Python） ===
Write-Host "[1/9] 检查 Python..." -ForegroundColor Yellow
try {
    $pyVersion = py --version 2>&1
    Write-Host "  ✓ Python 已装：$pyVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Python 没装 / winget 占位" -ForegroundColor Red
    Write-Host "  → 请先手动装 Python 3.12：https://www.python.org/downloads/release/python-3129/" -ForegroundColor Yellow
    Write-Host "  → ⚠ 第一个勾选框 Add python.exe to PATH 必须勾" -ForegroundColor Yellow
    exit 1
}

# === 步骤 2：永久改 UTF-8（覆盖陷阱 2：GBK） ===
Write-Host "[2/9] 永久改 UTF-8 代码页..." -ForegroundColor Yellow
reg add "HKLM\SOFTWARE\Microsoft\Command Processor" /v Autorun /t REG_SZ /d "chcp 65001 > nul" /f | Out-Null
setx PYTHONIOENCODING "utf-8" /M | Out-Null
setx PYTHONUTF8 "1" /M | Out-Null
chcp 65001 | Out-Null
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
Write-Host "  ✓ UTF-8 已永久生效" -ForegroundColor Green

# === 步骤 3：验 Rust（覆盖陷阱 3：cryptography 46.x 要 Rust，可选但推荐） ===
Write-Host "[3/9] 检查 Rust（cryptography 46.x 需要）..." -ForegroundColor Yellow
try {
    $rustVersion = rustc --version 2>&1
    Write-Host "  ✓ Rust 已装：$rustVersion" -ForegroundColor Green
} catch {
    Write-Host "  ⚠ Rust 未装" -ForegroundColor Yellow
    Write-Host "  → 将走 --no-deps 路线（陷阱 6/7）：hermes-agent 装上后选择性补依赖" -ForegroundColor Yellow
    $rustMissing = $true
}

# === 步骤 4：装 hermes-agent ===
Write-Host "[4/9] 装 hermes-agent..." -ForegroundColor Yellow
if ($rustMissing) {
    # 走 --no-deps 路线
    py -m pip install hermes-agent --no-deps -i https://pypi.tuna.tsinghua.edu.cn/simple
    if ($LASTEXITCODE -ne 0) { Write-Host "  ✗ 装 hermes-agent 失败" -ForegroundColor Red; exit 1 }

    # 补依赖（不带 cryptography / pywinpty / [crypto]）
    py -m pip install python-dotenv fire prompt_toolkit psutil pathspec python-multipart pillow Markdown PyJWT certifi croniter packaging rich tenacity tzdata websockets fastapi uvicorn ruamel.yaml pyyaml httpx openai pydantic jinja2 requests -i https://pypi.tuna.tsinghua.edu.cn/simple
    if ($LASTEXITCODE -ne 0) { Write-Host "  ✗ 补依赖失败" -ForegroundColor Red; exit 1 }
} else {
    # 走 Rust 路线
    py -m pip install hermes-agent -i https://pypi.tuna.tsinghua.edu.cn/simple
    if ($LASTEXITCODE -ne 0) { Write-Host "  ✗ 装 hermes-agent 失败（看 Rust 编译日志）" -ForegroundColor Red; exit 1 }
}
Write-Host "  ✓ hermes-agent 装好" -ForegroundColor Green

# === 步骤 5：验证 hermes CLI ===
Write-Host "[5/9] 验证 hermes 命令..." -ForegroundColor Yellow
$hermesVer = hermes --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ hermes --version 失败：$hermesVer" -ForegroundColor Red
    Write-Host "  → 可能 ModuleNotFoundError，回去看陷阱 6 补依赖" -ForegroundColor Yellow
    exit 1
}
Write-Host "  ✓ $hermesVer" -ForegroundColor Green

# === 步骤 6：写 .env 文件（陷阱 9.2 / 9.3，无 BOM） ===
Write-Host "[6/9] 配 provider 凭证..." -ForegroundColor Yellow
Write-Host "  选 provider：" -ForegroundColor Cyan
Write-Host "    1) minimax (国际)    → MINIMAX_API_KEY" -ForegroundColor White
Write-Host "    2) minimax-cn (国内) → MINIMAX_CN_API_KEY" -ForegroundColor White
Write-Host "    3) openai            → OPENAI_API_KEY" -ForegroundColor White
Write-Host "    4) anthropic         → ANTHROPIC_API_KEY" -ForegroundColor White
$providerChoice = Read-Host "  选 [1-4]"
$envVarMap = @{
    "1" = @{ var = "MINIMAX_API_KEY"; provider = "minimax"; model = "minimax/MiniMax-M3" }
    "2" = @{ var = "MINIMAX_CN_API_KEY"; provider = "minimax-cn"; model = "minimax/MiniMax-M3" }
    "3" = @{ var = "OPENAI_API_KEY"; provider = "openai"; model = "openai/gpt-4o" }
    "4" = @{ var = "ANTHROPIC_API_KEY"; provider = "anthropic"; model = "anthropic/claude-sonnet-4-5" }
}
$cfg = $envVarMap[$providerChoice]
if (-not $cfg) { Write-Host "  ✗ 无效选择" -ForegroundColor Red; exit 1 }

$apiKey = Read-Host "  贴 API key（输入隐藏）" -AsSecureString
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($apiKey)
$apiKeyPlain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

# 写 .env（无 BOM，陷阱 9.2 关键）
New-Item -ItemType Directory -Path $hermesDir -Force | Out-Null
$envContent = "$($cfg.var)=$apiKeyPlain`n"
[System.IO.File]::WriteAllText("$hermesDir\.env", $envContent, [System.Text.UTF8Encoding]::new($false))
Write-Host "  ✓ .env 写好（无 BOM）：$hermesDir\.env" -ForegroundColor Green
Write-Host "  ⚠ key 已落盘到 .env + 进 chat log——调试完务必去 provider 控制台 revoke 重发" -ForegroundColor Yellow

# === 步骤 7：设默认模型 + provider ===
Write-Host "[7/9] 设默认模型..." -ForegroundColor Yellow
hermes config set model.default $cfg.model | Out-Null
hermes config set model.provider $cfg.provider | Out-Null
Write-Host "  ✓ model=$($cfg.model), provider=$($cfg.provider)" -ForegroundColor Green

# === 步骤 8：验证对话 ===
Write-Host "[8/9] 验证对话..." -ForegroundColor Yellow
$testOutput = hermes -z "你好，告诉我你叫什么" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ 对话失败：" -ForegroundColor Red
    Write-Host $testOutput
    Write-Host "  → 看陷阱 9.2（凭证）或陷阱 9.4（provider ↔ env var 映射）" -ForegroundColor Yellow
    exit 1
}
Write-Host "  ✓ 对话通了：$testOutput" -ForegroundColor Green

# === 步骤 9：可选 - 创建心跳脚本（陷阱 8） ===
Write-Host "[9/9] 创建 Windows 心跳（可选）..." -ForegroundColor Yellow
$createHeartbeat = Read-Host "  创建 Task Scheduler 心跳？[y/N]"
if ($createHeartbeat -eq "y") {
    New-Item -ItemType Directory -Path $scriptsDir -Force | Out-Null
    New-Item -ItemType Directory -Path "$hermesDir\logs" -Force | Out-Null

    $heartbeatScript = @"
`$log = "$hermesDir\logs\heartbeat.log"
Add-Content `$log -Value "`$(Get-Date -Format o) heartbeat OK"
hermes gateway status | Out-Null
"@
    [System.IO.File]::WriteAllText("$scriptsDir\hermes-heartbeat.ps1", $heartbeatScript, [System.Text.UTF8Encoding]::new($false))

    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-File $scriptsDir\hermes-heartbeat.ps1"
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 30)
    Register-ScheduledTask -TaskName "Hermes-Heartbeat" -Action $action -Trigger $trigger -Description "Hermes 化身心跳" -Force | Out-Null
    Write-Host "  ✓ 心跳已注册到 Task Scheduler（每 30 分钟）" -ForegroundColor Green
}

# === 完成 ===
Write-Host ""
Write-Host "=== 部署完成 ===" -ForegroundColor Green
Write-Host "下次启动对话：hermes -z `"你的 prompt`"" -ForegroundColor Cyan
Write-Host "进交互模式：hermes" -ForegroundColor Cyan
Write-Host ""
Write-Host "⚠ 凭证安全提醒：去 $($cfg.provider) 控制台 revoke 刚贴的 key 重新生成" -ForegroundColor Yellow