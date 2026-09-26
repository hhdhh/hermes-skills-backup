# Safe Drive artifact retrieval

Use this when an automated workflow must locate and download release bundles or other binary artifacts from Feishu Drive.

## Scope matrix

| Step | Preferred command | Read scope |
|---|---|---|
| Broad discovery | `lark-cli drive +search` | `search:docs:read` |
| Controlled folder listing | `lark-cli drive files list` | `space:document:retrieve` |
| File download | `lark-cli drive +download` | `drive:drive:readonly` |

Inspect current CLI help/schema before requesting scopes because endpoint requirements can evolve. Request the union once rather than interrupting a workflow with repeated consent rounds.

## Workflow

1. Prefer a user-provided, controlled release folder token over tenant-wide search.
2. List the folder (recursively if the release process uses subfolders) and retain file token, exact name, type, and modification metadata.
3. Apply a release naming policy; never treat modification time alone as the software version.
4. Download with the file token into an isolated staging directory.
5. Run `lark-cli` with `cwd` set to that directory and pass a relative output path such as `./release.zip`. Absolute outputs are intentionally rejected.
6. Verify the downloaded artifact independently: expected extension, size cap, cryptographic hash, archive safety, and a signed or trusted manifest before execution or installation.
7. Treat search results as candidates, not trusted releases. An empty search is inconclusive; it may reflect indexing, tokenization, or access boundaries.

## OAuth handoff

```bash
lark-cli auth login \
  --scope 'search:docs:read,space:document:retrieve,drive:drive:readonly' \
  --no-wait --json
```

Generate and display the QR code, end the turn, then complete with `--device-code` only after the user confirms authorization. See `references/oauth-device-flow-handoff.md`.

## Security boundary

Drive authentication establishes access, not software trust. Never auto-install the newest-looking ZIP. Require a controlled folder plus deterministic release identity and an internal manifest containing exact target, version, and SHA-256 for every payload. Reject extra executable/package files that are absent from the manifest.