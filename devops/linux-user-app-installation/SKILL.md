---
name: linux-user-app-installation
description: Use when installing Linux GUI/CLI apps from user-space ar...
version: 1
author: hermes-agent
license: MIT
metadata:
  hermes:
    tags: [linux, ubuntu, desktop, tarball, appimage, desktop-entry, user-install]
    related_skills: [linux-desktop-system-config]
---

# Linux user app installation

> 完整描述：Use when installing Linux GUI/CLI apps from user-space archives. Inspect first, install without sudo when possible, verify launcher and runtime honestly.

Install Linux applications distributed as `.tar.gz`, `.zip`, standalone binaries, or user-space installers into the current user's home directory. Prefer reversible, non-sudo installs under `~/.local/` or `~/Apps/` unless the package explicitly requires system integration.

## When to use

- The user asks to install or deploy a downloaded Linux application archive.
- The artifact contains a binary plus `install.sh`, `.desktop`, README, or similar launcher files.
- The target should be installed for the current user, not system-wide.

## Workflow

### 1. Locate and identify the artifact

Check both localized and English download directories before asking the user:

```bash
file "$HOME/下载/<name>" "$HOME/Downloads/<name>" 2>/dev/null || true
du -h "$HOME/下载/<name>" "$HOME/Downloads/<name>" 2>/dev/null || true
```

For archives, list contents before extracting:

```bash
tar -tzf /path/to/app.tar.gz | sed -n '1,80p'
```

Verify OS and architecture early:

```bash
uname -s
uname -m
```

### 2. Inspect installer behavior in a temporary directory

Extract to `/tmp/<app>-inspect` first. Do not run an unknown `install.sh` until you have read it.

```bash
rm -rf /tmp/<app>-inspect
mkdir -p /tmp/<app>-inspect
tar -xzf /path/to/app.tar.gz -C /tmp/<app>-inspect
sed -n '1,200p' /tmp/<app>-inspect/**/README* 2>/dev/null || true
sed -n '1,240p' /tmp/<app>-inspect/**/install.sh 2>/dev/null || true
sed -n '1,160p' /tmp/<app>-inspect/**/*.desktop 2>/dev/null || true
file /tmp/<app>-inspect/**/<binary> 2>/dev/null || true
ldd /tmp/<app>-inspect/**/<binary> 2>/dev/null || true
```

Proceed directly when the installer only writes to user-owned locations like `~/.local/bin` and `~/.local/share/applications`. Ask before using `sudo`, modifying `/usr`, adding services, or changing external systems.

### 3. Install to user-space

If the package ships a safe user installer, run it from its extracted directory:

```bash
cd /tmp/<app>-inspect/<extracted-dir>
./install.sh
```

If there is no installer, use the standard layout:

```bash
mkdir -p "$HOME/.local/bin" "$HOME/.local/share/applications" "$HOME/Apps/<app>"
install -m 0755 /path/to/binary "$HOME/.local/bin/<app>"
install -m 0644 /path/to/<app>.desktop "$HOME/.local/share/applications/<app>.desktop"
```

Update any `.desktop` `Exec=` and `TryExec=` lines to absolute installed paths so the menu works even when PATH differs from the shell.

### 4. Verify installation artifacts

Do not stop at installer success text. Read back the actual installed targets:

```bash
test -x "$HOME/.local/bin/<app>" && file "$HOME/.local/bin/<app>"
test -f "$HOME/.local/share/applications/<app>.desktop" && sed -n '1,80p' "$HOME/.local/share/applications/<app>.desktop"
desktop-file-validate "$HOME/.local/share/applications/<app>.desktop" && echo desktop_ok
```

A `desktop-file-validate` hint about multiple main categories is usually cosmetic; report it as non-blocking when the desktop file still validates successfully.

### 5. Verify runtime without confusing headless-shell failures for app failures

GUI apps launched from the agent's non-GUI shell may fail with display or Qt/XCB errors even after a correct install. First try a bounded runtime probe and capture stderr:

```bash
timeout 8s "$HOME/.local/bin/<app>" --help >/tmp/<app>.log 2>&1; code=$?; echo exit_code=$code; sed -n '1,120p' /tmp/<app>.log
```

If the error is display-related (`could not connect to display`, Qt platform plugin `xcb`, Wayland/XAUTHORITY), retry with an offscreen backend to separate binary viability from visible GUI launch:

```bash
mkdir -p /tmp/<app>-runtime
QT_QPA_PLATFORM=offscreen XDG_RUNTIME_DIR=/tmp/<app>-runtime timeout 10s "$HOME/.local/bin/<app>" >/tmp/<app>-offscreen.log 2>&1; echo exit_code=$?
```

Interpretation:

- Offscreen process stays alive until timeout: the app binary can start; ask the user to launch from the real desktop session or continue with GUI-session diagnostics.
- Immediate loader error from `ldd` or missing shared libraries: install dependencies or hand the user the exact `sudo apt install ...` command.
- Same display error in both normal and offscreen modes: inspect bundled Qt/platform plugin paths and environment variables before declaring success.

## Pitfalls

### P1: Read `install.sh` before running it

Inspect the script first because downloaded installers may write outside the user's home, add services, or invoke `sudo`; user-space writes can proceed, system writes require explicit confirmation.

### P2: Use absolute `.desktop` launcher paths

Rewrite `Exec=` and `TryExec=` to the installed absolute binary path because desktop launchers do not always inherit the same PATH as the terminal.

### P3: Headless Qt/XCB errors are not proof the install failed

Agent shells often lack a real display or XAuthority cookie. Use `QT_QPA_PLATFORM=offscreen` as a viability check, then report desktop-session launch as the true GUI verification boundary.

### P4: Check localized downloads first on this user's Ubuntu

The user's Ubuntu desktop commonly stores browser downloads in `$HOME/下载`; search `$HOME/下载` before `$HOME/Downloads` to avoid unnecessary clarification.
