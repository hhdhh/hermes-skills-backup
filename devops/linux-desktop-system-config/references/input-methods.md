# Input method install recipe — ibus on Ubuntu 26.04 GNOME Wayland

Worked example: 2026-08-14, user request "帮我安装一个好用的中文输入法".

## Environment

- Ubuntu 26.04 LTS (resolute), GNOME Wayland
- User `kk` (no passwordless sudo, no `SUDO_PASSWORD` env)
- ibus daemon already running (1.5.34); libpinyin engine already installed
- ibus-pinyin NOT installed (the missing piece)
- Prior session had installed then uninstalled fcitx5 — environment vars had been cleaned but it's still worth re-checking
- Locale `LANG=zh_CN.UTF-8` (correct)
- `im-config -m` → current = `custom` (= `ibus`), good

## Detection commands

```bash
dpkg -l 2>/dev/null | grep -iE "fcitx|ibus|pinyin|zhong"
which fcitx fcitx5 ibus
ls -la ~/.config/fcitx* ~/.config/ibus 2>/dev/null
grep -nE "fcitx|GTK_IM_MODULE|QT_IM_MODULE|XMODIFIERS|INPUT_METHOD|SDL_IM_MODULE" \
    ~/.bashrc ~/.profile /etc/environment 2>/dev/null
ls /etc/xdg/autostart/ | grep -iE "fcitx|ibus"
ls ~/.config/autostart/ 2>/dev/null
im-config -m
locale | grep -iE "lang|ctype"
```

## Engine selection (presented to user)

| Engine | Pros | Cons |
|---|---|---|
| `ibus-pinyin` | Ubuntu official, large dictionary, stable, full 双拼 support | Smart-suggest slightly weaker |
| `ibus-libpinyin` | Better sentence-level prediction, cloud suggestions | Newer, occasional edge bugs |
| `ibus-rime` | Powerful (雾凇, 八股文), highly customizable | High setup barrier, need to install a schema |
| `ibus-sunpinyin` | Good sentence input | Maintenance has slowed |

Default recommendation: **ibus-pinyin** for "开箱即用 + Ubuntu 官方默认 + 双拼支持".

## Install steps

```bash
# User runs (no passwordless sudo):
sudo apt install -y ibus-pinyin
```

Verify install:
```bash
which ibus-engine-pinyin
dpkg -l ibus-pinyin | tail -1
```

## Configuration

```bash
export DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/$(id -u)

# CRITICAL: restart ibus daemon so the newly installed engine is visible
ibus-daemon -drxR
sleep 2

# Confirm
ibus list-engine | grep -E "pinyin|libpinyin"

# Set GNOME input sources (libpinyin was already there from earlier)
gsettings set org.gnome.desktop.input-sources sources \
    "[('xkb', 'us'), ('ibus', 'libpinyin'), ('ibus', 'pinyin')]"

# MRU controls default-on-next-login; put the preferred engine first
gsettings set org.gnome.desktop.input-sources mru-sources \
    "[('ibus', 'pinyin'), ('ibus', 'libpinyin'), ('xkb', 'us')]"
```

## Verification checklist

1. `ibus list-engine` shows `pinyin - Pinyin` (not just `libpinyin`)
2. `gsettings get org.gnome.desktop.input-sources sources` returns the expected tuple list
3. Open a text editor and type `nihao` → Chinese characters appear
4. `Super+Space` toggles English ↔ Chinese
5. `ibus-setup` opens if user wants to switch 全拼/双拼 schemes

## Gotchas hit in this session

- `ibus list-engine` after `apt install` but **before** `ibus-daemon -drxR` does NOT show the new engine. The daemon caches its engine list. Always restart.
- Setting `preload-engines` is unnecessary on GNOME — the per-session `input-sources/sources` + `mru-sources` are what matter.
- `gsettings` requires `DISPLAY`, `WAYLAND_DISPLAY`, `XDG_RUNTIME_DIR` to be set if you're running from a non-GUI shell (e.g. a service terminal).

## Cleanup after switching away from fcitx5

```bash
# Remove fcitx env-var residue (the silent-breaker in QT/Wayland apps)
sed -i '/GTK_IM_MODULE=fcitx\|QT_IM_MODULE=fcitx\|XMODIFIERS=@im=fcitx\|INPUT_METHOD=fcitx\|SDL_IM_MODULE=fcitx/d' \
    ~/.bashrc ~/.profile /etc/environment 2>/dev/null
```

## The "ibus 健康但打不出中文" trap (2026-08-15 session, captured here for future reference)

