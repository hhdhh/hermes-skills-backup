# Robot 293 Vision/GV Diagnostic Notes

## Session evidence

- `vision-service.service`: `active/running`, `Result=success`, `ExecMainStatus=0`, `NRestarts=0`; process `python -m autolife_robot_vision.main` remained present.
- Vision startup milestones: WebSocket connected; core initialized; RGBD shared-memory color/depth consumers opened; front/rear LiDAR subscriptions created; 60 Hz point-cloud timer created; ROS executor spinning; registration ACK received.
- `journalctl --user -u vision-service -f` stopped at the registration line because follow mode waits for new lines; this was not a hang.
- `/topic_gv_front_lidar_0_293` and `/topic_gv_rear_lidar_0_293` produced about 10 Hz each via bounded `ros2 topic hz` checks.
- `/robot_point_cloud_topic_0_293` showed `Publisher count: 0` and one subscription by `vision_service_0_293`; that alone did not prove vision failed. Inspect the node's actual publications and the consumer/output channel.

## Serial evidence

Expected aliases resolved as:

- `/dev/ttyBattery -> /dev/ttyACM0`, USB ID `1a86:55d3`, path `usb-0:5.1:1.0`
- `/dev/ttyIMU -> /dev/ttyACM1`, USB ID `1a86:55d4`, path `usb-0:5.2:1.0`
- `/dev/ttyLidarFront -> /dev/ttyUSB0`
- `/dev/ttyLidarRear -> /dev/ttyUSB1`

The battery udev rule matched `1a86:55d3` at devpath `5.1`, and `/dev/ttyBattery` had mode `0666`; nevertheless GV logged `Connection to battery reader failed`. Therefore USB enumeration, alias existence, and permissions are insufficient proof of BMS communication. Next checks are process contention (`sudo fuser -v`, `sudo lsof`), then deployed battery config (driver version, port, baud/protocol), then BMS response/power/wiring.

## Deployed-runtime checks

Inspect the actual unit with `systemctl --user cat gv-control-service.service`; it ran `autolife_robot_gv.main` inside the `robot_env` conda environment. Inspect installed configs under the environment's `site-packages/autolife_robot_gv/configs`, not only the wizard source. The deployed `robot_v2_2.json` enabled `mod_battery_main`, `mod_imu_main`, and front/rear LiDAR.

## Warnings classification

- Missing `libunistring.so.2` prevented several GStreamer plugins from loading, including `libgstlibav`, `libgstcurl`, `libgstnice`, and `libgstwebrtc`; assess impact specifically for video/WebRTC rather than treating it as proof that the ROS/SHM vision core failed.
- CycloneDDS deprecated `NetworkInterfaceAddress` and loopback multicast warnings may be harmless for same-host communication but matter for cross-host DDS discovery.
- `pkg_resources` deprecation from `webrtcvad` is non-fatal.
