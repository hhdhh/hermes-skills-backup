# Read-only transfer checklist

## Before transfer

- [ ] Confirm host, user, exact filename, and bounded search roots.
- [ ] `stat` the selected source and calculate its source SHA256.
- [ ] Inspect imports and local references without executing the artifact.
- [ ] Decide whether companions are needed; do not silently omit required runtime files.

## Transfer

- [ ] Stream or copy bytes; package on the receiving machine.
- [ ] Preserve basename and bytes exactly.
- [ ] Do not run the target script, install dependencies, or write on the source host.
- [ ] Avoid remote `py_compile`; it can create `__pycache__`.

## Verification

```bash
tar -tzf artifact.tar.gz
tar -xOzf artifact.tar.gz source.py | sha256sum
sha256sum source.py
sha256sum -c artifact.sha256
```

The source SHA256, decoded local file SHA256, and extracted archive member SHA256 should all match. Report the byte count and exact source path.

## Handoff

- Link the absolute local archive path.
- List archive members.
- Explain missing companions and runtime prerequisites.
- Teach usage in the order: unpack → checksum → `--help` → dry-run/test → real execution.
