---
name: hermes-studio-desktop-deploy
description: Use when installing/upgrading Hermes Studio desktop (Ekko...
---


# Hermes Studio (Ekko Studio) Linux desktop deploy

> 完整描述：Use when installing/upgrading Hermes Studio desktop (Ekko Studio) on Linux.

Desktop app + bundled web runtime for Hermes Agent. Official site https://hermes-studio.ai/#download; GitHub `EKKOLearnAI/hermes-studio`. Binaries and window titles still say **Ekko Studio** — search windows/processes by that name, not "Hermes Studio". The npm-installed `hermes-web-ui` is a separate deployment on port 8648; the desktop build's runtime listens on **8748** — they coexist.

## Download (CN network)
1. Official Cloudflare mirror, no proxy needed: `https://download.ekkolearnai.com/<tag>/Ekko.Studio-<tag-no-v>-x86_64.AppImage` (since v0.7.24 assets use the `Ekko.Studio-<tag-no-v>-` prefix, older tags used `Hermes.Studio-<tag>-`; also .deb / .exe / .dmg). Discover the current tag via `curl -sL https://api.github.com/repos/EKKOLearnAI/hermes-studio/releases/latest`.
2. ghfast proxy fallback: `https://ghfast.top/https://github.com/EKKOLearnAI/hermes-studio/releases/download/<tag>/<asset>` (~2 min for 218 MB).

Validate: `file` must report `ELF 64-bit LSB executable` for an AppImage — ASCII text means a proxy error page. Official-site download links are JS-rendered: curl of the page HTML contains no asset URLs, so read them via a browser (`Array.from(document.querySelectorAll('a')).map(a=>a.href)`), not grep. If the CF mirror stalls at tens-of-KB/s, resume with `curl -C -` and pick the fastest channel by a 6s sample (CF vs ghfast.top vs local proxy) — speeds can differ 30x.

## Install (no-sudo path)
Ubuntu 26.04 ships no libfuse2 → AppImage won't run in place. Extract instead: `chmod +x <appimage> && ./<appimage> --appimage-extract` → run `squashfs-root/AppRun`. The .deb route also works without a password hand-off when a desktop session is live: export the session env (below) and run `pkexec dpkg -i pkg.deb` — polkit pops a GUI password dialog on the user's screen.

## Launch (Electron on GNOME Wayland from an agent shell)
Needs the full session env incl. the dynamic mutter XAUTHORITY (the auth file suffix changes every login — always re-derive from gnome-shell's environ, never hardcode):
```bash
export DISPLAY=:0 XDG_RUNTIME_DIR=/run/user/$(id -u)
export XAUTHORITY=$(tr '\0' '\n' < /proc/$(pgrep -n gnome-shell)/environ | grep '^XAUTHORITY=' | cut -d= -f2-)
export XDG_SESSION_TYPE=wayland DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus
~/Applications/squashfs-root/AppRun --no-sandbox --ozone-platform=x11
```
Wrap this in `~/Applications/start-hermes-studio.sh` (dynamic XAUTHORITY survives re-login) plus `~/.local/share/applications/hermes-studio.desktop` with `StartupWMClass=Ekko Studio` and a single main Category (multiple main categories = desktop-file-validate warning, duplicate menu entries).

## Verify
- `ss -tln | grep 8748` listening; `curl -o /dev/null -w '%{http_code}' localhost:8748` → 200
- `wmctrl -l` shows an "Ekko Studio" window
- Browser to localhost:8748: first login is **admin/123456**; the session list rendering after login = end-to-end OK
- No desktop screenshot tools on stock Ubuntu (no gnome-screenshot/scrot/import) — verify UI through the browser against the local port instead of screenshots.

## Pitfalls
- The runtime binds **0.0.0.0:8748** — LAN-visible with default credentials. Change the password immediately after install, especially on shared/site networks.
- `Missing X server` / `Authorization required` from a non-session shell = missing XAUTHORITY (above), not a broken install.
- Prefer `--ozone-platform=x11` under XWayland to avoid Electron Wayland rendering quirks.
- `dlopen(): error loading libfuse.so.2` = extraction path above; do not chase sudo to install libfuse2.

## Related
- `linux-desktop-system-config` (user-owned) holds the general AppImage/Wayland/pkexec patterns (P6/P22/P23) and VS Code factory-reset pitfalls (P26–P28) — read it for the class-level rules.
- `github-release-asset-download` (user-owned) holds the general GitHub proxy ladder.
