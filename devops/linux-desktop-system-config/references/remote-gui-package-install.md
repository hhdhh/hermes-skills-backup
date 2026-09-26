# Remote GUI package installation over SSH

Use this recipe for Ubuntu/Debian desktop applications distributed through GitHub Releases.

## Probe

Before changing the host, collect:

```bash
id
sed -n '1,8p' /etc/os-release
dpkg --print-architecture
dpkg -l | grep -iE '<package-pattern>' || true
command -v <binary> || true
sudo -n true; printf 'sudo_nopasswd=%s\n' "$?"
```

A blank `DISPLAY` in a noninteractive SSH session is normal. It does not prove that the remote host lacks a desktop session.

## Select an official asset

Query the upstream GitHub Releases API and inspect asset names before choosing. Match architecture and package suffix exactly:

- Debian x86-64: `_amd64.deb`
- Debian ARM64: `_arm64.deb`
- RPM x86-64: `.x86_64.rpm`

Do not assume an AppImage exists merely because older releases had one. Release packaging can change.

## Install safely

Prefer the distribution-native package. For a remote sudo prompt:

- open an SSH channel with a PTY;
- execute ordinary `sudo dpkg -i package.deb`;
- send the password only in response to the actual sudo prompt;
- never use `sudo -S`, command-line password arguments, shell history, generated credential-bearing scripts, or logs containing the password.

If `dpkg -i` reports missing dependencies, repair with the distribution package manager and then verify package state. Never hide the first command's failure with shell constructs that make the overall exit code misleading.

## Verify

Read back all relevant external state:

```bash
dpkg-query -W -f='${Package} ${Version}\n' <package>
command -v <binary>
grep -E '^(Name|Exec|Type)=' '/usr/share/applications/<entry>.desktop'
dpkg -L <package> | grep -E '/(bin|desktop|systemd)/'
```

Success requires the expected package/version, executable, desktop integration when applicable, and a zero installation exit status. Importing subscriptions, enabling system proxy, TUN, autostart, or services are separate configuration actions and should not be silently enabled unless requested.
