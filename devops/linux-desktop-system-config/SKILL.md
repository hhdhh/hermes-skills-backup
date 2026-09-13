---
name: linux-desktop-system-config
description: Install Ubuntu/GNOME system packages with user sudo.
version: 1
author: hermes-agent
license: MIT
metadata:
  hermes:
    tags: [linux, ubuntu, gnome, wayland, apt, system-config, input-method]
    related_skills: []
---

# Linux desktop system config

Install + configure system packages on Ubuntu/GNOME/Wayland where the user owns the sudo password. Covers input methods, fonts, codecs, autostart services, and similar per-user-but-system-owned components.

## When to use

- User asks to install a desktop system package (input method, fonts, codecs, system service) that needs `sudo apt install`
- After install, configuration touches user-space (`gsettings`, `~/.config/autostart/`, dconf)
- Environment is GNOME Wayland or X11 with a normal user session

### 0. Sanity check: where is the keyboard event actually going?

IME "doesn't work" almost always means the keystroke never reached the IM daemon — not that the daemon is broken. Before assuming the engine or the terminal is the problem, trace the keystroke path:

```bash
# A. What does the IM CLIENT see as its IM_MODULE?
#    This is the #1 thing. If GTK_IM_MODULE=fcitx but fcitx5 isn't running,
#    the client silently falls back to plain XKB. No error, no log.
env | grep -iE "GTK_IM|QT_IM|XMODIFIERS|SDL_IM"
# Also check the daemon's own env (clients inherit from their parent process,
# and the daemon was launched with whatever env its autostart had at the time)
IBUS_PID=$(pgrep -f 'ibus-daemon' | head -1)
cat /proc/$IBUS_PID/environ 2>/dev/null | tr '\0' '\n' | grep -iE "GTK_IM|QT_IM|XMODIFIERS|SDL_IM"
# And any residue in shell rc / profile.d
grep -nE "GTK_IM_MODULE|QT_IM_MODULE|XMODIFIERS|SDL_IM_MODULE" \
    ~/.bashrc ~/.profile /etc/profile.d/*.sh 2>/dev/null

# B. Which terminal? (only matters if A passes)
ls /usr/bin/*terminal* /usr/bin/foot /usr/bin/kitty /usr/bin/alacritty /usr/bin/wezterm 2>/dev/null
dpkg -l 2>/dev/null | grep -E "gnome-terminal|ptyxis|foot|kitty|alacritty|wezterm" | awk '{print $2, $3}'

# C. Engine actually registered?
ibus engine
ibus list-engine | grep -i pinyin
```

If A shows `GTK_IM_MODULE=fcitx` and `pgrep fcitx5` is empty, **fix A first** — see P2 and P25. Don't burn time investigating terminal protocol issues until IM_MODULE is correct.

## Core workflow

### 1. Detect before recommending

Before installing, always inspect what's already there. Saves the user from reinstalling an already-present engine and reveals constraints.

```bash
# What's installed and what binary is on PATH
dpkg -l 2>/dev/null | grep -iE "<relevant pattern>"
which <binary>

# User vs system IM/UI state
gsettings get org.gnome.desktop.input-sources sources 2>/dev/null
gsettings get org.freedesktop.ibus.general preload-engines 2>/dev/null
im-config -m 2>/dev/null        # shows current system IM choice (ibus / fcitx / none)

# Autostart presence
ls ~/.config/autostart/ 2>/dev/null
ls /etc/xdg/autostart/ | grep -iE "<pattern>"
```

For input methods specifically: check `ibus list-engine` **after** a daemon restart — see pitfall P1.

### 2. Decide install vs user-action

If `SUDO_PASSWORD` is not in env AND `sudo -n true` fails, you can't install yourself. Don't guess passwords or pipe them via `sudo -S` (security guardrail blocks it). Instead, present the exact one-liner the user can run themselves. If the install also requires post-install configuration (settings, restart of a service), it's fine to do the configuration part while waiting for the install — most config doesn't need root.

### 3. Install (user or self)

Single command:
```bash
sudo apt install -y <packages>
```

### 4. Configure user-space

```bash
# Restart any daemon that caches a list of available engines / plugins
ibus-daemon -drxR           # -d daemonize, -r replace, -x execute, -R (X11-safe)
# GNOME input sources (input methods / keyboard layouts)
gsettings set org.gnome.desktop.input-sources sources "[('xkb','us'), ('ibus','<engine>'), ...]"
gsettings set org.gnome.desktop.input-sources mru-sources "[('ibus','<engine>'), ...]"
# MRU controls which source is active on next login — put the preferred one first.
```

