---
name: linux-host-file-transfer
description: Transfer large directories between Linux hosts over SSH w...
version: 1
author: hermes-agent
license: MIT
metadata:
  hermes:
    tags: [linux, ssh, scp, rsync, networking, conda, file-transfer]
    related_skills: [linux-desktop-system-config]
---

# Linux host file transfer

> 完整描述：Transfer large directories between Linux hosts over SSH with network-path diagnosis and verification.

Use when copying a directory or environment between Linux machines over SSH, especially when the machines have multiple network paths (direct Ethernet plus Wi-Fi) or when a large recursive `scp` appears to transfer many files but ends with an error.

## Core workflow

1. **Identify source and destination explicitly.** Record the source host, destination host/IP, source path, and intended final path. Do not infer that an old Ethernet IP and a current Wi-Fi IP refer to the same route or host.
2. **Test the route from the source host.** Run `ping -c 3 DEST_IP`, then `ssh -o ConnectTimeout=10 user@DEST_IP 'hostname'`. A successful ping only proves ICMP reachability; SSH proves the actual transport needed by `scp`.
3. **Inspect the destination before copying.** Check the final directory, any temporary staging directory, free space, and ownership. Use a staging directory outside the final Conda prefix to avoid nested-directory ambiguity.
4. **Copy to a fresh staging path.** For a directory, prefer:
   ```bash
   ssh user@DEST 'rm -rf /tmp/name.new'
   scp -r /absolute/source/name user@DEST:/tmp/name.new
   ```
   Do not rely on `scp source/. destination/existing-dir/` when recursive copying is already failing; it makes the final layout and error location harder to reason about.
5. **Check the actual command result.** The progress lines ending in `100%` only describe individual files. The final recursive operation is successful only when `scp` exits with status 0 and emits no final `failed to upload directory` error.
6. **Verify the staged copy remotely before installation.** Check that the directory exists, expected anchor files exist, and the file count or size is plausible:
   ```bash
   ssh user@DEST 'test -x /tmp/name.new/bin/python && find /tmp/name.new -type f | wc -l'
   ```
7. **Promote atomically-ish after verification.** Preserve an existing destination with a backup name or remove it only when the user explicitly accepts replacement. Then move the verified staging directory into place and test the expected executable.

## Multi-interface diagnosis

A host may be reachable through a new Wi-Fi address while the earlier direct-Ethernet address is stale or belongs to a different network segment. Always use the destination address that was verified by SSH from the source. On the source, inspect:

```bash
hostname
ip -br addr
ip route
ping -c 3 DEST_IP
```

If SSH from the agent environment is attempted and a password prompt appears, use an interactive PTY or hand the user a command; never guess credentials or put passwords in command arguments, scripts, or skills.

## `scp` pitfalls

- `scp -r` can copy a directory *as a child* of an existing destination, producing `dest/name/name`; staging to a unique path avoids this.
- A source path ending in `/.` means “contents of this directory,” but recursive uploads to an existing directory can still fail due to destination state, permissions, symlinks, or implementation-specific directory handling.
- A successful ping does not prove the source path exists on the host where `scp` is run. Confirm `test -d /absolute/source/name` locally first.
- Do not declare success from a long stream of `100%` lines. Inspect the final exit status and read back the destination.
- For resumable repeated transfers, `rsync -aP source/ user@DEST:/staging/name/` is generally better, but use `scp` when the user explicitly requests it. Preserve trailing-slash semantics deliberately.

## Conda environment note

A copied Conda prefix may contain absolute-prefix references and symlinks. Direct directory copying is not equivalent to a portable environment export. After transfer, validate the copied environment with its absolute interpreter:

```bash
/staging-or-final/path/bin/python -V
/staging-or-final/path/bin/python -c 'import sys; print(sys.executable); print(sys.prefix)'
```

If prefix relocation or different OS/architecture is involved, use a reproducible environment export or `conda-pack` when it works; do not silently claim a raw copied prefix is portable.

## Verification standard

A transfer is complete only when all requested acceptance checks pass: the destination host is the intended machine, the staged/final directory exists at the intended path, representative files and executables are present, the command exit status is 0, and (for executable environments) the interpreter starts. If the session only diagnosed a failed transfer and did not perform a successful retry, report it as unresolved rather than recording the failed attempt as a working recipe.

## Reference

- `references/scp-multi-interface-case.md` — condensed case study of stale Ethernet vs Wi-Fi addresses, recursive `scp` output interpretation, and remote verification commands.
