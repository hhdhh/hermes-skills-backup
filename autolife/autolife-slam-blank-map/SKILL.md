---
name: autolife-slam-blank-map
description: Use when 机器人建图空白/地图没形状/推着走无轮廓/slam_toolbox 收不到雷达。
---

# AutoLife S1 SLAM 建图空白排查修复

> 完整描述：AutoLife S1 SLAM 建图排查修复。Use when 机器人建图空白/地图没形状/推着走无轮廓/slam_toolbox 收不到雷达。/merged 空 → 定位机型缺前雷达 vs 合并器硬编码。含 PC2→front-scan bridge 修复与 dashboard 地图验证。

## 触发词

"建图有问题"、"地图空白 / 没形状"、"推着走没图"、"slam 重启后还是空"、"/merged 没数据"。

## 症状速查 → 第一检查点

| 症状 | 第一怀疑点 | 验证 |
|------|-----------|------|
| 推着走地图一直空白/无轮廓 | slam 输入 scan 空 | `ros2 topic info /topic_gv_front_lidar_0_<机号>` 看 Publisher count |
| /merged 无数据但后雷达/3D 雷达正常 | 合并器等前雷达，机缺前雷达 | 见下方根因定位 |
| slam_toolbox 一直 Activating 不建图 | 收不到 scan | 日志搜 `Registering sensor`（有 = 开始接数据）|
| App/map 看得到状态但没地图 | App 连错端口 | 见下方 dashboard 验证 |

## 根因定位（核心）

**不同机型雷达配置不同，但 `laser_merger.launch.py` 硬编码等「前+后」雷达合成 /merged**。若某机型没有前雷达，合并器永远等不到 front publisher → /merged 空 → slam_toolbox 建图空白。

1. **先确认机型**：读 gv settings.toml 的 `active_robot_version`（如 `robot_v2_4`），再对比该版本 `configs/robot_v2_<n>.json` 的 `ENABLED_MODULES`：
   - 有 `mod_lidar_front` → 有前 2D 雷达（v2_1/v2_2 等）
   - 只有 `mod_lidar_3d_mid` + `mod_lidar_rear` → **无前雷达**（v2_4 实测）
2. **证前雷达无 publisher**：
   ```bash
   source /opt/ros/jazzy/setup.bash; export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
   export CYCLONEDDS_URI="<CycloneDDS><Domain><General><NetworkInterfaceAddress>127.0.0.1</NetworkInterfaceAddress></General></Domain></CycloneDDS>"
   ros2 topic info /topic_gv_front_lidar_0_<机号>   # Publisher count: 0 = 铁证
   ros2 topic hz /topic_gv_rear_lidar_0_<机号>      # 后雷达 10Hz 正常（排除整组雷达都挂）
   ros2 topic info /topic_gv_mid_3d_lidar_points_0_<机号>  # 3D 中置 PointCloud2 有 publisher（360° 数据源）
   ```
3. **确认所有服务同阵营**（排除 DDS 分裂，见 autolife-robot-dds-camp-split）：全机 `CYCLONEDDS_URI` 都是 `127.0.0.1` = 同阵营，问题不在 DDS。
4. 排除后雷达/odom 本身坏：rear_lidar 10Hz、`/topic_gv_wheel_odom_0_<机号>` 正常发 = 只缺前雷达。

## 修复（方案 B：PC2→front-scan bridge，已验证热接入）

**思路**：用 3D 中置雷达点云（360° 覆盖）投影成 2D LaserScan，伪发到前雷达 topic，让 laser_merger 自然恢复合成 /merged。**不动 laser_merger、不动 slam 配置、不重启 slam（热接入，最安全）**。

