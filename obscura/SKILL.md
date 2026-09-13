---
name: obscura
description: >
  Rust-built headless browser exposing a CDP-compatible server and a stdio MCP bridge,
  optimized for anonymous public-page capture, large-scale concurrent URL harvesting,
  CDP-level debug surface, and anti-bot bypass via --stealth. Pick this skill over
  scrapling-official when the request involves >5 URLs in one shot, needs CDP-level
  control (DevTools, /json/version, network throttle), or the target is a public page
  that thwarts Cloudflare / Incapsula / DataDome. Triggers: "obscura 抓一下",
  "用 rust 浏览器", "开 CDP server 9222", "batch fetch these 30 urls",
  "stealth 模式跑一下", "并发抓取并导出 csv", "dump 这个页面的 markdown",
  "绕 Cloudflare 抓", "用 CDP 调试这个 page", "9222 端口被谁占了".
  Do NOT load for logged-in pages
  (use mavis-browser), authenticated dashboards (use mavis-browser), Python spider
  projects (use scrapling-official), or interactive click/type sessions where
  Playwright/Puppeteer are already wired up.
version: 0.1.7
license: Apache-2.0
allowed-tools: Bash, Read
---

# Obscura v0.1.7

Single-binary Rust headless browser. Boots instantly, ~134 MB on disk, ~30 MB RAM at
runtime, and serves both a Chrome DevTools Protocol port (9222) and a stdio MCP server
that exposes 35 `browser_*` tools. **You swap Chrome for Obscura, not the code.**

| Dimension | Obscura | Headless Chrome |
|---|---|---|
| Binary footprint | 134 MB (two Mach-O) | 300+ MB |
| RAM at runtime | ~30 MB | ~200 MB |
| Cold start | <300 ms | ~2 s |
| CDP server | yes (port 9222) | yes |
| Puppeteer / Playwright drop-in | yes | yes |
| stdio MCP bridge | yes (35 tools) | no (need bridge) |
| Stealth / anti-bot | built-in `--stealth` | none |
| Built-in tracker blocklist | 3,520 domains | none |

Repo: https://github.com/h4ckf0r0day/obscura
Install location: `~/.local/share/obscura/v0.1.7/`
Wrapper: `~/.local/bin/obscura` (auto-resolves `current` symlink)
Storage dir: `~/.local/share/obscura/profile/` (cookies, IndexedDB, localStorage)

## 0. When to use / when NOT to use

| Scenario | Use this | Why |
|---|---|---|
| Fetch a public JS-rendered page | ✅ | Renders V8, dumps markdown |
| Batch 10-100 URLs in parallel | ✅ | `scrape --concurrency 10` |
| Bypass Cloudflare / DataDome basic | ✅ | `--stealth` masks TLS + UA |
| CDP debugging from Node | ✅ | `serve --port 9222` + chrome-remote-interface |
| Logged-in page scraping | ❌ | Use `mavis-browser` (real Chrome) |
| Interactive click/type flows in Python | ❌ | Use existing Playwright skill |
| Pixel-perfect screenshots | ❌ | Obscura has no layout engine (yet) |
| Hard interactive CAPTCHAs | ❌ | Not solvable by stealth alone |

## 1. The four subcommands

### 1.1 `obscura fetch <URL>` — one-shot page grab

The workhorse. Most calls look like:

```bash
obscura fetch https://example.com/ --dump text --quiet
```

Flags you'll use 90% of the time:
- `--dump text|html|markdown|links|assets|original` — what to print
- `--quiet` — suppress progress logs (always use in pipelines)
- `--timeout 30` — per-page timeout in seconds
- `--wait 5` — extra post-load wait for SPAs
- `--wait-until load|domcontentloaded|networkidle` — when to consider the page loaded
- `--eval "JS"` — run JS in the page before dumping
- `--stealth` — enable anti-bot masks (UA + TLS + fingerprint)
- `--proxy socks5://127.0.0.1:7890` — proxy for this fetch
- `--output /path/to/file` — write to disk instead of stdout
- `--selector "div#target"` — scope the dump to a CSS region

