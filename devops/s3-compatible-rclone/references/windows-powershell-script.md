# Windows PowerShell script for rclone + S3-compatible storage

Annotated template — copy and modify for new remotes.

## The non-ASCII rule

PowerShell script files written on a Linux box have **no BOM and no codepage declaration**.
On Windows, the script engine reads the file using the system default codepage (CP936/GBK
on Chinese Windows). Any non-ASCII byte sequence that is not valid GBK is silently replaced
with `?`, and if the result looks like syntax (e.g. `=` `,` `(` `)`), the parser bails.

**Rule for cross-platform-authored PowerShell: zero non-ASCII bytes in the source.**
Chinese/extended text goes in a separate `.md` documentation file.

## Annotated template

```powershell
#Requires -Version 5.0
<#
.SYNOPSIS
    rclone upload/download for S3-compatible object stores.

.DESCRIPTION
    Switch upload/download via -Mode. Auto-installs rclone, verifies remote,
    shows real-time progress, supports resume.

.PARAMETER Mode
    upload or download.

.PARAMETER LocalPath
    Local file or directory.

.PARAMETER RemotePath
    Full rclone remote path, e.g. rustfs:bucket/prefix/

.PARAMETER Bucket
    Bucket name. Use with -RemotePrefix to skip typing the full path.

.PARAMETER RemotePrefix
    Sub-directory under the bucket. Trailing slash is auto-added.

.PARAMETER Exclude
    Array of glob patterns to exclude.

.PARAMETER Transfers
    Concurrent transfers (default 8).

.PARAMETER RcloneConf
    Path to rclone.conf. Defaults to script's own directory.
#>

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("upload", "download")]
    [string]$Mode,

    [string]$LocalPath     = "",
    [string]$RemotePath    = "",
    [string]$Bucket        = "",
    [string]$RemotePrefix  = "",
    [string[]]$Exclude     = @(),
    [int]$Transfers        = 8,
    [string]$RcloneConf    = "$PSScriptRoot\rclone.conf"
)

$ErrorActionPreference = "Stop"
$ProgressPreference    = "Continue"

# Build RemotePath from Bucket + RemotePrefix if RemotePath is empty
if ($Bucket -and -not $RemotePath) {
    if ($RemotePrefix -and -not $RemotePrefix.EndsWith("/")) {
        $RemotePrefix = $RemotePrefix + "/"
    }
    $RemotePath = "rustfs:${Bucket}/${RemotePrefix}"
}

# rclone download URL (Windows 64-bit)
$RcloneZipUrl = "https://downloads.rclone.org/rclone-current-windows-amd64.zip"
$RcloneExe    = "$PSScriptRoot\rclone.exe"
$WorkDir      = Join-Path $env:TEMP "rclone-bootstrap-$((Get-Random).ToString())"

# 1. Check / download rclone.exe
if (-not (Test-Path $RcloneExe)) {
    Write-Host "[1/4] rclone.exe not found, downloading..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $WorkDir -Force | Out-Null
    $ZipPath = Join-Path $WorkDir "rclone.zip"
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $RcloneZipUrl -OutFile $ZipPath -UseBasicParsing
    Expand-Archive -Path $ZipPath -DestinationPath $WorkDir -Force
    $ExeInZip = Get-ChildItem -Path $WorkDir -Recurse -Filter "rclone.exe" | Select-Object -First 1
    if (-not $ExeInZip) { throw "rclone.exe not found after extract" }
    Copy-Item $ExeInZip.FullName -Destination $RcloneExe -Force
} else {
    Write-Host "[1/4] rclone.exe present" -ForegroundColor Green
}

# 2. Config check
if (-not (Test-Path $RcloneConf)) {
    throw "Config not found: $RcloneConf"
}

# 3. Remote reachability check
& $RcloneExe lsd "rustfs:" --config="$RcloneConf" --no-check-certificate | Select-Object -First 5
if ($LASTEXITCODE -ne 0) { throw "Remote unreachable" }

# 4. Build the rclone command (use array, not concat string, to avoid quote-escape hell)
$CommonArgs = @(
    "--config=`"$RcloneConf`""
    "--no-check-certificate"
    "--retries", "10", "--retries-sleep", "5s"
    "--transfers", "$Transfers", "--checkers", "16"
    "--stats", "10s", "--stats-one-line", "-P"
)

if ($Mode -eq "upload") {
    $rcloneArgs = @("copy", "`"$LocalPath`"", "`"$RemotePath`"") + $CommonArgs
} else {
    $rcloneArgs = @("copy", "`"$RemotePath`"", "`"$LocalPath`"") + $CommonArgs
}

if ($Exclude.Count -gt 0) {
    foreach ($e in $Exclude) { $rcloneArgs += @("--exclude", "`"$e`"") }
}

& $RcloneExe @rcloneArgs
```

## The run.bat wrapper (eliminates execution policy complaints)

Save as `run.bat` in the same directory as `rustfs.ps1`:

```bat
@echo off
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0rustfs.ps1" %*
```

User runs:
```
run.bat -Mode download -RemotePath "rustfs:bucket/prefix/" -LocalPath D:\out
```

`%~dp0` expands to the directory containing the .bat file, so it's location-independent.

## Quick debug commands (for the user when things go wrong)

```powershell
# What version of rclone is being used?
& "$PSScriptRoot\rclone.exe" version

# Which remotes are configured?
& "$PSScriptRoot\rclone.exe" listremotes

# Can I reach the endpoint at all (TLS + DNS only)?
Test-NetConnection -ComputerName "rustfs.example.com" -Port 8444

# Verbose log for a failing copy (paste last 30 lines for diagnosis)
& "$PSScriptRoot\rclone.exe" copy <src> <dst> --config rclone.conf -vv --log-file rclone.log
```

## Common errors and fixes

| Error | Cause | Fix |
|---|---|---|
| `running scripts is disabled on this system` | Execution policy | Use `run.bat` (zero config) |
| `cannot find rclone.exe` | First run failed to download | Check internet; manually download rclone-current-windows-amd64.zip and place rclone.exe next to the script |
| `Remote unreachable` | TLS / DNS / endpoint wrong | `Test-NetConnection` first; verify endpoint with browser |
| `403 Forbidden` | AK/SK wrong OR bucket policy denies user | Re-check AK/SK; ask storage admin to check bucket policy |
| `SignatureDoesNotMatch` | AK/SK typo, or copy-pasted with stray whitespace | Open `rclone.conf` in Notepad; check no leading/trailing spaces on secret |
