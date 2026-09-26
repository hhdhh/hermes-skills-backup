---
name: autolife-slam-bridge
description: Use when v2_4 机器建图空白/地图无形状、/merged 无数据、front_lidar topic...
version: 1.0.0
---

# AutoLife SLAM 桥接修复（v2_4 机型）

> 完整描述：AutoLife v2_4 机型（3D中置雷达+后雷达，无前2D雷达）SLAM 建图空白修复：用 PC2→2D scan 桥接节点替代前雷达输入。Use when v2_4 机器建图空白/地图无形状、/merged 无数据、front_lidar topic 无 publisher。

## 根因

v2_4 机型 ENABLED_MODULES 无 mod_lidar_front（只有 mod_lidar_3d_mid + mod_lidar_rear），但 laser_merger.launch.py 硬编码订阅 front_lidar + rear_lidar 合成 /merged → front 恒无 publisher → /merged 空 → slam_toolbox 建图空白。

## 30 秒诊断

1. `ros2 topic info /topic_gv_front_lidar_0_{机号}` → **Publisher count: 0**
2. `ros2 topic hz /topic_gv_mid_3d_lidar_points_0_{机号}` → 正常（360° PointCloud2）
3. `ros2 topic hz /merged` → 无数据
4. 后雷达 + odom 正常（排除硬件故障）
5. settings.toml `active_robot_version = "robot_v2_4"` 确认机型

## 修复（方案 B：桥接节点，不改 slam/merger，热接入）

脚本已存本技能 `scripts/`：
- `pc2_front_scan.py` — rclpy 节点：订阅 mid_3d 点云 → z∈[-0.10,0.35] 高度带投影 → 720 束 LaserScan（0.5°/束，0.10~12m，本体半径 0.25m 遮挡）→ 发布到 front_lidar topic。robot_id 参数化，换机号即可复用。

部署（paramiko/SFTP 上传后）：
1. 上传 pc2_front_scan.py 到 `/home/ubuntu/`，md5 校验
2. 写 `~/.config/systemd/user/pc2-front-scan.service`，unit 关键：source /opt/ros/jazzy/setup.bash + RMW_IMPLEMENTATION=rmw_cyclonedds_cpp + ROS_DOMAIN_ID=0 + **CYCLONEDDS_URI 含 NetworkInterfaceAddress=127.0.0.1**（同阵营铁律）+ ROBOT_ID={机号} + `/usr/bin/python3 /home/ubuntu/pc2_front_scan.py`，Restart=always，After=gv-slam-service
3. `systemctl --user daemon-reload && systemctl --user enable --now pc2-front-scan.service`

## 验证

- `ros2 topic info /topic_gv_front_lidar_0_{机号}` → Publisher count: 1
- `ros2 topic hz /merged` → ~10Hz
- slam 日志 `Registering sensor`
- App/WS（`ws://机器人IP:9001/`）收 `{"topic":"map",...}`

## 已知坑

- **rviz 空白≠没建图**：slam 强制 reset 后 map→odom TF 需机器人动过才建立；Fixed Frame 临时设 odom 可先看激光。
- App 地图走 **WS :9001**（dashboard_gv_io），不是 8000（kiosk）。
- 远端 exec_command 含 CYCLONEDDS_URI 单引号会炸 → SFTP 写 .sh 再 bash 执行（内用双引号）。
- 8000 端口是 kiosk（logo-backend）；9001 是 dashboard-backend（map 转发）。

## 回滚

```
systemctl --user stop pc2-front-scan.service
systemctl --user disable pc2-front-scan.service
rm ~/.config/systemd/user/pc2-front-scan.service /home/ubuntu/pc2_front_scan.py
```

## 案例库

飞书案例 003：https://autolife.feishu.cn/docx/SzjKdUjcKoq7fNxwscIcVMO3n6e（321，2026-09-16）
