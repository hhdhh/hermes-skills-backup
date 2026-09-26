# Rich Feishu Docx authoring and verification

Use this recipe when creating or substantially rewriting a Feishu Docx from structured source material, especially operational guides, SOPs, runbooks, and beginner manuals.

## Command routing

- The document domain is `lark-cli docs`, **not** `lark-cli docx`.
- Prefer shortcuts: `docs +create`, `docs +fetch`, `docs +update`, and `docs +script`.
- Before authoring, read the CLI-bundled `lark-doc` skill and only the references needed for the chosen path. These are version-matched to the installed CLI:

```bash
lark-cli skills read lark-doc
lark-cli skills read lark-doc/references/lark-doc-create-workflow.md
lark-cli skills read lark-doc/references/lark-doc-xml.md
lark-cli skills read lark-doc/references/lark-doc-create.md
# Read lark-doc-update.md only if an edit/fix is needed.
```

## Tested creation workflow

### 1. Choose the reader contract before writing

For operational documentation, use the SOP/runbook contract rather than a feature catalog. Organize around the reader's task:

1. Audience, goal, applicable version, and safety boundary on the first screen.
2. Fastest safe first-use path.
3. Prerequisites and permissions.
4. One action per step, immediately followed by an observable result or pass criterion.
5. Put warnings and hold points **before** dangerous commands.
6. Separate automated checks from required physical/manual acceptance.
7. Include failure handling, rollback boundaries, exit/status meanings, and known limitations.
8. End with an actionable checklist when sign-off is required.

### 2. Initialize a dedicated draft workspace

```bash
lark-cli docs +script --command init-draft \
  --presentation-decision '<complete JSON decision>' \
  --format json
```

Record `data.workspace` and `data.draft_path` exactly. Keep the same current working directory. The returned draft path does not exist yet; create it directly.

### 3. Write one complete DocxXML release candidate

Use XML for rich manuals requiring callouts, tables, checkboxes, headings, and code blocks. The document should begin with one `<title>`. Keep heading levels continuous. Pass local content as a relative `@./...` path from the current working directory; absolute `@file` paths are rejected as unsafe.

Prefer explicit user identity for user-owned documents:

```bash
--as user
```

Continue with `--as bot` only when the token originated from an established bot-identity chain.

### 4. Parse before publishing

```bash
lark-cli docs +script --command parse \
  --content '@./<draft_path>' \
  --format json
```

A top-level `ok: true` is not enough. Require `data.assessment.status == "passed"`. Fix only the reported region unless the draft is empty or structurally invalid.

### 5. Create once

```bash
lark-cli docs +create --as user \
  --doc-format xml \
  --content '@./<draft_path>' \
  --format json
```

Capture `data.document.document_id` and `data.document.url`. Inspect `data.warnings` even when `ok` is true.

### 6. Repair the same document, never create a duplicate

If creation succeeds with a warning, minimally fix the local draft and update the already-created document. For a brand-new document whose entire body is still controlled by this draft, `overwrite` is acceptable:

```bash
lark-cli docs +update --as user \
  --doc '<existing URL or token>' \
  --command overwrite \
  --doc-format xml \
  --content '@./<draft_path>' \
  --format json
```

For any pre-existing or collaboratively edited document, fetch first and use targeted `str_replace` or `block_*` operations; do not overwrite unrelated content.

### 7. Fetch and verify the rendered source

```bash
lark-cli docs +fetch --as user \
  --doc '<URL or token>' \
  --scope full \
  --detail with-ids \
  --doc-format xml \
  --format json
```

Verify all of the following before claiming completion:

- `ok == true` and the expected document ID/revision are returned.
- Title and required section sentinels exist.
- Safety warnings, command blocks, acceptance/checklist items, and final limitations survived import.
- The create/update response has no unexplained warnings or partial-success state.
- For long documents, parse the JSON and check sentinels/counts programmatically instead of eyeballing one long XML string.

### 8. Clean only the generated workspace

After successful verification—or after a blocked/failed attempt—delete exactly the `data.workspace` directory returned by `init-draft`. Do not use wildcards and do not delete source materials.

## Version-sensitive pitfall observed with CLI 1.0.87

A document created successfully but returned a degradation warning for `seq` on an `<ol>` element. Removing the list-level `seq` attribute and updating the same document produced a warning-free result. Treat this as version-sensitive: always follow the installed CLI's current XML reference and service warnings rather than assuming a locally parsed attribute will be accepted remotely.

## Completion standard

Do not report only that the API call succeeded. Deliver the actual Feishu URL and state that the document was fetched back and checked. If a warning cannot be removed, disclose it and its concrete effect instead of calling the document fully verified.
