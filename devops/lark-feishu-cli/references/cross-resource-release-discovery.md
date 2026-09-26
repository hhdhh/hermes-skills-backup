# Cross-resource release discovery in Feishu

Use this when a Feishu manual says “find the latest package in the update group/cloud drive” but does not provide one stable download URL. The goal is to resolve **documentation → version authority → release source → downloadable artifact** without scraping browser cookies or persisting an operator’s credentials on the target machine.

## 1. Follow citations before searching broadly

A fetched Docx may contain a citation such as:

```xml
<cite doc-id="..." file-type="sheets" title="..." />
```

Treat the cited Sheet as the version authority. Resolve and inspect it using the authenticated CLI:

```bash
lark-cli drive +inspect --url 'https://<tenant>/sheets/<token>' --as user --format json
lark-cli sheets +workbook-info --url 'https://<tenant>/sheets/<token>' --as user --format json
```

Then read each relevant worksheet. Use exact sheet IDs or names returned by `+workbook-info`:

```bash
mkdir -p /tmp/lark-release-discovery
cd /tmp/lark-release-discovery
lark-cli sheets +cells-get \
  --url 'https://<tenant>/sheets/<token>' \
  --sheet-id '<sheet_id>' \
  --range 'A1:U500' \
  --include value \
  --output-path ./version-table.json \
  --as user --format json
```

`--output-path` must be relative to the current directory; absolute output paths are rejected by the CLI safety guard. Check the receipt’s `complete=true` before trusting the file.

Extract at least: package/application name, approved version, release address, target environment, and any notes. Do not infer “latest” from a filename alone when an authoritative version table exists.

## 2. Search Drive only with the needed scope

`drive +search` requires `search:docs:read`. If the CLI reports `missing_scope`, request exactly that scope with the normal device-flow handoff:

```bash
lark-cli auth login --scope 'search:docs:read' --no-wait --json
```

Display the returned verification URL and a QR code, then end the turn. After the user confirms authorization, complete it with the returned device code. Do not broaden scopes pre-emptively.

Search narrowly and sort by edit time:

```bash
lark-cli drive +search \
  --query '<package-or-bundle-name>' \
  --doc-types file \
  --sort edit_time \
  --page-size 20 \
  --as user --format json
```

A search result is a candidate, not proof of approval. Cross-check it against the version table and source allowlist.

## 3. Search IM when the manual points to an update group

A Drive search does not replace message search. Use IM search for release announcements, links, and attached files:

```bash
lark-cli im +messages-search \
  --query '<package-or-version>' \
  --include-attachment-type file \
  --page-all --page-limit 20 --page-size 50 \
  --as user --no-reactions --format json
```

For links, use `--include-attachment-type link`. If a result identifies a relevant chat and time window, inspect that bounded context with `im +chat-messages-list`; do not dump an entire unrelated chat history.

Download a message attachment with the message-resource shortcut, or a Drive file with:

```bash
lark-cli drive +download --file-token '<token>' --output ./artifact.zip --as user
```

Inspect each command’s `--help` first because attachment resources and Drive file tokens are different object types.

## 4. Safe updater boundary

Do **not** embed Feishu cookies, OAuth refresh tokens, app secrets, or a human account’s credential files into a robot updater. Prefer one of these models:

1. Operator performs an authenticated, interactive fetch; the robot updater consumes the downloaded bundle.
2. CI/release automation publishes a signed manifest plus artifacts to a machine-scoped repository.
3. A short-lived, least-privilege download token is supplied at runtime and removed after use.

Before installation, require a manifest that pins artifact name, size, SHA-256, package version, target environment, and installation order. “Newest modified file” alone is not a safe release policy.

## Verification checklist

- The Doc citation was resolved to the intended Sheet.
- `+cells-get` receipt says `complete=true`.
- Approved package/version rows were extracted from the version authority.
- The artifact source matches an allowlisted host or authenticated Feishu resource.
- The downloaded artifact’s size and SHA-256 match a trusted manifest.
- No browser cookie, OAuth token, app secret, or raw private chat dump was copied into the target project or logs.
