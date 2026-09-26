# Robotics Host Audit Reference

Use this reference when the Linux host runs ROS 2 robotics workloads with cameras, shared memory, motion control, navigation, and AI consumers.

## Evidence layers

Collect evidence from each layer independently:

1. **Hardware presence** — USB/PCI/CAN/serial/video nodes, permissions, occupancy.
2. **Driver/runtime** — vendor SDK enumeration, supported profiles, linked native libraries.
3. **Producer initialization** — driver registration and worker creation in logs.
4. **Transport creation** — expected `/dev/shm` objects, DDS topics, sockets, metadata and calibration objects.
5. **Consumer attachment** — explicit `opened`/subscribed messages and live process FDs.
6. **Application function** — ROS service/action creation, model initialization, control outputs.
7. **Lifecycle behavior** — cleanup, core dumps, restart counters, dependent-unit cancellation.

Never collapse these into one statement such as “camera broken.” A healthy layer does not prove the next layer.

## ROS 2 environment fidelity

A diagnostic shell must reproduce the service environment:

- ROS distro setup;
- workspace/Conda overlay setup;
- `ROS_DOMAIN_ID`;
- `RMW_IMPLEMENTATION`;
- `CYCLONEDDS_URI` or FastDDS profile;
- `AMENT_PREFIX_PATH`, `LD_LIBRARY_PATH`, `PYTHONPATH` when custom interfaces are involved.

A direct Python import without the unit’s library path can produce a false missing-library diagnosis. Conversely, injecting only Python packages from another environment can make message classes import while native ROS typesupport libraries remain unavailable.

## Custom ROS interface failure signature

Typical signature:

```text
Could not load library lib<package>__rosidl_typesupport_introspection_c.so
type_support is null
failed to create service
```

Interpretation:

- Python interface package is visible;
- required native typesupport library is absent or not in the dynamic loader path;
- the failure occurs at ROS entity creation, not necessarily at sensor/SHM attachment.

Verification path:

1. confirm the exact `.so` exists in the intended prefix;
2. inspect its `ldd` dependencies under the unit-equivalent environment;
3. inspect `AMENT_PREFIX_PATH` and `LD_LIBRARY_PATH`;
4. source the complete overlay rather than stitching only `PYTHONPATH`;
5. create the smallest service/client in that environment;
6. only then restart the systemd unit and verify `NRestarts` remains stable.

## Shared-memory producer/consumer model

For camera SHM, identify all expected object families:

- image/data buffer;
- metadata/ring-buffer header;
- intrinsics/extrinsics/calibration;
- optional JPEG/encoded stream.

Interpretation examples:

- object absent + no producer registration → producer skipped or failed before creation;
- object present + consumer `opened` → transport is healthy; investigate later stages;
- object present but stale owner/generation → inspect lifecycle and boot cleanup;
- `/dev/shm` nearly full → capacity issue is plausible;
- plenty of space does not prove producer initialization.

## Navigation chain

Map both launch parent and generated children:

```text
front/rear laser → merger/filter → TF → map server + AMCL
→ global/local costmaps → planner/smoother/controller
→ BT navigator/waypoint/docking → velocity smoothing → base controller
```

Check lifecycle managers and node lifecycle state, not merely process presence. An executable can be running while a lifecycle node is unconfigured or inactive.

## Control and safety chain

For arm/base services, document:

- upstream task/action sources;
- motor/CAN/serial interfaces;
- controller workers or multiprocessing children;
- protection/speed-limit state transports;
- watchdogs and stability services;
- stop behavior (`KillSignal`, `KillMode`, `TimeoutStopSec`).

Short stop timeouts can turn slow native cleanup into SIGKILL and obscure the primary error.

## AI consumer chain

A useful decomposition is:

```text
sensor/SHM → preprocessing → detector/segmenter → pose estimator
→ ROS service/action → task orchestrator → actuator controller
```

GPU/model initialization can be expensive. When `Restart=always` is combined with a deterministic late-start failure, repeated model loading wastes CPU/GPU and can make the whole host appear overloaded. Monitor restart deltas and consider bounded start limits after root cause is fixed.

## Report checklist

- [ ] ROS graph captured with the unit-equivalent DDS environment
- [ ] systemd lifecycle edges distinguished from application data-flow edges
- [ ] expected SHM names and observed objects compared
- [ ] producer and consumer logs both checked
- [ ] stable/on-demand/crash-loop states distinguished
- [ ] restart counters sampled twice
- [ ] native cleanup crashes separated from initial application exceptions
- [ ] exposed ports classified as loopback vs wildcard
- [ ] secrets redacted
- [ ] remediation includes observable success criteria
