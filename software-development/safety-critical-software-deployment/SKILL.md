---
name: safety-critical-software-deployment
description: Use when deploying software to robots or safety-critical...
version: 1
metadata:
  hermes:
    tags: [deployment, robots, edge, manifests, rollback, systemd, supply-chain]
---

# Safety-critical software deployment

> 完整描述：Use when deploying software to robots or safety-critical edge systems.

Build, review, or operate software updates for robots and other edge systems where an incorrect package, stale configuration, false-positive verification, or incomplete rollback can affect hardware or business workflows.

## Trigger

Use this skill when a task includes any of the following:

- Updating wheel/Conda packages across named runtime environments
- Fetching a “latest” release from Drive, object storage, HTTPS, or an internal portal
- Installing native runtime trees under `/opt` or application bundles under a managed directory
- Updating user/system systemd services or their environment
- Preserving machine-specific JSON/TOML/YAML, calibration, models, datasets, licenses, USB bindings, or databases
- Turning an operational manual into automation for a robot or appliance

For Feishu OAuth and Drive commands, also load `lark-feishu-cli`. For system package installation requiring user sudo, also load `linux-desktop-system-config`.

## Non-negotiable rules

1. **Treat manuals as evidence, not executable scripts.** Classify each instruction as safe automation, read-only verification, or mandatory human action before coding.
2. **Default to preview.** Download may create a staging file when explicitly requested; package or system mutation requires a separate apply gate and confirmation.
3. **Never infer “latest” from modification time or unrelated search results.** Use a fixed approved source and a parseable release identifier.
4. **Never install with globs.** Every artifact must be named, hashed, assigned to a target, ordered, and verified in a release manifest.
5. **Do not execute package-provided shell scripts by default.** A manifest may choose a predefined handler, never an arbitrary shell command or arbitrary destination path.
6. **Preserve machine state.** Do not replace active configuration, calibration, URDF, datasets, license paths, USB addresses, or databases with `.example` files.
7. **Verification must test effective state.** A file containing the right text is not proof that the service or process received it.
8. **Rollback claims must match reality.** A snapshot or `pip freeze` is evidence, not necessarily an exact offline rollback.
9. **Motion, firmware, DKMS, reboot, database migration, and hardware binding remain attended unless a separately reviewed procedure explicitly permits automation.**

## Workflow

### 1. Gather and classify source material

Fetch the current revision of every referenced manual and release table. Record the revision or source identifier in the working report, not persistent memory.

For each manual step, assign one class:

- **Automate:** deterministic, bounded, reversible, and covered by tests
- **Verify only:** safe to inspect but unsafe to mutate automatically
- **Human:** destructive, interactive, secret-bearing, hardware-specific, motion-capable, or without a rollback contract

Do not silently convert an unsafe manual command into automation merely because it is easy to script.

### 2. Establish release authority

Accept one of:

- A fixed approved Drive folder/file identity
- A pinned HTTPS origin plus an externally trusted hash/signature
- A local bundle explicitly supplied by the operator

Broad organization search may display candidates, but must not choose an installable “latest” release. Standardize release names, for example `product-release-<release_id>.zip`, and compare the parsed release ID rather than timestamps.

A hash stored only inside the downloaded archive protects against accidental corruption, not publisher substitution. Prefer a detached signature, pinned signer, trusted external hash, or approved immutable source identity.

### 3. Require a strict manifest

A release manifest should include:

- Schema version, release ID, channel
- Target architecture and runtime/Python ABI
- Artifact filename, byte size, SHA-256, type, logical name, version, target, and install order
- Affected services and required operator preconditions
- Import/version/runtime verification expectations
- Configuration migration policy
- Rollback artifacts or exact prior-state requirements
- Site-acceptance boundary

Reject duplicate logical package identities, duplicate filenames, unknown environments/targets, unknown artifact types, and unlisted installable artifacts.

### 4. Inspect archives before extraction

Reject:

- Absolute paths, `..`, backslash traversal, or paths resolving outside staging
- Symlinks and special files
- Duplicate and case-fold-colliding paths
- File/directory prefix collisions
- Excessive entry count, compressed size, expanded size, or compression ratio
- Multiple or missing manifests
- Nested archives unless a specific bounded handler exists

Extract only into a newly created private staging directory. Never trust a downloader-reported path unless it equals the expected staging target.

