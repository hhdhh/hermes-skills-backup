# Parallel segmented download for high-latency links (pure ASCII).
# Pair with scripts/range_http_server.py on the source machine.
# Usage: .\win-parallel-download.ps1 -Url http://10.x.x.x:8001/big.tar.gz -Out C:\Users\u\dst\big.tar.gz [-N 12]
# Success criterion: prints DONE + SHA256; caller MUST compare the hash with the source.
param([string]$Url,[string]$Out,[int]$N=12)
$ProgressPreference='SilentlyContinue'
$dst=Split-Path $Out -Parent
New-Item -ItemType Directory -Force $dst | Out-Null

# probe total size via HEAD (server must implement do_HEAD)
$req=[System.Net.HttpWebRequest]::Create($Url); $req.Method='HEAD'; $req.Timeout=15000
$resp=$req.GetResponse(); $total=[int64]$resp.ContentLength; $resp.Close()
Write-Host "total=$total"
$part=[math]::Ceiling($total/$N)

# N parallel segment fetches via Start-Job + curl.exe -r
$jobs=@()
for($i=0;$i -lt $N;$i++){
  $s=$i*$part; $e=[math]::Min($s+$part-1,$total-1)
  if($s -gt $e){continue}
  $jobs+=Start-Job -Arg ($Url,$i,$s,$e) -ScriptBlock {
    param($u,$i,$s,$e)
    $ProgressPreference='SilentlyContinue'
    & curl.exe -s --retry 5 --retry-all-errors -o "$env:TEMP\seg$i" -r "$s-$e" $u
    if($LASTEXITCODE -eq 0 -and (Test-Path "$env:TEMP\seg$i")){'ok'}else{'fail'}
  }
}
$null=$jobs|Wait-Job -Timeout 800
$null=$jobs|Receive-Job; $jobs|Remove-Job -Force

# retry any missing/short segment serially (exact size check)
$okIdx=@()
for($i=0;$i -lt $N;$i++){
  $s=$i*$part; $e=[math]::Min($s+$part-1,$total-1)
  if($s -gt $e){continue}
  $want=$e-$s+1
  $p="$env:TEMP\seg$i"
  if((Test-Path $p) -and ((Get-Item $p).Length -eq $want)){ $okIdx+=$i; continue }
  & curl.exe -s --retry 5 --retry-all-errors -o $p -r "$s-$e" $Url
  if((Test-Path $p) -and ((Get-Item $p).Length -eq $want)){ $okIdx+=$i } else { Write-Host "SEG-FAIL $i" }
}

# merge in segment order, then print SHA256 for caller-side comparison
if($okIdx.Count -eq $N){
  $fs=[System.IO.File]::Create($Out)
  foreach($i in $okIdx){
    $b=[IO.File]::ReadAllBytes("$env:TEMP\seg$i"); $fs.Write($b,0,$b.Length)
    Remove-Item "$env:TEMP\seg$i" -Force
  }
  $fs.Close()
  Write-Host ("DONE size={0}" -f (Get-Item $Out).Length)
  (certutil -hashfile $Out SHA256 | Select-Object -Skip 1 -First 1).Trim()
} else { Write-Host "INCOMPLETE $($okIdx.Count)/$N"; exit 1 }
