---
name: feishu-document-authoring
description: Use when creating or publishing a Feishu cloud document f...
version: 1.0.0
author: hermes-agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [feishu, lark, docs, authoring, xml, markdown, verification]
    related_skills: [lark-feishu-cli, google-workspace]
---

# Feishu document authoring

> 完整描述：Use when creating or publishing a Feishu cloud document from supplied notes. Author structured, actionable content, validate it, publish it, and read back the result.

Use this class-level skill when the user asks to write, organize, publish, or verify a Feishu/Lark cloud document from notes, procedures, troubleshooting material, or other source content.

## Core principles

1. **Write for the reader's task.** Start with audience, goal, prerequisites, scope, and the shortest useful path. For operational material, organize by symptom or task, not by the order in which the author remembered facts.
2. **Preserve user facts literally.** Keep file paths, URLs, configuration keys, ports, versions, commands, and quoted values exactly as supplied unless the user explicitly asks for normalization. If a value is a placeholder (for example, an IP to be supplied by operations), label it rather than inventing it.
3. **Make procedures executable.** Put one action per step, show the expected observable result, and finish with a verification checklist. Separate examples from instructions.
4. **Use Chinese formal numbering when the source uses it.** Prefer `一、`, `二、`, then `1.`, `2.`; do not mix a Chinese heading hierarchy with decimal headings such as `1.1`.
5. **Keep visuals subordinate to meaning.** Use headings, paragraphs, code blocks, lists, tables, and callouts only when they lower reading or execution cost. A callout should carry a real warning or important constraint, not decoration.

## Required publishing workflow

### 1. Check the CLI and identity

Use the Feishu China CLI (`lark-cli`, from `@larksuite/cli`) and explicitly use `--as user` for user-owned documents. Do not expose app secrets or tokens in output. Inspect `lark-cli docs +create --help` if flags are unclear.

### 2. Follow the authoring workflow for non-trivial documents

For a document created from notes rather than an already complete file, use the CLI's embedded authoring guidance:

```bash
lark-cli skills read lark-doc
lark-cli skills read lark-doc/references/lark-doc-create-workflow.md
```

Choose the appropriate content contract (usually knowledge/reference or workplace/SOP), decide the presentation mode, and initialize a draft workspace:

```bash
lark-cli docs +script --command init-draft \
  --presentation-decision '<complete JSON decision>' --format json
```

Record the returned `data.workspace` and `data.draft_path`. Write the release candidate directly to the returned draft path; do not pre-create another temporary workspace.

### 3. Author the release candidate

Use XML for semantic authoring when rich structure is useful. Before writing XML, read the matching syntax reference:

```bash
lark-cli skills read lark-doc/references/lark-doc-xml.md
```

The XML should normally contain one `<title>`, then continuous heading levels, prose, lists or `<ol>`, fenced code represented by `<pre><code>...</code></pre>`, and a final verification section. Escape XML text (`&lt;`, `&gt;`, `&amp;`) but never escape tags. For literal configuration, preserve indentation and quote characters inside `<code>`.

Markdown is acceptable for explicitly requested Markdown or simple import. Read its reference first and use a relative `@./...` file path; do not pass absolute paths to `@file`.

### 4. Profile-check before publishing

Run the parser against the exact candidate:

```bash
lark-cli docs +script --command parse \
  --content '@./<draft_path>' --format json
```

Require `data.assessment.status` to be `passed`. Fix diagnostics locally before publishing. A successful command (`ok: true`) alone is not enough.

### 5. Create once, then verify by read-back

Publish only the latest validated candidate:

```bash
lark-cli docs +create --as user --doc-format xml \
  --content '@./<draft_path>' --format json
```

Record the returned document URL and inspect warnings. Then read the exact created document back:

```bash
lark-cli docs +fetch --as user \
  --doc '<returned URL>' --doc-format xml --detail simple --format json
```

Verify `ok: true`, the expected title, and the key user-supplied configuration facts. Do not claim success from the create response alone.

### 6. Clean up safely

After verification, remove only the task's returned draft workspace, not any user source files. Verify that the workspace no longer exists. If publishing failed, retain enough error detail to report the blocker honestly; never fabricate a document URL.

## Operational-document content pattern

For troubleshooting or deployment notes, use this structure where applicable:

- Scope and audience
- Safety/backup warning
- `一、` symptom or task group
- Exact file path
- Existing value
- Replacement value or transformation
- Required restart/reload
- Observable validation command or UI check
- Known ambiguity labeled as an assumption or value to obtain from operations
- Final checklist

When showing a JSON/YAML/TOML change, include the smallest relevant snippet and explicitly call out what must remain unchanged (for example, protocol, port, path, or surrounding structure).

## Pitfalls

- Do not create a cloud document before the draft has passed the profile check.
- Do not create multiple documents to repair a local content issue; after creation, use the update workflow and fetch for repair/verification.
- Do not replace unknown environment values with plausible examples. Keep placeholders explicit.
- Do not rely on a URL existing in the source notes as proof that a service is online; a document may link to a dashboard, but live status requires a separate check.
- Do not leave task draft directories behind, and do not use wildcard deletion.

## Supporting references

- `references/operational-document-example.md` — condensed, reusable pattern for turning robot/system troubleshooting notes into a verified Feishu document.
