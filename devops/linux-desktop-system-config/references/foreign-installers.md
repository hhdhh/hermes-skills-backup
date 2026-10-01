# Foreign and suspicious desktop installers

Use this when a user asks to install a downloaded artifact whose extension may not match its contents or the host OS.

## 1. Validate the artifact before choosing an install path

Check all three independently:

```bash
uname -m
file -- /absolute/path/to/installer
du -h -- /absolute/path/to/installer
```

For a suspiciously small text file, read it as text. A filename ending in `.dmg` or `.exe` is not proof of format. Download portals sometimes save an error response or placeholder message under the requested installer name.

Expected signatures:

- macOS DMG: `Apple Disk Image` or a recognizable UDIF/disk-image signature
- Windows installer: PE executable (`PE32`/`PE32+`), often NSIS/Inno/MSI metadata
- Debian package: `Debian binary package`
- AppImage: ELF executable plus AppImage metadata

Preserve the original artifact until diagnosis is complete. Download a corrected artifact to a distinct, descriptive filename rather than overwriting evidence silently.

## 2. Establish official platform support

Use the vendor's official product/download page as the primary source. Record exactly which operating systems and architectures it names. Do not infer a Linux build from generic phrases such as “desktop version.”

Decision order:

1. Native official package for the current OS and architecture
2. Official browser/web version
3. Official Windows package under Wine/Bottles, only as an explicitly experimental compatibility route
4. Virtual machine or a native alternative when compatibility is unreliable

Avoid third-party “activated,” repacked, or cracked builds. If an official download URL is embedded in the vendor page, verify the final file type and calculate a checksum after download:

```bash
file -- /path/to/download
sha256sum -- /path/to/download
```

A checksum proves file identity for later comparison; it does not prove publisher authenticity unless the vendor publishes a matching checksum or signature.

## 3. Treat Wine as a compatibility project, not a native install

Before proposing Wine, inspect:

- host architecture and distro version
- GPU and active driver
- available disk/RAM
- installed Wine/Bottles/Flatpak components
- whether the application depends on hardware video acceleration, DRM, kernel drivers, anti-cheat, or proprietary login/webview components

Use an application-specific Wine prefix so experiments do not damage the user's default prefix:

```bash
export WINEPREFIX="$HOME/.local/share/wineprefixes/<app>"
export WINEARCH=win64
mkdir -p "$WINEPREFIX"
wineboot -u
```

Do not claim a current vendor release works under Wine merely because an older community report exists. Version, Wine build, desktop protocol, GPU driver, and codecs materially affect results.

## 4. Sudo handoff and GUI installers

If `sudo -n true` fails, produce one self-contained script in `/tmp`, following the parent skill's driver pattern. The script should:

1. validate the downloaded file again
2. acquire authorization once (`sudo -v` in a user terminal; a GUI `pkexec` path may be offered only if tested in that session)
3. install required compatibility packages
4. create a dedicated prefix
5. launch the real installer
6. locate the installed executable
7. create a user launcher only after locating it
8. launch and verify the actual application process/window

Keep interactive installer cancellation distinguishable from dependency failure, and print the log path on failure.

## 5. Completion standard

These are separate milestones; report them separately:

- **Found:** official source and supported platforms confirmed
- **Downloaded:** artifact exists and its real format/checksum were verified
- **Runtime prepared:** compatibility dependencies and isolated prefix exist
- **Installed:** target executable was found after the installer exited
- **Working:** application launched and remained alive long enough for a meaningful smoke test; ideally confirm its window or usable UI

Never call the task installed when only the installer was downloaded or when a handoff script is waiting for the user's password/UI confirmation. If the interactive step remains, state the exact blocker and give one invocation, but leave the task status incomplete.

## Case note: 2019-era `.deb` on Ubuntu 26.04 — vendored-lib shadowing fix (verified 2026-09-27)

NetEase Cloud Music 1.2.1 (last Linux build, 2019) failed to start on Ubuntu 26.04: its wrapper prepends `libs/` to `LD_LIBRARY_PATH`, and vendored 2019 `libmount.so.1`/`libselinux.so.1` shadowed system versions — system `libgio` needs `MOUNT_2_40`, loader aborts. Chasing single libs (LD_PRELOAD) just moved the failure down a chain (glib → pango).

Root fix (no sudo, all user-space, reversible):
1. `mkdir ~/ncm-libs`; symlink every `libs/*.so*` + `libs/qcef/libcef.so` into it.
2. Delete symlinks whose name ALSO exists in `/usr/lib/x86_64-linux-gnu/` — **except `libQt5*`/`libqcef*`/`libcef*`**: mixed Qt versions abort with `Cannot mix incompatible Qt library (5.9.5) with (5.15.18)`; mixed system-stack libs abort with missing symbol versions. Keep vendored Qt whole, let everything else resolve to system.
3. Write `~/.local/bin/netease-cloud-music` wrapper: `LD_LIBRARY_PATH=~/ncm-libs` + vendored `QT_PLUGIN_PATH`/`QT_QPA_PLATFORM_PLUGIN_PATH`, `exec` real binary.
4. Copy system `.desktop` to `~/.local/share/applications/`, rewrite `Exec=` to the wrapper.
5. Verify from a clean process table: `ps -C netease-cloud-music` alive ≥10 s, `xwininfo -root -tree | grep` shows the window, zero fatal lines in log.

Pitfalls hit: CDN `d1.music.126.net` — plain HTTPS curl = 403 (need `Referer: https://music.163.com/` + browser UA + any `NMTID` cookie from a prior music.163.com request); plain HTTP works but throttled to ~250 B/s. Also `pkill -x` silently fails on >15-char process names — use `pkill -f 'name[c]'` bracket trick or kill PIDs.

## Case note: misleading `.dmg` from a platform-mismatched portal

A nominal `.dmg` on an Ubuntu x86_64 host was only 33 bytes of UTF-8 text saying no valid download was available for the current system. The durable lesson is to inspect content and official platform support before mounting, converting, or installing. The vendor's desktop documentation listed Windows and macOS, not Linux. An official Windows bootstrap installer could be downloaded and verified as PE/NSIS, but Wine installation remained unverified because administrator authorization and interactive installer confirmation had not occurred. Therefore only the download—not installation—was complete.