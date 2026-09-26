# Remote restarting-service diagnosis

Use this reference when a remote systemd service appears `active` but its feature is unavailable.

## Read-only triage

1. **Verify identity first.** Reused IPs can point to a different host.
   ```bash
   hostname
   cat /proc/sys/kernel/random/boot_id
   uptime -s
   ip -brief addr
   ```
2. **Inspect lifecycle, not only state.** `Restart=always` can make a crash loop look healthy.
   ```bash
   systemctl --user show SERVICE \
     -p ActiveState -p SubState -p Result -p MainPID \
     -p ExecMainStatus -p NRestarts -p ActiveEnterTimestamp
   ```
3. **Capture one complete crash window.** Read from one `Started` event through its matching exit and scheduled restart. Do not mix generations.
4. **Trace producer → transport → consumer.** For shared-memory camera/audio pipelines, verify:
   - hardware enumerates;
   - producer module/process starts;
   - expected `/dev/shm` objects exist and are fresh;
   - consumer attaches;
   - callback receives data.
   Callback registration alone is not proof of a working feature.
5. **Separate control-plane and feature-plane success.** `session.created` proves provider auth/connectivity, not whole-service health. `active` does not prove an AI session exists.
6. **Use an isolated differential probe.** Invoke the same endpoint, key source, runtime, and client class outside the full process. If isolated succeeds but integrated fails, investigate config selection, lifecycle, event loop, concurrency, or startup load.
7. **Prioritize first failure.** A deterministic Python exception that initiates shutdown normally outranks a native segfault during cleanup.

## Diagnostic signatures

### ROS: `Logger severity cannot be changed between calls`

`rclpy` caches logger filter context by caller location. A wrapper or compiled/Cython call site that emits different severities from the same apparent caller can raise this error. Preserve both traceback frames: the original log call and the exception-handler log call. Fix the application to use stable severity per call site, distinct call sites/logger names, or an updated compatible build. Do not globally patch `rclpy` simply to hide the application bug.

### Missing shared-memory camera object

`No shared memory exists with the specified name` means the consumer cannot attach; it does not prove hardware is missing. Compare expected names in SDK/module config with `/dev/shm`, then find why the producer did not create them. Stale SHM can make a failed device look healthy, so corroborate with producer PID and fresh counters/timestamps.

### Predictive proxy warning followed by success

A message such as “proxy variable not set; direct connection likely to fail” is predictive, not the outcome. Read subsequent events. `session.created` and `session.updated` outweigh the warning.

## Reporting

Report independent chains separately:

- service lifecycle/crash/restart;
- provider/auth/connectivity;
- audio capture/VAD;
- camera producer/SHM/face consumer;
- secondary hardware warnings.

Label proven facts versus hypotheses and say explicitly whether anything was modified. Never claim a fix from an isolated probe alone; verify the integrated service remains stable and the user-visible feature works.