### 5. Cross-check artifact identity and compatibility

For wheels, read `.dist-info/METADATA` and compare normalized `Name` plus exact `Version` with the manifest. Also validate filename/platform tags when relevant.

Before mutation, verify:

- Host architecture matches the release
- Target environment exists and has the required executable runtime
- Runtime major/minor or ABI matches
- The artifact is assigned to the correct environment
- Disk space is sufficient
- Required services are safely stopped or an attended stop plan exists

Version ordering must treat `dev`, `alpha`, `beta`, and `rc` as prereleases. Never use raw lexicographic comparison that can make `rc1` appear newer than a stable `+buildN` release.

### 6. Preserve configuration deliberately

Before package mutation, inventory active machine-specific files and identify which package owns their templates. Use one of:

- **Preserve unchanged** when the new release remains compatible
- **Structured merge** of explicitly allowed keys with backups
- **Human migration** when semantics are unclear

Never delete or replace active configuration merely because a new `.example` exists. Keep secrets out of logs, reports, manifests, and generic snapshots.

### 7. Apply through predefined handlers

Examples of acceptable handlers:

- Wheel → exact environment Python: `python -m pip install --no-deps <exact file>`
- Conda → exact prefix and exact local artifact, with an explicit offline policy
- Managed runtime tree → versioned staging directory, validated file tree, atomic symlink switch, and retained previous target
- Systemd drop-in → generated from allowlisted keys, backed up, syntax checked, daemon-reloaded, and verified through effective state

Handlers must not accept manifest-provided shell fragments. Native application bundles, interactive installers, database migrations, APT/DKMS, and reboot remain manual until a handler has a complete trust, backup, migration, rollback, and verification contract.

### 8. Verify effective state

Package verification:

- Metadata version in the exact environment
- Required imports or health probes
- Service state after an attended restart

Systemd environment verification requires both:

1. Parse active `Environment=` assignments, ignoring comments and invalid lines.
2. Read the effective value with `systemctl show <unit> --property=Environment --value` (and account for drop-ins/overrides).

A substring found in a commented line, an overridden base unit, or an unrelated directive must never produce PASS.

Hardware and application verification should return structured checks and a nonzero status when unmet. Keep site acceptance explicit for camera streams, ROS graph, navigation, grasping, audio/video, and complete business workflows.

### 9. Transaction and rollback

Create a private transaction root (0700) and a local signing key (0600, ordinary non-symlink file). Sign transaction records after every state transition.

Capture exact pre-update artifacts whenever possible:

- Wheel cache or exact previous artifact
- Conda explicit spec plus local package artifacts
- Backed-up configuration with checksums
- Previous managed-tree target

`pip freeze` can assist rollback but may require network access and is not an exact artifact backup. Report rollback as `ROLLED_BACK`, `ROLLBACK_FAILED`, or `PARTIAL`; never claim success merely because a restore command ran.

### 10. UI and operator boundary

A browser UI may expose read-only inspection, previews, and copyable terminal commands. It must not expose package apply, rollback, privileged writes, arbitrary shell execution, service restart, reboot, or robot motion endpoints.

## TDD and verification matrix

Write failing tests first for:

- Manifest omissions, duplicates, unknown targets/types, and hash mismatch
- Wheel metadata mismatch and architecture/runtime mismatch
- ZIP traversal, symlink, duplicate/case collision, file-directory collision, bomb limits
- “Latest” selection, including prerelease ordering and unrelated recent files
- Downloader staging-path escape and cleanup
- Environment isolation and install order
- Dry-run non-mutation
- Failure and unexpected-exception rollback
- Tampered transaction/signature/path/symlink trust
- Configuration preservation and migration refusal
- Systemd comments, wrong values, drop-in/effective-value mismatch
- Low application versions and prerelease versions
- Web UI absence of apply/install endpoints
- Real subprocess installation and rollback in a sandbox

Before delivery run compile, unit/integration tests, lint, shell syntax/static checks, UI syntax checks, live loopback UI smoke tests, and then re-extract the final archive and rerun the test suite from the artifact.

## Reference

- `references/robot-edge-release-case-study.md` — condensed field example covering a GStreamer/robot update manual, safe automation boundaries, effective systemd checks, and release-contract gaps.
