---
name: secure-local-automation
description: Use when building local installers and privileged control...
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [installer, local-web-ui, rollback, security, verification]
    related_skills: [requesting-code-review, systematic-debugging, test-driven-development]
---

# Secure Local Automation

> 完整描述：Use when building local installers and privileged control UIs.

Build and review beginner-friendly local installers, configuration tools, diagnostic consoles, and rollback systems that may affect privileged host state or physical equipment.

## When to Use

- A CLI or local Web UI previews or applies OS/network/service configuration.
- A tool creates backups and later restores or deletes paths from a manifest.
- A UI fronts robot, laboratory, industrial, or other motion-capable systems.
- The project is not in Git but still needs a fail-closed security review.

## Core Contract

1. Default system mutations to preview; require explicit apply and a terminal confirmation.
2. Keep privileged and motion operations out of convenience Web APIs.
3. Treat generated reports and snapshots as explicit file-producing exceptions to dry-run language.
4. Never embed credentials, pipe passwords, use shell string construction, or execute unreviewed remote scripts.
5. Preserve existing site configuration; merge or stage examples instead of overwriting.
6. Require on-site supervision and a distinct acknowledgement phrase for operations that can move equipment.
7. Report real exit codes and fail closed when evidence is missing or malformed.

## Procedure

### 1. Map the threat and mutation surface

List every endpoint/command and classify it as read-only, local file output, configuration mutation, privileged mutation, or motion. Trace each mutation to its writer, backup behavior, confirmation gate, and rollback path.

### 2. Design the CLI boundary

Use argument arrays for subprocesses. Keep `sudo` and confirmations attached to a real terminal. Reject disruptive network activation over SSH. Return nonzero status for failed services, routes, diagnostics, or incomplete acceptance checks.

### 3. Design the local Web boundary

Bind only to a literal loopback address and reject non-local Host headers. Use CSRF for every mutation, strict CSP/security headers, bounded JSON bodies, schema projection, redaction, and operation locks. Expose previews, diagnostics, safe config-file saves, and command copying; do not expose apply, service control, or motion endpoints.

Use DOM creation and `textContent` for dynamic values. Avoid `innerHTML` even when current server values appear trusted; future error strings and catalogs expand the trust boundary.

### 4. Make backup/rollback authentic

Containment checks on backup payloads are necessary but insufficient: a forged manifest can redirect restore or delete targets. Require a trusted backup root, direct-child session directories, matching session IDs, a local integrity/authenticity signature, symlink rejection, and an allowlist for privileged targets. Refuse unsigned or tampered backups; document manual legacy recovery.

### 5. Verify independently

Review entry points, changed files, command runners, path handling, HTTP handlers, tests, and documentation. A missing Git repository changes how the review set is assembled; it does not justify skipping review. An interrupted or malformed independent-review result is a failure, not approval.

After every security fix rerun compilation, unit/integration tests, language lint, shell checks, and frontend syntax checks. Rebuild the archive only after the final checks and publish a new checksum.

## Required Tests

- Loopback-only bind, Host rejection, CSRF rejection, CSP/security headers.
- No apply/motion endpoint exists.
- Config output is schema-projected and secret-redacted.
- Concurrent config writes do not lose updates.
- CLI propagates nested command failures to nonzero exit codes.
- Rollback rejects external payloads, arbitrary targets, symlink parents/targets, unmanaged sudo paths, session mismatch, missing signatures, and tampered manifests.
- Existing site configuration and datasets are preserved.
- Motion service order verifies dependency readiness rather than sleeping a fixed duration.

## References

See `references/high-risk-local-tooling.md` for the condensed review checklist and implementation patterns.

## Pitfalls

- Calling a timeout/interruption an independent approval.
- Restricting backup payload reads but trusting attacker-editable restore targets.
- Locking only the final save instead of the whole load/merge/validate/save transaction.
- Claiming everything is dry-run while wizards, reports, or snapshots create files.
- Reusing an archive checksum after modifying any file.
- Making novice UX “easy” by bypassing terminal or motion safety gates.
