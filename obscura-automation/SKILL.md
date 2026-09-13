---
name: Obscura Automation
slug: obscura-automation
version: 1.0.0
homepage: https://github.com/h4ckf0r0day/obscura
description: Stealth headless browser for AI agents and web scraping. Use when Playwright/Puppeteer is too heavy or detected, when needing anti-bot evasion, or for parallel scraping at scale. Rust binary, 70MB, 30MB RAM, instant startup, full CDP/Puppeteer/Playwright compatibility. Do NOT use for visual design verification ("does it look right?"), animation completion detection, page-load SLO timing, or image/pixel diff.
changelog: "2026-06-07 - Initial integration of h4ckf0r0day/obscura v0.1.7"
metadata: {"clawdbot":{"emoji":"🥷","requires":{"bins":["obscura"],"os":["darwin","linux"]},"os":["darwin","linux"],"skills":{"obscura-cli":{"path":"scripts/obscura-cli.sh","type":"executable"},"obscura-serve":{"path":"scripts/obscura-serve.sh","type":"executable"},"obscura-task":{"path":"scripts/obscura-task.js","type":"executable"},"obscura-puppeteer":{"path":"scripts/obscura-puppeteer.js","type":"executable"},"obscura-playwright":{"path":"scripts/obscura-playwright.js","type":"executable"}}}}
---

## When to Use

- 需要抓被反爬保护的网站（Cloudflare、DataDome、PerimeterX）
- Playwright/Chrome 启动太慢、内存占用太高（Chrome 200MB+ vs Obscura 30MB）
- 大规模并行抓取（Obscura 启动毫秒级，可 spawn 数百 worker）
- AI Agent 需要真实浏览器交互（CDP 兼容 Puppeteer/Playwright）
- 关键词：「反检测」「隐身」「stealth」「anti-bot」「headless」「CDP」「抓取」「爬虫」「scraping」「Playwright 慢」「Chrome 太重」

## Use Case → Command Quick Map

