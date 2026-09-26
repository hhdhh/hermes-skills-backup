# Safety-first robot provisioning from operational manuals

Use this reference when converting several field manuals into one Ubuntu robot installer/configurator.

## Durable workflow

1. Extract every source completely, including virtualized document blocks, code blocks, tables, and images that carry configuration values. Preserve a source/version map before designing automation.
2. Build a requirement matrix: task, source, supported software/hardware version, prerequisites, automatic vs manual boundary, success evidence, rollback.
3. Resolve conflicts explicitly. Examples: old vs new package paths, model-specific files, pre/post protocol versions, and whether calibration is routine or exception-only. Never silently choose the newest-looking example.
4. Expose composable capabilities rather than a single exclusive profile. A robot may need base + remote + voice + application-specific configuration.
5. Make system mutations opt-in (`--apply`), preview exact targets, validate inputs, use atomic writes, and back up originals. State exceptions honestly: wizards/reports/snapshots create files, and NetworkManager property changes need an explicit reverse operation.
6. Treat optional hardware as optional. Do not require a 5G MAC on robots without 5G; only add enabled interfaces to generated network and application configuration.
7. Separate three deliverables:
   - automatic configuration and read-only diagnostics;
   - a field runbook for physical/UI/version-dependent work;
   - an operator acceptance checklist with signatures/evidence.
8. Never automate unattended motion, calibration, mapping, grasp tuning, firmware flashing, partition growth, machine-id reset, router credentials/DMZ, license issuance, or unverified installer scripts. Provide prerequisites, responsible role, success criteria, cleanup, and rollback instead.
9. Existing site configuration wins over examples during upgrade. Do not merge-copy model weights/datasets over old trees or overwrite settings/XML from `.example`; stage, diff, migrate deliberately, and reject stale residue.
10. For ordered services, verify actual readiness rather than sleeping a fixed interval. If the dependency does not become healthy before timeout, do not start the dependent service.
11. Diagnostics must use truthful exit codes. Missing required service/network connections are non-zero. An automated shipment suite remains `INCOMPLETE` until physical power-cycle, emergency-stop, app/VR, motion, credential cleanup, and DMZ checks are signed off.
12. Distinguish local rollback snapshots from shareable reports. Raw settings and systemd units may contain secrets; mark snapshots local-only and emit separately redacted JSON/Markdown reports.

## Verification minimum

- Unit tests for validators, idempotent edits, optional-hardware branches, secret redaction, map/config invariants.
- CLI tests for dry-run non-mutation, apply cancellation, motion acknowledgement, truthful non-zero statuses.
- A sandbox apply→rollback test that proves original files return byte-for-byte.
- Static checks for shell and Python plus command-surface smoke tests.
- Package the artifact only after tests; verify archive entries and checksum.
