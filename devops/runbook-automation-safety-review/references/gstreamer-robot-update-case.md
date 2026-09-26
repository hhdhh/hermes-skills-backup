# GStreamer and Robot Update Review Case

Use this reference as a worked example of splitting a mixed update guide across state domains. It is not a command runbook and contains no machine-specific credentials or artifact hashes.

## Mixed domains in one guide

A guide titled as a GStreamer update may also include:

- four Python wheels in a Conda environment;
- a native runtime tree under `/opt`;
- JSON, TOML, and URDF template replacement;
- RealSense APT repository and DKMS packages;
- compatibility SONAME symlink;
- user systemd units and environment variables;
- third-party server, relay, and web-admin installers;
- license/public-key paths and database migration;
- machine-specific USB bus mapping;
- reboot and physical-device validation.

A wheel/Conda transaction must not be presented as rollback for the other domains.

## Representative classification

| Action | Classification | Reason |
|---|---|---|
| Install an exact, manifest-listed wheel into a declared environment | Safe with conditions | Requires trusted release identity, independent digest/signature, mandatory package completeness, preflight, snapshot, exact install, and version verification. |
| Pick “latest” files in a browser and transfer them | Manual | Access and release selection are human decisions unless a controlled release channel exists. |
| Extract a native runtime ZIP directly over `/opt` | Preview-only at first | Needs safe extraction, fixed layout, staging, runtime checks, atomic switch, and matching rollback. |
| Replace all live configs from `.example` | Preview-only/manual merge | Can erase identity, credentials, calibration, hardware mappings, and local tuning. |
| Replace URDF/calibration files | Manual | Model and calibration compatibility are machine-specific. |
| Add APT source and install DKMS | Manual, with automated preflight | Kernel, Secure Boot, headers, repository key, and reboot consequences require a dedicated workflow. |
| Symlink a new native library SONAME to an older name | Manual/block by default | File existence does not prove ABI compatibility. |
| Patch known environment variables into two explicit user units | Safe with conditions | Back up, parse `[Service]`, narrow upsert, unit validation, daemon reload, and effective-environment verification. |
| Execute package-provided `install.sh` or `install_local.sh` | Manual | Archive validation does not establish script semantics or database safety. |
| Supply license paths or choose database migration | Human decision; narrow write may be automated | Values and migration approval are operational inputs. |
| Detect and set USB bus ID | Manual value confirmation; patch may be automated | Bus topology can vary between machines and reconnects. Prefer stable serial/udev identity. |
| Reboot | Manual | Disruptive action requires maintenance-window and local recovery confirmation. |

## Verification depth examples

### Native GStreamer

Do not stop at `/opt/autolife_gstreamer` existing. Evidence should progress through:

1. expected directories and scanner executable exist;
2. package layout and ELF architecture are valid;
3. dependent libraries resolve;
4. user service effective environment points to approved paths;
5. `gst-inspect-1.0` or the actual application loads required plugins;
6. the camera/media flow works after an operator-approved restart.

A literal `$LD_LIBRARY_PATH` inside a systemd `Environment=` line is suspicious because systemd does not perform shell expansion there. Validate the effective value rather than matching source text.

### RealSense

Report separately:

- APT package versions;
- DKMS build/load state for the running kernel;
- Secure Boot/signing state;
- `rs-enumerate-devices` command availability;
- physical device enumeration and expected model/firmware;
- application-level image capture.

“No device connected” must not be conflated with “driver missing.”

### Application versions

Parse semantic/build versions and compare against explicit thresholds. Exit code 0 or non-empty stdout is not enough. If prose and checklist disagree, report the conflict and block below the stricter threshold until the document owner resolves it.

## Minimal safe enhancement sequence

1. Add a read-only readiness/plan command that returns structured PASS/WARN/FAIL and explicit manual boundaries.
2. Require a release profile that names every mandatory wheel and trusted external provenance.
3. Add semantic config diffs without writes.
4. Automate only narrow systemd environment patches with signed backup and effective-state verification.
5. Design separate transactions for `/opt`, APT/DKMS, and applications; do not merge them under Python rollback language.
6. Keep unknown scripts, database migration, license assignment, hardware identity, ABI shims, and reboot manual.

## Document-quality checks

Flag contradictions such as:

- prose saying “two variables” while listing four;
- version thresholds differing between procedure and checklist;
- a service referenced in configuration but absent from prerequisites/package list;
- a hardware ID described as machine-specific but followed by a universal fixed value;
- `cp` or `rm` instructions that lack backup, exact-source validation, or rollback.

These are release blockers for automation, not cosmetic editorial issues.
