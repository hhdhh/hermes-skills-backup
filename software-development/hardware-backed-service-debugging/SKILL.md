---
name: hardware-backed-service-debugging
description: Use when a service controls physical devices.
version: 1.0.0
metadata:
  hermes:
    tags: [debugging, systemd, hardware, can, robotics, services]
---

# Hardware-Backed Service Debugging

> 完整描述：Use when a service controls physical devices. Isolate endpoint, transport, and cleanup faults.

## Purpose

Diagnose services that initialize motors, sensors, serial/CAN/USB devices, or other physical endpoints. Separate application faults from transport-wide faults, single-endpoint faults, and secondary shutdown noise before changing software.

## Workflow

### 1. Capture one complete lifecycle

For a systemd service, gather the unit definition, status, structured properties, and logs over at least one complete startup/failure/restart interval. Include:

- `ActiveState`, `SubState`, `Result`, `NRestarts`, main PID/status;
- the first device-specific failure;
- an application-level initialization-success marker, if one exists;
- transport inventory, driver status/error counters, and kernel disconnect/reset logs.

With `Restart=always`, an `active (running)` snapshot is not proof of health. A young process may simply be between failures.

### 2. Find the first causal error

Build a timestamped chain:

1. transport/controller registrations;
2. endpoint discovery or probe;
3. first endpoint-specific error;
4. worker/process exit;
5. cleanup exceptions;
6. supervisor timeout/restart.

Prefer the earliest failure that explains everything downstream. Treat shutdown-context errors, destroyed-object reads, sibling-worker exits, and supervisor timeouts as consequences unless they occur first.

### 3. Localize the fault domain

Compare the failed endpoint with working peers:

- **Same adapter and same bus has a working peer:** whole-adapter, driver, permissions, and total bus failure are less likely. Inspect endpoint power, connector, wiring branch, configured address/ID, device fault state, and termination.
- **All endpoints on one bus fail:** inspect bus power, adapter/channel mapping, bitrate, termination, and cabling.
- **All adapters disappear or kernel logs resets:** inspect host USB/power/driver before application code.
- **Transport is healthy but every configured probe fails:** verify mapping, IDs, protocol parameters, and recent configuration changes.

Do not infer that a shared bus is healthy merely because its device node exists; require successful traffic from a peer or trustworthy counters.

### 4. Compare with known-good history

Search for the last positive initialization marker and compare its discovered modules, bus mappings, and IDs with the first failing run. A previously working mapping followed by one persistent missing endpoint usually ranks physical endpoint/power/connectivity above static software configuration.

### 5. Use a tight verification loop

Choose a non-actuating probe when machinery could move. The loop should assert the exact endpoint response or the application's positive initialization marker—not merely that systemd reports `active`.

After hardware intervention, observe a complete startup interval and verify:

- restart count stops increasing;
- the missing endpoint responds;
- the application emits its success marker;
- no new transport errors appear.

### 6. Report by evidence, not speculation

State:

- exact failed endpoint and expected address/ID;
- transport/channel;
- which peers on that same path are verified working;
- host driver/device-node/error-counter evidence;
- which later messages are secondary;
- prioritized physical checks;
- whether the service was actually restored or remains unresolved.

Avoid changing DDS, optional dependencies, or unrelated warnings when evidence isolates a physical endpoint.

## Safety

Robot and actuator diagnostics can cause motion. Prefer read-only inspection. Do not enable motors, send CAN frames, bypass safeguards, or restart a motion service unless scope and physical safety are established.

## Reference

See `references/can-robot-service-example.md` for a condensed real-world evidence pattern and probe set.