### 5. Verify

Verify the operation actually worked (not just that the command exited 0):
- For input methods: `ibus list-engine | grep <name>` should show the new engine after restart
- `gsettings get ... current` returns the index you just set
- Try opening a text editor and typing to confirm

### 6. Runtime engine switching (user asks "切换到 X")

When the user wants to flip between already-installed engines (e.g. between pinyin and libpinyin), do both:
```bash
export DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/$(id -u)

# sources array index of the target engine (see pitfall P8)
TARGET_IDX=2
TARGET_NAME=pinyin

gsettings set org.gnome.desktop.input-sources current "$TARGET_IDX"
gsettings set org.gnome.desktop.input-sources mru-sources \
    "[('ibus', '$TARGET_NAME'), ...other sources in order...]"

# Nudge the ibus daemon — gsettings alone doesn't always wake it
ibus engine "$TARGET_NAME"

# Verify (this is the source of truth)
ibus engine
```
Without `ibus engine`, the daemon may keep using the previously active engine even though `current` changed.

## Pitfalls

### P1: daemon must be restarted after engine install
`ibus list-engine` returns the engines known to the running ibus-daemon, **not** the engines installed on disk. After `apt install ibus-pinyin`, the running daemon still doesn't know about it until you restart:
```bash
ibus-daemon -drxR
```
Always restart the daemon after every `apt install ibus-*` and verify before assuming the engine is available.

### P2: prior input method residue (the silent IME killer)
If the user previously used fcitx5 and switched to ibus (or vice versa), check that environment vars aren't still pointing at the old framework. They cause **silent** breakage in GTK/QT/Wayland apps — no error, no log, the client just falls through to plain XKB and you see English letters where Chinese should be:
```bash
grep -nE "GTK_IM_MODULE|QT_IM_MODULE|XMODIFIERS|INPUT_METHOD|SDL_IM_MODULE|fcitx|ibus" \
    ~/.bashrc ~/.profile /etc/environment /etc/profile.d/*.sh \
    ~/.config/im-config/*.env 2>/dev/null
```
Empty result = clean. Any leftover fcitx lines must be removed.

**Critical — also check the daemon's own environment**, not just the user's shell rc files. ibus-daemon inherits env vars from whatever launched it (gdm, autostart .desktop, or your test shell). If the daemon has `GTK_IM_MODULE=fcitx`, every GTK client in that session will read the wrong value too:
```bash
IBUS_PID=$(pgrep -f 'ibus-daemon' | head -1)
cat /proc/$IBUS_PID/environ 2>/dev/null | tr '\0' '\n' | grep -iE "GTK_IM|QT_IM|XMODIFIERS|SDL_IM"
```
The reason this fails silently: GTK clients try `GTK_IM_MODULE=fcitx` → look for fcitx5 socket → not running → **fall back to XKB without an error**. You see "ibus is healthy, all checks pass, but I can't type Chinese." See P25 for the diagnostic ladder and full case study.

### P3: `im-config` vs gsettings
- `im-config` is the system-wide selector (ibus / fcitx / none). Changing it requires re-login.
- `gsettings org.gnome.desktop.input-sources sources` is the per-session list of active input sources. This is what the user actually toggles with `Super+Space`.

