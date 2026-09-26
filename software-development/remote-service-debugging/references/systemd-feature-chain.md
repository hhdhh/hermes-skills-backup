# systemd feature-chain reference

## Evidence collection

Use paging-disabled output so unit definitions are not silently truncated:

```bash
SYSTEMD_PAGER=cat systemctl --user cat NAME.service
systemctl --user show NAME.service \
  -p ExecStart -p Environment -p EnvironmentFiles \
  -p MainPID -p NRestarts --no-pager
systemctl --user --failed --no-pager
journalctl --user -u NAME.service --since '-30 min' --no-pager
```

For system services, omit `--user`.

## Secret-safe config comparison

Prefer a small parser script that:

- loads current and backup structured configuration;
- emits field presence, length, type, and non-secret differences;
- never emits credential values;
- asserts the restored field came from a known-good backup;
- reparses the resulting file before restart.

Text redaction must cover key/token/secret fields before diff output. A timestamped pre-repair copy makes rollback possible.

## Interpreting startup logs

Read chronology, not isolated matches:

- process start and device/IPC attachment;
- feature initialization announcement;
- credential/config validation;
- connection retries and timeouts;
- session-created/session-updated evidence;
- callback or logger exceptions after the originating failure.

An unrelated subsystem's success line (for example TTS) is not proof that realtime chat, ASR, or another sibling subsystem succeeded.

## Tight probes by layer

- **unit:** `is-active`, PID stability, restart count;
- **config:** native parser plus loaded path confirmation;
- **local IPC/device:** open/read/write the exact socket, SHM path, port, or device;
- **network:** DNS, TCP, TLS, then protocol-specific request;
- **provider:** authenticated minimal request or session creation;
- **application:** smallest internal invocation that reaches the provider;
- **end-to-end:** actual user input and observable output.

## Remote disconnect boundary

If SSH/ping fails after a repair:

1. retry reachability briefly with bounded timeouts;
2. preserve the last journal/state evidence already captured;
3. do not infer current service state;
4. report that end-to-end verification is blocked by host loss;
5. resume from reachability and the verification ladder when the host returns.
