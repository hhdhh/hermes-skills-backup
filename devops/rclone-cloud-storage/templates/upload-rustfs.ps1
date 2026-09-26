#Requires -Version 5.0
<#
.SYNOPSIS
    Upload files/directories to a self-hosted S3-compatible object store via rclone.

.DESCRIPTION
    Auto-downloads rclone.exe on first run (reuses existing copy on subsequent runs).
    Uses the rclone.conf in the same directory as this script.
    Uploads $LocalPath to rustfs:<Bucket>/<RemotePrefix> with progress, retry,
    and resume (re-running the same command skips already-uploaded files).

.NOTES
    First-time Windows setup (run once in PowerShell):
        Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

    Edit the three parameters below before running. The rest is automatic.
#>

# ============== YOU EDIT THESE THREE LINES ==============
$LocalPath     = "D:\data\2026-08-17"             # local file or directory to upload
$Bucket        = "robot-289"                       # target bucket
$RemotePrefix  = "2026-08-17/"                     # sub-path inside bucket; MUST end with /
# ========================================================

$ErrorActionPreference = "Stop"
$ProgressPreference    = "Continue"

# rclone download — Windows 64-bit.  Change to ...-386.zip or ...-arm64.zip if needed.
$RcloneZipUrl = "https://downloads.rclone.org/rclone-current-windows-amd64.zip"
$RcloneExe    = "$PSScriptRoot\rclone.exe"
$RcloneConf   = "$PSScriptRoot\rclone.conf"
$WorkDir      = Join-Path $env:TEMP "rustfs-upload-$((Get-Random).ToString())"

# ---- 1. rclone.exe present? ----
if (-not (Test-Path $RcloneExe)) {
    Write-Host "[1/4] rclone.exe not found, downloading..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $WorkDir -Force | Out-Null
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $RcloneZipUrl -OutFile (Join-Path $WorkDir "rclone.zip") -UseBasicParsing
    Expand-Archive -Path (Join-Path $WorkDir "rclone.zip") -DestinationPath $WorkDir -Force
    $ExeInZip = Get-ChildItem -Path $WorkDir -Recurse -Filter "rclone.exe" | Select-Object -First 1
    if (-not $ExeInZip) { throw "rclone.exe not found in downloaded zip" }
    Copy-Item $ExeInZip.FullName -Destination $RcloneExe -Force
    Write-Host "      rclone.exe ready: $RcloneExe" -ForegroundColor Green
} else {
    Write-Host "[1/4] rclone.exe present: $RcloneExe" -ForegroundColor Green
}

# ---- 2. config present? ----
if (-not (Test-Path $RcloneConf)) {
    throw "rclone.conf not found at $RcloneConf.  Place it in the same directory as this script."
}
Write-Host "[2/4] config: $RcloneConf" -ForegroundColor Green

# ---- 3. verify remote is reachable ----
Write-Host "[3/4] verifying remote connectivity..." -ForegroundColor Yellow
& $RcloneExe lsd "rustfs:$Bucket" --config="$RcloneConf" --no-check-certificate
if ($LASTEXITCODE -ne 0) { throw "Remote unreachable or AK/SK wrong.  Check rclone.conf and network." }

# ---- 4. upload ----
$Remote = "rustfs:${Bucket}/${RemotePrefix}"
Write-Host "[4/4] uploading" -ForegroundColor Green
Write-Host "      source:      $LocalPath"
Write-Host "      destination: $Remote"
Write-Host "      (Ctrl+C to stop; re-run to resume from where it stopped)"
Write-Host ""

& $RcloneExe copy "$LocalPath" "$Remote" `
    --config="$RcloneConf" `
    --no-check-certificate `
    --retries 10 --retries-sleep 5s `
    --transfers 8 --checkers 16 `
    --stats 10s --stats-one-line -P

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Upload complete." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Upload failed (exit $LASTEXITCODE).  Re-run the script to resume." -ForegroundColor Red
    exit $LASTEXITCODE
}
