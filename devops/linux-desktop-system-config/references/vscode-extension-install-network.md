# VS Code extension install in restricted networks

Quick-reference for the specific failure: `code --install-extension <id>` hangs and ends with `AggregateError [ETIMEDOUT]` while `curl https://marketplace.visualstudio.com/` returns 200 immediately.

## Why

Marketplace **browse** is served from `marketplace.visualstudio.com` (Microsoft CDN, usually reachable). Extension **artifacts** (.vsix downloads) come from `*.gallery.vsassets.io` / `update.code.visualstudio.com` — different edge, often blocked or heavily throttled. A `curl https://marketplace.visualstudio.com/` check lies to you.

## Fix

Set `HTTPS_PROXY` (uppercase also works, Node honors both) before running `code --install-extension`:

```bash
export http_proxy=http://127.0.0.1:7890
export https_proxy=http://127.0.0.1:7890
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
code --install-extension ms-python.python
```

(Port `7890` is the common Clash/mihomo default. Check `~/.config/mihomo/config.yaml` or the running proxy's UI for the actual port.)

## Bulk restore after a clean reinstall

```bash
# Install Chinese pack first so error messages render locally:
code --install-extension ms-ceintl.vscode-language-pack-zh-hans

# Then loop the rest (skip the language pack in the file):
grep -v 'vscode-language-pack-zh-hans' ~/backup-vscode-<date>/extensions.txt \
  | while read ext; do
      code --install-extension "$ext" 2>&1 | grep -E 'Installing|Failed|already installed' | tail -1
    done

# Verify count matches expectation:
code --list-extensions | wc -l
```

## Pitfalls

- **Don't try `curl https://marketplace.../api/<ext>` as a "preflight".** It will succeed and waste time. The real failure mode is the .vsix download.
- **An extension might pull a hidden dependency** (e.g. `ms-python.vscode-pylance` depends on `ms-python.python`). Expect the final count to be N+M where M is small; this is correct, not duplication.
- **`code` CLI uses Node's net stack**, which respects `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY` env vars. Setting only lowercase `http_proxy` works for curl but **not always** for Node-fetch code inside VS Code extensions. Set all four.
- **Each install can take ~1 min through proxy.** 20 extensions = ~20 min. Run in background and don't block on it.
- **After install, the extension may auto-write to `settings.json`** (e.g. `sub2api-provider` writes its `reasoningOverride` key). If the goal is a truly empty config, wipe settings.json after the install loop.
