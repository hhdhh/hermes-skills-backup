---
name: autolife-slam-mapping-blank
description: Use when 建图模式推着走不出图、/merged 无数据、某雷达 topic 有 publisher但无数据。
version: 1.0.0
---

# AutoLife SLAM 建图空白修复（v2_x 雷达缺失类）

> 完整描述：AutoLife v2_x 机型 SLAM 建图空白/地图无形状修复。Use when 建图模式推着走不出图、/merged 无数据、某雷达 topic 有 publisher但无数据。含两案：v2_4 无前雷达用 3D 中置投影桥接，front+rear 双雷达缺一则后雷达360°转发替代。

## 根因总览

「建图空白」与 DDS 阵营分裂（同见 `autolife-robot-dds-camp-split`）不同，是**合成 /merged 的雷达输入不全**——laser_merger（或 dual_laser_merger）把 front_lidar + rear_lidar 两路合成 360°，缺任何一路则 /merged 为 0 数据 → slam_toolbox 收不到激光 → 建图空白。**雷达本体常正常**（后雷达 10Hz），丢的是某一侧的输入。

## 30 秒诊断（先分清缺哪路，别改框）

逐路测 hz，先确认实际数据流状态，别信 topic 的 Publisher count（有 publisher ≠ 有数据）：
```bash
source /opt/ros/jazzy/setup.bash
# 确认阵营（所有服务 URI 一致，排除 DDS 分裂；不一致先查 dds-camp-split）
# 逐雷达测实际数据：
ros2 topic hz /topic_gv_rear_lidar_0_<机号>      # 后雷达（多数机 360°, ±π）
ros2 topic hz /topic_gv_front_lidar_0_<机号>     # 前雷达
ros2 topic hz /topic_gv_mid_3d_lidar_points_0_<机号>  # 3D 中置点云（v2_4 才有）
ros2 topic hz /merged                            # 合并输出，空 = 雷达输入缺
# 查 sensor_service 日志定位 what not found：
journalctl --user --no-pager | grep -i 'error reading.*lidar'
```
判读：后雷达 10Hz + front 无数据 → 缺前雷达；后雷达 10Hz + 3D点云 10Hz + front 空 → v2_4 缺前2D；日志 `Lidar module mod_lidar_X not found` = 那个雷达硬件没接/没数据，不是软件问题。

## 案 A：v2_4（无前2D，有3D中置点云）—— 3D 投影桥接

配置 `active_robot_version = "robot_v2_4"`，ENABLED_MODULES=[mod_lidar_3d_mid, mod_lidar_rear]，无 mod_lidar_front。laser_merger 硬编码等 front → /merged 空。

修复：写 rclpy 节点订阅 mid_3d 点云，z∈[-0.10, 0.35] 高度带投影成 720 束 LaserScan（0.5°/束，0.10~12m，本体半径 0.25m 内遮挡），发布到 front_lidar topic。脚本模板见本技能 `scripts/pc2_front_scan.py`（robot_id 参数化）。

## 案 B：front+rear 双2D 但 front 硬件缺失 —— 后雷达直接转发

配置 v2_2 等（ENABLED_MODULES=[...front, rear]），但 `journalctl` 报 `mod_lidar_front not found`（硬件没接/坏了），后雷达仍是完整 360°。**此时不需要 3D 投影**——后雷达已覆盖全周，直接把后雷达数据复制到 front_lidar topic 即可让合并器正常合成。改动最小。

脚本（`scripts/rear_to_front_scan.py`）：订阅 rear_lidar LaserScan → 原样发布到 front_lidar topic。部署同案 A：systemd user 服务，environment 带 `CYCLONEDDS_URI`（NetworkInterfaceAddress=127.0.0.1）保证同阵营。

## 部署（两案通用）

```bash
# script + systemd unit：
# ExecStart: source /opt/ros/jazzy/setup.bash && export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp \
#   && export ROS_DOMAIN_ID=0 && export "CYCLONEDDS_URI=<CycloneDDS><Domain><General>\
#   <NetworkInterfaceAddress>127.0.0.1</NetworkInterfaceAddress></General></Domain></CycloneDDS>" \
#   && /usr/bin/python3 /home/ubuntu/<script>.py --ros-args -p robot_id:=<机号>
# unit: Restart=always, After=gv-slam-service
mkdir -p ~/.config/systemd/user && cp <script>.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now <service-name>.service
# 验证（修复前必须能测到会话体系，才能确认修复生效）：
ros2 topic hz /merged                   # 应 ~10Hz
ros2 topic info /topic_gv_front_lidar_0_<机号>  # Publisher count 1
journalctl --user -u gv-slam-service | grep register  # slam 开始 Registering sensor
# App 端经 WebSocket ws://机器人IP:9001/ 收 
{"topic":"map",...}  （9001 是 dashboard_gv_io，不是 8000 kiosk）
```

## 坑

1. **系统 python3 在 source ros 后即可 import rclpy** —— 部署脚本 ExecStart 用 `/usr/bin/python3` 即可，不需 conda python。部署前先测一次：source 后 `python3 -c "import rclpy"`。
2. **ExecStart 里嵌 CYCLONEDDS_URI 单引号会炸** —— 实测 paramiko exec_command 带单引号 syntax error，用双引号包 URI；或 SFTP 写 .service/.sh 再执行。
3. **topic 命名带机号后缀** `_0_<机号>`（如 `_0_320`），robot_id 参数化脚本要传对。
4. **rviz Fixed Frame 默认 map 但 map→odom TF 建图初期未建立会空白** —— 建图初始化或机器人未动时 map→odom 缺失，rviz 什么都没很正常；把 Fixed Frame 临时设 odom 先看激光，或先推机器人建立位姿。
5. **后雷达是完整 360°（front+rear 双雷达机器）** —— 不要以为缺 front 就必须 3D 投影，看后雷达角度范围，360° 直接转发即可。

## 回滚

```bash
systemctl --user stop <svc>
systemctl --user disable <svc>
rm ~/.config/systemd/user/<svc>.service /home/ubuntu/<script>.py
```

## 案例库

飞书案例 003：https://autolife.feishu.cn/docx/SzjKdUjcKoq7fNxwscIcVMO3n6e（321，2026-09-16）
