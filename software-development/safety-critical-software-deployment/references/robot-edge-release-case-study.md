# Robot edge release case study

This reference condenses a successful workflow for turning an operational robot update guide into safer automation. It is a pattern, not a copy of any upstream manual.

## Source shape

The guide combined several unrelated mutation classes:

1. Four Python wheels in one Conda environment
2. A native GStreamer runtime tree under `/opt`
3. Replacement of JSON, TOML, and URDF files from `.example`
4. RealSense APT/DKMS installation and a compatibility `.so` symlink
5. Vision/Flow user-service environment variables
6. Three native/web application bundles with interactive shell installers
7. License paths, database migration, USB bus binding, and reboot

The crucial learning is that “one update guide” is not “one transaction type.” Split it by trust and rollback semantics.

## Classification that worked

### Safe automation with a release contract

- Exact wheels listed in `release.json`
- Per-file SHA-256
- Wheel `Name`/`Version` metadata cross-check
- Architecture and Python major/minor preflight
- Exact target environment
- Preview, explicit apply, post-install metadata verification
- Signed transaction record and best-effort package rollback

### Read-only verification

- Expected GStreamer directories and scanner file exist
- RealSense device enumeration
- Application version commands
- Vision/Flow unit source contains valid `Environment=` assignments
- `systemctl --user show <unit> --property=Environment --value` confirms effective values
- Config-preservation boundary is surfaced in the result

### Human boundary until a stronger contract exists

- Replacing active configs/URDF with `.example`
- APT repository and DKMS installation
- Compatibility symlink between different native library SONAME versions
- Executing downloaded `install.sh` or `install_local.sh`
- `curl | sh` runtime installation
- Database migration prompts
- License/public-key changes
- Fixed USB bus ID copied across robots
- Reboot and hardware/business acceptance

## Effective systemd check

A naive substring search produced false positives when values existed only in comments or an overridden unit. The corrected check:

1. Parse only active `Environment=` directives with shell-aware tokenization.
2. Ignore `#` and `;` comments.
3. Compare exact values; for `LD_LIBRARY_PATH`, require the managed prefix as the first path segment.
4. Query systemd's effective environment with `systemctl show ... --property=Environment --value`.
5. Require both source and effective checks to pass.

## Version-check pitfall

Raw lexical tuples can classify `2.2.0-rc1` as newer than `2.2.0+build11`. Rank prerelease labels explicitly (`dev < alpha < beta < rc < stable/build`) and add regression tests.

## Release-source gap

A web portal displaying “latest files” is not an authoritative release feed when it lacks an immutable manifest, detached signature/trusted hash, target assignment, and rollback data. In that state:

- permit explicit operator-supplied artifact inspection;
- automate only manifest-conforming packages;
- expose native/application work as verification and a human runbook;
- do not fabricate a one-click updater around filename globs or shell installers.

## Delivery evidence

A strong delivery included full tests and static checks, a live loopback-only UI smoke check proving no apply endpoint, an expected non-robot-host failure path, and a second test run after extracting the final archive.