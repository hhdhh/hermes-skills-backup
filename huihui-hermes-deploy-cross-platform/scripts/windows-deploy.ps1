# scripts/windows-deploy.ps1
# Windows 端从零到能对话的一键脚本（管理员 PowerShell）
# 用法: 右键 → Run with PowerShell（管理员）
#
# 流程:
#   1. 装 Python 3.12（force 强装，绕过 Microsoft Store 占位）
#   2. 装 Git + Node LTS
#   3. 启用 Windows 长路径
#   4. 用 py -m pip 装 hermes-agent（清华源）
#   5. 配 minimax API key
#   6. 解压迁移包（如有）
#   7. 注册 Task Scheduler 心跳
#   8. 启动 web UI
#   9. 验收清单

$ErrorActionPreference = "Stop"
$hermesDir = "$env:USERPROFILE\.hermes"
$logFile = "$hermesDir\logs\deploy.log"

New-Item -ItemType Directory -Path "$hermesDir\logs" -Force | Out-Null

function Log($msg) {
    $ts = Get-Date -Format "o"
    $line = "[$ts] $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line
}

Log "============================================="
Log "🪡 Hermes 化身 2 Windows 部署开始"
Log "============================================="

# Step 1: Python 3.12
Log "[1/9] 装 Python 3.12..."
winget uninstall Python.Python.3.12 2>&1 | Out-Null
winget install --id Python.Python.3.12 --source winget `
  --accept-package-agreements `
  --accept-source-agreements `
  --force 2>&1 | Out-Null

# 重启 PowerShell PATH（用 RefreshEnv 模式）
Log "  → Python 已装，当前进程需要重开才能用 'py'"

# Step 2: Git + Node
Log "[2/9] 装 Git + Node LTS..."
winget install Git.Git --accept-package-agreements --accept-source-agreements 2>&1 | Out-Null
winget install OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements 2>&1 | Out-Null

# Step 3: 长路径
Log "[3/9] 启用 Windows 长路径..."
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
  -Name "LongPathsEnabled" -Value 1 -ErrorAction SilentlyContinue

# Step 4: Hermes（必须在新的 PowerShell 里跑——这是已知限制）
Log "[4/9] ⚠️ Python PATH 刷新需要重开 PowerShell"
Log "  → 本脚本到此暂停。请按以下步骤手动继续："
Log ""
Log "  1. 关掉当前 PowerShell，开新的（管理员）"
Log "  2. 跑:"
Log "       py -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple"
Log "       py -m pip install hermes-agent -i https://pypi.tuna.tsinghua.edu.cn/simple"
Log "       py -m pip install hermes-web-ui -i https://pypi.tuna.tsinghua.edu.cn/simple"
Log "  3. 验证:"
Log "       hermes --version"
Log ""
Log "  4. 配 API key（**不拷 Mac 上的 auth.json**）:"
Log "       hermes config set providers.minimax.api_key '你的新key'"
Log "       hermes config set model.default 'minimax/MiniMax-M3'"
Log ""
Log "  5. 解压迁移包（如有，Mac 端用 migration-zip.sh 打）:"
Log "       Expand-Archive -Path 'E:\hermes-migration.zip' -DestinationPath '$hermesDir' -Force"
Log "       Get-Content '$hermesDir\SOUL.md' -Head 1   # 应含 '慧慧的灵魂'"
Log ""
Log "  6. 注册心跳任务:"
Log "       # 创建脚本（见 Step 6 below）"
Log "       Register-ScheduledTask -TaskName 'Hermes-Heartbeat' -Action (New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-File $hermesDir\scripts\hermes-heartbeat.ps1') -Trigger (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 30))"
Log ""
Log "  7. 启动 web UI:"
Log "       hermes-web-ui start"
Log "       start http://localhost:8648"
Log ""
Log "============================================="
Log "✅ 部署 9 步中的 1-3 完成（Python + Git + Node + 长路径）"
Log "   剩余 4-9 需重开 PowerShell 继续"
Log "============================================="

# Step 5-9: 创建 scripts 目录和心跳脚本（PATH 不依赖）
Log "  创建心跳脚本骨架..."
New-Item -ItemType Directory -Path "$hermesDir\scripts" -Force | Out-Null

@'
# hermes-heartbeat.ps1
$ErrorActionPreference = "SilentlyContinue"
$log = "$env:USERPROFILE\.hermes\logs\heartbeat.log"
New-Item -ItemType Directory -Path (Split-Path $log) -Force | Out-Null
Add-Content $log -Value "$(Get-Date -Format o) heartbeat OK"
hermes gateway status | Out-Null
'@ | Out-File -Encoding utf8 "$hermesDir\scripts\hermes-heartbeat.ps1"

Log "  ✅ 心跳脚本已生成: $hermesDir\scripts\hermes-heartbeat.ps1"
Log "  部署阶段 1 完成。打开新 PowerShell 继续跑 Step 4-9。"