User reported "还是不行" after the initial install. All surface checks passed:
- `ibus engine` → `pinyin` ✓
- `ibus list-engine | grep pinyin` → found ✓
- D-Bus `GetEnginesByNames` → responded ✓
- `gsettings ... sources` → `[('xkb','us'), ('ibus','pinyin')]` ✓
- `ibus-engine-pinyin` process running ✓
- `libpinyin` data files present ✓

**Actual root cause**: `cat /proc/$(pgrep ibus-daemon | head -1)/environ` showed
```
GTK_IM_MODULE=fcitx
QT_IM_MODULE=fcitx
XMODIFIERS=@im=fcitx
SDL_IM_MODULE=fcitx
```
The user's previous fcitx5 install had left these in the autostart context where ibus-daemon was launched, and the running ibus-daemon had inherited them. Every GTK client in the session saw `GTK_IM_MODULE=fcitx` → looked for fcitx5 socket → didn't find it (fcitx5 wasn't running) → **silently fell back to plain XKB with no error**. The user pressed `n i` and got `ni` typed into the terminal — no candidate window ever opened because the candidate window was never asked for.

**The lesson**: "ibus 守护进程在跑" is NOT the same as "ibus is receiving key events from clients". The two are decoupled via `GTK_IM_MODULE`. Always check BOTH:

1. **Daemon health**: `ibus engine`, `ibus list-engine`, D-Bus methods, engine process running
2. **Client routing**: what `GTK_IM_MODULE` do the GUI apps actually see? Check the daemon's own `/proc/$PID/environ` AND any shell rc / profile.d / autostart that could re-export it

**Fix** (also captured in `/tmp/fix-ibus-terminal-input.sh` from this session):
```bash
# 1. Find every place that re-exports the wrong value
sudo grep -rnE "GTK_IM_MODULE=|QT_IM_MODULE=|XMODIFIERS=" \
    /etc/ /usr/lib/ ~/.bashrc ~/.profile ~/.config/ 2>/dev/null
# 2. Remove the wrong lines, write the right ones
mkdir -p ~/.config/im-config
cat > ~/.config/im-config/ibus.env <<'EOF'
export GTK_IM_MODULE=ibus
export QT_IM_MODULE=ibus
export XMODIFIERS=@im=ibus
export SDL_IM_MODULE=ibus
EOF
# 3. Restart daemon with correct env
pkill -f 'ibus-daemon' && sleep 1
ibus-daemon --xim --replace --daemonize
# 4. Restart every GTK client (Chrome, terminals, editors) so they re-read env
```

**The secondary issue** (only hit after the IM_MODULE fix in this session): Ubuntu 26.04's `ibus 1.5.34rc2` package doesn't ship `ibus-ui-gtk4` — only `ibus-ui-gtk3` and `ibus-ui-emojier`. So GTK4 clients (gnome-terminal 3.58, Ptyxis 50.1) get the preedit text into the engine but the candidate window GUI doesn't render. The IME works, you just can't see the candidates. This is a separate, packaging-level issue — full discussion in SKILL.md P25 "second cause" section.

**Symptom triage table** (use this for any "can't type Chinese" report):
| Symptom | Likely cause | First check |
|---|---|---|
| Press `n i` types `ni` with no candidate UI | IM_MODULE wrong / daemon env wrong | `cat /proc/$(pgrep ibus-daemon | head -1)/environ` for IM_MODULE |
| Candidate UI shows but selecting doesn't insert | Terminal-specific protocol (Ptyxis 50.1 on Wayland) | Test in `gnome-text-editor` to isolate |
| ibus engine process not running at all | Engine not installed OR daemon not restarted | `apt list --installed \| grep ibus-pinyin` then `ibus-daemon -drxR` |
| `ibus list-engine` empty | Daemon hasn't been restarted since install | `ibus-daemon -drxR` (P1) |

## Runtime engine switching (same session, 2026-08-14)

User asked to flip between already-installed pinyin ↔ libpinyin. Confirmed: `gsettings set ... current` alone is not enough — the ibus daemon keeps its own state and needs `ibus engine <name>` to follow.

```bash
export DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/$(id -u)

# sources = [('xkb','us'), ('ibus','libpinyin'), ('ibus','pinyin')]
# index:        0              1                    2

# Switch to pinyin
gsettings set org.gnome.desktop.input-sources current 2
gsettings set org.gnome.desktop.input-sources mru-sources \
    "[('ibus','pinyin'), ('ibus','libpinyin'), ('xkb','us')]"
ibus engine pinyin
ibus engine   # → "pinyin" (source of truth)

# Switch back to libpinyin
gsettings set org.gnome.desktop.input-sources current 1
gsettings set org.gnome.desktop.input-sources mru-sources \
    "[('ibus','libpinyin'), ('ibus','pinyin'), ('xkb','us')]"
ibus engine libpinyin
```