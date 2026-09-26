# Manifest and rollback reference

## Minimal manifest

```json
{
  "schema_version": 1,
  "release_id": "product-2026.08.18",
  "channel": "stable",
  "packages": [
    {
      "filename": "example_pkg-2.3.0-py3-none-any.whl",
      "sha256": "<64 lowercase hex>",
      "environment": "runtime_a",
      "name": "example-pkg",
      "version": "2.3.0",
      "kind": "wheel"
    }
  ]
}
```

Use a project-specific allowlist for `environment`; do not accept arbitrary filesystem paths from the manifest.

## Release selection

Recommended release file naming:

```text
product-release-<release_id>.zip
```

Parse and compare the release ID under a documented policy. Modification timestamp is display/audit metadata, not version order. A global cloud search returns candidates only. Automatic `latest` selection requires a controlled location and release-policy-compliant names.

## Archive rejection checklist

- compressed size and expanded-size limits
- member-count limit
- compression-ratio limit
- absolute or parent-relative paths
- Windows backslash traversal normalized before checking
- symlink, hardlink, FIFO, socket, device, or other special-file entries
- more than one manifest
- package/executable files absent from the manifest
- filename/suffix inconsistent with package kind

## Rollback capability matrix

| Change | Minimum evidence | Strong rollback |
|---|---|---|
| Python wheels | `pip freeze --all` + old artifacts | cloned/packed environment or retained wheels + uninstall-new-package set |
| Conda packages | explicit package list/revision | environment clone/pack or `conda list --revisions` rollback with cached packages |
| Native service binary | old binary + metadata | atomic A/B directories with symlink switch |
| Live config | pre-write backup | schema-aware reversible migration plus signed backup |
| Service state | active/enabled state | restore exactly the pre-update state |
| Firmware/hardware | vendor recovery image | domain-specific supervised recovery; never generic package rollback |

Do not label a transaction `ROLLED_BACK` unless every affected change class was restored and verification passed. Otherwise use `ROLLBACK_FAILED` or `NEEDS_ATTENTION` and preserve evidence.

## Integration fixture

For a wheel updater, create a tiny local package in a temporary directory, build a wheel, install it into an isolated venv with the same command shape as production, verify `importlib.metadata.version`, then invoke rollback and verify the pre-state. This catches command-line, path, metadata-name, and uninstall/restore defects that mocks cannot.