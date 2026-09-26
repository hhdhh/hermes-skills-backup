# Pre-delivery review checklist

Use before handing off an rclone/S3 transfer kit.

## Bundle
- [ ] Scripts, config, README, and full docs use matching filenames.
- [ ] Docs identify packaged vs runtime-generated vs optional files.
- [ ] Archive contains only intended files and passes an integrity test.

## Secrets and configuration
- [ ] Credentials exist only in the protected config, not scripts/docs/output.
- [ ] Config permissions are owner-only where supported.
- [ ] Existing rclone remotes are preserved; updates are atomic.

## Windows
- [ ] PowerShell 5.1-compatible encoding (ASCII-only script if Chinese locale may misdecode UTF-8 without BOM).
- [ ] Native argument arrays preserve spaces/special characters.
- [ ] Auto-downloaded binary is version-pinned and SHA-256 verified.
- [ ] Temporary download/extraction files are removed.
- [ ] Execution-policy recovery uses `Unblock-File` or per-process bypass, not MachinePolicy changes.

## Linux
- [ ] `bash -n` passes.
- [ ] `set -euo pipefail` and path quoting are present.
- [ ] Invalid upload source fails before install/config/network activity.

## Transfer semantics
- [ ] Uses `copy` by default; no delete/sync/purge unless explicitly confirmed.
- [ ] Docs warn that same-path files may be overwritten.
- [ ] Retries, transfer concurrency, and progress are bounded and documented.
- [ ] TLS verification is enabled, or any temporary bypass is clearly justified with CA-remediation guidance.

## Live verification
- [ ] Remote listing succeeds without bulk transfer.
- [ ] A safe dry/static test covers argument handling and filenames with spaces.
- [ ] Final artifact path/URL is read back and verified before reporting success.
