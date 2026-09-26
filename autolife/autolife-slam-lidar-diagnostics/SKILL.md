---
name: autolife-slam-lidar-diagnostics
description: Use when 机器人建图空白、地图没形状、推到不动、slam 收不到雷达、/merged 空、rviz 看不到...
version: 1.0.0
---

# AutoLife SLAM / 雷达建图诊断与修复（Hermes 版）

> 完整描述：Diagnose and repair AutoLife robot SLAM build (建图空白/地图没形状) and lidar-to-map link failures. Use when 机器人建图空白、地图没形状、推到不动、slam 收不到雷达、/merged 空、rviz 看不到图、激光 topic 无 publisher。Covers the no-front-2D-lidar machine class (v2_4) fix via a pointcloud→scan bridge, plus the rviz-blank-but-data-present TLF trap.

> 适用机型：**robot_v2_4（如 321）** —— 只有 3D 中置雷达 + 后雷达，**无前 2D 雷达**。
> 本技能是 class-level 的雷达/建图链路诊断；属于用户自有 `autolife-doctor-operations` 的技能集群（未 adopt，curator 不能改那个，故独立成册）。

## 症状 → 根因判定

**建图空白 / 地图没形状 / 推到不动 / slam_toolbox 一直 Registering sensor 但不出图** →
先判**雷达数据是否进 slam**，别上来就怀疑雷达硬件坏了。

| 检查项 | 命令 | 判断 |
|--------|------|------|
| 前雷达有 publisher 吗 | `ros2 topic info /topic_gv_front_lidar_0_<id> -v` | **Publisher=0** → 该机型没这个雷达或桥没接 |
| 后雷达正常吗 | `ros2 topic hz /topic_gv_rear_lidar_0_<id>` | 应有 10Hz |
| 3D 中置有 360° 数据吗 | 订阅 `/topic_gv_mid_3d_lidar_points_0_<id>` 解一帧 | 应有 pointcloud，360° 全覆盖 |
| 该机型启用了哪些雷达 | 查 `robot_vX_Y.json` 的 ENABLED_MODULES | **v2_4：只有 mod_lidar_3d_mid + mod_lidar_rear，无 mod_lidar_front** |
| /merged（slam 输入）有数据吗 | `ros2 topic hz /merged` | 空/无 → 合并器没合成出 scan |
| slam 模式 | settings.toml `slam_settings.slam_mode` | `build` 才建图 |

**根因一句话**：`robot_v2_4` 无前 2D 雷达，但 `laser_merger.launch.py` **按 v2_1/v2_2 硬编码** 无条件等 `topic_gv_front_lidar_0_<id>` → 该 topic Publisher=0 → 合并器合成出的 `/merged` 是空的 → slam_toolbox 收不到 scan → 建图一片空白。后雷达/3D 中置都正常。

## 修复（方案 B：pointcloud→scan bridge，热接入，不动 slam/merger/机型配置）

不碰 laser_merger、不碰 slam_toolbox、不碰机型配置。**新增一个纯 Python rclpy 节点**，把 3D 中置点云投影成 2D LaserScan，伪发到「前雷达」topic，让合并器自动恢复合成。**热接入**——bridge 起来链路自动恢复，无需重启任何机器自带服务。

**核心节点**（`pc2_front_scan.py`，本地先写好再 SFTP 推）：
- 订阅 `/topic_gv_mid_3d_lidar_points_0_<id>`（PointCloud2，PointXYZ，point_step=12）
- 高度带投影 `z∈[-0.10, 0.35]`（避开机架结构），`np.frombuffer(msg.data, uint8).reshape(n, point_step)` 解析 x/y/z
- 720 束（0.5°/束），`RANGE 0.10~12.0m`，`CLEARANCE 0.25m`（本体半径内当遮挡，设 RANGE_MIN 制造闭合轮廓）
- 发布 `/topic_gv_front_lidar_0_<id>`（LaserScan，frame_id 沿用 pointcloud 的 `mid_3d_lidar_frame`）
- 纯 stdlib + numpy + rclpy；**本机没有 ros2 环境时 LSP 报 rclpy import 错是正常的**，只在机器人上跑

