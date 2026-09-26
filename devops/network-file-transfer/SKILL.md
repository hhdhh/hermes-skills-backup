---
name: network-file-transfer
description: Transfer large directories between Linux hosts over SSH w...
---

# Network File Transfer

> 完整描述：Transfer large directories between Linux hosts over SSH with verified source/destination identity, progress checks, and post-transfer validation.

Use this skill when copying large directories or environments between Linux machines over SSH/SCP, especially when hosts have multiple wired/Wi-Fi addresses.

## Core workflow

1. **Identify both hosts before copying.** On the intended destination, run `hostname; ip -br addr` and record the hostname, not just the IP. On the source, do the same. Never assume an IP is the other machine: a self-address, loopback, alias, or second NIC can make `scp` copy back onto the source.
2. **Validate the route.** Use `ping -c 3 DEST_IP`, then `ssh USER@DEST_IP 'hostname'`. Prefer a low-latency direct wired path for large transfers, but only after confirming that address belongs to the destination host.
3. **Check the source and destination paths.** On the source, run `test -d SOURCE && du -sh SOURCE`. On the destination, check whether the final directory already exists. For a first transfer, use a temporary destination directory to avoid nesting or partial-directory ambiguity.
4. **Transfer the directory itself into the parent directory.** For source `/home/ubuntu/miniconda3/envs/snack_bot_env` and destination parent `/home/ubuntu/miniconda3/envs/`, the canonical command is:
   ```bash
   scp -r /home/ubuntu/miniconda3/envs/snack_bot_env \
     ubuntu@DEST_IP:/home/ubuntu/miniconda3/envs/
   ```
   Do not add `/.` unless deliberately copying contents into an already-created directory and the local SCP implementation is known to support that form.
5. **Treat the final exit status as authoritative.** Individual `100%` lines only mean individual files completed. Wait for the shell prompt, then run `echo $?`; only `0` means the recursive transfer completed successfully.
6. **Verify remotely.** Check destination hostname, directory existence, representative executables, total size, file count, and—when transferring an environment—run the copied interpreter's `--version`. Do not claim completion based only on SCP progress lines.

## Monitoring a long-running transfer

From another terminal, inspect the source host:
```bash
ssh USER@SOURCE_IP 'hostname; pgrep -a -f "[s]cp|[s]sh.*DEST_IP"; ps -eo pid,ppid,etime,stat,pcpu,pmem,cmd | grep -E "[s]cp|[s]sh.*DEST_IP"'
```
Inspect the destination without modifying it:
```bash
ssh USER@DEST_IP 'hostname; du -sh DEST_DIR 2>/dev/null || true; find DEST_DIR -type f 2>/dev/null | wc -l'
```
A changing destination size/file count plus live `scp`/SFTP processes indicates an in-progress transfer. Do not start a second copy or interrupt the first merely because the terminal is quiet.

## Pitfalls

- **IP identity confusion:** `192.168.10.2` may be the source's wired address while `192.168.77.x` belongs to the Wi-Fi network. Always verify with `hostname`; ping success alone proves reachability, not identity.
- **Self-copy:** SSH to an IP and seeing the same hostname as the source proves the address is local/self, not the remote machine. Stop and choose the destination's verified address.
- **Partial success:** SCP can print hundreds of successful file lines and still end with `failed to upload directory`. The final exit code and remote verification decide success.
- **Existing target directory:** Copying into a pre-existing directory can create ambiguous partial state or nested paths. Prefer a temporary directory for risky/repeat transfers, then move it into place only after validation.
- **Large environments:** Conda environments may contain tens of gigabytes and many small files. Expect long runtimes; monitor from a second SSH session and ensure destination disk space is sufficient.
- **Credentials:** Never persist or embed passwords in scripts, skill files, or command history. Use the interactive SSH password prompt or configured SSH keys.

## References

- See `references/large-conda-environment-transfer.md` for the validated multi-NIC/Conda transfer case, diagnostic outputs, and verification recipe.
