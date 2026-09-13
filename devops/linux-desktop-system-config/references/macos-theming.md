---

## Phase 8 — cross-reference

The single biggest "this looks like macOS now" change beyond the theme itself is **explicit corner radii + vibrancy panel**. The toolkit (GTK4 themes, libadwaita apps, the GNOME Shell panel, the dock) all need explicit corner radii — they do not inherit from the theme name.

**See `references/macos-rounded-corners.md` for the full recipe.** Key bits:

- App window / top panel: 12 px via `dconf` Blur My Shell
- Bottom dock: 22 px (also requires `force-straight-corner=false`)
- Plank: 23 px (theme file) + alpha 135/160 for vibrancy
- GTK 4 controls: `~/.config/gtk-4.0/gtk-overrides.css` + `@import` in `gtk-Dark.css` / `gtk-Light.css`
- `override-background-dynamically=true` for real vibrancy (not flat blur)
- `enable-all=true` for applications blur (every window gets frosted)
- gnome 50 dropped `enable-appmenu`; Ptyxis `cursor-shape` enum is `block/ibeam/underline`; Ulauncher autostart needs `--hide-window`; GDM login needs `WhiteSur-gtk-theme/other/gdm/install.sh` (sudo)

All values in a copy-pasteable recipe in `references/macos-rounded-corners.md`.