| If you want to... | Run this | Why |
|---|---|---|
| Get a page's title / DOM value | `obscura fetch <url> --eval "document.title"` | One-shot, no daemon needed |
| Extract multiple fields from many pages | `obscura scrape url1 url2 ... --eval "..." --format json` | Built-in concurrency (default 25) |
| Drive a browser from Node.js (login flows, multi-step) | `obscura serve --port 9222 --stealth` then Puppeteer/Playwright → `ws://127.0.0.1:9222` | CDP server stays alive between commands |
| Save the rendered HTML for offline parsing | `obscura fetch <url> --dump html > page.html` | Use `--wait-until networkidle0` for SPAs |
| Save the original bytes (image / PDF / binary) | `obscura fetch <url> --dump original > asset.bin` | Bypasses JS/DOM mutation |
| Bypass simple anti-bot (Cloudflare basic) | Use `--stealth` build: `obscura --features stealth fetch <url>` | Fingerprint randomization on |
| Verify a fix deployed correctly | See [§5 Blacklist](#5-blacklist--do-not-use-obscura-for) first — Obscura cannot verify **visual** correctness, only text/DOM presence | |
| Scrape at scale (hundreds of pages) | `obscura scrape ... --concurrency 50 --quiet --format jsonl` | `--quiet` suppresses progress, JSONL streams |

A Rust-written stealth headless browser from [h4ckf0r0day/obscura](https://github.com/h4ckf0r0day/obscura) (14K+ stars, Apache-2.0, v0.1.7).

| Metric | Obscura | Headless Chrome |
|---|---|---|
| Memory | **30 MB** | 200+ MB |
| Binary | **70 MB** | 300+ MB |
| Anti-detect | **Built-in** | None |
| Page load | **85 ms** | ~500 ms |
| Startup | **Instant** | ~2s |
| Puppeteer | ✅ | ✅ |
| Playwright | ✅ | ✅ |

**Stealth features** (`--features stealth` build):
- Per-session fingerprint randomization (GPU, screen, canvas, audio, battery)
- Realistic `navigator.userAgentData` (Chrome 145 high-entropy)
- `event.isTrusted = true` for dispatched events
- Hidden internal properties (safe `Object.keys(window)`)
- Native function masking (`Function.prototype.toString` clean)
- `navigator.webdriver = undefined`
- 3,520 tracker domains blocked

## Capabilities

### 1. CLI (one-shot fetch)
```bash
# Basic fetch
obscura fetch <url> --eval "<js>"

# Dump modes
obscura fetch <url> --dump text        # Plain text
obscura fetch <url> --dump html        # Rendered HTML
obscura fetch <url> --dump links       # All links
obscura fetch <url> --dump assets      # Sub-resource URLs
obscura fetch <url> --dump original > photo.jpg  # Binary-safe (bypasses JS/DOM)

# With proxy
obscura --proxy socks5://127.0.0.1:1080 fetch <url>

# Wait for dynamic content
obscura fetch <url> --wait-until networkidle0

# Bound slow/broken pages
obscura fetch <url> --timeout 10
```

### 2. CDP Server (long-running)
```bash
obscura serve --port 9222
obscura serve --port 9222 --stealth    # Enable anti-detect
# Connects via ws://127.0.0.1:9222 (Puppeteer/Playwright compatible)
```

### 3. Parallel Scraper
```bash
obscura scrape url1 url2 url3 ... \
  --concurrency 25 \
  --eval "document.querySelector('h1').textContent" \
  --format json

# Quiet mode (suppress progress on stderr)
obscura scrape <url> --quiet --format json
```

### 4. Docker
```bash
docker run -d --name obscura -p 127.0.0.1:9222:9222 h4ckf0r0day/obscura
```

## Quick Examples

```bash
# Get page title
obscura fetch https://example.com --eval "document.title"

# Extract all story links from Hacker News
obscura fetch https://news.ycombinator.com --eval "Array.from(document.querySelectorAll('.titleline > a')).map(a => ({title: a.textContent, url: a.href}))"

# Render JS-heavy page and dump HTML
obscura fetch https://news.ycombinator.com --dump html

# Login flow (POST + 302 + cookies)
# (handle via Puppeteer/Playwright connected to CDP, see below)
```

## Decision Checkpoints

> These are the 4 places to **stop and confirm** before continuing. LLM agents should treat `🔴` as a hard pause, not a suggestion.

- 🔴 **Before installing the binary** — Verify `uname -m` matches the binary architecture (`arm64` for Apple Silicon, `x86_64` for Intel). Verify SHA-256 against the GitHub release notes. Do not install from a non-release URL.
- 🔴 **Before swapping toryx-automation / Playwright backend** — Snapshot the existing config: `cp -r ~/.openclaw/workspace/skills/toryx-automation ~/.openclaw/workspace/skills/toryx-automation.bak.$(date +%Y%m%d-%H%M%S)`. Reversibility required.
- 🔴 **Before scraping a site with anti-bot (Cloudflare / DataDome / PerimeterX)** — Confirm the target is not behind a paywall, login wall, or explicitly disallows bots in `robots.txt`. If it does, **stop and ask the user**. Stealth ≠ permission.
- 🔴 **Before running `--stealth` in production** — Confirm the use case is legitimate (e.g., price monitoring, public data aggregation). If it involves logging into other people's accounts, bypassing access controls, or scraping personal data — **do not proceed**.

## Failure Recovery

| Trigger symptom | First-line fix | If still failing |
|---|---|---|
| `obscura: command not found` | Check `$PATH` includes `~/.local/bin` or the install location; `which obscura` | Re-download binary from GitHub release; verify SHA-256 |
| `obscura serve` exits immediately | Check port 9222 not in use: `lsof -nP -iTCP:9222 -sTCP:LISTEN` | Try a different port: `obscura serve --port 9333` |
| Page returns empty / `<html></html>` | Site blocks headless — try `--features stealth` build or set realistic UA via Puppeteer | Use real Chrome with stealth plugin; Obscura is not a magic bypass |
| `fetch` hangs > 15s | Add `--timeout 10`; check if JS-hydration needed (`--wait-until networkidle0`) | Switch to Puppeteer with explicit `waitForSelector` |
| Browser detected despite `--stealth` | Fingerprint drift between Obscura version and target's detection rule | Update Obscura; report issue upstream with target site + version |
| `--dump original` returns binary garbage | `obscura` may have run JS on it; use raw `curl` for binary assets | Stream to file: `curl -sSL <url> -o asset.bin` |
| Chrome refuses `connectOverCDP` to `ws://127.0.0.1:9222` | Obscura not actually serving; check `curl http://127.0.0.1:9222/json/version` | Restart `obscura serve --port 9222 --stealth` in background |

### Puppeteer
```js
import puppeteer from 'puppeteer-core';
const browser = await puppeteer.connect({
  browserWSEndpoint: 'ws://127.0.0.1:9222/devtools/browser',
});
const page = await browser.newPage();
await page.goto('https://news.ycombinator.com');
console.log(await page.title());
await browser.disconnect();
```

### Playwright
```js
import { chromium } from 'playwright-core';
const browser = await chromium.connectOverCDP({
  endpointURL: 'ws://127.0.0.1:9222',
});
const ctx = await browser.newContext();
const page = await ctx.newPage();
await page.goto('https://en.wikipedia.org/wiki/Web_scraping');
console.log(await page.title());
await browser.close();
```

## Integration with Existing Skills

This skill is designed to **swap into** or **augment** several existing skills:

| Target Skill | Mode | What it gets |
|---|---|---|
| `toryx-automation` | **Replace** Playwright backend | Same commands, 10× faster, stealth by default |
| `multi-search-engine` | **Augment** with stealth fetcher | Anti-bot evasion for blocked sources |
| `in-depth-research` | **Augment** content extraction | Render JS-heavy pages before extract |
| `autonomous-research` | **Augment** web pipeline | Drop-in replacement for headless Chrome |
| `multi-source-research` | **Augment** with stealth fetch | Fetch sources that block scrapers |
| `office-automation-pro` | **Augment** web→PDF/Word | Render then export |

See `integrations/` for drop-in scripts and recipes.

## Status

- ✅ Binary install: `bin/obscura` (70MB ARM64 macOS, from v0.1.7 release)
- ✅ CLI smoke test verified (fetch + serve + scrape)
- ✅ CDP server tested with Puppeteer / Playwright
- ✅ Stealth build available (default download includes stealth features)
- ✅ SHA-256 verifiable (Rust reproducible build)
- 🔄 Integration scripts with `toryx-automation` (in `integrations/toryx-swap.sh`)
- 🔄 `multi-search-engine` stealth fallback (in `integrations/search-stealth.sh`)

## 5. Blacklist — do NOT use Obscura for

> Each item below is a **real limitation** discovered through live use (2026-06-07 design-skill test). Don't repeat the same mistake. If a use case hits one of these, **switch tools first**, don't try to work around it.

- ❌ **Visual design verification ("does it look right?")** — Obscura is a stealth text/DOM extractor, not a renderer-screenshot tool. It can dump rendered HTML and the text/DOM tree, but it cannot tell you whether a layout is visually correct, fonts loaded, animations played, colors applied, hover states worked, or screenshots match expectations. **For "does it look right?" use a real browser (Safari / Chrome / `mavis-browser`) with `--screenshot` or `screencapture`**. Obscura is for "is the right text / DOM / token there?"

- ❌ **Page-load timing as a reliability signal** — Obscura reports `--wait-until networkidle0` returning in 85 ms because it doesn't actually wait for paint/JS-hydration the same way Chrome does. Don't trust "page loaded" timing from Obscura for SLO assertions; use Puppeteer/Playwright with explicit `waitForSelector` for production checks.

- ❌ **CSS animation completion detection** — Animation events (`animationend`, `transitionend`) are not reliably emitted by Obscura's runtime. If you need "wait for animation to finish" use a real headless Chrome with `--virtual-time-budget` or a CDP-aware harness.

- ❌ **Image comparison / pixel diff** — No built-in image hashing, no perceptual diff. Don't try to use Obscura output for "did the page change?" workflows; compute a hash of the downloaded asset separately.

- ❌ **Credential stuffing / account takeover** — Apache-2.0 + stealth features do not authorize illegal use. Repos that hide this in skill text get reported.

- ❌ **Trusting the "🟢" 14K-star badge without audit** — `h4ckf0r0day` is not OpenClaw-verified. The binary is reproducible from the GitHub Actions Rust build, so verify with `shasum -a 256 bin/obscura` against the release SHA before installing in production. Stars ≠ safety.

## 6. When Obscura wins — quick rule of thumb

| Question | Use Obscura? | Use instead |
|---|---|---|
| Is the page returning the expected text/DOM/token? | ✅ Yes | — |
| Did my scrape evade the anti-bot? | ✅ Yes | — |
| Is the layout visually correct? | ❌ No | Real headless Chrome with screenshot |
| Did the page load fast enough for SLO? | ⚠️ Not as timing source | Chrome with `performance.timing` |
| Did the CSS animation play through? | ❌ No | Chrome + `--virtual-time-budget` |
| Does the screenshot match the design? | ❌ No | `screencapture` / Chrome headless screenshot |

## Notes

- License: Apache-2.0 (commercial use OK)
- Author `h4ckf0r0day` is not OpenClaw-verified; verify SHA-256 before install (see [§5 Blacklist](#5-blacklist--do-not-use-obscura-for))
- Latest release verified: 2026-06-06 (v0.1.7, active)
- See [§5 Blacklist](#5-blacklist--do-not-use-obscura-for) for legal/ethical use boundaries
