---
name: remote-readonly-artifact-transfer
description: Use when retrieving code/artifacts over SSH without chang...
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [SSH, read-only, artifact transfer, packaging, checksums, verification]
    related_skills: [codebase-inspection, github-repo-management]
---

# Remote Read-Only Artifact Transfer

> 完整描述：Use when retrieving code/artifacts over SSH without changing the source machine; package, checksum, and verify locally.

Retrieve a named source file or small artifact from a remote Linux host over SSH while preserving the remote machine and source content. Use this when the user asks to find, download, package, or send code from a host and explicitly requires read-only handling.

## Core invariants

1. Confirm the exact remote path before transferring; do not guess among similarly named files.
2. Use read-only remote operations only: `find`, `stat`, `sha256sum`, `base64`, and text inspection are acceptable. Do not run the target program, install dependencies, generate files, or edit configs.
3. Treat compilation checks as potentially state-changing. `python -m py_compile` can create `__pycache__`; under a strict read-only requirement, compile the transferred content locally or use an in-memory compile check (`compile(source, filename, 'exec')`) remotely.
4. Preserve bytes exactly. Do not normalize line endings, rewrite encoding, format, or “fix” the source during transfer.
5. Verify after packaging: archive listing, extracted-file checksum, byte count, and a readable README containing source path and checksum.
6. Never persist the remote password in scripts, archives, README files, logs, or skill references. Prefer an interactive password prompt; if automation is necessary, use a transient in-memory prompt mechanism and delete temporary helpers afterward.

## Workflow

### 1. Discover and identify

Use SSH to find the exact filename in bounded, expected roots, then inspect it with `stat` and compute a source SHA256. Record:

- remote host and exact path
- byte size and modification time
- source permissions if relevant
- source SHA256

If multiple candidates exist, report them and ask which one to transfer rather than silently selecting one.

### 2. Inspect dependencies without executing the artifact

Read imports and referenced local filenames with non-mutating commands such as `grep`, `sed`, or a small parser. Find companion files in the same directory and relevant bounded roots. Clearly distinguish:

- files actually transferred
- files referenced by the script but not included
- runtime packages/configuration required for full execution

Do not claim the standalone file is a complete runnable bundle unless all required companions have been identified and included.

### 3. Transfer bytes safely

For a single text/binary file, stream it over SSH using base64 and decode locally, or use `scp` when available. Base64 is useful when password automation or transport logging must be controlled, but strip only transport whitespace before decoding; never alter decoded bytes.

For a package, create the archive locally after download. Include the original basename and a concise README. Avoid creating a tarball remotely when the user says the source machine must remain unchanged.

### 4. Verify locally

Run all of the following locally:

```bash
tar -tzf artifact.tar.gz
sha256sum -c artifact.sha256
# independently compare the checksum of the file extracted from the archive
```

For Python, syntax-check the extracted file locally. If the user asked for a strict remote read-only operation, mention that any local `__pycache__` is local and separate from the source host.

### 5. Deliver and explain usage

Return a Markdown link to the absolute local archive path. State what is inside, the exact source path, byte count, checksum, and what was not transferred. Give a safe usage progression:

1. unpack;
2. verify checksum;
3. run `--help`;
4. run dry-run/test mode if supported;
5. only then explain real execution and its possible side effects.

Do not imply that a script can run on a different machine merely because it was transferred; call out missing frontend files, SDKs, system packages, credentials, or configs.

## Pitfalls

- `py_compile` is not strictly read-only on the remote host because it may create `__pycache__`.
- A successful SSH command is not proof of an intact transfer; verify bytes independently.
- A tarball checksum alone verifies the archive, not necessarily the source file inside it; include and verify the inner file checksum.
- `find` across `/` can be slow and can expose unrelated files; use bounded roots first and expand only when needed.
- Help output can reveal the operational scope of a script, but it is not a safe substitute for a dry run.

## Support reference

See `references/readonly-transfer-checklist.md` for a compact checklist and verification recipe.