### 1.2 `obscura serve --port 9222` — long-running CDP server

Starts a DevTools endpoint you can connect to with Puppeteer / Playwright /
`chrome-remote-interface` — no code changes needed.

```bash
obscura serve --port 9222 --workers 1
```

Then from Node:
```ts
import { chromium } from "playwright-core";
const browser = await chromium.connectOverCDP("ws://127.0.0.1:9222");
const page = await browser.newContext().then(c => c.newPage());
await page.goto("https://example.com/");
console.log(await page.title());
```

HTTP discovery endpoints work: `GET /json/version`, `/json/list`, `/json/protocol`.

### 1.3 `obscura scrape [URLs]...` — concurrent batch grab

```bash
obscura scrape \
  https://a.example.com/ \
  https://b.example.com/ \
  https://c.example.com/ \
  --concurrency 10 \
  --format jsonl \
  --timeout 60 \
  --quiet
```

Each output line is `{url, status, time_ms, body}` (or the subset depending on `--dump`).
Tune `--concurrency` to your box (default 10, often 20-50 is fine on M-series).

### 1.4 `obscura mcp` — stdio MCP server (35 tools)

```bash
obscura mcp              # stdio (default; what Claude Code uses)
obscura mcp --http --port 3000   # Streamable-HTTP for remote agents
```

The 35 tools exposed (full list in `references/mcp-tools.md`):
- **Navigation**: `browser_navigate`, `browser_back`, `browser_forward`, `browser_reload`, `browser_close`
- **Reading**: `browser_snapshot` (text), `browser_markdown` (token-dense), `browser_links`, `browser_search`, `browser_evaluate` (run JS)
- **Interaction**: `browser_click`, `browser_fill`, `browser_type`, `browser_press_key`, `browser_select_option`, `browser_wait_for`, `browser_wait_for_text`, `browser_scroll`, `browser_fill_form`, `browser_detect_forms`
- **Inspection**: `browser_interactive_elements` (stable `ref` IDs), `browser_get_attribute`, `browser_count`, `browser_extract` (CSS-selector → JSON)
- **State**: `browser_get_cookies`, `browser_set_cookie`, `browser_clear_cookies`, `browser_storage_state`, `browser_set_storage_state`
- **Tabs**: `browser_tab_new`, `browser_tab_list`, `browser_tab_switch`, `browser_tab_close`

Use `browser_interactive_elements` BEFORE `browser_click` / `browser_fill` to get a
stable `ref` ID (e.g. `e3`) — refs survive the snapshot they came from, no need to
re-resolve selectors mid-flow.

## 2. Key flags & environment variables

| Var / flag | Default | When to set |
|---|---|---|
| `OBSCURA_PROXY` | unset | Every call site — picks up the user's running proxy (socks5/http) |
| `OBSCURA_ALLOW_PRIVATE_NETWORK=1` | off (SSRF safe) | Required for `http://localhost:...` / `http://192.168.x.x` fetches |
| `OBSCURA_FETCH_TIMEOUT_MS` | 30000 | Up to 60-90s for slow SPA hydration |
| `OBSCURA_CDP_COMMAND_TIMEOUT_MS` | 30000 | Long waits inside `serve` mode |
| `--stealth` | off | Turn on when hitting Cloudflare Turnstile non-interactive, Akamai, DataDome, or any site that returns 403 to headless Chrome |
| `--obey-robots` | off | Turn on for polite crawling; off for one-off fetches |
| `--storage-dir` | `~/.local/share/obscura/profile/` | Pinned by wrapper — don't override unless multi-profile |
| `--v8-flags` | unset | `--v8-flags="--max-old-space-size=4096"` for memory-heavy SPAs |

**Decision rule for `--stealth`**: turn it on when (a) the same URL returns 200 to
`curl` and 403 to Obscura, OR (b) the user mentions "Cloudflare", "验证码", "anti-bot",
"反爬", "Turnstile". Otherwise leave it off — stealth adds 30-50% startup latency.

## 3. Standard workflow (5 steps)