### P4: `gsettings` requires a session
`gsettings` only works when `DISPLAY` is set (and you're running as the user who owns the session). Run as the user, with `DISPLAY=:0` exported. For Wayland, also need `WAYLAND_DISPLAY=wayland-0` and `XDG_RUNTIME_DIR=/run/user/$(id -u)`.

### P5: autostart vs `~/.config/autostart/` vs `/etc/xdg/autostart/`
System autostart (`/etc/xdg/autostart/ibus.desktop`) runs at login for everyone. A user override in `~/.config/autostart/` with the same name takes precedence. If you need to disable a system autostart for one user, copy the `.desktop` to `~/.config/autostart/` and add `Hidden=true`.

### P6: don't pipe passwords to `sudo -S`
The Hermes safety guardrail refuses blind password guesses. If `SUDO_PASSWORD` env var is set, you may use `sudo -S` legitimately (the variable exists for this purpose). Otherwise present the command for the user to run themselves.

### P7: gsettings `current` ≠ ibus daemon active engine (runtime switching)
GNOME's `org.gnome.desktop.input-sources current` (an index into `sources`) and ibus daemon's currently-active engine are two separate state machines. Setting `gsettings ... current` updates GNOME — the daemon *usually* catches up, but not always immediately. To guarantee they agree (verified empirically 2026-08-14):
```bash
# Both: GNOME index AND explicit ibus nudge
gsettings set org.gnome.desktop.input-sources current <N>     # N is index in sources[]
ibus engine <engine-name>                                     # daemon-side switch
```
Then verify with `ibus engine` (no args) — it prints the active engine. Only trust this output, not `current`.

### P8: `sources` array indices are positional
The `sources` array is ordered. Index `N` = `sources[N]`. If the array is `[('xkb','us'), ('ibus','libpinyin'), ('ibus','pinyin')]`, then:
- `current=0` → us (English)
- `current=1` → libpinyin
- `current=2` → pinyin

When adding/removing an engine, re-count the indices before setting `current`. Misalignment here is silent — `gsettings set` accepts any uint32.

## Reference recipes

- `references/input-methods.md` — full ibus install + engine selection + cleanup recipe (worked example: ibus-pinyin on Ubuntu 26.04 GNOME Wayland, Aug 2026). Also covers the old-`.deb` + current-Ubuntu path (fcitx-baidupinyin 1.0.1 / 搜狗 4.2.1 era) with the dpkg `--force-depends` recovery sequence for the `iU` lock state.
- `references/macos-theming.md` — full macOS-style desktop install + driver updates recipe (WhiteSur theme + SF Pro/SF Mono fonts + Blur My Shell + Ptyxis dark palette + Firefox WhiteSur + Plank + Ulauncher launcher, Ubuntu 26.04 GNOME Wayland, Aug 2026). Covers 7 phases from user-space downloads through gdm re-login. Includes the gnome-background-properties XML template, Ptyxis palette preset list, and the persist.sh pattern for P15.
- `references/macos-rounded-corners.md` — Phase 8 addendum: explicit corner-radius + vibrancy recipe for the panel, dock, Plank, and GTK 4 libadwaita apps. The single biggest "this looks like macOS now" change beyond the theme itself. Also captures GNOME 50 key-removals (no `enable-appmenu`), Ptyxis `cursor-shape` enum, and Ulauncher autostart `--hide-window` flag.

## Driver updates: theme packs, fonts, extensions, wallpapers

Beyond input methods, the most common non-codec system-config task is "make this Linux desktop look like X" (macOS, Windows, etc.). These installs span three layers, and knowing which is which prevents the "I downloaded it but nothing changed" trap:

| Layer | Goes to | Needs sudo? | Survives logout? |
|---|---|---|---|
| GTK themes / icons / cursors | `~/.themes` + `~/.local/share/icons` | **No** | Yes |
| Fonts (`.otf`/`.ttf`) | `~/.fonts` + `fc-cache` | **No** | Yes |
| GNOME extensions | `~/.local/share/gnome-shell/extensions/<uuid>/` | **No** | **Only after re-login** |
| Wallpapers (`.jpg`) | `~/.local/share/backgrounds/` + `~/.local/share/gnome-background-properties/*.xml` | **No** | Yes |
| Tweaks / theme switches | `gsettings` | **No** | Yes (current session) |
| apt deps (sassc, libglib2.0-dev-bin, libxml2-utils, gnome-tweaks, plank, etc.) | system | **Yes** | Yes |

The "no sudo" parts are huge — most of the visual work is user-space. Drive those to completion first. Only the apt deps block on sudo, and that can be a single short handoff to the user.

### Driver pattern: hand off a self-contained script

When the agent can't run sudo (no `sudo -n`, no NOPASSWD) and apt deps are needed, **don't dump a one-liner**. Write a complete script under `/tmp/...step2.sh` that contains (a) the apt install, (b) the user-space post-install, (c) the gsettings switches, all gated with `set -e` so the user sees exactly where it stopped. The user copies and runs it once. Time cost: one user-side invocation, not five back-and-forths.

```bash
cat > /tmp/install-step-N.sh <<'EOF'
#!/bin/bash
set -e
# system deps
sudo apt-get install -y pkg1 pkg2
# user-space followups
gsettings set org.gnome.desktop.interface gtk-theme 'WhiteSur-blue'
EOF
chmod +x /tmp/install-step-N.sh
echo "请运行: bash /tmp/install-step-N.sh"
```

### Pitfalls specific to user-space driver installs

**P9: GNOME extensions are not visible until re-login**
`gnome-extensions list --user` returns empty for any extension you just deployed to `~/.local/share/gnome-shell/extensions/`. The shell scans that directory **once at session start**. Two options:
- Run `gnome-extensions enable <uuid>` only **after** the user has logged out and back in once. The tool will still say "does not exist" before that — that's expected, not a bug.
- Tell the user to log out and back in after the user-space deploys, BEFORE running the `enable` step.

**P10: `glib-compile-schemas` placement**
Extensions that ship their own `org.gnome.shell.extensions.<name>.gschema.xml` will not register their gsettings keys if you compile the schema inside the extension's own `schemas/` directory. The **`schemas/` dir is for shipping only** — the GSettings daemon doesn't read it. You must copy the `.gschema.xml` to `~/.local/share/glib-2.0/schemas/` and run `glib-compile-schemas` there:
```bash
mkdir -p ~/.local/share/glib-2.0/schemas
cp <extension>/schemas/*.gschema.xml ~/.local/share/glib-2.0/schemas/
glib-compile-schemas ~/.local/share/glib-2.0/schemas/
# Now gsettings list-recursively org.gnome.shell.extensions.<name> works
```
This bit me on Blur My Shell — the extension was "enabled" but the schema was missing, so all preference reads returned `没有该架构`. Symptom: extension shows as enabled but no settings are readable and no blur happens.

**P11: extension metadata.json from `.json.in` template**
GNOME's official extensions repo (e.g. `GNOME/gnome-shell-extensions`) ships `user-theme/metadata.json.in` with placeholders like `@uuid@`, `@shell_current@`. You must construct a real `metadata.json` with the actual values before deploying. The current UUID for User Themes is `user-theme@gnome-shell-extensions.gnome.org` (was `...gcampax.github.com` historically). Build the JSON by hand — don't try to templatize it.

**P12: `gnome-extensions enable` without a session**
The `gnome-extensions` CLI talks to the active session via D-Bus. If `gnome-shell` is not running in the agent's session (you're a non-interactive shell), the tool can't enumerate user extensions and will report "extension does not exist" even when the directory is correct. This is the same P9 root cause. Verify by checking `ps -ef | grep gnome-shell` — if the agent is running under a different user/session, the deploy is correct; the user just needs to re-login.

