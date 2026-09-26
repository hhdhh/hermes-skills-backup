---
name: service-orchestration-debugging
description: Use when systemd-managed services restart, cancel, or cas...
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [systemd, services, user-services, dependencies, logs, robotics]
    related_skills: [systematic-debugging]
---

# Service Orchestration Debugging

> 完整描述：Use when systemd-managed services restart, cancel, or cascade-fail. Trace unit dependencies and verify application health.

## Purpose

Diagnose `systemctl` service failures and cancellations by separating systemd job state, unit state, dependency propagation, and application startup health. Use this for user services, robotics pipelines, vision stacks, and other multi-service processes.

## Core rule

A message such as `Job for X.service canceled` is a scheduling/dependency symptom, not necessarily the application root cause. Investigate the unit graph and the upstream service before changing files or repeatedly restarting units.

## Procedure

1. **Capture the exact state without mutating it.**
   ```bash
   systemctl --user status X.service --no-pager -l
   systemctl --user show X.service \
     -p LoadState -p ActiveState -p SubState -p Result \
     -p MainPID -p ExecMainCode -p ExecMainStatus \
     -p FragmentPath -p DropInPaths -p Requires -p BindsTo -p PartOf
   systemctl --user cat X.service
   systemctl --user list-dependencies X.service --all --no-pager
   ```

2. **Read the journal around the event.** Correlate timestamps and include the full application traceback, not just the final systemd line.
   ```bash
   journalctl --user -u X.service --since '10 minutes ago' \
     --no-pager -o short-precise
   ```

3. **Inspect every upstream dependency named by `Requires=`, `BindsTo=`, or `PartOf=`.** If an upstream unit is `auto-restart`, unstable, or repeatedly exits, stop trying to start the dependent. Find the upstream application error first.

4. **Understand start cancellation.** If `ExecStartPre` is a sleep or other control process and the journal says `status=15/TERM`, systemd likely canceled a pending start because a related unit changed state. This is distinct from an application crash (`ExecStart` nonzero exit or traceback).

5. **Validate the application environment independently.** Reproduce the unit's exact `ExecStart` shell, including `source` commands, conda environment, ROS setup, environment variables, working directory, and config paths. Check imports and required files with a minimal probe before running the full service.

6. **Recover in dependency order only after the root error is addressed.** Start the upstream service, verify `ActiveState=active` and stable logs/process state, then start the dependent. `Result=success` alone is insufficient: it may describe a successful stop/restart operation while the unit is still `activating` or `auto-restart`.

7. **Report four separate facts:** the visible command result, the dependent unit state, the upstream cause, and the validated next action. Do not conflate systemd's job result with application health.

## Robotics/ROS-specific checks

For services launched through ROS and conda, verify the exact environment rather than the interactive shell:

```bash
source /opt/ros/<distro>/setup.bash
source <workspace>/install/<package>/local_setup.bash  # if the unit does this
conda run --no-capture-output -n <env> python -c \
  'import sys; print(sys.executable); import rclpy; print(rclpy.__file__)'
```

Then check package-owned configuration files and paths named by the traceback. A missing config file in `site-packages` is an installation/package-content issue; do not mask it by inventing a default file unless the package's source or deployment contract defines that file.

## Pitfalls

- Do not infer failure from `Result=success` without `ActiveState` and `SubState`.
- Do not repeatedly restart a dependent while its upstream is in `auto-restart`.
- Do not call a `SIGTERM` during `ExecStartPre` an application crash.
- Do not fix only the final `systemd` symptom while ignoring the first application traceback.
- Do not mutate service units during diagnosis; collect evidence first.

## References

- `references/remote-systemd-dependency-debugging.md` — reusable remote probe and a validated dependency-cancellation pattern.
