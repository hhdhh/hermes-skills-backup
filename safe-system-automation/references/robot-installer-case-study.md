# Robot installer case study

A field manual mixed router credentials, Netplan, hostname/ROS identity, package updates, display settings, disk/swap, PCAN DKMS, udev, firmware, licensing, diagnostics, calibration, and robot motion. The safe implementation split these rather than creating one unattended script.

## Automated orchestration

The implemented class of flow was:

1. Validate config and required identity.
2. Run read-only environment checks.
3. Enumerate live interfaces and require configured LAN/5G MACs to exist.
4. Render Netplan and application setting updates in memory.
5. Confirm home, service directory, and application settings/template exist.
6. Request sudo once.
7. Update profile, hostname, linger, and existing user-service environment variables.
8. Write a MAC-bound Netplan file and run `netplan generate`, but do not activate it.
9. Merge only managed keys into application TOML; preserve unrelated site settings.
10. Run diagnostics and return a local `netplan try --timeout 120` hold point.

The CLI used `configure plan`, `configure run` (preview), and `configure run --apply`. The loopback Web UI only exposed copyable versions of those commands.

## Transaction design

All file mutations shared one backup session. Existing files were copied; newly created files were recorded. The manifest was HMAC-signed with a local key, its session ID had to match its directory, backup payloads had to remain inside the session directory, and privileged restoration targets were allowlisted. A mid-run write failure attempted rollback and reported rollback failure separately.

A raw diagnostic snapshot remained explicitly local-only and was not accepted as a rollback input.

## Manual boundaries retained

- Router password, SSID, IP/MAC binding, and DMZ
- Display orientation and automatic login
- Partition growth and swap replacement
- PCAN/DKMS, udev, machine-id
- Camera firmware
- Company packages, HWID, licenses, server/tablet binding
- Calibration, reset, mapping, navigation points, grasp tuning, order execution, stress loops, and all robot motion

The manual included default credentials and broad commands such as wildcard wheel installation and disabling update services. These were not embedded. The tool instead preserved secrets, package/environment separation, security updates, PipeWire, and onsite motion gates.

## Verification pattern

Useful tests covered:

- dry-run stage order;
- no sudo/write after preflight failure;
- all target validation before first mutation;
- MAC absent and present cases;
- created-file rollback bookkeeping;
- signed restoration of managed hostname/Netplan targets;
- automatic rollback after injected mid-run failure;
- SSH Netplan activation rejection;
- Web UI absence of an apply endpoint;
- archive version/contents/cache exclusion.

The software checks can pass on a development host, but real robot hardware, ROS graph, cameras, radar, networking activation, and motion require site acceptance and must be reported as such.