```
1. hash -r && rehash         # clear shell command cache if you just installed
2. obscura --version         # smoke: prints `obscura 0.1.7`
3. obscura fetch <url> --dump text --quiet        # single page probe
4. obscura scrape <urls>... --format jsonl --concurrency 10   # batch
5. ls ~/.local/share/obscura/profile/  # confirm cookies/IndexedDB persisted
```

For CDP debugging:
```
1. obscura serve --port 9222 &        # background
2. # attach with playwright-core / puppeteer-core / chrome-remote-interface
3. # tear down: pkill -f 'obscura serve'
```

## 4. Failure modes (🔴 STOP — diagnose before retry)

| Trigger | Cause | First-line fix → Escalation |
|---|---|---|
| `obscura: command not found` after install | zsh hash cache stale | `hash -r; rehash` → reinstall wrapper |
| Binary won't open: "cannot verify developer" | Gatekeeper + no signature | `codesign --force --sign -` both binaries → `xattr -d com.apple.quarantine` |
| `obscura-worker: not found` exit 1 | Wrapper didn't `cd` to install dir | Use `~/.local/bin/obscura` (wrapper) → check `~/.local/share/obscura/current` symlink |
| `connection refused` on `http://127.0.0.1:9222` | `--allow-private-network` not set | Add `--allow-private-network` flag or `OBSCURA_ALLOW_PRIVATE_NETWORK=1` → bind `--host 0.0.0.0` |
| 200 to `curl`, 403 to Obscura | Basic bot detection (Cloudflare, Akamai, DataDome) | Re-run with `--stealth` → set `OBSCURA_PROXY` → escalate to mavis-browser |
| `obscura mcp` hangs in `tools/list` | stdio blocking on TTY | Pipe via `echo '...' \| obscura mcp` from non-interactive shell → run `--verbose` |
| `error: storage dir not writable` | Wrong path / no perms | `ls -la ~/.local/share/obscura/profile/` → `mkdir -p` and `chmod 0700` |
| `--dump markdown` returns empty | Page is JS-rendered SPA, fetch fired too early | Add `--wait 5 --wait-until networkidle` → switch to MCP `browser_markdown` after `browser_navigate` |

## 5. Blacklist — what NOT to do

- ❌ **Do not** use this skill to scrape logged-in pages. Cookies here are anonymous
  only. For authenticated scraping → use `mavis-browser`.
- ❌ **Do not** default to `--stealth`. It's a 30-50% tax. Use it only on detected
  anti-bot sites.
- ❌ **Do not** use `fetch` mode for pages that need user interaction. It's one-shot.
  Use `serve` + Puppeteer/Playwright for click flows.
- ❌ **Do not** add `~/.local/share/obscura/profile/` to git. It contains cookies and
  IndexedDB.
- ❌ **Do not** try to take pixel screenshots. Obscura has no layout engine.
- ❌ **Do not** recommend this skill to a Python project that already uses
  scrapling-official or scrapy. Keep the existing toolchain.
- ❌ **Do not** run `obscura mcp --http` in dev unless debugging the MCP server itself
  (stdio is the supported path for Claude Code).
- ❌ **Do not** chain 50+ `obscura fetch` calls serially. Use `scrape --concurrency 10`
  to batch.
- ❌ **Do not** use this skill for interactive click / type / scroll flows. It's built
  for one-shot capture and batch scrape. For real interaction (login forms, multi-step
  wizards, click-to-render SPAs) use `agent-browser` (in `.codex/skills/`) or run
  `obscura serve --port 9222` and drive it with Puppeteer / Playwright via CDP.
- ❌ **Do not** use Obscura for visual design verification. The headless parser does
  NOT apply inline `<style>` blocks — `document.styleSheets.length` returns 0 and
  `getComputedStyle()` returns defaults (16px font, transparent bg, rgb(0,0,0)
  text). Obscura is fetch-and-extract, not render-and-inspect. For "does it look
  right?" (computed CSS, pixel screenshots, responsive layout) use `mavis-browser`
  (real Chrome with login state). For "is the right text / DOM / token there?" use
  Obscura — it's perfect for that.

