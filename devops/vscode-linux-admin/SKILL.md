---
name: vscode-linux-admin
description: Use when resetting, reinstalling, or restoring VS Code on...
version: 1
---

# VS Code admin on Linux (reset / reinstall / extension restore)

> 完整描述：Use when resetting, reinstalling, or restoring VS Code on Linux — factory reset, deb install, extension restore.

## Why "reset" fails: the state lives outside settings.json

Emptying `~/.config/Code/User/settings.json` to `{}` does NOT reset VS Code. The durable state is spread over:

| State | Location | Touched by settings.json edit? |
|---|---|---|
| Editor settings | `~/.config/Code/User/settings.json` | Yes |
| Extension logins/tokens, per-extension options | `~/.config/Code/User/globalStorage/` | No |
| UI + cached state (SQLite) | `~/.config/Code/User/state.vscdb` | No |
| Per-workspace state | `~/.config/Code/User/workspaceStorage/`, `User/History/` | No |
| Extension binaries | `~/.vscode/` | No |

`dpkg -P code` removes only system files. If the user says "settings won't reset", the missing step is deleting `~/.config/Code` + `~/.vscode` — that deletion IS the reset.

## Factory-reset procedure (verified Ubuntu 26.04, GNOME Wayland)

1. Backup: `code --list-extensions > ~/vscode-backup/extensions.txt` and `cp -r ~/.config/Code/User ~/vscode-backup/User` (≈100 MB, contains globalStorage tokens if you ever need them back).
2. Quit VS Code BEFORE deleting state — a live instance rewrites it on exit. Kill carefully (see pitfall P3).
3. `pkexec dpkg -P code` (polkit GUI prompt on the user's screen; needs session env exported — DISPLAY/XAUTHORITY/DBUS as in hermes-studio-desktop-deploy).
4. `rm -rf ~/.config/Code ~/.vscode` — the actual reset.
5. Reinstall: `pkexec dpkg -i <code_x.y.z_amd64.deb>`; verify `dpkg -l code` shows `ii` and `code --version` matches.
6. Restore extensions (see P1) and diff against the backup list.

Tell the user up front: extension BINARIES come back, extension-INTERNAL logins (ChatGPT token, sub2api baseUrl, SSH defaults) do not — that is the point of the reset. List which ones need reconfiguring.

## Pitfalls

**P1: `code --install-extension` ETIMEDOUT while `curl marketplace.visualstudio.com` returns 200**
The marketplace homepage and the VSIX download CDN are different endpoints; the CDN can be unreachable while the homepage answers in <1 s. Never conclude "marketplace is down" from a homepage 200, and never conclude "no network" before probing for a local proxy:
```bash
for p in 7890 1080 8080 10809 20171; do timeout 2 bash -c "echo >/dev/tcp/127.0.0.1/$p" 2>/dev/null && echo "proxy port $p open"; done
export https_proxy=http://127.0.0.1:7890 http_proxy=http://127.0.0.1:7890
while read ext; do code --install-extension "$ext"; done < ~/vscode-backup/extensions.txt
```
Through a local Clash this runs ~30–60 s per extension — run as a background job with completion notify, then verify `diff <(sort backup.txt) <(code --list-extensions | sort)`. A few EXTRA ids (e.g. `ms-python.python` pulled as a dependency) are normal; MISSING ids are not.

**P2: filename with spaces/parens (`code_1.137.0..._amd64 (1).deb`)**
Copy to a plain `/tmp/code-x.y.z.deb` before dpkg/pkexec — quoting through polkit layers is needlessly fragile.

**P3: `pkill -f` can kill your own shell**
`pkill -f '/usr/share/code/code'` matched the wrapping shell's own command line (the pattern is a substring of it) and SIGTERMed the compound command mid-sequence (exit -15, partial output). Inspect first with `pgrep -af '<pattern>'`, prefer `pkill -x code`, or kill PIDs captured from `pgrep` beforehand.

## Related
- General Linux desktop patterns (pkexec session env, AppImage, mutter XAUTHORITY): `linux-desktop-system-config` (user-owned).
