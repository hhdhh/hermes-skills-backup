# Remote systemd Dependency Debugging

## Reusable read-only probe

Run after SSH authentication, with `set +e` so one missing unit/property does not hide the rest:

```bash
set +e
systemctl --user status <unit>.service --no-pager -l
systemctl --user show <unit>.service \
  -p LoadState -p ActiveState -p SubState -p Result -p MainPID \
  -p ExecMainCode -p ExecMainStatus -p FragmentPath \
  -p Requires -p BindsTo -p PartOf
systemctl --user cat <unit>.service
journalctl --user -u <unit>.service --since '15 minutes ago' \
  --no-pager -o short-precise
systemctl --user list-dependencies <unit>.service --all --no-pager
```

Inspect each dependency with the same commands. For an exact environment probe, copy the unit's `ExecStart` setup into a controlled command and test the interpreter, imports, and paths named in the traceback.

## Validated pattern

A face-detection service had:

```ini
Requires=vision-service.service
BindsTo=vision-service.service
PartOf=vision-service.service
ExecStartPre=/bin/sleep 10
Restart=always
```

Restarting `vision-service` while the face service was inside the 10-second pre-start caused systemd to terminate the sleep:

```text
Control process exited, code=killed, status=15/TERM
Failed with result 'signal'
Job ... canceled
```

The cancellation was not the root application failure. The upstream vision service was actually failing during initialization because a package-owned configuration file was absent:

```text
FileNotFoundError: .../site-packages/autolife_robot_arm/settings.toml
VisionService core initialization failed
```

The correct interpretation was: dependency restart/cascade cancellation is the visible symptom; inspect the upstream journal and fix the missing package artifact or deployment mismatch before restarting the dependent.
