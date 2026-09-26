# Native Artifact and Field-Safety Test Matrix

Use this reference to turn a Linux updater design into focused tests. Keep each row as a separate vertical RED→GREEN slice where practical.

## Manifest and Dispatch

| Behavior | Positive case | Negative/boundary case |
|---|---|---|
| Schema compatibility | Existing Python-only manifest still loads | Unknown future schema is rejected clearly |
| Closed artifact kinds | Registered kind reaches its fixed handler | Unknown kind, dynamic module, or command field is rejected |
| Target allowlist | Target ID maps to a code-owned path | Absolute, relative, traversal, or unknown target is rejected |
| Identity/integrity | Hash and authenticated release metadata match | Missing hash, altered bytes, wrong release identity |
| Architecture/version | Declared architecture and version match host/contract | Wrong architecture, ambiguous or malformed version |

## Archive Safety

- ZIP and TAR happy-path fixtures with real temporary files.
- Absolute path, `..`, backslash ambiguity, empty normalized path.
- Symlink, hardlink, device, FIFO, socket.
- Exact duplicate and Unicode/case-folded duplicate paths.
- File/child and directory/file prefix collisions.
- Excess members, member size, total expanded size, and compression ratio.
- SUID/SGID and unexpected executable modes.
- Truncated/corrupt archive and nested archive policy.
- Verify that no output member is written when prevalidation fails.

## Configuration Preservation

| Policy | Required tests |
|---|---|
| `preserve` | Existing bytes/hash/mode/owner unchanged; installer tampering is detected, restored, and reverified |
| `create_if_missing` | Missing file is seeded; existing file remains untouched; second run is idempotent |
| `patch_known_keys` | Only registered keys change; comments/unknown values remain; malformed/unsupported grammar stops safely |
| `replace_managed` | Backup exists before replacement; rollback restores exact prior state |
| `manual_merge` | No edit occurs; report names source, target, hashes, and required human action without leaking contents |

Also test absent paths, directories, symlink targets, permissions errors, secrets in diagnostics, and rollback after partial configuration work.

## Transaction and Activation

Fault-inject before and after every persisted state transition:

- inspect → prepared;
- prepared → staged;
- staged → activated;
- activated → verified;
- any state → rollback started → rolled back/rollback failed.

Verify signed state after every mutation, interruption recovery, idempotent replay, target on the same filesystem for atomic rename, old-tree retention until verification, and exact restoration of preexisting state. Preview must create no transaction, staging directory, backup, or command-side mutation.

## systemd Environment

### Static

- Unit/drop-in exists and has the correct section.
- Expected environment keys appear exactly once after merge.
- Paths remain beneath the managed root and required executable files have execute permission.
- Syntax verifier succeeds; malformed quoting and duplicate/conflicting drop-ins fail.
- Literal `$VAR` is rejected when shell expansion would be required.

### Effective

- Vendor unit plus multiple ordered drop-ins yields the expected final values.
- `daemon-reload` pending state is distinguishable.
- `systemctl show/cat` failure, missing unit, masked unit, and wrong user manager are represented honestly.

### Runtime

- Active process environment matches the effective configuration.
- Configured-but-not-restarted returns `CONFIGURED_PENDING_RESTART`, not PASS.
- Long-running daemon uses active/result/restart evidence.
- Oneshot service uses result/exit/output evidence and may be inactive after success.

## Native Applications

For each fixed application verifier:

- exact version and minimum-version cases;
- missing/non-executable binary;
- version command timeout, nonzero exit, or malformed output;
- expected service semantics (daemon versus oneshot);
- crash/restart loop evidence;
- required configuration and license paths without exposing their contents;
- configured database migration reported as manual/incomplete unless authoritative machine-readable evidence exists.

## Driver and Hardware Readiness

Separate checks for:

1. OS/repository package installation;
2. kernel headers, DKMS/module build/load, and Secure Boot;
3. userspace library/SONAME/link integrity;
4. utility availability;
5. physical device enumeration;
6. real functional/image acceptance.

Test no-device as `INCOMPLETE` where appropriate, not an automatic package failure. Include unsupported architecture, dangling compatibility link, utility timeout, permission denied, USB 2 versus USB 3 evidence, and firmware mismatch. Firmware updates and compatibility links remain manual unless vendor policy and rollback are explicit.

## CLI and UI

- Read-only checks have deterministic structured output and exit codes.
- Preview and inspect never require sudo.
- Apply paths retain confirmation and motion acknowledgements.
- Web UI may list/call read-only checks but does not expose privileged apply endpoints.
- Reports redact secrets and distinguish PASS, FAIL, WARN, INCOMPLETE, and pending restart.

## Field Acceptance

Automated reports must leave explicit incomplete items for:

- reboot persistence;
- real plugin load or media pipeline;
- connected-camera image quality;
- database migration correctness;
- server/license/backend binding;
- USB topology chosen for this machine;
- physical motion, emergency stop, and end-to-end business flow.

A final releasable state requires both automated evidence and operator sign-off; tests should assert that automation alone cannot mark field acceptance complete.