**P13: Ubuntu Dock vs Dash-to-Dock schema**
Ubuntu 26.04 ships both `ubuntu-dock` (the default) and the upstream `dash-to-dock` (when installed via apt). They share most dconf keys but expose them under different schemas — `org.gnome.shell.extensions.ubuntu-dock` vs `org.gnome.shell.extensions.dash-to-dock`. Setting the position on the wrong schema is silent. Check which one is actually loaded:
```bash
gnome-extensions list --enabled | grep -i dock
ps -ef | grep -E "ubuntu-dock|dash-to-dock" | grep -v grep
```
Then set the keys on the right schema.

**P14: libadwaita apps follow `color-scheme`, not the GTK theme name**
When you set `gsettings set org.gnome.desktop.interface gtk-theme 'WhiteSur-blue'`, GTK3 apps see it. Libadwaita (GTK4) apps follow `org.gnome.desktop.interface color-scheme` instead — they pick between the dark and light variants of whatever is in `~/.config/gtk-4.0/`. So if you set `color-scheme=prefer-dark` but also keep `gtk-theme=WhiteSur-blue` (singular), libadwaita will use the dark variant automatically. Don't try to set `-dark` / `-light` suffix in the gtk-theme key — that's a GTK3 convention.

**P15: gsettings can reset between apt installs and re-login**
Some apt package installs trigger a gdm/pam phase that resets user-mode dconf on the user mount. After bunching a sequence of `apt install` + `gsettings set`, you may find the latter are silently reverted. Mitigation: write a `persist.sh` that re-applies every gsettings, and run it once after install completes AND verify after re-login. Symptom: theme/icons/font reverted to Ubuntu defaults even though the install command exited 0.

**P16: `gnome-background-properties/*.xml` requires the parent dir to exist first**
Heredoc redirecting into `~/.local/share/gnome-background-properties/foo.xml` silently fails if the parent directory doesn't exist (bash opens the path for writing but the dir doesn't exist). The file is never created, and the Wallpaper switcher in Settings > Background won't show the new entries. Always `mkdir -p` the parent before writing the xml.

**P17: relocatable dconf schemas require `dconf write`, not `gsettings set`**
Plank's `net.launchpad.plank.dock.settings` is a relocatable schema. `gsettings set ...` will fail with "schema is relocatable (must specify a path)". Use `dconf write /net/launchpad/plank/docks/dock1/<key> <value>` with the absolute path. The trailing value needs to be quoted: `dconf write /net/launchpad/plank/docks/dock1/theme "'WhiteSur-Dark'"` (double-quoted single-quoted string).

