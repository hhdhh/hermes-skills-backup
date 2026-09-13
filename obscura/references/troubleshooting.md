# Obscura — Troubleshooting Catalog

If a recipe in `recipe-pipeline.md` fails, walk down this list in order. Each
section has: symptom → diagnosis command → fix command.

## T1. Binary won't open (Gatekeeper)

**Symptom**: macOS pops "Obscura cannot be opened because the developer cannot be
verified" on first run, or `obscura` exits with code 1 and a quarantine message.

**Diagnose**:
```bash
xattr -l /Users/kk/.local/share/obscura/v0.1.7/obscura
# Look for: com.apple.quarantine
```

**Fix**:
```bash
xattr -dr com.apple.quarantine /Users/kk/.local/share/obscura/v0.1.7/
codesign --force --sign - --timestamp=none \
  /Users/kk/.local/share/obscura/v0.1.7/obscura \
  /Users/kk/.local/share/obscura/v0.1.7/obscura-worker
spctl --assess --verbose=4 --type execute \
  /Users/kk/.local/share/obscura/v0.1.7/obscura
```

## T2. `obscura: command not found` after install

**Symptom**: `which obscura` returns nothing, or returns the wrong path.

**Diagnose**:
```bash
echo $PATH | tr ':' '\n' | grep -E '\.local/bin'
ls -la ~/.local/bin/obscura
```

**Fix**:
```bash
# Ensure ~/.local/bin is in PATH (zsh)
grep -q 'HOME/\.local/bin' ~/.zshrc || \
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
# Reload
source ~/.zshrc
hash -r; rehash
```

## T3. `obscura-worker: not found` / worker dies on startup

**Symptom**: `obscura fetch` fails immediately, stderr mentions worker.

**Diagnose**:
```bash
ls -la /Users/kk/.local/share/obscura/current/
file /Users/kk/.local/share/obscura/current/obscura-worker
```

**Fix**:
The wrapper at `~/.local/bin/obscura` does `cd "${EXEC_DIR}"` before exec so worker
resolution works. If you bypassed the wrapper and called the binary directly, that's
the bug. Always go through the wrapper:
```bash
~/.local/bin/obscura fetch https://example.com --dump text --quiet
# ✓
~/.local/share/obscura/current/obscura fetch https://example.com --dump text --quiet
# ✗ worker lookup fails
```

## T4. `connection refused` on `http://127.0.0.1:9222`

**Symptom**: Started `obscura serve --port 9222`, but `curl http://127.0.0.1:9222/json/version` times out.

**Diagnose**:
```bash
lsof -nP -iTCP:9222 -sTCP:LISTEN
# Empty → server didn't bind.
# Hit → server is up.
```

