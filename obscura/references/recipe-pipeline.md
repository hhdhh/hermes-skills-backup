# Obscura × Other Skills — 5 Pipeline Recipes

This file documents the five recommended ways to combine Obscura with skills already
in your ecosystem. Each recipe has a trigger phrase, a precise call sequence, and
the failure-recovery step.

## Recipe 1: scrapling-official → Obscura fallback chain

**Trigger**: User says "scrapling 抓不到这个站", "用 scrapling 失败时换 rust 试试",
"scrapling 跑 Python spider 慢", or you observe scrapling returning 403/503/anti-bot
pages.

**Call sequence**:
```
1. scrapling-official: scrapling fetch --stealth <url>
2. If exit code != 0 or body contains "challenge" / "captcha":
3. → fall back to: obscura fetch <url> --stealth --dump markdown --quiet
4. If Obscura also fails: → fall back to mavis-browser (real Chrome with login)
```

**When to escalate from scrapling to Obscura** (decision table):
| scrapling behavior | Recommended next step |
|---|---|
| 200 with valid HTML | stop, you have it |
| 200 but only the CF challenge page | `obscura fetch <url> --stealth` |
| 403 / 503 / empty | `obscura fetch <url> --stealth` |
| Connection timeout > 30s | check `OBSCURA_PROXY` env, retry with explicit `--proxy` |
| Hard interactive CAPTCHA in body | stop and ask the user for a 2captcha/anticaptcha key |

## Recipe 2: multi-search-engine → Obscura scrape → llm-wiki

**Trigger**: User says "调研 X 并写一份 wiki", "对比多源关于 X 的观点",
"综合搜索结果出报告".

**Call sequence**:
```
1. multi-search-engine: query=X, return top 20 URLs across 16 engines
2. Obscura batch:
   urls=$(echo "$RESULTS" | jq -r '.[].url')
   echo "$urls" | xargs obscura scrape --format jsonl --concurrency 10 --quiet \
     --dump markdown --output /tmp/wiki-sources.jsonl
3. Feed /tmp/wiki-sources.jsonl into llm-wiki's "import-urls" command
4. (Optional) Re-summarize with humanizer for natural-language output
```

**Why Obscura over WebFetch here**:
- WebFetch returns HTML or rendered text, not token-dense markdown
- WebFetch does not run JS — many "list of URLs" search results are SPA
- Obscura's `scrape` parallelizes 10-50 URLs in one call; WebFetch is serial

## Recipe 3: deep-research / osint-investigation → Obscura as the fetch layer

**Trigger**: User says "深度研究 X", "state of the art in X", "OSINT about target Y",
"做一份关于 X 的综合报告".

**Call sequence**:
```
1. deep-research: fan-out queries across arxiv / google scholar / news / github
2. Returns ~50 candidate URLs (mix of PDFs and HTML)
3. Obscura batch-fetch the HTML subset:
   cat html_urls.txt | xargs obscura scrape --format jsonl --concurrency 15 \
     --wait-until domcontentloaded --timeout 60 --quiet
4. Obscura also handles PDF preview pages (read the abstract page, not the PDF):
   obscura fetch <arxiv-abstract-url> --dump markdown --quiet
5. Feed the JSONL into deep-research's adversarial verify stage
6. (Optional) Run a second Obscura pass on top cited URLs for triangulation
```

**Why Obscura over web_extract here**:
- arxiv abstract pages are JS-rendered; web_extract misses metadata
- Research sites often gate behind Cloudflare; Obscura's `--stealth` handles this
- `scrape` parallelizes; web_extract is N round-trips

## Recipe 4: node-inspect-debugger ↔ Obscura CDP

**Trigger**: User says "用 CDP 调试这个 page", "分析这条 network 请求",
"复现这个 SPA bug", "看看 9222 端口能不能挂上 chrome devtools".

**Call sequence**:
```
1. Start Obscura in serve mode (background):
   obscura serve --port 9222 --workers 1 &
   # Note: --allow-private-network is implicit when binding to 127.0.0.1
2. node-inspect-debugger attaches to ws://127.0.0.1:9222/<browser-id>
3. Drive with chrome-remote-interface (or via Node REPL):
   const CDP = require('chrome-remote-interface');
   const client = await CDP({port: 9222});
   const {Network, Page, Runtime} = client;
   await Promise.all([Network.enable(), Page.enable(), Runtime.enable()]);
   await Page.navigate({url: 'https://target/'});
   await Page.loadEventFired();
   console.log(await Runtime.evaluate({expression: 'document.title'}));
4. Tear down:
   pkill -f 'obscura serve'
```

**Why this combination**:
- Obscura is the smallest possible "real browser" you can host for CDP
- `node-inspect-debugger` already knows how to drive a CDP target
- You can profile / throttle / intercept without spinning up Chrome

## Recipe 5: moco + Obscura — E2E testing without a real backend

**Trigger**: User says "E2E 测这个前端", "用 stub 站点跑回归",
"录一段 moco 响应然后让 Obscura 抓", "前端联调不想打真 API".

**Call sequence**:
```
1. Define stub responses in moco JSON:
   cat > moco-stub.json <<EOF
   [{
     "request": {"uri": "/api/users/42"},
     "response": {"json": {"id": 42, "name": "Alice"}}
   }]
   EOF
2. Start moco on 12306:
   moco start -p 12306 -g moco-stub.json &
3. Build a static HTML page that hits /api/users/42 and renders the response.
4. Have Obscura fetch the page and assert the response was rendered:
   obscura fetch http://127.0.0.1:12306/users/42.html --dump markdown --quiet \
     | grep -q 'Alice' && echo OK || echo FAIL
5. Tear down: pkill -f moco
```

**Why this combination**:
- moco gives you deterministic, replayable HTTP responses
- Obscura gives you "what would a real browser see when this SPA hydrates?"
- Together: full E2E without a backend, in seconds

**Vary the recipe**:
- Stub the third-party CDN with moco at a different port and pass it as
  `--proxy http://127.0.0.1:12307` to Obscura
- Stub 404/500 responses to verify Obscura surfaces them in `scrape` JSONL output

## General integration notes

- All five recipes assume `obscura --version` returns `0.1.7` and the wrapper is at
  `~/.local/bin/obscura`. If not, see `SKILL.md` §4 (Failure modes) and
  `references/troubleshooting.md`.
- For any recipe that runs >30 URLs, prefer `scrape --concurrency 10+` over a shell
  `for` loop. The CLI is tuned for batch.
- For any recipe that hits anti-bot (recipe 1 + 3 often do), always include
  `--stealth` and consider setting `OBSCURA_PROXY` to your local proxy.
- Cookies/profile state persists in `~/.local/share/obscura/profile/`. To reset
  between runs, delete that directory. To preserve across runs (e.g. logged-in
  scraping for recipe 3), keep it.
