# Session transcript: 5-repo GH release download via ghfast

Ubuntu 26.04 GNOME Wayland user wanted a macOS-style desktop. This required:

1. `vinceliuice/WhiteSur-gtk-theme` (master branch)
2. `vinceliuice/WhiteSur-icon-theme` (master)
3. `vinceliuice/WhiteSur-cursors` (master) — **renamed from `WhiteSur-cursor-theme`**
4. `sahibjotsaggu/San-Francisco-Pro-Fonts` (master)
5. `aunetx/blur-my-shell` v72 release zip (GNOME 50 compatible)
6. `supercomputra/SF-Mono-Font` (master) — needed later when fonts became an issue
7. `vinceliuice/WhiteSur-wallpapers` tag `2023-06-11`
8. `GNOME/gnome-shell-extensions` (main) — for User Themes extension

Network conditions: in mainland China, GitHub raw + codeload + git clone all either kicked back resets or stalled at 600s on tarballs. Direct `https://github.com/...` returned 200 with headers but body delivery stalled.

## Sequence that worked

```bash
# 1. Probe the proxies — pick the one that responds
for url in \
  "https://github.com" \
  "https://ghfast.top" \
  "https://gh-proxy.com" \
  "https://raw.githubusercontent.com"; do
  code=$(curl -sI -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null)
  echo "$url: $code"
done
# github.com: 200 (fast, but raw stall)
# ghfast.top: 200 (proxy works)
# gh-proxy.com: 200
# raw.githubusercontent.com: 301 (redirects, but stalls on actual fetch)

# 2. For each repo, discover the default branch first
curl -sL --max-time 15 "https://api.github.com/repos/vinceliuice/WhiteSur-gtk-theme" \
  | grep '"default_branch"'
# → master

# 3. Download via ghfast.top
curl -sSL --max-time 180 \
  "https://ghfast.top/https://github.com/vinceliuice/WhiteSur-gtk-theme/archive/refs/heads/master.tar.gz" \
  -o WhiteSur-gtk-theme.tar.gz

# 4. Validate: NOT 9 bytes, IS a real tarball
ls -lh WhiteSur-gtk-theme.tar.gz                    # 4.2M
tar xzf WhiteSur-gtk-theme.tar.gz
ls WhiteSur-gtk-theme-master/                       # contains install.sh, src/, etc.
```

The same loop ran for icon-theme (~8.1M, 69M uncompressed) and wallpapers (~26M).

## The 9-byte Not-Found trap

When the repo name was wrong, ghfast returned:

```bash
curl -sIL --max-time 30 "https://ghfast.top/https://github.com/vinceliuice/WhiteSur-cursor-theme/archive/refs/heads/main.tar.gz"
# HTTP/2 404
# content-length: 9       ← key indicator
# body: "Not Found"
```

That 9-byte body is the single most reliable signal that you have a wrong URL. The download still "succeeds" (HTTP 200 in the curl exit) so you'll silently end up with a 9-byte file if you don't validate:

```bash
[ "$(wc -c < file.tar.gz)" -lt 100 ] && echo "Bad download — likely 404 from proxy"
```

The fix was to discover the actual renamed repo via the author's other repos:

```bash
curl -sL --max-time 15 "https://api.github.com/users/vinceliuice/repos?per_page=100" \
  | grep '"name"' | grep -i "cursor"
# → "WhiteSur-cursors"   (note: plural!)
```

## Branch-name guessing trap

Branch names vary. Don't guess:

```bash
# epk/SF-Mono-Nerd-Font uses master (older repo)
curl -sL "https://api.github.com/repos/epk/SF-Mono-Nerd-Font" \
  | grep '"default_branch"'  # master

# aunetx/blur-my-shell uses main
curl -sL "https://api.github.com/repos/aunetx/blur-my-shell" \
  | grep '"default_branch"'  # main
```

Trying `main` on a `master` repo returns 9 bytes. Trying `master` on a `main` repo also returns 9 bytes. Always check explicitly.

## The "raw URL works for tarball but not for individual files" trap

For `supercomputra/SF-Mono-Font`, the per-file `raw.githubusercontent.com/.../SFMono-Regular.otf` URLs were rejected (connection reset). But the full tarball at `ghfast.top/.../archive/refs/heads/master.tar.gz` worked. If individual file fetches fail, switch to the tarball and extract only what you need:

```bash
curl -sSL "...archive/refs/heads/master.tar.gz" -o sfmono.tgz
tar xzf sfmono.tgz
cp SF-Mono-Font-master/SFMono-*.otf ~/.fonts/
fc-cache -fv ~/.fonts
```

## Release-zip vs tag-tarball

For `aunetx/blur-my-shell`, the release ZIP is the right choice (it's a packed extension, not a source tree):

```bash
# Check the latest release tag
curl -sL "https://api.github.com/repos/aunetx/blur-my-shell/releases/latest" \
  | grep tag_name
# → "v72"

# Download the prebuilt zip
curl -sSL --max-time 60 \
  "https://ghfast.top/https://github.com/aunetx/blur-my-shell/releases/download/v72/blur-my-shell%40aunetx.shell-extension.zip" \
  -o bms.zip

# 372K, real zip
file bms.zip
# Zip archive data, made by v2.0 UNIX
```

The URL-encoded `@` in the filename (`%40`) is what GitHub auto-generates. Both `%40` and raw `@` work.

## Files produced by this session

After all 8 repos were downloaded, the working directory was:

```
/tmp/mac-theme/
├── WhiteSur-gtk-theme-master/    (21M)  — install.sh runs apples-style
├── WhiteSur-icon-theme-master/   (69M)  — install.sh -> ~/.local/share/icons
├── WhiteSur-cursors-master/      (6.1M) — install.sh -> ~/.local/share/icons
├── WhiteSur-wallpapers-2023-06-11/ (26M) — 10 jpgs 4k
├── San-Francisco-Pro-Fonts-master/ (109M) — 65 .otf files
├── SF-Mono-Font-master/           (731K) — 12 .otf files
├── gnome-shell-extensions-main/   (321K) — for User Themes
└── blur-my-shell@aunetx.shell-extension.zip (372K) — final deployed to ~/.local/share/gnome-shell/extensions/
```

## Lessons for next session

1. **Always validate byte count** after `ghfast` download. 9 bytes = wrong URL, not network error.
2. **Always check `default_branch` via API** before guessing `main` vs `master`.
3. **Tarball over individual file** when individual fetches stall — extract what you need.
4. **Repo renames** are common. When "this repo doesn't exist" but you know the author, fetch `/users/<author>/repos` and grep.
5. **Tags stay even after rename** — `vinceliuice/WhiteSur-cursor-theme` → `WhiteSur-cursors` (the tag history migrated). The repo name in the URL is what changed.
