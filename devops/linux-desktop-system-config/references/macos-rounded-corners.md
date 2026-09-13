# macOS-style rounded corners + vibrancy panel — addendum

This is the "this looks like macOS now" change beyond the theme itself. The toolkit (GTK4 themes, libadwaita apps, the GNOME Shell panel, the dock) all need **explicit** corner radii — they do not inherit from the theme name.

## The corner-number cheat sheet

Big Sur / Ventura-ish. Apply with `dconf write` (or `gsettings set` for keys that accept it):

| Surface | Radius |
|---|---|
| App window | 12 px |
| Top panel | 12 px |
| Bottom dock | 22 px |
| Plank | 23 px (theme file) |
| GTK 4 widget | 8 px (buttons/entries) / 12 px (windows) |

## The recipe

```bash
# Blur My Shell — pin corner radii (defaults are 0/18/30, which read as Windows)
dconf write /org/gnome/shell/extensions/blur-my-shell/panel/corner-radius 12
dconf write /org/gnome/shell/extensions/blur-my-shell/dash-to-dock/corner-radius 22
dconf write /org/gnome/shell/extensions/blur-my-shell/applications/corner-radius 12
dconf write /org/gnome/shell/extensions/blur-my-shell/applications/corner-when-maximized true

# Plank: edit its theme file directly. TopRoundness + BottomRoundness are integers 0-30+;
# 23 matches Big Sur. Also loosen the alpha for vibrancy (default 175/200 is too opaque).
sed -i 's/FillStartColor=25;;25;;25;;175/FillStartColor=25;;25;;25;;135/' \
  ~/.local/share/plank/themes/WhiteSur-Dark/dock.theme
sed -i 's/FillEndColor=25;;25;;25;;200/FillEndColor=25;;25;;25;;160/' \
  ~/.local/share/plank/themes/WhiteSur-Dark/dock.theme

# Dash-to-Dock: opt out of squared corners (the key `force-straight-corner` defaults true)
gsettings set org.gnome.shell.extensions.dash-to-dock force-straight-corner false
gsettings set org.gnome.shell.extensions.dash-to-dock background-color '#222226'
gsettings set org.gnome.shell.extensions.dash-to-dock custom-background-color true
gsettings set org.gnome.shell.extensions.dash-to-dock background-opacity 0.65

# GTK 4 (libadwaita) app radius: write a CSS override and import it
mkdir -p ~/.config/gtk-4.0
cat > ~/.config/gtk-4.0/gtk-overrides.css <<'EOF'
* { border-radius: 12px; }
window { border-radius: 12px; }
button, .button, entry, .entry, combobox, .dropdown { border-radius: 8px; }
headerbar, .titlebar {
  border-top-left-radius: 12px;
  border-top-right-radius: 12px;
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
}
EOF
# Append the @import to BOTH the dark and light theme files (whichever is active
# depends on color-scheme)
for f in gtk-Dark.css gtk-Light.css; do
  grep -q 'gtk-overrides.css' ~/.config/gtk-4.0/$f || \
    printf '\n/* macOS style corners */\n@import url("gtk-overrides.css");\n' >> ~/.config/gtk-4.0/$f
done

# macOS-style transparent / vibrancy top panel — `force-light-text` makes the
# clock and battery icon white on blurry backgrounds
dconf write /org/gnome/shell/extensions/blur-my-shell/panel/color "(0.0, 0.0, 0.0, 0.0)"
dconf write /org/gnome/shell/extensions/blur-my-shell/panel/override-background true
dconf write /org/gnome/shell/extensions/blur-my-shell/panel/override-background-dynamically true
dconf write /org/gnome/shell/extensions/blur-my-shell/panel/force-light-text true
dconf write /org/gnome/shell/extensions/blur-my-shell/panel/unblur-in-overview false
dconf write /org/gnome/shell/extensions/blur-my-shell/panel/style-panel 0
dconf write /org/gnome/shell/extensions/blur-my-shell/panel/sigma 22

# Apply blur to all application windows (not just the panel) — this is the
# "frosted glass around the active window" effect
dconf write /org/gnome/shell/extensions/blur-my-shell/applications/blur true
dconf write /org/gnome/shell/extensions/blur-my-shell/applications/static-blur true
dconf write /org/gnome/shell/extensions/blur-my-shell/applications/enable-all true
dconf write /org/gnome/shell/extensions/blur-my-shell/applications/sigma 22
dconf write /org/gnome/shell/extensions/blur-my-shell/applications/opacity 215
dconf write /org/gnome/shell/extensions/blur-my-shell/applications/customize true
```

## Why each piece matters

**`force-straight-corner=false`**: dash-to-dock is *literally* a rectangle by default — even with the theme applied, the dock stays squared. `force-straight-corner=false` lets the dock respect the Blur My Shell corner radius. The same wedge applies to native whiteboards and Nautilus — the comprehensive workaround is the GTK 4 override in `gtk-overrides.css`.

**`override-background-dynamic=true`**: this is the difference between a flat blur and a real vibrancy effect — the panel background fades to the wallpaper color *gradually* as you scrub through windows, instead of staying uniformly gray.

**`enable-all=true` for applications**: this is the difference between "the panel is frosted" and "every window gets a frosted glass effect when you swap them". Without it, only the GNOME Shell panel blurs — application windows stay opaque.

**The GTK 4 override path**: the `~/.config/gtk-4.0/gtk-Dark.css` and `gtk-Light.css` files are *regenerated* by WhiteSur's install.sh. Re-running the install will wipe your `@import` line — re-apply it after.

## Key facts that change under your feet

- **GNOME 50 menu-bar**: `org.gnome.shell.enable-appmenu` no longer exists in GNOME 50. App-menu support is automatic for libadwaita apps — there is no gsettings key to toggle. Don't waste time hunting for it.
- **Ptyxis `cursor-shape` enum**: `block` / `ibeam` / `underline` (not `bar/ibeam/underline`). macOS bar is `ibeam` here.
- **Ulauncher autostart**: use `Exec=ulauncher --hide-window`. Plain `Exec=ulauncher` shows the window on every login.
- **Ptyxis has no corner-radius gsettings** — it's a flat rectangle by design. The mac look comes from the dark palette + transparent opacity, not corners.
- **GDM login screen corners**: covered by `WhiteSur-gtk-theme/other/gdm/install.sh` (requires sudo). Without it, the login screen is stock Ubuntu orange against the macOS desktop — jarring.

## Persistence reminder

After running `sudo apt install` (and especially after a re-login), several gsettings can reset. The `persist.sh` pattern in the main macOS-theming reference recipe documents the workaround — rerun it after any blast-radius-changing system event.
