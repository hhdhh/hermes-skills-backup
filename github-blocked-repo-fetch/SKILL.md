---
name: github-blocked-repo-fetch
description: Use when a git clone of a github repo times out / gets cu...
---

# Fetch GitHub repo content when github.com is partially blocked

> 完整描述：Fetch GitHub repo content when github.com itself is blocked but api.github.com / raw.githubusercontent.com stay reachable. Probe which GitHub hosts respond, then pull a small repo's full file tree via the git/trees API and fetch each blob raw — no git clone, no proxy relay. Use when a git clone of a github repo times out / gets curl 000, when the user needs to 真读 a small github repo (技能 SKILL.md、配置、脚本套件) from behind a GFW-style firewall, or when web_extract fails to fetch a github page. Companion to github-release-asset-download (that covers big tarballs via proxy; this covers small repos with zero proxy).

A firewall does not block all GitHub hosts uniformly. `github.com` may be
firewalled (curl returns 000) while `api.github.com` stays up and
`raw.githubusercontent.com` still serves blobs. When that happens you can
read a small repo's full contents WITHOUT cloning and WITHOUT a proxy relay
— zero third-party dependency, ideal for analyzing someone's skill/config/script
repo in place.

## 0. Decide: this route vs the proxy ladder

| Situation | Route |
|---|---|
| Small repo (a SKILL.md, config, a few scripts) | **git/trees API + raw fetch** (this skill) |
| Large repo / release tarball / need full history | proxy ladder in `github-release-asset-download` |
| web_extract on a github URL returns empty | try this route before a browser |

## 1. Probe differential reachability FIRST — never assume a full block

```bash
for u in https://github.com https://api.github.com https://raw.githubusercontent.com https://codeload.github.com; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -m 8 "$u" 2>&1); echo "$u -> $code"; done
```

Interpretation:
- `github.com -> 000` (timeout) but `api.github.com -> 200` and
  `raw.githubusercontent.com -> 301` ⇒ use the API+raw route below, no clone.
- `raw` returns 301 with no `-L` — that's the CDN redirect, normal. Always `curl -sSL`.
- everything 000 ⇒ DNS/route-level block; fall back to the proxy ladder.

## 2. Confirm default branch, then enumerate the file tree in ONE call

```bash
# default branch (reuse this key across calls — it's per-repo and cached)
curl -s -m 15 "https://api.github.com/repos/<owner>/<repo>" \
  | grep -o '"default_branch": *"[^"]*"'

# whole tree in a single request — replaces N per-directory listings
curl -s -m 20 "https://api.github.com/repos/<owner>/<repo>/git/trees/<branch>?recursive=1" \
  | python3 -c 'import sys,json;[print(t["type"], t["path"]) for t in json.load(sys.stdin).get("tree",[])]'
```

## 3. Fetch each blob by its original relative path

```bash
curl -sSL -m 20 "https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>" -o "$path"
```

Clean small repos fetch fine one file at a time. Don't add `?ref=` — the branch already
carries it in the URL path.

## 4. PITFALL: mirror the directory structure; do NOT flatten paths

When persisting fetched files, SANITIZING `/` out of the path into a flat
filename (`"${f//\//_}"`) silently collapses `scripts/netbird_preflight.py`
into `scripts_netbird_preflight.py` on disk. Every later read of the true
path (`read_file("<repo>/scripts/netbird_preflight.py")`) then fails, and
several identical read failures read like a filesystem/loop bug instead of
the self-inflicted path rename it actually is.

Instead:
```bash
mkdir -p "$(dirname "$f")" && curl -sSL -m 20 "$RAW/$f" -o "$f"
```

And after ANY failed read, the FIRST diagnostic is `ls` the directory to see
what actually got written — do not blindly re-issue the read.

## 5. Watch the API budget

Anonymous GitHub API = 60 requests/hour reset (unauthenticated pool). One
`git/trees?recursive=1` is almost always worth the single request vs N calls.
Cache per-repo results (default_branch, tree) when fetching many files from
the same repo.

## 6. Optional whole-repo path: tarball via raw CDN

`raw.githubusercontent.com` can also serve an archive directly for a one-shot
whole-repo grab (no API calls, no clone):

```bash
curl -sSL "https://codeload.github.com/<owner>/<repo>/tar.gz/refs/heads/<branch>" -o repo.tar.gz
```

Note `codeload` is the host most likely to stall under a partial firewall —
prefer the per-file raw route for small repos.
