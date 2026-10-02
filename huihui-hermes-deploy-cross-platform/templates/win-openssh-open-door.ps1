# One-time admin paste: open OpenSSH Server on a Windows box and bring NetBird up.
# MUST stay pure ASCII: any non-ASCII char breaks parsing under GBK codepage PowerShell 5.1.
# Keep Chinese explanations in a separate README, never in this file.
# Usage: Win+X -> Terminal (Admin) -> paste whole file -> expect final line "sshd ... Running".

Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Set-Service -Name sshd -StartupType Automatic
Start-Service sshd
if (-not (Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue)) {
  New-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -DisplayName "OpenSSH Server (sshd)" -Enabled True -Direction Inbound -Protocol TCP -LocalPort 22 -Action Allow
}
$nb = Get-Service NetBirdHelper -ErrorAction SilentlyContinue
if (-not $nb) { $nb = Get-Service netbird -ErrorAction SilentlyContinue }
if ($nb) { Set-Service $nb.Name -StartupType Automatic; Start-Service $nb.Name; "NetBird started: " + $nb.Name } else { "NetBird service NOT installed" }
Get-Service sshd
