# Manifest, archive, transaction, and rollback notes

## Minimal release-manifest shape

```json
{
  "schema_version": 1,
  "release_id": "product-2026.08.18",
  "channel": "stable",
  "architecture": "x86_64",
  "python_version": "3.12",
  "packages": [
    {
      "filename": "example_pkg-2.3.1-py3-none-any.whl",
      "kind": "wheel",
      "sha256": "<64 lowercase hex>",
      "name": "example-pkg",
      "version": "2.3.1",
      "environment": "runtime_env"
    }
  ]
}
```

Treat this only as a minimum. Production manifests often need sizes, install order, service impact, required imports, signatures, configuration migrations, and rollback artifacts.

## Archive validation order

1. Bound compressed file size.
2. Read the complete member table without extracting.
3. Normalize separators and reject absolute/parent paths.
4. Reject symlinks/special files from mode bits.
5. Case-fold member paths; reject duplicates and file/directory prefix collisions.
6. Bound member count, cumulative expanded bytes, individual/cumulative compression ratios, and nesting.
7. Only then extract to private staging with controlled modes.
8. Require exactly one manifest and reject installable artifacts not listed in it.

## Wheel cross-check

Open the wheel as ZIP, require exactly one `*.dist-info/METADATA`, parse RFC-style headers, and require:

- normalized `Name` equals manifest package name (`[-_.]+` collapse to `-`, lowercase)
- `Version` exactly equals manifest version
- artifact SHA-256 equals the manifest hash

This prevents a correctly hashed but incorrectly described artifact from being routed to the wrong environment.

## Transaction design

A transaction record should include:

- release ID and source identifier
- exact artifact paths/hashes and target environments
- exact interpreter/package-manager paths
- pre-update package state and copied rollback artifacts
- each install command result
- verification results
- rollback attempts/results and final status

Write atomically, permissions `0600`, under a non-symlink transaction directory no wider than `0700`. Sign records using a local `0600` key. On rollback, accept only direct children of the trusted transaction root and revalidate every referenced path.

## pip rollback nuance

`pip freeze --all` is not a complete offline rollback guarantee. It can restore exact pins only if the required distributions remain obtainable. For stronger rollback, cache prior wheels or maintain an approved internal immutable package index.

When restoring from a freeze:

1. reinstall exact prior pins with `--no-deps --force-reinstall -r before.txt`
2. uninstall update-target packages absent from `before.txt`
3. verify the restored versions
4. report partial rollback if any distribution is unavailable or any command fails

Conda revisions/artifacts, APT packages, firmware, configuration migrations, and data need dedicated rollback inputs.

## Acceptance checklist

- [ ] Source is approved and latest-selection policy is deterministic
- [ ] Manifest schema, hashes, metadata, architecture, and runtime match
- [ ] Dry-run shows exact environments, files, and commands
- [ ] Configuration/calibration/data preservation is explicit
- [ ] Apply requires confirmation
- [ ] Transaction record is private and signed
- [ ] Version/import/service checks pass
- [ ] Failure and unexpected-exception rollback tests pass
- [ ] Final deliverable is re-extracted and retested
- [ ] Hardware/business/site acceptance remains clearly separated from sandbox verification
