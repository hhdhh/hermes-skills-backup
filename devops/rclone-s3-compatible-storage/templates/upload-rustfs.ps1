#Requires -Version 5.0
<#
.SYNOPSIS
    上传文件/目录到 rustfs (S3 兼容存储)
.NOTES
    改下面 3 个 $ 开头变量就能用。
    首次运行如提示脚本执行被禁止,先在 PowerShell 执行:
        Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
#>

# ============== 你需要改的 3 个变量 ==============
$LocalPath     = "D:\data\2026-08-17"             # 本地要上传的文件/目录
$Bucket        = "robot-shanghai-yuyu"             # 桶名
$RemotePrefix  = "290/"                            # 远端前缀(子目录),末尾要带 /
$RcloneConf    = "$PSScriptRoot\rclone.conf"       # 配置文件路径(默认脚本同目录)
# ==================================================

$ErrorActionPreference = "Stop"
$ProgressPreference    = "Continue"

# rclone 下载地址(Windows 64-bit)
$RcloneZipUrl = "https://downloads.rclone.org/rclone-current-windows-amd64.zip"
$RcloneExe    = "$PSScriptRoot\rclone.exe"
$WorkDir      = Join-Path $env:TEMP "rustfs-upload-$((Get-Random).ToString())"

# ---- 1. 检查/下载 rclone.exe ----
if (-not (Test-Path $RcloneExe)) {
    Write-Host "[1/4] rclone.exe 不存在,正在下载..." -ForegroundColor Yellow
    Write-Host "      URL: $RcloneZipUrl"
    New-Item -ItemType Directory -Path $WorkDir -Force | Out-Null
    $ZipPath = Join-Path $WorkDir "rclone.zip"
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $RcloneZipUrl -OutFile $ZipPath -UseBasicParsing
    Write-Host "      下载完成,解压..." -ForegroundColor Yellow
    Expand-Archive -Path $ZipPath -DestinationPath $WorkDir -Force
    $ExeInZip = Get-ChildItem -Path $WorkDir -Recurse -Filter "rclone.exe" | Select-Object -First 1
    if (-not $ExeInZip) { throw "解压后找不到 rclone.exe,解压目录: $WorkDir" }
    Copy-Item $ExeInZip.FullName -Destination $RcloneExe -Force
    Write-Host "      rclone.exe 已就绪: $RcloneExe" -ForegroundColor Green
} else {
    Write-Host "[1/4] rclone.exe 已存在,跳过下载: $RcloneExe" -ForegroundColor Green
}

# ---- 2. 检查配置 ----
Write-Host "[2/4] 检查配置文件..." -ForegroundColor Yellow
if (-not (Test-Path $RcloneConf)) {
    throw "找不到配置文件: $RcloneConf`n请把 rclone.conf 放到脚本同目录。"
}
Write-Host "      配置: $RcloneConf" -ForegroundColor Green

# ---- 3. 验证远端可达 + 桶存在 ----
Write-Host "[3/4] 验证远端连通性..." -ForegroundColor Yellow
& $RcloneExe lsd "rustfs:$Bucket" --config="$RcloneConf" --no-check-certificate
if ($LASTEXITCODE -ne 0) { throw "远端连接失败,检查网络/AK/SK/endpoint" }

# ---- 4. 开始上传 ----
$Remote = "rustfs:${Bucket}/${RemotePrefix}"
Write-Host "[4/4] 开始上传" -ForegroundColor Green
Write-Host "      源: $LocalPath"
Write-Host "      目标: $Remote"
Write-Host "      进度条按数字键 1 隐藏,Ctrl+C 取消(可重跑续传)"
Write-Host ""

& $RcloneExe copy "$LocalPath" "$Remote" `
    --config="$RcloneConf" `
    --no-check-certificate `
    --retries 10 --retries-sleep 5s `
    --transfers 8 --checkers 16 `
    --stats 10s --stats-one-line -P

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ 上传完成!" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "❌ 上传失败,退出码 $LASTEXITCODE。可以直接重跑脚本续传。" -ForegroundColor Red
    exit $LASTEXITCODE
}