**P18: validate gsettings values before bulk-applying**
`gsettings set` will fail with "value not in valid range" for some keys. Different keys have different enum/value types. Bad values short-circuit `set -e` scripts and leave half-applied state. Two recovery patterns:
- `gsettings range <schema> <key>` to enumerate valid values before scripting
- Run each `gsettings set` in its own `if` block so one bad value doesn't abort the rest (for recipes that aren't gdm-critical)

For example: `new-tab-position` accepts only `last` or `next` (not `after-current`); `scrollbar-policy` accepts `never`/`system`/`always`; `opacity` is float 0.0-1.0 not int.

**P19: pre-2022 `.deb` packages lock apt when half-installed**
Old IM debs (搜狗 4.2.1 / 百度 1.0.1 / Deepin-era fcitx4 wrappers, anything from ≤ 2020) declare Depends like `libqt5core5a (>= 5.7.1)` and `qml-module-qtquick-controls (>= 5.5.1)`. Ubuntu 22.04+ renamed `libqt5core5a` → `libqt5core5b` → eventually dropped Qt5 entirely from the `5a` series. The deb goes into `iU` state (unpacked but not configured) because dpkg can't resolve the old version spec against the current package pool.

The trap: **apt refuses every install while a deb is in `iU`**. Not just the offending one — `apt install fcitx-bin` also fails. The error looks like "you have held broken packages" but the real cause is the half-installed deb sitting in dpkg's state table.

Fix sequence (worked on Ubuntu 26.04, Aug 2026, fcitx-baidupinyin 1.0.1):
```bash
# 1. Force-remove the half-installed deb to break the lock
sudo dpkg --remove --force-depends fcitx-baidupinyin
sudo dpkg --configure -a

# 2. Now apt is free again — install the modern equivalents
sudo apt install -y fcitx fcitx-bin fcitx-data fcitx-modules \
    fcitx-module-dbus fcitx-module-x11 fcitx-frontend-qt5 \
    fcitx-frontend-gtk3 fcitx-ui-classic fcitx-config-gtk \
    libqt5qml5 qml-module-qtquick-controls qml-module-qtquick-layouts \
    qml-module-qtgraphicaleffects qml-module-qtquick-window2 \
    qml-module-qtquick-dialogs qml-module-qtquick-templates2 \
    qml-module-qtquick-particles2 libqt5quicktemplates2-5 \
    libqt5quickparticles5 qml-module-qtquick2 qml-module-qtqml \
    qml-module-qtqml-models2 qml-module-qt-labs-folderlistmodel \
    qml-module-qt-labs-settings libqt5qmlworkerscript5 \
    qml-module-qtquick-privatewidgets

# 3. Put the old deb back with --force-depends (still wants the renamed libs)
sudo dpkg -i --force-depends /path/to/fcitx-baidupinyin.deb
# Fallback if dpkg -i errors out:
sudo apt --fix-broken install -y
sudo dpkg -i --force-depends /path/to/fcitx-baidupinyin.deb
```
Verify the engine binary exists: `ls /usr/lib/x86_64-linux-gnu/fcitx/ | grep <keyword>`. For baidu: `fcitx-baidupinyin.so`.

Full recipe with im-config + gsettings + fcitx profile in `references/input-methods.md` under "Installing a Chinese IM from an old `.deb`".

**P20: `set -e` + `which foo 2>/dev/null` can exit the script silently**
A driver-pattern script with `set -euo pipefail` will abort at `which fcitx-config-gtk` if that binary isn't installed yet (which is normal mid-install). The `2>/dev/null` swallows the "not found" message, the script just stops with no output explaining why. Two fixes, pick whichever matches the script's intent:
```bash
# Option A: don't fail when the binary is optional
command -v fcitx-config-gtk || true

# Option B: still verify, but with a clear message
if command -v fcitx-config-gtk >/dev/null; then
    say "fcitx-config-gtk: present"
else
    warn "fcitx-config-gtk: missing (ok if not needed)"
fi
```
Symptom in practice (Aug 2026, install-baidu-fcitx.sh): script ran Step 0 → 1 → 2 → 3 cleanly, then exited at the first `which fcitx5 2>/dev/null` line in Step 3. dpkg state was correct, user only saw "Step 3 partially printed" with no error. The fix is to never use bare `which` inside `set -e` blocks — always pair with `|| true` or `command -v`.

