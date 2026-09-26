# Drive search/list/download contract for agent workflows

Use this when an agent discovers or downloads uploaded files through `lark-cli`.

## Treat the operations independently

| Operation | Typical command | Relevant user scope |
|---|---|---|
| Full-text discovery | `lark-cli drive +search ... --as user --format json` | `search:docs:read` |
| Folder enumeration | `lark-cli drive files list --folder-token ... --page-all --as user --format json` | commonly `space:document:retrieve` |
| Uploaded-file download | `lark-cli drive +download --file-token ... --output ... --as user --format json` | `drive:file:download` |

A user token may support direct download while folder listing is unavailable. Test the exact operation needed; do not infer one capability from another.

If OAuth completion returns `Unable to authorize. The app is pending approval`, this is an application/tenant approval state, not evidence that the user declined. Report the blocker accurately; an administrator must approve/publish the requested capability before a fresh consent flow can succeed.

## Robust direct-download adapter

1. Create a private staging directory under the intended download root.
2. Pass a relative `--output` and run the CLI with `cwd` set to that root.
3. Capture stdout/stderr and require exit code 0.
4. stdout may contain a progress prelude such as `Downloading: ...`; locate the first `{` before JSON decoding.
5. Read `data.saved_path`; accept `data.output_path` only as a compatibility fallback.
6. Resolve the returned path and require it to equal the exact staging target. Reject any outside path—never hash, move, delete, or trust it.
7. Confirm it is a regular file, compute SHA-256, then atomically move it to the final cache location.
8. Independently inspect the artifact; transport authentication alone does not establish package trust.

## Safe release discovery

For software releases, prefer one approved folder token over tenant-wide search. A search hit, chat attachment, or newest modification time is not automatically the latest approved release. Require a deterministic naming/manifest policy and compare authoritative release IDs.

Never embed OAuth tokens, app secrets, passwords, or authorization URLs in project configuration or logs.
