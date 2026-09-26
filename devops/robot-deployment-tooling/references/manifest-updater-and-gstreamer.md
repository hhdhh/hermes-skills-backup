# Manifest updater and GStreamer readiness notes

## Release source and manifest

- Automatic latest selection requires an approved fixed folder/feed and strict names such as `autolife-release-<release_id>.zip`; never infer latest from arbitrary search hits or modification time.
- Require one `release.json` with architecture, Python major.minor, package filename/hash/name/version/kind/target environment, install order, affected services, expected verification, and rollback data.
- Install only explicitly listed artifacts with exact paths and `--no-deps`; reject extra wheels/Conda packages.
- Normalize wheel distribution names with `[-_.]+ -> -` and lowercase; parse exactly one `.dist-info/METADATA`, then compare `Name` and `Version` with the manifest.

## ZIP checks

Reject traversal/absolute paths, symlinks and special files, exact and case-folded duplicate names, file-directory collisions, excessive entries or expanded size, implausible compression ratios, and archives without exactly one manifest.

## Transaction model

- Use a 0600 random local HMAC key and non-symlink 0700 state/transaction directories.
- Sign transaction state before mutation and after every terminal status.
- Capture pre-update package state; failure should trigger rollback for normal `Exception` subclasses while allowing interrupts/system exits to propagate.
- Freeze files alone do not guarantee offline rollback; exact previous Conda artifacts must be retained for that claim.

## GStreamer/systemd readiness

- Check required directories and make `GST_PLUGIN_SCANNER` a regular non-symlink executable.
- Parse valid, uncommented `Environment=` directives with shell quoting.
- Also query effective systemd values (`systemctl --user show SERVICE --property=Environment --value`); require both source and effective environments to match expected paths and `ROBOT_ID`.
- Validate RealSense presence and application versions read-only. Keep DKMS/APT, install scripts, symlink fabrication, firmware, reboot, license, USB bus IDs, and database migrations as manual boundaries.

## Version ordering

Use semantic phase ordering rather than lexical token ordering:

`dev < alpha/a < beta/b < rc < stable < post/build`

Regression cases must include `2.2.0-rc1 < 2.2.0+build11`, a lower stable build, and final-vs-prerelease selection.

## Required regression tests

- Comments/stale service values cannot pass; effective systemd mismatch fails.
- Non-executable scanner fails.
- Nested sections such as `paths: null`, `robot: []`, or `network.lan: []` return validation errors without traceback.
- Wheel metadata mismatch fails.
- ZIP duplicate/collision/traversal/symlink cases fail.
- Unexpected installer exception attempts signed rollback.
- Downloaded CLI-reported paths outside staging are rejected without touching the outside file.
- Freshly extracted release archive runs the full suite and reports the expected version.
