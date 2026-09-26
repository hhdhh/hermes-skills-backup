# Recipe: create a Feishu / Lark Doc from agent-side content

The high-frequency task: "把这个总结做成飞书文档发给我" / "save this to a Lark doc" / "create a Feishu doc with this content". Use `lark-cli docs +create` with `--doc-format markdown` and `--content @file`.

## Pre-flight: confirm identity and scope

```bash
lark-cli auth status     # confirm identity=user (defaultAs) and tokenStatus
lark-cli auth scopes     # confirm docx:document:create is granted
```

If `tokenStatus: needs_refresh`, the next user-API call auto-refreshes — don't manually intervene. If scope is missing, the user must add it in the Feishu app config and re-publish.

## Canonical recipe (5 steps)

### 1. Pick the destination

| User intent | Argument |
|---|---|
| "我的云空间" / "my Feishu" / "my personal space root" | `--parent-position my_library` |
| "放到那个 Wiki / 知识库" | `--parent-token <wiki_node_token>` (ask user for the link/token) |
| "放到那个文件夹" | `--parent-token <folder_token>` (ask user for the link/token) |
| "no preference" | omit both — defaults to wherever `defaultAs` user puts it |

**Never guess the parent.** The `my_library` constant is the only well-known shortcut; everything else needs a token from the user.

### 2. Stage the content in a cwd-relative file

`@file` is **cwd-relative**, not absolute. It rejects paths like `@/tmp/x.md` with `unsafe file path`.

```bash
mkdir -p /tmp/lark-doc-draft && cd /tmp/lark-doc-draft
# write the markdown (use write_file tool, not heredoc)
# then mkdir -p FIRST so the writer tool creates the parent
```

The `mkdir -p` BEFORE the write is important — write_file creates parent dirs, but if you `cd` into a directory that doesn't exist yet, the next `cd` fails. Always `mkdir -p` then `cd`.

### 3. Draft the Markdown content

Use `--doc-format markdown`. The body should:

- Put the title in `--title` (CLI prepends `<title>...</title>` so it wins over any H1 in body).
- Escape `|` inside table cells as `\|`, `$` as `\$`, `<` as `\<`, `` ` `` as `` \` ``, `*` as `\*`. Inside fenced code blocks and inline code, no escaping needed.
- Use 4-column tables with `| --- |` separators.
- ASCII diagrams in fenced code blocks (` ``` `) render fine.

For deeper format reference (escape rules, XML extensions, image syntax): `lark-cli skills read lark-doc/references/lark-doc-md.md` — read this before the first `+create` in a session, the CLI literally says so.

### 4. Dry-run, then create

```bash
# dry-run first — assembles the API request without executing
lark-cli docs +create \
  --doc-format markdown \
  --title "我的文档标题" \
  --content @./draft.md \
  --parent-position my_library \
  --as user \
  --dry-run

# if dry-run looks right, drop --dry-run
lark-cli docs +create \
  --doc-format markdown \
  --title "我的文档标题" \
  --content @./draft.md \
  --parent-position my_library \
  --as user
```

`--as user` is explicit even when it's the default — it makes the intent visible and survives config drift.

### 5. Sanity-check with fetch, then clean up

```bash
# verify the document actually has the structure (tables, code blocks, lists)
lark-cli docs +fetch --doc "<document_id>" --doc-format markdown

# clean up the staging dir
rm -rf /tmp/lark-doc-draft
```

The `+fetch` is a cheap insurance: it catches silent Markdown escaping bugs (a `*` that ate the next word, a `|` that broke the table) before the user opens the doc.

## Output shape

```json
{
  "ok": true,
  "identity": "user",
  "data": {
    "document": {
      "document_id": "Qg1ZdYwNHomR0Sxgh6XcMvlonCd",
      "revision_id": 3,
      "url": "https://autolife.feishu.cn/docx/Qg1ZdYwNHomR0Sxgh6XcMvlonCd",
      "new_blocks": []
    }
  }
}
```

- `revision_id` ≥ 2 is normal — the CLI counts the title-prepend as a revision.
- `url` is the link to give the user. Always inline it in the response.
- `new_blocks` is non-empty only when the doc contains whiteboards / embedded media.

## Pitfalls

### M1: `@file` is cwd-relative, not absolute

```bash
# WRONG — rejected with "unsafe file path"
lark-cli docs +create --content @/tmp/draft.md ...

# RIGHT
mkdir -p /tmp/foo && cd /tmp/foo
lark-cli docs +create --content @./draft.md ...
```

### M2: `mkdir -p` before `cd` before the write

`cd /tmp/lark-doc-draft` fails if the dir doesn't exist. `mkdir -p` then `cd` then write_file. Same as the `lark-feishu-cli` P5 family.

### M3: `--parent-token` and `--parent-position` are mutually exclusive

Pick one. Asking the user "where should this go?" is non-optional — the only safe default is `my_library` when they say "my cloud space" / "我的云空间" / "my personal space root".

### M4: `running` identity gotcha

If `auth status` shows `identity: bot` but the user wants the doc in **their** personal space, the doc lands in the bot's folder, not the user's. Always pass `--as user` when the user implicitly or explicitly means "my personal space". The `defaultAs` setting controls the default but doesn't override `--as`.

### M5: Don't use `docs +create` for updates

For editing an existing doc, use `docs +update` (different flag set, supports `--pattern` for in-place edits). `+create` always makes a new doc.

### M6: Token refresh is automatic, but slow

If `tokenStatus: needs_refresh`, the first user-API call (like `+create`) takes an extra second for the refresh round-trip. Subsequent calls are fast. Don't pre-emptively run `auth login` to "warm up" — just run the real call.

### M7: lark-cli surfaces a `_notice` block with every response

```json
"_notice": { "update": { "latest": "1.0.88", "current": "1.0.87", "message": "..." } }
```

This is informational, not an error. Don't react to it in the response — the user doesn't care about CLI version drift mid-task. Same family as `_notice.rate_limit` etc.
