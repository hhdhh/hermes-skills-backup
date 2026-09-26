---
name: github-release-asset-download
description: Fetch GitHub release assets via a proxy chain.
version: 1
author: hermes-agent
license: MIT
metadata:
  hermes:
    tags: [github, release, download, proxy, mirror, codeload, ghfast]
    related_skills: [blocked-page-recovery, linux-desktop-system-config]
---

# GitHub release asset download

Download GitHub release assets (tarballs, zipballs, individual binaries) when the direct path is slow, blocked, or interrupted. The pattern emerged from a real session where multiple repos had to be downloaded from behind a Chinese-network proxy, with no `git clone` access and no working `raw.githubusercontent.com`.

## When to use

- Direct `curl https://codeload.github.com/...` or `curl https://github.com/.../archive/...` connects but stalls/times out mid-transfer
- `git clone` is unavailable or too slow
- `raw.githubusercontent.com` returns "Connection reset" (common behind aggressive proxies)
- You're downloading a release tag, not the default branch, and don't know if the repo uses `main` or `master` as default

## The download ladder

```bash
# 1. Try ghfast.top proxy on the codeload URL (highest success rate)
URL="https://ghfast.top/https://github.com/<owner>/<repo>/archive/refs/tags/<TAG>.tar.gz"
curl -sSL --max-time 180 "$URL" -o artifact.tar.gz

# 2. Fall back to ghfast.top on the default branch
URL="https://ghfast.top/https://github.com/<owner>/<repo>/archive/refs/heads/<BRANCH>.tar.gz"
curl -sSL --max-time 180 "$URL" -o artifact.tar.gz

# 3. Fall back to a direct tarball (will time out ~600s for big repos)
URL="https://codeload.github.com/<owner>/<repo>/tar.gz/refs/tags/<TAG>"
curl -sSL --max-time 600 "$URL" -o artifact.tar.gz

# 4. Last resort: API discovery + per-asset download
curl -sL "https://api.github.com/repos/<owner>/<repo>/releases/tags/<TAG>" \
  | grep browser_download_url
```

For branch-disambiguation (does this repo use `main` or `master`?):

```bash
curl -sL --max-time 15 "https://api.github.com/repos/<owner>/<repo>" \
  | grep '"default_branch"'
```

## Detect "fake success" responses

These patterns look like success but are silently empty:

| Response | What it actually means | How to detect |
|---|---|---|
| `ghfast` returns 9-byte body with `Not Found` | Repo or branch doesn't exist (HTTP 404 rewritten) | `wc -c < file` < 100 AND `file file` shows `ASCII text` |
| Raw returns 14-byte body with `404: Not Found` | Wrong branch/path/filename | `file file` shows `ASCII text` |
| `codeload` aborts at 600s with partial bytes | Connection throttled, file actually exists | compare expected size vs `wc -c` |
| Tarball unzips to only `LICENSE` and `README.md` | Repo exists but no tracked files at that ref | `find extracted -type f | wc -l` |

Always validate after download:

```bash
# Did we get a real tarball?
file artifact.tar.gz                                        # expect "gzip compressed data"
# How many files inside?
tar tzf artifact.tar.gz | wc -l                             # expect > 0
# Quick sanity check on a known file
tar tzf artifact.tar.gz | grep -i "install.sh\|metadata.json" | head -3
```

If `file` reports `ASCII text` or `file` reports a wrong type, the download is bad — re-run with the next ladder rung.

## Detect repo renames / deletions

GitHub repos get renamed or deleted all the time. The 404 from ghfast is often a "this repo name doesn't exist anymore" 404, not a network problem. To confirm:

```bash
# Does the repo exist at all?
curl -sL --max-time 15 "https://api.github.com/repos/<owner>/<repo>" | head -20
# If response starts with {"message": "Not Found", ... → repo is gone, find a different name

# User-facing name guess: list the author's other repos
curl -sL --max-time 15 "https://api.github.com/users/<owner>/repos?per_page=100" \
  | grep '"name"' | head -30
```

Worked example: `vinceliuice/WhiteSur-cursor-theme` was renamed to `WhiteSur-cursors` (plural). The 404 from any URL containing the original name is correct — the new name is the one to use.

## Why codeload / raw often don't work through a proxy

`codeload.github.com` and `raw.githubusercontent.com` are aggressive-cache servers that don't always negotiate with CDNs. Through a reverse proxy (ghfast, ghproxy, etc.) the connection may:

