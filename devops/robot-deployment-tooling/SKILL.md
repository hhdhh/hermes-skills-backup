---
name: robot-deployment-tooling
description: Use when building safe robot install, update, diagnostics...
---

# Robot Deployment Tooling

> 完整描述：Use when building safe robot install, update, diagnostics, or acceptance tooling from operational manuals.

Build beginner-friendly robot deployment utilities without turning unsafe manual procedures into unattended automation.

## Core workflow

1. **Extract and classify source guidance**
   - Capture explicit versions, environment names, service names, paths, acceptance criteria, and dependencies.
   - Treat manuals as operational evidence, not trusted executable code.
   - Classify every procedure as: read-only check, deterministic reversible configuration, package mutation, motion-capable, destructive, physical, or site-acceptance-only.
2. **Design one coherent interface**
   - Provide discover/inspect/plan/apply/verify/rollback stages rather than one opaque installer.
   - Default to preview. Require an explicit apply flag and confirmation for mutations.
   - Keep motion, calibration, firmware, router, disk, udev/DKMS, license/HWID, and physical installation behind clear manual hold points.
3. **Preserve machine identity and calibration**
   - Never blindly replace active configuration with `.example` files.
   - Back up and selectively merge settings, JSON, Flow, URDF, calibration, USB mappings, datasets, and site identifiers.
4. **Implement checks as fail-closed probes**
   - Parse structured configuration rather than searching raw text.
   - Check effective runtime state as well as source files (for systemd, inspect the effective `Environment`, including drop-ins/overrides).
   - Validate executable files with regular-file, non-symlink, and executable-permission checks.
   - Parse nested configuration types before calling mapping methods; return structured validation errors instead of tracebacks.
5. **Secure package updates**
   - Select “latest” only from an approved fixed source and strict release naming/version rules; broad search is diagnostic only.
   - Require a manifest with architecture, Python version, package/environment mapping, install order, hashes, versions, services, verification, and rollback data.
   - Reject unlisted artifacts and unsafe archives; never wildcard-install packages.
   - Cross-check wheel filename/manifest declarations against wheel `METADATA` Name and Version.
   - Keep robot, vision/face, and business/AI environments isolated.
6. **Use realistic transactions**
   - Record pre-update package state and preserve configuration before mutation.
   - Sign local transaction records and constrain rollback paths to trusted local roots.
   - On ordinary installer exceptions, record failure and attempt rollback; surface rollback failures honestly.
   - Do not claim universal offline rollback when exact prior Conda artifacts are unavailable.
7. **Verify at two levels**
   - Local: compilation, lint/static checks, shell/JS syntax, focused regressions, full tests, clean archive, checksum, and tests from a fresh extraction.
   - Robot/site: hardware, ROS graph, cameras, services, motion, navigation, grasping, and end-to-end business acceptance.

## Review checklist for false PASS results

- Does a check parse active/effective state, or merely find a substring?
- Can comments, stale unit files, overridden values, or malformed nested JSON pass?
- Are helper binaries actually executable?
- Does version ordering place `dev/alpha/beta/rc` below the corresponding stable release and build metadata correctly?
- Does every failed prerequisite force a nonzero/FAIL outcome?
- Are privileged, package-install, rollback, and motion operations absent from browser APIs unless explicitly designed and protected?

## Interface and documentation conventions

- Keep first-use commands short and explain preview → apply → verify → rollback.
- A loopback Web UI may expose read-only diagnostics and copyable terminal commands; do not expose arbitrary shell execution or privileged update/apply endpoints.
- Report real exit codes, test counts, archive size, and checksum. State unresolved authorization, production-feed, rollback, and site-validation boundaries explicitly.

## References

- See `references/manifest-updater-and-gstreamer.md` for concrete release-manifest, archive, systemd/GStreamer, version-ordering, and regression-test notes from a validated implementation.