**Fix A** (server didn't bind at all): check stderr from `obscura serve` — most
often a port collision. Try a different port:
```bash
obscura serve --port 19222 --host 127.0.0.1
```

**Fix B** (server is up but client can't reach): make sure the client is on
`127.0.0.1`, not `localhost` (IPv6 mismatch). Or bind to `0.0.0.0`:
```bash
obscura serve --host 0.0.0.0 --port 9222 --allow-private-network
```

## T5. `fetch` returns 403 / anti-bot challenge

**Symptom**: `curl <url>` returns 200 with the real page, but `obscura fetch <url>`
returns 403 or a "challenge" HTML.

**Diagnose**:
```bash
obscura fetch <url> --dump text --quiet | head -20
# If you see "Checking your browser" or similar, it's a bot challenge.
```

**Fix**:
```bash
# Add --stealth (UA + TLS fingerprint + 3520-domain tracker blocklist)
obscura fetch <url> --stealth --dump text --quiet

# If still blocked, route through your local proxy
OBSCURA_PROXY=socks5://127.0.0.1:7890 obscura fetch <url> --stealth --quiet
```

If `--stealth` doesn't clear it, the site is using **interactive** bot defense
(Turnstile interactive, hCaptcha challenge) — Obscura cannot solve these. Escalate
to mavis-browser with a real Chrome session.

## T6. `fetch --dump markdown` returns empty

**Symptom**: HTML is full of `<div id="root"></div>`, page is JS-rendered SPA.

**Diagnose**:
```bash
obscura fetch <url> --dump html --quiet | head -5
# If it's mostly an empty <div>, you have a SPA.
```

**Fix**:
```bash
obscura fetch <url> --dump markdown --quiet \
  --wait 5 --wait-until networkidle
# Or use the MCP browser_markdown tool which runs after page-ready
```

If still empty, the SPA needs user interaction (login, scroll-to-load, click-to-render).
Switch to MCP `browser_navigate` + `browser_interactive_elements` + `browser_click`
flow, or escalate to mavis-browser.

## T7. MCP server `tools/list` hangs

**Symptom**: `echo '{...}' | obscura mcp` never returns.

**Diagnose**:
```bash
# Check if it's just slow to warm up
timeout 5 echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | obscura mcp
# If "timeout" prints, the server is hung.
```

**Fix**:
```bash
# Run with verbose output
obscura mcp --verbose
# Or use HTTP mode for inspection
obscura mcp --http --port 3000 &
curl -X POST http://127.0.0.1:3000 \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

If still hung, the worker is dying on startup. Check `~/.local/share/obscura/profile/`
is writable.

## T8. `error: storage dir not writable`

**Symptom**: `obscura fetch` exits with code 1 and a "storage" message.

**Diagnose**:
```bash
ls -la ~/.local/share/obscura/profile/
mkdir -p ~/.local/share/obscura/profile && touch ~/.local/share/obscura/profile/test
```

**Fix**:
```bash
rm -rf ~/.local/share/obscura/profile
mkdir -p ~/.local/share/obscura/profile
chmod 0700 ~/.local/share/obscura/profile
```

If you're running in a context where `$HOME` is unset (rare), the wrapper resolves
to `/Users/kk/...` explicitly, so this should not happen unless the path is moved.

## T9. Architecture mismatch (Rosetta on Apple Silicon)

**Symptom**: `Bad CPU type in executable` on M1/M2/M3.

**Diagnose**:
```bash
uname -m                # should be arm64 on Apple Silicon
file /Users/kk/.local/share/obscura/v0.1.7/obscura
# should say: Mach-O 64-bit executable arm64
```

**Fix**: Re-download the correct tarball:
```bash
curl -LO https://github.com/h4ckf0r0day/obscura/releases/latest/download/obscura-aarch64-macos.tar.gz
# (NOT obscura-x86_64-macos.tar.gz)
```

## T10. Cleanup / uninstall

```bash
pkill -f 'obscura (mcp|serve)' 2>/dev/null || true
rm -f ~/.local/bin/obscura ~/.local/bin/obscura-worker
rm -rf ~/.local/share/obscura/v0.1.7 \
       ~/.local/share/obscura/current \
       ~/.local/share/obscura/profile
rm -rf ~/.claude/skills/obscura
# Remove from ~/.claude/settings.json:
#   jq 'del(.mcpServers.obscura)' ~/.claude/settings.json > /tmp/s && mv /tmp/s ~/.claude/settings.json
```

## T11. Versioning / upgrades

To install a new version alongside:
```bash
mkdir -p ~/.local/share/obscura/v0.1.8
tar -xzf obscura-aarch64-macos.tar.gz -C ~/.local/share/obscura/v0.1.8
chmod 0755 ~/.local/share/obscura/v0.1.8/obscura{,-worker}
xattr -dr com.apple.quarantine ~/.local/share/obscura/v0.1.8/
codesign --force --sign - --timestamp=none ~/.local/share/obscura/v0.1.8/obscura{,-worker}
# Atomic flip of the symlink:
ln -sfn v0.1.8 ~/.local/share/obscura/current
hash -r; rehash
obscura --version   # → obscura 0.1.8
```

Old versions can be removed with `rm -rf ~/.local/share/obscura/v0.1.7` after
confirming the new one works. The `profile/` directory is shared across versions.
