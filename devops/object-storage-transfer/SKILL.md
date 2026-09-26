---
name: object-storage-transfer
description: Use when transferring files with rclone/S3-compatible sto...
version: 1
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [rclone, s3, object-storage, upload, download, proxy]
---

# Object Storage Transfer

> 完整描述：Use when transferring files with rclone/S3-compatible storage.

Build, troubleshoot, and verify safe cross-platform transfers against S3-compatible object storage with `rclone`.

## Core workflow

1. **Discover before writing configuration**
   - Run `rclone version` and `rclone config file`.
   - Inspect only remote names and non-secret fields; never print AK/SK.
   - Confirm endpoint reachability, bucket name, and intended source/destination structure.
2. **Preserve existing configuration**
   - Never overwrite an existing non-empty `rclone.conf` just to add one remote.
   - Back up or atomically append the new section.
   - Restrict permissions to owner-only (`chmod 600`) on Unix.
3. **Verify in layers**
   - DNS resolution.
   - Direct TCP/TLS reachability.
   - `rclone lsd remote:`.
   - `rclone lsd remote:bucket/`.
   - Only then run `copy`.
4. **Use safe transfer semantics**
   - Prefer `rclone copy`; do not use `sync` unless deletion semantics are explicitly requested.
   - Explain that `copy` preserves target-only files but may replace a same-path file when rclone considers it different.
   - Quote all local and remote paths; preserve spaces as single arguments.
5. **Verify completion**
   - Use `rclone check remote:path local:path --one-way --size-only` when full hashes are unavailable or expensive.
   - Report actual exit codes and outputs, not expected behavior.

## Proxy-aware diagnosis

A local HTTP/SOCKS proxy can accept CONNECT and still break TLS to private object-storage endpoints. A telltale pattern is:

```text
HTTP/1.1 200 Connection established
SSL_ERROR_SYSCALL
```

Test direct access separately:

```bash
curl --noproxy '*' -kIsS --connect-timeout 10 --max-time 20 'https://endpoint:port/'
env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY \
    -u http_proxy -u https_proxy -u all_proxy \
  rclone lsd remote: --no-check-certificate -vv
```

If direct rclone succeeds, either:
- add the endpoint hostname/IP to both `NO_PROXY` and `no_proxy`, or
- wrap rclone invocations with the `env -u ...` form.

Do not misdiagnose this as bad credentials when direct authenticated listing works.

See `references/rclone-s3-proxy-troubleshooting.md` for the full decision tree.

## Resume behavior

Re-running the **same** `rclone copy` command after interruption is the normal recovery method:

- fully completed matching files are skipped;
- missing or differing files are transferred;
- a partially written individual file may restart rather than resume at its exact byte offset;
- source and destination paths must remain identical between runs.

Avoid calling this byte-level resumability. Describe it as file-level restart/continuation.

## Cross-platform script rules

### Linux/macOS

- Validate arguments and local paths before installing packages, modifying config, or contacting the remote.
- Keep credentials in `rclone.conf`, not embedded in the shell script.
- When installing automatically, acquire sudo once in a user-run script; do not try to authenticate sudo from an agent subprocess.
- Write config atomically with a temporary file followed by rename.
- If a bundled config is required, resolve it relative to `BASH_SOURCE[0]`, not the caller's current directory.

### Windows PowerShell

- Keep `.ps1` source ASCII-only when it must run under legacy Windows PowerShell 5.1 on Chinese systems; place Chinese instructions in Markdown.
- Pass arguments as a PowerShell array without manually embedding quote characters:

```powershell
$args = @('copy', $LocalPath, $RemotePath, "--config=$RcloneConf")
& $RcloneExe @args
```

- Validate paths before downloads/network side effects.
- If downloading `rclone.exe`, pin a version, verify the vendor-published SHA-256, then extract and clean temporary files.
- For downloaded scripts, document `Unblock-File .\script.ps1`; use one-shot `-ExecutionPolicy Bypass` only when policy requires it.

## TLS safety

`--no-check-certificate` is a temporary compatibility measure, not a harmless default. It disables server certificate verification and permits MITM interception. Retain it only when the endpoint truly uses an untrusted/private certificate, document the risk, and prefer installing the correct CA then removing the flag.

## User-facing handoff

For users who ask for a complete solution:

- provide a self-contained script plus one invocation;
- keep a short quick-start document and a detailed reference document;
- state exactly which variables/paths they must change;
- use explicit examples for upload, download, list, size, interruption recovery, and verification;
- avoid repeatedly asking low-value questions when the destination and remote are already known.

## Security checklist

- Never echo or paste secret keys into chat, logs, screenshots, or generated documentation.
- Do not commit `rclone.conf` to Git or package credentials in broadly shared archives.
- Prefer scoped/rotatable credentials.
- Verify archive integrity after packaging.
- Flag automatically downloaded executables that lack integrity verification.
