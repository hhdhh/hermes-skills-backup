# Feishu long-form document authoring and verification

Use this workflow when creating or substantially revising a Feishu Docx through `lark-cli`, especially operational manuals, runbooks, onboarding guides, and release documentation.

## Proven workflow

### 1. Inspect the current document before writing

Prefer an existing document when the user wants the established link, sharing settings, and history preserved.

```bash
lark-cli docs +fetch \
  --doc '<DOC_URL_OR_TOKEN>' \
  --as user \
  --scope outline \
  --max-depth 3 \
  --doc-format markdown \
  --format json
```

Then fetch the full body and record `document_id` and `revision_id`:

```bash
lark-cli docs +fetch \
  --doc '<DOC_URL_OR_TOKEN>' \
  --as user \
  --doc-format markdown \
  --detail simple \
  --format json
```

Before editing, read the CLI's current embedded guidance:

```bash
lark-cli skills read lark-doc
lark-cli skills read lark-doc/references/lark-doc-fetch.md
lark-cli skills read lark-doc/references/lark-doc-update.md
lark-cli skills read lark-doc/references/lark-doc-md.md
```

### 2. Choose targeted edit vs deliberate full replacement

- Use `str_replace` or `block_*` edits when unrelated content, comments, embedded resources, or rich blocks must remain intact.
- Use `overwrite` only when the task explicitly calls for a complete rewrite and the old body has been inspected. It can discard unsupported resources or unrelated material.
- A document update does not authorize a completion DM or chat message. Treat message delivery as a separate side effect requiring its own user request/authorization.

### 3. Author long content in a local file

For long Markdown, avoid inline shell arguments. Create the source file in the command's current working directory and reference it with a relative path:

```bash
lark-cli docs +update \
  --doc '<DOC_URL_OR_TOKEN>' \
  --as user \
  --command overwrite \
  --doc-format markdown \
  --content @./manual.md \
  --revision-id '<OBSERVED_REVISION>' \
  --format json
```

`@file` must be relative to the current working directory; absolute `@/tmp/...` paths are rejected. Keep Markdown escaping intact. Markdown mode may intentionally contain supported DocxXML blocks such as `<title>` and `<callout>`.

Use the observed revision as an optimistic-concurrency guard. Do not assume the returned revision increments by exactly one: a single document update can create several internal revisions.

### 4. Check the write response

A successful response should include:

- `ok: true`
- `result: success`
- the expected document URL/token
- a new `revision_id`
- an empty `warnings` array, or warnings that have been explicitly investigated

The API response alone is not enough; always read the document back.

### 5. Verify structure and required content from Feishu

Fetch the post-write outline:

```bash
lark-cli docs +fetch \
  --doc '<DOC_URL_OR_TOKEN>' \
  --as user \
  --scope outline \
  --max-depth 3 \
  --doc-format markdown \
  --format json
```

Verify key terms and safety gates with a keyword query:

```bash
lark-cli docs +fetch \
  --doc '<DOC_URL_OR_TOKEN>' \
  --as user \
  --scope keyword \
  --keyword 'version|install|rollback|safety phrase' \
  --doc-format markdown \
  --format json
```

Finally fetch the full body and mechanically check all required headings, commands, version/checksum values, safety boundaries, and checklist items. Report the actual revision, heading counts, required-term results, and warnings.

## Verification checklist for operational manuals

Check at minimum:

- title and target software version
- first-time-user quick path
- prerequisites and field definitions
- dry-run/apply semantics and confirmations
- complete command families, not just representative examples
- success criteria and exit-code meanings
- backups, snapshots, rollback, and rollback limitations
- safety hold points and manual boundaries
- troubleshooting for expected operator mistakes
- acceptance checklist
- artifact checksum and real test evidence when applicable
- no passwords, tokens, API keys, licenses, or temporary credentials

## Pitfalls

1. `--detail with-ids` is not supported with Markdown fetch output. Use XML when block IDs are required; otherwise use Markdown without `with-ids`.
2. After structural edits, block IDs and revision semantics may change. Refetch before another block edit.
3. Do not remove Markdown escape backslashes from fetched content before replaying it.
4. Preserve the existing document URL when continuity matters; creating a new document can lose established sharing and references.
5. Never claim publication is complete from a local draft alone. Require a successful write response and Feishu read-back verification.
6. Organization-wide search results are discovery evidence, not automatically trusted release sources. Document source limitations explicitly when an approved folder/feed is unavailable.
