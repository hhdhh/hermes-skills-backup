---
name: secure-package-update-pipelines
description: "Use when building cloud-to-host package update pipelines."
version: 1
metadata:
  hermes:
    tags: [updater, manifest, supply-chain, rollback, archives]
---

# Secure Package Update Pipelines

Build inspectable, manifest-driven software updates from cloud storage, HTTPS, or local release bundles. Use for Conda/pip environments, appliance software, robots, edge nodes, and other hosts where machine-specific configuration and rollback matter.

## Non-negotiable model

Split the updater into explicit phases:

1. **Discover** an approved source.
2. **Download** into private staging.
3. **Inspect** archive structure, manifest, metadata, and hashes.
4. **Plan** exact mutations without performing them.
5. **Apply** only after explicit confirmation.
6. **Verify** versions, imports, services, diagnostics, and acceptance boundaries.
7. **Rollback** from a signed transaction with realistic restoration inputs.

Download is not installation. A successful package-manager exit is not acceptance. A raw filesystem snapshot is not necessarily a package rollback.

## 1. Establish source authority

- Prefer one approved folder/file token, release feed, or manifest URL over unrestricted organization-wide search.
- Never choose “latest” from arbitrary chat attachments, filename lexicographic order, or cloud modification time.
- Require deterministic release IDs and a documented ordering policy. Treat final releases as newer than pre-releases with the same numeric prefix.
- Cloud authentication proves transport access, not package integrity. Require artifact hashes or signatures.
- Keep credentials out of manifests, logs, subprocess arguments where possible, and project files.

## 2. Require a strict release manifest

A release manifest should identify at least:

- schema version, release ID, channel
- target architecture and runtime/Python major.minor
- each artifact’s filename, kind, size, SHA-256, package name, version, target environment, and install order
- affected services and an allowlisted restart policy
- verification expectations
- rollback inputs or declared rollback limitations

Reject unknown target environments, duplicate filenames, duplicate package/environment assignments, missing hashes, unsupported kinds, ambiguous install order, and unlisted installable artifacts.

For wheels, cross-check manifest name/version against `*.dist-info/METADATA` using normalized package names. For other package formats, inspect native metadata where practical rather than trusting filenames alone.

## 3. Harden archive handling before extraction

Reject:

- absolute paths, `..`, backslash traversal, and empty paths
- symlinks and special files
- duplicate paths, case-folded duplicate paths, and file/directory prefix collisions
- excessive members, compressed size, expanded size, nesting, or compression ratios
- multiple manifests when exactly one is required

Validate the complete member table before writing any member. Extract to a private staging directory, never to a shared documents root.

## 4. Preflight every mutation

Before stopping services or installing anything:

- verify all target environment paths and executables
- verify architecture and runtime versions
- verify free disk space and transaction-root permissions
- hash every artifact again
- capture installed package state and required machine-specific configuration
- confirm rollback inputs exist
- validate affected services against a hard allowlist

Default to preview/dry-run. Apply must require a deliberate flag and confirmation. Do not concatenate shell commands; use argument arrays and exact absolute artifact paths.

## 5. Isolate environments and preserve configuration

- Map every artifact to one explicit environment in the manifest and policy.
- Invoke the target environment’s interpreter/package manager directly.
- Never use wildcard installs such as `pip install *.whl` or broad local-package globs.
- Do not execute package-provided shell scripts automatically.
- Do not copy `.example` templates over active configuration.
- Back up and migrate known machine-specific fields explicitly; leave calibration, datasets, flow definitions, credentials, and hardware identity untouched unless a dedicated migration handles them.
- Stop/restart only manifest-declared services intersected with a hardcoded/configured allowlist. Keep motion-capable or disruptive services behind stronger operator gates.

## 6. Record a trustworthy transaction

Store transactions below a private root (permissions no wider than `0700`) with a local key no wider than `0600`.

- Reject symlinked roots, keys, transaction directories, manifests, and rollback inputs.
- Record exact environment executables, pre-update package state, artifact hashes, install results, verification results, and rollback results.
- Sign transaction data (for example HMAC-SHA256) and verify the signature before manual rollback.
- Restrict accepted rollback paths to direct children of the trusted transaction root.

## 7. Make rollback technically honest

For pip-style environments, a freeze file is useful but has limits:

- reinstall exact previous pins with `--no-deps --force-reinstall`
- uninstall target packages that did not exist before the transaction
- catch unexpected installer exceptions, not only anticipated domain errors, and attempt rollback
- report partial rollback when exact artifacts or indexes are unavailable

Conda/native packages may need cached artifacts or explicit revisions. Firmware, OS packages, services, calibration, and data require dedicated rollback mechanisms. Never claim a generic snapshot restored them if it did not.

## 8. Verify beyond installation

Verify:

- expected package versions via package metadata
- required imports
- service states and diagnostics
- configuration preservation/migration
- application-specific smoke tests
- an explicit site-acceptance boundary for hardware, motion, networking, or business workflows

Return nonzero on failed verification. Surface the transaction directory and exact recovery command.

## 9. Test matrix

Use TDD and include:

- missing/malformed manifest, missing hashes, duplicate assignments
- wrong architecture/runtime and unknown environments
- hash mismatch and unlisted artifacts
- traversal, symlink, duplicate path, case collision, prefix collision, zip bomb limits
- package metadata/name/version mismatch
- discovery that refuses to guess latest
- authenticated download whose returned path escapes staging
- dry-run with no writes/installs/service stops
- preflight failure before first mutation
- exact per-environment install commands
- mid-install domain failure and unexpected exception rollback
- signed rollback path/signature tampering
- a real temporary package install, verification, and rollback
- final archive re-extraction followed by the full test suite

## Delivery discipline

Report separately what was verified in a sandbox, through a real cloud download, and on the actual target host. If cloud-folder permissions, release manifests, target hardware, or services are unavailable, disclose that boundary instead of presenting the updater as end-to-end production-validated.

## References

- `references/manifest-archive-rollback-notes.md` — compact manifest example, archive checks, wheel metadata validation, transaction/rollback pitfalls, and acceptance checklist.
