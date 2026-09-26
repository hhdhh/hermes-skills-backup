# Windows GUI installers through distro Wine

Use this for installer handoffs on Linux when the application has no native package and the user explicitly accepts a Wine compatibility path.

## Validate before installing

Extensions are not evidence of file type. A failed download endpoint can save a short text error under `.dmg` or `.exe`. Check all of:

```bash
stat -c '%s %n' /path/to/installer
file /path/to/installer
sha256sum /path/to/installer
```

Reject text/HTML/error placeholders. Also distinguish package compatibility up front: a real macOS `.dmg` is not a Linux installer and cannot be run by Wine; Wine needs a Windows PE executable.

## Debian/Ubuntu `wineserver` discovery

Some distro layouts expose `/usr/bin/wine` and `/usr/bin/wineboot` but keep the server at `/usr/lib/<multiarch>/wine/wineserver`, outside `PATH`. Resolve it after package installation:

```bash
WINESERVER="$(command -v wineserver || true)"
if [ -z "$WINESERVER" ]; then
    WINESERVER="$(dpkg -L wine64 2>/dev/null | grep '/wineserver$' | head -n 1 || true)"
fi
[ -x "$WINESERVER" ] || exit 1
export WINESERVER
```

The `export` is essential: calling the absolute path in the parent script fixes direct `wineserver -w` calls, but `winetricks` is a child process and otherwise repeats its own lookup and may report `wineserver not found!`.

## Tight verification probe

Before starting downloads or GUI installers, test the exact boundary:

```bash
WINESERVER=/resolved/path \
WINEPREFIX="$HOME/.local/share/wineprefixes/app" \
WINEARCH=win64 \
winetricks -q settings win10
```

Require exit 0. Warnings about Wine architecture or experimental WoW64 are not by themselves success or failure; trust the exit code and subsequent artifacts/process state.

## Script resilience

- Detect installed packages individually; do not infer that all dependencies are installed from one aggregate pipeline.
- Keep one app per `WINEPREFIX` so cleanup and retries do not affect other Wine applications.
- After launching a GUI installer, verify installation by locating the expected executable and then starting it. A running bootstrap/downloader process proves only that the bootstrapper opened, not that the application installed.
- Do not declare success from a window title alone. Require the installed executable, launcher, process, and—where available—an application log or responsive window.
