---
name: cross-platform-object-storage-transfer
description: "Use for rclone/S3 upload-download kits across Windows/Linux."
version: 1
author: hermes-agent
license: MIT
platforms: [linux, windows, macos]
metadata:
  hermes:
    tags: [rclone, s3, object-storage, powershell, bash, transfer]
---

# Cross-platform object-storage transfer kits

Build and verify reusable upload/download handoff bundles for S3-compatible storage using rclone.

## Trigger

Use when a user needs to configure, upload, download, or distribute a repeatable rclone workflow across Windows and Linux, especially when they request complete scripts, exact commands, packaged documentation, or a Feishu/Lark document.

## Workflow

1. **Discover before writing**
   - Confirm endpoint, remote name, bucket/prefix, local source/destination, and whether the certificate is publicly trusted.
   - Inspect the existing rclone version and configuration path rather than assuming them.
   - Never print secrets in logs or summaries.

2. **Prefer a two-script bundle**
   - `rustfs.ps1`-style PowerShell entry point for Windows.
   - `rustfs.sh`-style Bash entry point for Linux/macOS.
   - A separate `rclone.conf`; scripts must not embed credentials.
   - `README.md` for quick use and `DOCS.md` for complete instructions.
   - Keep filenames in documentation exactly aligned with the archive contents.

3. **Windows requirements**
   - Keep `.ps1` source ASCII-only when Windows PowerShell 5.1 compatibility matters; put Chinese instructions in Markdown to avoid legacy encoding parser failures.
   - Use argument arrays (`& $exe @args`), not manually quoted argument strings.
   - Validate mode, paths, and required arguments before network or install side effects.
   - If auto-downloading rclone, pin a version, verify the published SHA-256, then extract and remove temporary files.
   - Document `Unblock-File` and a per-process `-ExecutionPolicy Bypass` fallback; do not advise weakening MachinePolicy.

4. **Linux requirements**
   - Start with `set -euo pipefail`; quote all paths.
   - Validate arguments and upload source existence before installing, writing config, or contacting the remote.
   - Preserve existing remotes. Add the new section with a temporary file and atomic rename; set mode 0600.
   - Avoid `curl | sudo bash` when a native package manager is available. If sudo must be performed by the user, hand off one self-contained script.

5. **Transfer behavior and safety**
   - Default to `rclone copy`, not `sync`.
   - Explain precisely: `copy` preserves destination-only files but can overwrite same-path files when content differs; it is not “no overwrite.”
   - Use progress, retries, and bounded transfers; allow direct rerun for resume-like behavior.
   - `--no-check-certificate` is a temporary exception for an actually untrusted/private certificate, not a default. Explain MITM risk and recommend installing the correct CA, then removing the flag.

6. **Documentation and delivery**
   - Include setup, upload, download, list, size, path examples, common errors, security notes, and copy-vs-sync semantics.
   - Programmatically compare documented filenames against actual bundle contents; distinguish packaged, generated, and optional files.
   - Package only intended files, test archive integrity, and link the absolute local archive path when sending it.
   - For Feishu, create/update the document from Markdown using the authenticated user identity and verify the returned URL/revision.

## Verification gates

- `bash -n` passes for shell scripts.
- Invalid paths fail before configuration/network side effects.
- Scripts contain no access/secret key values.
- PowerShell source contains no non-ASCII text when targeting Windows PowerShell 5.1.
- Download checksum is compared against an independently retrieved official checksum.
- Archive integrity test passes and documented filenames equal actual packaged filenames.
- No `sync`, delete, purge, or destructive operation unless explicitly requested and confirmed.

## Pitfalls

- A remote URL alone does not supply access and secret keys.
- `rclone copy SRC DIR` copies SRC contents into DIR; add an explicit destination subdirectory if preserving the source directory name matters.
- Do not infer data-date semantics from folder names after reading only a truncated listing; enumerate the full relevant level.
- Never expose credentials while demonstrating config content.

## References

- See `references/review-checklist.md` for a compact pre-delivery audit.