**P21: fcitx4 + Wayland is a dead end on Ubuntu 26.04 — go straight to fcitx5**
Old Chinese IM `.deb` packages (fcitx-baidupinyin 1.0.1, 搜狗 4.2.1 era) require fcitx 4.x. Installing them via the P19 path succeeds (dpkg shows `ii`), the engine `.so` loads (`fcitx-baidupinyin.conf` and `fcitx-baiducloud.conf` both appear in fcitx-verbose log), but the daemon crashes within ~1 second with two terminal errors:
```
(ERROR-76300 ui.c:165) no usable user interface.
(ERROR-76300 xim.c:239) XIM启动错误。是否有另一个名为ibus的XIM守护程序正在运行？
(INFO-76300 instance.c:443) Exiting.
```
Root causes that **don't have a workaround in fcitx4**:
1. `-x` (execute) flag was removed in fcitx 4.2.9.9 (Ubuntu 26.04 ships this), so the canonical `fcitx -drx` startup prints "无效的选项 -- x" and aborts. Use `fcitx -d -r` instead — but that doesn't fix the UI.
2. fcitx4's UI panels (`classic`, `kimpanel`) all require x11 / XWayland access for the candidate window. Under Ubuntu 26.04's default mutter Wayland session, neither can initialize — `kimpanel-ui` needs a compatible panel extension, `classic-ui` needs a working XIM on `:0`, and the XIM port is already held by the running ibus-daemon.

**Don't burn time here.** Skip fcitx4 entirely. Recommended replacement (preserves cloud-style suggestions):
```bash
sudo apt purge -y fcitx fcitx-baidupinyin fcitx-bin fcitx-data fcitx-modules
sudo apt install -y fcitx5 fcitx5-chinese-addons fcitx5-module-cloudpinyin \
    fcitx5-frontend-gtk3 fcitx5-frontend-qt5 fcitx5-frontend-qt6 \
    fcitx5-pinyin fcitx5-config-qt
sudo im-config -n fcitx5
# /etc/environment.d/fcitx5.conf (same key set as the fcitx recipe)
fcitx5 -d -r
```
`fcitx5-module-cloudpinyin` ships the cloud-suggestion module that asynchronously pulls candidates from 搜狗 / 百度 / Google — close to the "联网联想" experience users expect from 百度/搜狗 Linux. Verified on Ubuntu 26.04, Aug 2026: ibus-pinyin and ibus-libpinyin were preserved as fallbacks in `org.gnome.desktop.input-sources sources`.

If the user explicitly insists on keeping fcitx4, they need libfuse-less workaround for the UI too — which doesn't exist. Push them to fcitx5.

**P22: AppImage needs libfuse2 (not libfuse3) — but Ubuntu 26.04 ships only libfuse3**
Ubuntu 26.04 ships `libfuse3.so.4` but **no `libfuse.so.2`**. AppImages built against libfuse2 fail to start with:
```
dlopen(): error loading libfuse.so.2
AppImages require FUSE to run.
You might still be able to extract the contents of this AppImage
if you run it with the --appimage-extract option.
```
Two fixes:
- **Preferred (no sudo needed, no FUSE runtime required):** extract the AppImage to `~/Apps/<name>/squashfs-root/` and create a launcher script in `~/.local/bin/` that execs the extracted `AppRun`. This works for any AppImage that doesn't need FUSE-specific kernel features at runtime. Worked for both Wox 2.3.0 and Snipaste 2.11.3.
- **Alternative (requires sudo, restores double-click behavior):** `sudo apt install libfuse2`. The new package coexists fine with libfuse3.

