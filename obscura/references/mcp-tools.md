# Obscura MCP Tools — Full Reference

The `obscura mcp` stdio server exposes **35 tools**, all prefixed `browser_`. They are
modeled on the Playwright MCP server so that the two are drop-in interchangeable from
the Claude Code side.

## Quick start

Verify the server is wired in `~/.claude/settings.json`:
```json
"mcpServers": {
  "obscura": {
    "command": "/Users/kk/.local/bin/obscura",
    "args": ["mcp"]
  }
}
```

Then from a Claude Code session you can call any tool by its full name, e.g.
"Use the browser_navigate tool to go to https://...".

## The 35 tools at a glance

### Navigation (5)
| Tool | What it does |
|---|---|
| `browser_navigate(url, waitUntil?)` | Go to URL, wait for load (default), domcontentloaded, or networkidle |
| `browser_back` | History back |
| `browser_forward` | History forward |
| `browser_reload` | Reload current page |
| `browser_close` | Close the page, reset state |

### Reading (7)
| Tool | What it does |
|---|---|
| `browser_snapshot` | Current page as plain text (title + URL + readable body) |
| `browser_markdown(max_chars?)` | Current page as Markdown — **use this over snapshot when you want token-dense content** |
| `browser_links(limit?, internal_only?)` | List all `<a>` elements as `{text, href}` |
| `browser_search(query, case_sensitive?, limit?, context_chars?)` | Substring matches with surrounding context |
| `browser_evaluate(expression)` | Run arbitrary JS, return result |
| `browser_console_messages` | All console output from the page |
| `browser_network_requests` | All network requests made by the page |

### Interaction (10)
| Tool | What it does |
|---|---|
| `browser_click(ref?, selector?)` | Click an element. Prefer `ref` from a recent `browser_interactive_elements` |
| `browser_fill(ref?, selector?, value)` | Set an input's value |
| `browser_type(ref?, selector?, text)` | Append text to an input |
| `browser_press_key(key, selector?)` | Keyboard event (Enter, Tab, Escape) |
| `browser_select_option(selector, value)` | Pick option in a `<select>` |
| `browser_wait_for(selector, timeout?)` | Wait for CSS selector to appear |
| `browser_wait_for_text(text, timeout?)` | Wait for substring in rendered text |
| `browser_scroll(direction?, amount?, ref?, selector?)` | Scroll page or element |
| `browser_fill_form(fields[], submit_ref?, submit_selector?)` | Fill many inputs in one call — `type` can be `text`/`check`/`uncheck`/`select` |
| `browser_detect_forms` | List every `<form>` with action, method, and input descriptors |

### Inspection (4)
| Tool | What it does |
|---|---|
| `browser_interactive_elements(limit?)` | List clickable/typeable elements with stable `ref` IDs (`e3`, `e17`, etc.) — call this BEFORE clicking |
| `browser_get_attribute(ref?, selector?, attribute)` | Read one attribute (href, src, value, class, data-*) |
| `browser_count(selector)` | How many elements match a CSS selector — cheap existence probe |
| `browser_extract(schema)` | Structured scrape — `schema: {field: "css_selector"}`. Use `selector@attr` for attribute reads, `field[]` for arrays |

### State (5)
| Tool | What it does |
|---|---|
| `browser_get_cookies(domain?)` | Dump cookie jar, filter by domain optional |
| `browser_set_cookie(name, value, domain, path?, secure?, http_only?)` | Inject one cookie |
| `browser_clear_cookies` | Wipe the jar |
| `browser_storage_state` | Export `{cookies, origins: [{localStorage, sessionStorage}]}` |
| `browser_set_storage_state(state)` | Restore the JSON from above — use this to skip a login on a fresh run |

### Tabs (4)
| Tool | What it does |
|---|---|
| `browser_tab_new(url?)` | Open isolated tab, returns tab_id |
| `browser_tab_list` | List tabs with id/url/title/active |
| `browser_tab_switch(tab_id)` | Make this tab the target of subsequent calls |
| `browser_tab_close(tab_id?)` | Close a tab (active by default) |

## Recommended call patterns

### 1. Read a page cheaply (snapshot only)
```
browser_navigate(url=...)
browser_markdown(max_chars=4000)
```

### 2. Click a button by ref
```
browser_navigate(url=...)
browser_interactive_elements()         # → returns refs like e3, e17
browser_click(ref="e17")
browser_markdown()                     # see what changed
```

### 3. Fill a login form
```
browser_navigate(url=LOGIN_URL)
browser_detect_forms()                 # → learn the form structure
browser_fill_form(fields=[
  {ref: "e3", value: "user@example.com"},
  {ref: "e5", value: "hunter2"},
  {type: "check", ref: "e7", value: true}
], submit_ref="e9")
browser_storage_state()                # save session for next time
```

### 4. Skip a login on next run
```
# First run
browser_set_storage_state(state=<from previous browser_storage_state>)
browser_navigate(url=DASHBOARD_URL)
# Already logged in.
```

### 5. Scrape a list page
```
browser_navigate(url=LIST_PAGE)
browser_extract(schema={
  "titles[]":  "h2 a",
  "urls[]":    "h2 a@href",
  "summaries": "p.lede"
})
```

## Debugging the MCP server itself

If `browser_*` calls hang or error:

```bash
# Probe the server directly
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | obscura mcp

# Run server on HTTP for inspection
obscura mcp --http --port 3000
# then: curl -X POST http://127.0.0.1:3000 -H 'Content-Type: application/json' \
#   -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'

# Increase verbosity
obscura mcp --verbose
```

## Things to remember

- **Refs are scoped to one navigation.** A `ref="e3"` from a `browser_snapshot` is only
  valid until the next `browser_navigate`. Don't cache them across pages.
- **`browser_extract` is the highest-leverage tool** for structured scraping. Use
  schema syntax `field[]` for lists, `selector@attr` for attribute reads.
- **`browser_storage_state` + `browser_set_storage_state` is the right way to
  persist sessions.** Don't try to serialize cookies manually.
- **Tabs are isolated** — each `browser_tab_new` gets its own URL/page state.
  Useful for "I need to keep a comparison page open while I do X on another".