- Stall mid-stream on large files (no chunked-transfer resume)
- Reset cleanly after 600s without delivering all bytes
- Return a 200 with a 9-byte body when the upstream returned 404 (cached response)

The `ghfast.top/<full-original-url>` pattern explicitly preserves the original URL in the path, so the proxy can look up the correct upstream. It's the highest-success-rate relay for `codeload` fetches.

## Common pitfalls

### P1: branch name guessing
Many repos use `main` (e.g. `aunetx/blur-my-shell`), but others still use `master` (e.g. `vinceliuice/WhiteSur-*`, `epk/SF-Mono-Nerd-Font`). Always discover with the API before trying a branch URL.

### P2: tag vs head
- `archive/refs/tags/<TAG>` for a specific release tag
- `archive/refs/heads/<BRANCH>` for the default branch
- `archive/refs/heads/<BRANCH>/sub/path` for a path inside a branch (only works for tarball, not git clone)

Sub-directory archive downloads via tarball are supported by GitHub. Use them when you only need a sub-folder of a large repo:
```bash
curl -sSL "...archive/refs/heads/main.tar.gz" \
  | tar xzf - "<repo>-main/<sub-path>/"
```

### P3: `-L` is mandatory
`ghfast.top` redirects to the actual download. Without `-L`, you get the redirect body, not the file. Always `curl -sSL`.

### P4: `wc -c` validation
GitHub returns 9-byte "Not Found" stubs through ghfast (see Detect table). Anything under 100 bytes that's a tarball/zip is a proxy error, not a real file. Always check byte count + `file` type before extracting.

### P5: API rate limits
Anonymous API requests have 60 requests/hour. If you're checking 20 repos, that's already a third of your budget. Cache the `default_branch` lookup result if you need to fetch multiple branches from the same repo.

### P6: assets with `+` or special chars in the URL
`aunetx/blur-my-shell` releases use `blur-my-shell%40aunetx.shell-extension.zip` (URL-encoded `@`). Both `%40` and raw `@` are accepted by GitHub, but the encoded form is what's in the API. Use the URL the API gives you verbatim.

### P7: tag's "Source code" assets may not be at the expected path
GitHub auto-generates `Source code (zip)` and `Source code (tar.gz)` for every release, but only on the release page. The `api.github.com/repos/{owner}/{repo}/releases/tags/{tag}` endpoint returns them under `browser_download_url`. Prefer `archive/refs/tags/{tag}.{ext}` URLs instead — they're direct and don't require the API at all.

## Linux desktop package workflow

When installing a desktop application's official GitHub release on Debian/Ubuntu, prefer the architecture-matched `.deb` over AppImage when the user wants normal application-menu integration. Do not guess the version or asset name: query the repository's `releases/latest` API, select the exact asset, and preserve the upstream filename.

Discovery and selection pattern:

```bash
REPO='owner/repo'
ARCH=$(dpkg --print-architecture)       # amd64 or arm64
VERSION=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"])')
# Inspect all assets, then select the asset whose name matches the native Debian arch.
curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print("\\n".join(a["name"]+"\\t"+a["browser_download_url"]+"\\t"+str(a["size"]) for a in d["assets"]))'
```

For projects that use `x64` in the filename while Debian reports `amd64`, map deliberately (`amd64 -> x64`, `arm64 -> arm64`) instead of substituting strings blindly. Before installation, validate the download with `file`, byte size, and `dpkg-deb --info`; a successful HTTP response alone is not sufficient.

If sudo cannot be authenticated in the agent's non-interactive terminal, download and validate the package now, then hand off one self-contained executable script that runs `sudo -v`, installs with `sudo apt-get install -y <local.deb>`, and verifies the package, executable, and `.desktop` entry. This avoids asking the user to repeat several commands and avoids password guessing or `sudo -S`.

A good handoff script uses `set -euo pipefail`, checks that the expected local artifact exists, prints the exact stopping step, and verifies the installed package with `dpkg-query` plus the paths that matter for launch/menu integration. Do not claim the application is installed until the user-side script has actually run; distinguish “downloaded and ready” from “installed”.

## Reference recipes

- `references/session-example.md` — full transcript of downloading 5 GitHub repos in one session (WhiteSur theme/icon/cursor, SF Pro/Mono fonts, Blur My Shell, WhiteSur wallpapers) through this exact ladder. Includes the detection sequence that found the renamed `WhiteSur-cursors` repo.
