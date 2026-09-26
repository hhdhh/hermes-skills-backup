---
name: transactional-software-updates
description: "Use when building automated software/package updaters."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [software-update, release, manifest, rollback, artifact, supply-chain]
    related_skills: [lark-feishu-cli, test-driven-development, systematic-debugging]
---

# Transactional software updates

Build update workflows that discover artifacts, verify provenance and integrity, install into exact targets, verify the result, and recover honestly when a stage fails.

## When to use

- Automating binary, wheel, Conda, plugin, or application bundle updates
- Downloading releases from Drive/cloud storage, HTTPS, object storage, or an internal registry
- Updating several isolated runtimes where installing a package into the wrong environment is a serious failure
- Adding `discover/download/inspect/plan/apply/verify/rollback` commands

Do not use this workflow for firmware, calibration, disk repartitioning, machine identity, or motion-capable hardware unless a domain-specific updater and on-site safety process exists.

## Trust model

Authentication only proves that the caller may read the storage location. It does **not** prove that the newest-looking file is an approved release.

Require all of the following before installation:

1. A controlled release location (prefer an explicit folder/bucket/repository over global search).
2. Deterministic release identity; never infer semantic version solely from modification time.
3. A machine-readable manifest that names every installable payload.
4. SHA-256 or stronger for every payload, checked after download and before mutation.
5. Explicit target mapping for every package/runtime/environment.
6. Rejection of extra executable/package files absent from the manifest.

## Command model

Expose separate, composable stages:

```text
discover  candidates only; no download or install
download  fetch one selected artifact into isolated staging
inspect   archive safety + schema + file list + hashes
plan      exact targets, versions, commands, services, rollback capability
apply     explicit confirmation; snapshot then mutate
verify    expected versions + health checks
rollback  trusted transaction only; report partial recovery honestly
latest    optional thin orchestration over controlled location + deterministic versioning
```

Default every mutating path to preview. A graphical UI may copy commands, but should not bypass terminal confirmation or expose arbitrary privileged execution.

## Manifest requirements

At minimum, record:

- schema version, release ID, and channel
- each filename, SHA-256, logical package name, expected version, package kind, and exact target environment
- optional source/release metadata for auditability

Validate paths as single safe filenames; reject duplicates, unknown target names, wrong filename suffixes, missing hashes, and duplicate package identities within one environment.

## Archive safety

Before extraction:

- cap compressed bytes, expanded bytes, member count, and compression ratio
- reject absolute paths, `..`, backslash-based traversal, symlinks, hardlinks, devices, and special files
- extract into a fresh staging directory with restrictive permissions
- require exactly one manifest at the expected bundle level
- do not execute scripts found in the archive merely because extraction succeeded

## Transaction order

1. Validate the release and every target before the first mutation.
2. Capture pre-state for each affected environment.
3. Persist and locally sign the transaction record before installation.
4. Stop only explicitly allowlisted services when necessary; record which were active.
5. Install exact files into exact targets—never `pip install *.whl`.
6. Verify installed metadata versions, process/service health, and domain checks.
7. Restart only services that were previously active.
8. Mark completed only after verification passes.
9. On failure, attempt rollback and distinguish `ROLLED_BACK` from `ROLLBACK_FAILED`.

## Rollback honesty

A package list is not automatically a complete rollback artifact.

- `pip freeze` can describe Python state but may require network/index availability and may not restore deleted files, native libraries, or editable installs.
- Conda rollback needs an explicit revision, clone, environment pack, cached artifacts, or exact package URLs; pip-only restore does not recover `.conda` changes.
- A robust updater retains old artifacts or an environment snapshot/clone until post-update acceptance completes.
- Configuration migration should preserve existing values and merge new defaults; never blindly copy `.example` over live configuration.

If full recovery cannot be guaranteed, state the boundary in `plan` and the transaction report instead of promising automatic rollback.

## Verification

Use layered proof:

1. Unit tests for manifest validation, target routing, archive attacks, dry-run semantics, and trusted-transaction rejection.
2. A disposable real install→metadata verify→rollback integration fixture using a tiny local package and isolated environment.
3. Static checks and full regression suite.
4. Target-system acceptance for hardware, services, networking, or business workflows.

Mocked package-manager commands alone are not proof that the update mechanism works.

## References

- `references/manifest-and-rollback.md` — manifest example, release selection rules, archive guards, and rollback capability matrix.
- For Feishu Drive retrieval and OAuth scopes, load `lark-feishu-cli` and read `references/drive-artifact-retrieval.md`.