# Robot installer audit case study

This reference captures reusable detail from a requirements-to-implementation audit of a Linux robot installer. It is intentionally sanitized: no passwords, setup keys, private URLs, robot identifiers, or vendor credentials are reproduced.

## Source shape

The operational manual mixed several kinds of material in one document:

- router/Wi-Fi/DHCP/IP-MAC/DMZ web configuration;
- Ubuntu identity, stable NIC naming, Netplan, route metrics, display settings, and login policy;
- image-maintenance actions such as disk growth, machine identity, update policy, swap, DKMS, and udev;
- package/service installation, licensing, overlay networking, and server enrollment;
- hardware diagnostics, firmware updates, robot motion, and calibration;
- software update and configuration-template recovery.

The implementation provided a standard-library Python CLI, a loopback-only UI, JSON configuration, backup/rollback, service profiles, diagnostics, and tests.

## High-value mapping pattern

The most important implemented path was:

`wizard/config -> preflight -> identity -> Netplan -> application settings -> diagnostics`

Evidence came from the parser/dispatch and concrete functions rather than the README alone. Useful surfaces included:

- configuration schema and validation;
- stable NIC rendering and guarded Netplan application;
- bounded TOML and systemd environment updates;
- route priority changes;
- service status/actions;
- diagnostics and reports;
- backup manifests and rollback;
- an orchestration plan/run layer.

## Reusable P0 findings

These are common installer risks worth checking in any similar audit:

1. **Complete preflight before mutation** — an orchestrator that writes identity before discovering a missing NIC MAC or missing settings template can leave a half-configured machine.
2. **Rollback all state classes** — backing up a hostname file is insufficient if rollback rejects that privileged target or does not restore runtime hostname/linger state.
3. **Use mutation allowlists** — iterating every user service and injecting environment variables can affect unrelated units.
4. **Derive motion risk from actual units/actions** — a “base” or “local” profile may still start an arm controller; profile names are not safety evidence.
5. **Verify semantics, not command success** — reading a route table is not proof that the intended interface, address, metric, or 5G DHCP state is correct.
6. **Never report completion before local activation** — writing Netplan plus `generate` is only a staged result when `netplan try` still needs a local operator.
7. **Rotate exposed source credentials** — manuals may contain live-shaped setup keys or default passwords. Report and rotate; never copy them into code or audit output.

## Safe automation boundary used

### Safe/default

- schema validation and previews;
- version, disk, time, interface, route, service, ROS, GPU, USB, serial, audio, and camera enumeration;
- bounded config updates with backup;
- report generation and snapshots;
- artifact checksums and source verification.

### Guarded/opt-in

- hostname and service environment changes;
- Netplan writes and route metric changes;
- service enable/disable/start/restart;
- DKMS, disk growth, swap, udev, and package installation only after topology/source checks.

### Human-only

- physical cable/port identification and power cycling;
- router web UI when no stable vendor API exists;
- display orientation and subjective audio/visual checks;
- OAuth, license issuance, and server approval;
- firmware flashing;
- robot motion, calibration, mapping, grabbing, emergency-stop, and shipment acceptance.

## Verification pattern

The target was not a Git repository. The audit therefore used:

- key-file checksums and mtimes;
- final re-reading of parser, dispatch, implementation, tests, and docs;
- `PYTHONDONTWRITEBYTECODE=1` for Python tests;
- source-hash comparison before/after the final test run;
- read-only CLI help and preview execution.

The implementation changed concurrently during the audit. Transient failures caused by partially landed changes were not retained as final product findings. The final state was rebaselined and the full suite was rerun on stable hashes.

## Suggested implementation surfaces

For this class of installer, useful additions include:

- `validate_machine_configuration()` — validates every later-stage prerequisite before writes;
- `audit_network_state()` / `verify_network_state(profile)` — checks MAC presence, duplicate Netplan definitions, address, DHCP, and route metrics;
- section-aware TOML reconciliation followed by parser validation;
- service state checks covering both active and enabled;
- a security audit that detects credential-shaped content without printing values;
- artifact verification and manifest-driven installation rather than wildcard install or `curl | sh`.
