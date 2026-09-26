# High-risk local tooling review checklist

## Non-git projects

A missing Git repository is not a reason to skip review. Build an explicit review set from entry points, task-created/modified files, command runners, path/backup logic, HTTP handlers, tests, and documentation. Read the files and search usages of dangerous primitives; describe the result as a snapshot review rather than a diff review.

## Local Web UI

Verify:

- Literal loopback bind plus Host validation.
- Unpredictable CSRF token on every mutation.
- CSP denies inline scripts, frames, objects, foreign connections, and form actions unless required.
- No shell string concatenation; subprocesses receive argument arrays.
- Public config is schema-projected and responses are redacted.
- Dynamic data uses DOM nodes/`textContent`, not `innerHTML`.
- Read-modify-write holds one lock across load, merge, validation, and save.
- Privileged apply and motion APIs do not exist; command copying retains terminal safety gates.

## Rollback manifests

Path containment protects backup payload reads but does not authenticate restore/delete destinations. Combine:

- Fixed trusted backup root and direct-child session directories.
- Session ID equal to directory name.
- HMAC-SHA256 (or equivalent) with a mode-0600 local key outside sessions.
- Payload containment and symlink-component rejection.
- Privileged target allowlist.
- Fail-closed refusal of missing/invalid signatures.

Test external payloads, arbitrary targets, symlink parents/targets, unmanaged sudo paths, session mismatch, missing signatures, and tampering.

## Reviewer interruption

Timeout, interruption, partial transcript, or malformed JSON is not approval. Perform one bounded retry or an explicitly identified primary-agent review. Remediate findings and rerun all gates before delivery.

## Final delivery

After the last fix, rerun compilation, tests, linters, shell checks, and frontend syntax checks. Rebuild archives only afterward, verify expected entries and absence of caches, and report a newly computed checksum.