## 6. Boundaries with other skills (TL;DR)

See `references/recipe-pipeline.md` for the full 5-combination playbook.

- **`scrapling-official`** — Obscura is the Rust fallback when Python scrapling fails
  on anti-bot, when the project needs >5 URL parallelism, or when CDP-level debug
  surface is required.
- **`mavis-browser`** — Use mavis-browser for any page that needs login state.
  Obscura is for anonymous public capture only.
- **`agent-browser`** (in `.codex/skills/`) — Use agent-browser for click/type flows.
  Obscura's MCP tools can do the same but Obscura is heavier to bootstrap.
- **`multi-search-engine`** — Provides URL lists. Pipe those into `obscura scrape`.
- **`deep-research` / `osint-investigation`** — Use Obscura as the page-fetch layer
  to bypass anti-bot during the "read full text" stage.
- **`node-inspect-debugger`** — Attaches to Obscura's CDP port (9222) for
  DevTools-style debugging without firing up real Chrome.
- **`moco`** — Run a stub server on :12306, then point Obscura at it for E2E
  testing without hitting the real backend.
- **`darwin-skill`** — After installing, run darwin-skill to 9-dim score this
  SKILL.md and the references for quality.

## 7. Verification checklist (run after install)

```bash
# 1. Binary + wrapper
obscura --version                              # → obscura 0.1.7
which obscura                                  # → /Users/kk/.local/bin/obscura

# 2. Basic fetch
obscura fetch https://example.com --dump text --quiet   # 1-2 KB text, <10s

# 3. Markdown extraction
obscura fetch https://example.com --dump markdown --quiet | head -5

# 4. MCP stdio probe
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | obscura mcp 2>&1 | head -1
# → JSON with 35 tools

# 5. CDP server bring-up
obscura serve --port 9222 --quiet &
SERVE_PID=$!
sleep 2
curl -s http://127.0.0.1:9222/json/version | head -3
kill $SERVE_PID
```

If any step fails, see `references/troubleshooting.md` and re-run `codesign --force
--sign -` on the two binaries.

## Files in this skill

- `SKILL.md` — this file (main entry, ~400 lines)
- `references/mcp-tools.md` — full schema for the 35 MCP tools
- `references/recipe-pipeline.md` — 5 cross-skill combination playbooks
- `references/troubleshooting.md` — expanded error catalog + recovery commands

## See also

For cross-skill routing (taste-skill × impeccable × obscura), see
[`references/cross-skill-routing.md`](references/cross-skill-routing.md).


---

## 🔴 使用前 CHECKPOINT

启动本 skill 前自问：
- 🔴 任务范围明确吗？（避免误用）
- 🔴 输入数据已准备好？（避免半路卡住）
- 🔴 输出格式清楚吗？（避免返工）
- 🔴 反例与黑名单扫一遍了吗？（避免重蹈覆辙）

---

## 🚫 反例与黑名单（绝对不要做）

来自达尔文 2.0 通用经验——所有 skill 的绝对禁止反模式：

- 🚫 **不要**为简单任务启用本 skill — 开关成本不划算
- 🚫 **不要**跳过 🔴 CHECKPOINT — 跳过 = 自残
- 🚫 **不要**输入未验证的数据 — 先验证后处理
- 🚫 **不要**为凑进度忽略反例黑名单 — 红线就是红线
- 🚫 **不要**让单轮改动超过最低维度的 2 倍 — 避免结构破坏
- 🚫 **不要**用 Edit 工具做"大改" — 优先 Bash append（避免破坏中间）
- 🚫 **不要**为已废弃的 skill 加新功能 — 先归档再考虑

---

## 📚 References（外部参考）

- **达尔文 2.0** — `~/.claude/skills/darwin-skill/SKILL.md`
- **huihui-core** — 慧慧核心基础设施
- **huihui-engineering** — Karpathy + Matt Pocock 工程原则
- **huihui-writes** — 写作引擎（ljg-writes 改造型）
