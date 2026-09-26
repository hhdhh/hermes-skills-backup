# Autolife service topology audit reference

Use this reference when asked to inspect “all services” on an Autolife robot and explain relationships.

## Report structure

1. **Scope and safety**
   - State SSH target, timestamp, read-only/no-change status.
   - State that secrets were redacted.
2. **Machine baseline**
   - hostname, machine ID, ROBOT_ID, OS/kernel, boot time, user groups, linger state.
   - CPU, RAM, GPU, disk, `/dev/shm`, key USB/PCI devices.
3. **Network and ports**
   - `ip -br addr`, `ip route`, DNS, NetBird/wt0 if present.
   - `ss -lntup` grouped by SSH, web, relay, DB/cache, ROS/DDS.
4. **System services**
   - Group by role instead of listing every static Ubuntu unit:
     - network/time: NetworkManager, wpa_supplicant, resolved, chrony, NetBird
     - devices/media: udev, NVIDIA, PipeWire/ALSA, bluetooth, bolt
     - remote access: ssh, NoMachine, GNOME remote desktop
     - data/logging: PostgreSQL, Redis, journald/rsyslog, cron/timers
5. **User robot services**
   - Table columns: unit, entrypoint, environment, responsibilities, dependency edges, current state.
6. **Runtime/data-flow maps**
   - Vision/RGBD/audio/AI, navigation/SLAM, arm/control, web/relay.
7. **Current risks and actions**
   - Failed units, restart loops, missing libraries/assets/keys, external network failures, open ports, disk/SHM thresholds.
8. **Verification and path appendix**
   - Commands and config/unit paths.

## Common user-level units and meanings

| Unit | Typical role |
| --- | --- |
| `vision-service.service` | Vision core, cameras, RGBD/RealSense, mic/speaker SHM, UDP media sockets, local websocket registration, AI chatbot/TTS hooks. |
| `arm-control-service.service` | Arm/neck/waist-leg motor control, robot action service, protection/stability state. |
| `gv-control-service.service` | Ground vehicle base sensors and motion control. |
| `gv-slam-service.service` | SLAM/Nav2 stack: laser merger/filter, AMCL, map server, planner, controller, BT navigator, docking. |
| `flow-service.service` | Task and workflow orchestration over ROS services/actions. |
| `ai-grasp-service.service` | AI grasp pipeline using RGBD SHM and ROS services; often depends on `vision-service` with `Requires+BindsTo+PartOf`. |
| `face-detection-service.service` | Face detection consumer, commonly bound to `vision-service`. |
| `data-logger-service.service` | On-demand data logging for training/diagnostics. |
| `autolife-relay.service` | External relay/UDP link, often ports 30001–30004. |
| `rust-web-server.service` | Rust web backend, often port 3000. |
| `autolife-admin-build.service` | SvelteKit/Bun admin UI, often port 3001. |
| `logo-backend.service` | Kiosk/Logo backend bridge, often ROS + HTTP. |

## Dependency patterns

- `Requires+BindsTo+PartOf=vision-service.service` means the dependent service is cancelled/stopped when Vision fails or restarts. This explains “Job canceled” during `ExecStartPre=/bin/sleep` when Vision crashes.
- `Restart=always` is common; health must be based on restart counter and logs, not just `active`.
- `After=network.target` is only ordering, not readiness. Cloud/API features still need app-level retries or explicit network/proxy validation.
- Many services use ROS_DOMAIN_ID=0, ROBOT_ID suffixes, and CycloneDDS loopback binding. Use the same environment when running `ros2 node/topic/service/action list`.

## Known Autolife diagnostic distinctions

- **RGBD producer missing:** `/dev/shm` lacks `camera_image_buffer_rgbd_head_color/depth` and logs lack `native-realsense-rs Camera mod_camera_rgbd_head registered`; inspect the actual Vision enabled-module config path.
- **RGBD consumer OK but downstream fails:** consumer logs show `SHMCameraFrameConsumer ... opened`, so investigate AI/ROS/typesupport or application logic.
- **ROS interface typesupport failure:** errors naming `libautolife_robot_srvs__rosidl_typesupport_introspection_c.so` or `type_support is null` usually point to overlay/LD_LIBRARY_PATH/install issues, not camera input.
- **Voice feedback missing:** split OpenAI key, external network, TTS asset existence, TTS backend initialization, and ALSA hardware registration separately.

## Example read-only collection commands

```bash
hostnamectl
systemctl --user list-unit-files --type=service --no-pager --no-legend
systemctl --user list-units --type=service --all --no-pager
systemctl --user --failed --no-pager
find /home/ubuntu/.config/systemd/user -maxdepth 1 -type f -name '*.service' -print
systemctl --user cat vision-service.service arm-control-service.service gv-control-service.service gv-slam-service.service flow-service.service --no-pager
systemctl --user show vision-service.service -p ActiveState -p SubState -p MainPID -p NRestarts -p Result -p ExecStart -p Environment
journalctl --user -u vision-service.service -b --no-pager -n 500
source /opt/ros/jazzy/setup.bash && ros2 node list && ros2 topic list -t && ros2 service list -t
find /dev/shm -maxdepth 1 -printf '%f %s\n' | sort
ss -lntup
```