Extraction pattern (use the AppImage's own extractor, which knows its layout):
```bash
chmod +x /path/to/Foo.AppImage
mkdir -p ~/Apps/foo
cd ~/Apps/foo
/path/to/Foo.AppImage --appimage-extract     # produces squashfs-root/
```
Then point the launcher at `~/Apps/foo/squashfs-root/AppRun`.

**P23: AppImage + XWayland + mutter auth file**
For Qt5 / Qt6 GUI AppImages launched from a non-GUI terminal (e.g. via `nohup ... &`), they fail with:
```
Authorization required, but no authorization protocol specified
qt.qpa.xcb: could not connect to display :0
```
Root cause: mutter writes the Xwayland auth cookie to `/run/user/$UID/.mutter-Xwaylandauth.<RANDOM>` (the suffix changes every session), and `$XAUTHORITY` env must point at it. A child process started from a non-session shell inherits `$XAUTHORITY` only if the parent shell was launched inside the GNOME session — most agent-spawned terminals are not.

**Fix for any X11-only GUI app launched from a non-GUI shell** (Snipaste, KeePassXC, Krita, Audacity, etc.):
```bash
AUTH_FILE=$(ls -t /run/user/$(id -u)/.mutter-Xwaylandauth.* 2>/dev/null | head -1)
[ -n "$AUTH_FILE" ] && [ -r "$AUTH_FILE" ] && export XAUTHORITY="$AUTH_FILE"
export DISPLAY="${DISPLAY:-:0}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-wayland;xcb}"   # Qt only
exec /path/to/app "$@"
```
For native Wayland apps this is unnecessary. For mixed-mode Qt apps, the `wayland;xcb` fallback chain lets the app pick the better backend. Embed this in every `~/.local/bin/<app>` wrapper for GUI AppImages.

Verify it worked: `ls -la /proc/<pid>/exe | grep <appname>` should resolve to the binary, and there should be no `qt.qpa.xcb: could not connect` in stderr.

**P24: GitHub releases direct download is slow from CN — use `gh-proxy.com` mirror**
Direct `curl https://github.com/.../release-X.Y.Z/foo.AppImage` from a CN network can run at ~50 KB/s (3 minutes for 5 MB, often times out before 30 MB completes). The agent sees `speed_download ≈ 50000 B/s` and exits 124 on the timeout. Two reliable mirrors that mirror github.com releases without auth:
- `https://gh-proxy.com/https://github.com/<owner>/<repo>/releases/download/<tag>/<asset>`
- `https://ghfast.top/https://github.com/<owner>/<repo>/releases/download/<tag>/<asset>`

Both proxy through Cloudflare's SIN edge (latency ~30ms from CN). Observed speeds: 2.2 MB/s for a 30 MB Wox AppImage (13 seconds vs 600+ seconds). `gh-proxy.net` is unreliable (often redirects to survey pages) — skip it.

Note this only applies to **release assets**, not arbitrary GitHub URLs. Code raw.githubusercontent.com direct works fine.

**P25: "ibus is healthy in checks but I can't type Chinese" — 90% of the time it's an IM_MODULE mismatch, not a protocol bug**

The classic false-positive trap: agent runs `ibus list-engine` (sees `pinyin`), runs `gsettings get ... sources` (sees `[('xkb','us'), ('ibus','pinyin')]`), runs `ibus engine` (returns `pinyin`), declares "输入法正常" — and the user goes "doesn't work in my terminal, pressing `n i` just types `ni`." The agent then assumes it's a Wayland protocol issue and recommends switching terminals. **Usually wrong.** The checks all passed because the engine, the daemon, the D-Bus layer, and the IM client routing are **all separate things**, and only the last one was actually broken.

**The real chain**: GTK clients read `GTK_IM_MODULE` from the environment → look for the matching daemon socket → if not found, **silently fall back to plain XKB** with no error. The daemon may be running perfectly and the engine may be loaded — but the client never tried to connect. This is why every "is ibus healthy" check returns green.

**Diagnostic ladder — run in order, stop at first signal**:

```bash
# 0. THE FIRST CHECK (skip this and you'll be wrong half the time):
#    What does the IM CLIENT see? Check both user shell AND ibus-daemon's own env.
IBUS_PID=$(pgrep -f 'ibus-daemon' | head -1)
echo "--- user shell env ---"
env | grep -iE "GTK_IM|QT_IM|XMODIFIERS|SDL_IM"
echo "--- ibus-daemon env ---"
cat /proc/$IBUS_PID/environ 2>/dev/null | tr '\0' '\n' | grep -iE "GTK_IM|QT_IM|XMODIFIERS|SDL_IM"
echo "--- residual exports in shell rc / profile.d ---"
grep -nE "GTK_IM_MODULE|QT_IM_MODULE|XMODIFIERS|SDL_IM_MODULE" \
    ~/.bashrc ~/.profile /etc/profile.d/*.sh 2>/dev/null
```

If `GTK_IM_MODULE=fcitx` is showing up but `fcitx5` is not running (`pgrep -f fcitx5` empty), **this is your problem**. The client will look for fcitx5's socket, not find it, and silently fall back to XKB. ibus-daemon is healthy and the engine is loaded, but the client never tried to talk to it.

```bash
# 1. Which terminal? (only matters AFTER 0 passes)
dpkg -l | grep -E "gnome-terminal|ptyxis|foot|kitty|alacritty|wezterm"

# 2. Is the engine actually registered and active? (engine-side)
ibus engine
ibus list-engine | grep -i pinyin

# 3. Is the D-Bus side responsive? (daemon-side)
gdbus call --address "$(ibus address | sed 's/.*=//;s/,.*//')" \
  --dest org.freedesktop.IBus --object-path /org/freedesktop/IBus \
  --method org.freedesktop.IBus.GetEnginesByNames "['pinyin']"

# 4. Does ibus work in a known-good GTK app?
#    Open gnome-text-editor, type. If Chinese works there, the engine is fine
#    AND IM_MODULE is correct for that process. If it doesn't, restart ibus-daemon
#    with `ibus-daemon --xim --replace --daemonize` and retry before blaming the terminal.

# 5. Does ibus work in the failing terminal?
#    Just have the user try. No clean way to script this without focus events.
#    If the same env vars that worked in step 4 don't work in step 5,
#    THEN suspect a terminal-specific IME protocol issue.
```

**The most common cause (Aug 2026, Ubuntu 26.04 + ibus 1.5.34rc2 + previously-installed-then-removed fcitx5)**: user upgraded or installed a package that brought back a stale `GTK_IM_MODULE=fcitx` export somewhere (e.g. an autostart .desktop was regenerated, a profile.d script was re-enabled by an apt hook, or the user installed a tool that prepended it). ibus-daemon was already running with the bad env from when it was launched, so even fixing the user's shell wouldn't help until the daemon itself was restarted. Fix:
```bash
# 1. Find every place that re-exports the wrong value
sudo grep -rnE "GTK_IM_MODULE=|QT_IM_MODULE=|XMODIFIERS=" /etc/ /usr/lib/ \
    ~/.bashrc ~/.profile ~/.config/ 2>/dev/null
# 2. Comment out or delete them
# 3. Restart ibus-daemon with correct env
pkill -f 'ibus-daemon' && sleep 1
GTK_IM_MODULE=ibus QT_IM_MODULE=ibus XMODIFIERS=@im=ibus \
    ibus-daemon --xim --replace --daemonize
# 4. Restart every GTK client (Chrome, terminal, editor) so they re-read env
```

**When the terminal IS the problem (the 10% case)**:
- **Ptyxis 50.1 + GNOME Shell 50.1 + ibus 1.5.34rc2** on Wayland — `zwp_text_input_v3` preedit handshake is flaky. Symptom is the same (`n i` types `ni`), but `GTK_IM_MODULE=ibus` in both shell and daemon env, and Chinese works fine in `gnome-text-editor`. Confirmed on multiple machines, tracked at https://gitlab.gnome.org/GNOME/ptyxis/-/issues/101 .
- **Ubuntu 26.04's ibus 1.5.34rc2 package doesn't ship `ibus-ui-gtk4`** — only `ibus-ui-gtk3` and `ibus-ui-emojier`. For GTK4 clients (gnome-terminal 3.58, Ptyxis 50.1, recent Firefox/Chrome popups) the preedit text goes through but the candidate-window GUI doesn't render. Symptom: typing produces the right pinyin but the candidate overlay never appears. Workarounds: (a) install a GNOME Shell extension that adds a candidate panel to the top bar, (b) switch to fcitx5 which has its own `fcitx5-frontend-gtk4` in the repo, (c) wait for ibus 1.5.34 final which should add GTK4 panel support.

**Coexistence fix when the terminal itself is the problem** (the 10% case where step 0 above passes and Chinese works in non-terminal apps but not in the terminal):
```bash
sudo apt install -y gnome-terminal gnome-terminal-data
which gnome-terminal && gnome-terminal --version
# Ptyxis stays the default; gnome-terminal appears in the app menu.
# Use gnome-terminal for Chinese input until upstream fixes the v3 protocol.
```

Why coexistence wins: (a) one `apt install` of ~12 MB, (b) doesn't change `update-alternatives` for `x-terminal-emulator`, (c) doesn't break Ptyxis's other features, (d) gives the user a known-good Chinese-input terminal as a fallback. This matches the user's additive-not-replace preference.

**Other Wayland terminals known to work with ibus**: foot (wlroots text-input v3, fine since 1.17), kitty (native, fine), wezterm (native, fine), alacritty (native, fine since 0.13). If user has flexibility, switching to one of these is also a valid fix.

**Symptom signatures for fast triage in future sessions**:
- "中文打不出来 / 按 n i 出 ni / 完全没有候选词" in any app, AND shell env has `GTK_IM_MODULE=fcitx` with no fcitx running → P2 (silent fall-through), fix the IM_MODULE and restart daemon
- Same symptom, but `GTK_IM_MODULE=ibus` everywhere AND Chinese works in `gnome-text-editor` → terminal-specific, suspect P25 second-cause
- `ibus list-engine` returns empty even after `apt install ibus-pinyin` → daemon cache, restart with `ibus-daemon -drxR` (P1)