1. **先验证 3D 点云可解析**（临时脚本订阅一帧）：frame=mid_3d_lidar_frame，角度覆盖 -180°..180°，距离 0.16~8m = 数据完整可用。
2. **写 bridge 节点**（纯 Python rclpy，零系统改动，不需 apt 装 pointcloud_to_laserscan——ROS apt 源常未配置）：
   - 订阅 `topic_gv_mid_3d_lidar_points_0_<机号>`
   - 高度带投影 `z∈[-0.10, 0.35]` → 720 束（0.5°）
   - RANGE 0.10~12.0m，本体半径 0.25m 内丢弃
   - 发布 `topic_gv_front_lidar_0_<机号>`（LaserScan，frame=mid_3d_lidar_frame）
3. **部署**：脚本传 `/home/ubuntu/` + md5 校验，建 systemd user 服务 `pc2-front-scan.service`（source jazz setup + RMW=cyclonedds + ROS_DOMAIN_ID=0 + ROBOT_ID + CYCLONEDDS_URI=127.0.0.1 + `/usr/bin/python3 <脚本>`，Restart=always, After=gv-slam）。`systemctl --user daemon-reload && enable --now`。
4. **验证链路全通**（逐级，每级都有唯一证据）：
   - `ros2 topic info /topic_gv_front_lidar_0_<机号>` → Publisher count: 1
   - `ros2 topic hz /merged` → ~10Hz（修复前拉不到）
   - `ros2 topic echo /merged --once` → frame=base_link, 720 束 360°
   - slam 日志 → `Registering sensor: [Custom Described Lidar]`（开始接数据）
   - `ros2 topic info /map -v` → slam_toolbox 有 Publisher
   - **oduancy grid 真形状** → 见下方 dashboard 验证

## Dashboard 地图验证（App 看不到图才是终点）

服务器侧链路可能全好，App 还是空图 → **问题在 App 连的地址/端口**。

**关键架构**（321 实测）：
- 8000 = kiosk（logo-backend，前端展示层，只推 `ai/vision/battery` 状态帧，**不是地图**）
- **9001 = dashboard-backend（dashboard_gv_io，ROS2 bridge）**：订阅 /map + odom + imu + front/rear lidar 等，WebSocket 把 `map` 帧推给 App

**验证 App 数据通道**（本机直接连，websocket-client）：
```python
import websocket
ws = websocket.create_connection("ws://<机IP>:9001/", timeout=10)
# 监听几秒，会收到 {"topic": "map", "payload": {header/info/data}} 帧
# 还有 {"topic": "robot_pose", frame_id=map} / odom 等
```
- 9001 **路径是根 `/`**（FastAPI 根 WS），不是 `/ws`——`/ws` 会 403
- App 若配成 8000 或旧端口 → 看得到 AI 状态但没地图，就是这个坑
- **地图真形状判据**：抓 map 帧，`info.width × height`、`occupied(==100)` 格数 > 0（如 73×182 / 286 障碍格）即 slam 在建真图，不再是空

## 坑（真机踩过）

1. **跨网段机器不在 robots.json** 时不要只靠 robssh（走 NetBird mesh 名会解析成 IPv6）——现场内网 IP（主人给的 `192.168.65.76`）paramiko 直连更可靠。
2. **远端命令引号坑**：命令含 `CYCLONEDDS_URI="<...>"` 单引号会 syntax error → 用 SFTP 写脚本文件 (/tmp/xxx.sh) 再 `bash`，脚本内双引号包 URI。
3. **dashboard 包源码是编译 .so + .pyi**，grep 前端 JS 会撞上一堆 `ts.worker`/monaco 噪音——直接从 `.pyi` 的 `def start(host, port=9001)` 认端口，别死磕编译 JS。
4. **Ops 图验证别用 browser tool**（real-profile 起不来）——用 Python websocket-client 直连验证更快更可靠。
5. **地图大小不随推动即时变全**：刚初始化只有 23×47 / 局部区域，大部分 data=-1（unknown）正常——确认 non-unknown 里有 occupied(100) 格就算在建，不必等满图。

## 相关技能

- DDS 阵营分裂（同症状易混淆）：`autolife-robot-dds-camp-split`
- 机器人连接/凭据/机队定位：`autolife-remote-repair` / `autolife-find-robot`
