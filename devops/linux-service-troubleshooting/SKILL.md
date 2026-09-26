---
name: linux-service-troubleshooting
description: "Use when Linux systemd services crash, loop, or misbehave."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    tags: [linux, systemd, troubleshooting, services, remote-debugging]
---

# Linux Service Troubleshooting

## Purpose

Diagnose Linux system and user services from evidence before changing configuration. Build a tight, repeatable probe; distinguish the process's root failure from systemd's restart behavior; protect credentials and application secrets throughout remote investigation.

## Workflow

1. **Identify scope and exact unit**
   - Determine whether it is a system unit or `systemctl --user` unit.
   - Capture status, unit source, effective launch properties, and recent precise logs.
2. **Reproduce narrowly**
   - Prefer an application-provided check, verifier, health endpoint, or foreground invocation that reproduces the exact failure quickly.
   - Record the command's real exit code; do not mask it with pipelines or fallback commands.
3. **Trace launch context**
   - Inspect `ExecStart`, working directory, environment-file locations, user, paths, and dependencies.
   - Follow referenced configuration and assets without printing secrets.
4. **Establish a timeline**
   - Compare modification times for binary, unit, config, and relevant assets with the first failing log entry.
5. **Rank and falsify hypotheses**
   - Test one cause at a time with the smallest probe. Prefer direct component diagnostics over interpreting broad application error text.
6. **Fix only the confirmed root cause**
   - Do not treat restart policy, log volume, or transient unit state as the application defect.
7. **Verify end to end**
   - Re-run the tight probe, restart only when authorized, inspect status/logs, and exercise the service's real health path.

## Baseline commands

For user units, add `--user` consistently:

```bash
systemctl --user status UNIT --no-pager -l
systemctl --user cat UNIT
systemctl --user show UNIT -p ExecStart -p EnvironmentFiles -p WorkingDirectory -p FragmentPath
journalctl --user -u UNIT -n 100 --no-pager -o short-precise
```

For system units, omit `--user` and use the system journal.

## Safety and reporting

- Redact passwords, tokens, private keys, license bodies, database URLs, and secret-bearing environment values.
- Preserve literal paths, identifiers, hashes, exit codes, and error text used as evidence.
- Do not bypass licensing, authentication, or authorization controls.
- Do not change restart policy or stop a service unless the user authorized the operational impact.
- Report what is proven separately from what is merely possible.

## References

- See `references/remote-systemd-license-failures.md` for cryptographic license/HWID failures under restart loops.