**systemd user 服务**（`pc2-front-scan.service`）：
- `After=gv-slam-service`、`Restart=always`、enable 开机自启
- unit 内 `source /opt/ros/jazzy/setup.bash` + `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` + `ROBOT_ID=<id>` + **`CYCLONEDDS_URI` 要指 `127.0.0.1`（跟机队其他服务同阵营）**

**⚠️ 引号坑（血泪）**：远端 `exec_command` 里嵌 `CYCLONEDDS_URI='<...>'` 单引号会 syntax error。**用 SFTP 把脚本写到 `/tmp/xxx.sh`（脚本内 CYCLONEDDS_URI 用双引号包），再 `bash /tmp/xxx.sh` 执行**。

## 验证（全绿才收工）

1. `ros2 topic info /topic_gv_front_lidar_0_<id>` → **Publisher count 从 0 变 1**
2. `ros2 topic hz /merged` → **恢复 ~10Hz**（修复前拉不到）
3. `slam_toolbox` 日志出现 `Registering sensor` → slam 开始收 scan
4. `ros2 topic info /map -v` → slam_toolbox 是 Publisher，`/map` 能 echo 出 frame + resolution + 尺寸（非空）
5. WebSocket 通道（主人用它确认后端可达）：`ws://<机器人IP>:9001/` 监听数秒，能收到 `{"topic": "map", ...}` 帧 → dashboard/前端链路通

## ⚠️ rviz 空白但数据都在 —— 查 TF，不是假修好了

修好 /merged 后，**rviz 打开空白 ≠ 数据丢了**。`/map`、`/merged` 明明都有 publisher，但 rviz 看不到 → **查 TF 树**：

- `ros2 run tf2_ros tf2_echo map odom` → 若报 *"frame does not exist"* → **`map→odom` TF 缺失**
- `ros2 run tf2_ros tf2_echo odom base_link` → 正常则 odom→base_link 在

**机制**：slam_toolbox 在 mapping 模式**收到有效 scan 并匹配出初始位姿后才发布 `map→odom`**。刚 `reset` 强制重建图会有窗口期，#**推一下机器人**（产生 odom 运动）它初始化后即出。rviz 默认 Fixed Frame=`map`，缺 map→odom 就空白。

**立刻可见的绕法**：把 rviz **Fixed Frame 设成 `odom`**（odom→base_link TF 在，能立即看 `/merged` 激光和 `/map`）。用 `-d 配置.rviz` 加载预配好的文件（Fixed=odom + Map(/map) + LaserScan(/merged)）。前端 dashboard 手机 app 能显示地图是因为它自己维护 robot_pose，不需要完整 TF 链——**别拿 app 显示来判断 rviz 是否正常**。

rviz 必须在**机器人本地桌面**跑（GNOME 直接开），别用 SSH -X。环境：`source /opt/ros/jazzy/setup.bash` + 上面那套 CYCLONEDDS_URI(127.0.0.1)。

## 侦察命令速查（诊断时省时间）

```bash
source /opt/ros/jazzy/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI="<CycloneDDS><Domain><General><NetworkInterfaceAddress>127.0.0.1</NetworkInterfaceAddress></General></Domain></CycloneDDS>"
ros2 topic info /<topic> -v                    # Publisher/Subscription + QoS
ros2 topic hz /<topic>                          # 频率
ros2 topic echo /<topic> --once                 # 一帧内容(frame_id/尺寸)
ros2 run tf2_ros tf2_echo <A> <B>               # TF 变换存在?  frame does not exist = 缺
ros2 topic info /tf -v                          # 谁在发 TF
journalctl --user -u gv-slam-service -n 40      # slam 日志(找 Registering/error/mode)
```

## 连接 321 特例

- 321 不在本地网段/NetBird 时，主人可能报内网 IP（如 `192.168.65.76`）。
- `robssh.py` 走 NetBird mesh 名会解析成 IPv6 ping 不通 → **paramiko 直连内网 IP，${ROBOT_CREDS}** 最可靠。
- SSH 密码全机队统一 ${ROBOT_CREDS}（含 sudo）。
