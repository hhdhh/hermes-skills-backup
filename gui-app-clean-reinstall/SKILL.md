---
name: gui-app-clean-reinstall
description: Use when user asks to "reset" / "reinstall" / "重置" a desk...
version: 1
---

# GUI App Clean Reinstall

> 完整描述：Use when user asks to "reset" / "reinstall" / "重置" a desktop GUI app and clearing settings.json alone won't work. Covers the gap between dpkg/apt uninstall and actual state cleanup for Electron-style apps. Trigger on: vscode/code settings still not reset, extension config persists, app remembers old data after reinstall, "还是不行" after uninstall.

## Core rule (read first)

For Electron-style GUI apps on Linux, **uninstalling the package does NOT remove user state.** The package manager (`dpkg -P`, `apt remove`) deletes binaries and `/etc` configs; user data lives under the home directory and survives. Resetting the app requires deleting both layers.

If the user says "重置设置" / "settings still not reset" / "还是没清干净" → the problem is almost certainly leftover user state, not the package.

## Two-layer state model

| Layer | Path | What lives there |
|---|---|---|
| System | `/usr/share/<app>/`, `/usr/bin/<app>`, `/etc/<app>/` | Binary, system-wide configs |
| User | `~/.config/<app>/`, `~/.cache/<app>/`, dotdirs like `~/.<app>/` | Per-user settings, extension state, caches, login sessions, IndexedDB, state.vscdb |

After `dpkg -P <app>`: layer 1 is gone. Layer 2 is untouched. Next launch rebuilds layer 1, **layer 2 persists**, and the app "remembers everything."

## Procedure (Linux GUI app)

```
1. BACKUP user state first (you'll regret it otherwise)
     cp -r ~/.config/<app> ~/backup-<app>-<date>/
     cp -r ~/.cache/<app> ~/backup-<app>-<date>/cache/  2>/dev/null
     # Capture install state for selective restore:
     <app> --list-extensions  > ~/backup-<app>-<date>/extensions.txt   2>/dev/null
     <app> --list-extensions --show-versions  >> ~/backup-<app>-<date>/extensions.txt  2>/dev/null

2. CLOSE the app completely (multiple renderer/gpu processes)
     pkill -x <app-bin>
     sleep 3
     pgrep -x <app-bin> && echo STILL_RUNNING || echo closed

3. UNINSTALL the package (purge, not remove — remove leaves /etc configs)
     sudo dpkg -P <pkg>      # Debian/Ubuntu, fully purges
     # or:  sudo apt purge -y <pkg>
     # Verify: dpkg -l <pkg>  →  "no packages found"

4. SCRUB user state dirs (THIS is the missing step)
     rm -rf ~/.config/<app>  ~/.cache/<app>  ~/.local/share/<app>
     # For VS Code specifically: ~/.config/Code  AND  ~/.vscode  (extensions live there)
     # For Slack/Discord: ~/.config/Slack  ~/.config/discord  ~/.cache/...

5. REINSTALL the package (from .deb / .rpm / official repo)

6. RESTORE selectively — never blindly copy the old config back
     <app> --install-extension $(cat ~/backup-<app>-<date>/extensions.txt | grep -v '^#')   2>&1 | tail -20
     # Settings/UI prefs: copy only what user explicitly asks for. Login tokens: do NOT restore.
```

## Pitfalls

- **`apt remove` ≠ `dpkg -P`.** `remove` deletes binaries but keeps `/etc` configs. Use `dpkg -P` (or `apt purge`) when you want a true wipe.
- **The app auto-rebuilds state dirs on first launch.** After step 4, the directory may reappear empty as soon as the binary starts — that's expected, not a failure. Verify by listing contents, not by checking existence.
- **Default XDG paths aren't universal.** Electron apps often use `~/.config/<lowercase-bin>` (VS Code → `Code`) while native apps use `~/.config/<app>` (Slack → `Slack`). `find ~ -maxdepth 3 -name '<app>*' -type d` if unsure.
- **Multiple processes masquerade as one.** Electron apps spawn main + renderer + gpu + utility + zygote processes. `pgrep -x <bin>` may match the parent while children linger. Use `pkill -f '/usr/share/<app>/<bin>'` for the whole tree.
- **Reinstalling the SAME package version with dpkg** without first purging can fail with "already installed." Purge first, then install.
- **External installs (AppImage / .tar.gz) have no package manager.** Skip the uninstall step entirely; the user state dirs are the only state. Just close → scrub → relaunch from the same binary.
- **Don't restore `globalStorage` blindly.** It contains each extension's local config and login tokens. The user said "重置" — they don't want the old state back. Restore only what they name (extensions list, snippets, keybindings); leave `globalStorage` empty until they ask.
- **First launch after a true reset always rebuilds `settings.json` with `{}` plus a fresh `chatLanguageModels.json` / `CachedData/` etc.** Don't flag those as "still has settings" — they're VS Code's first-run bootstrap files, not user config.

## Decision: did the reset actually take?

```bash
# After step 5 + first launch:
<app-bin> --version                                   # confirms new install
ls -A ~/.config/<app>/User 2>/dev/null                # should show only bootstrap files
cat ~/.config/<app>/User/settings.json 2>/dev/null    # should be {} or near-empty
```

If `settings.json` still has content after a clean reinstall + scrub → some other config layer survived (check `globalStorage/`, `CachedData/`, `workspaceStorage/`). The procedure in this skill is the *complete* answer; if it didn't work, something was missed in step 4.

## Cross-platform paths (for reference)

| App | Linux | macOS | Windows |
|---|---|---|---|
| VS Code | `~/.config/Code` + `~/.vscode` | `~/Library/Application Support/Code` + `~/.vscode` | `%APPDATA%\Code` + `%USERPROFILE%\.vscode` |
| Slack | `~/.config/Slack` | `~/Library/Application Support/Slack` | `%APPDATA%\Slack` |
| Discord | `~/.config/discord` + `~/.cache/discord` | `~/Library/Application Support/discord` | `%APPDATA%\discord` |
| Notion | `~/.config/Notion` | `~/Library/Application Support/Notion` | `%APPDATA%\Notion` |

For macOS/Windows, the package manager is different (brew / `osascript` / `Add/Remove Programs`) but the user-state scrub is identical.

## When NOT to use this skill

- The user just wants to change one setting, not reset everything → read `settings.json`, edit, done.
- The user wants to reset *a single extension's* config → clear `~/.config/<app>/User/globalStorage/<ext-id>/`, not the whole app.
- The app is system-managed (snap, flatpak) → user state lives in `~/snap/<app>/` or `~/.var/app/<app>/`, not the standard XDG paths.
