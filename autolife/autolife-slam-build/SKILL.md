---
name: autolife-slam-build
version: 1.0.0
description: 修复 AutoLife S1/S3（v2_4 机型）SLAM 建图：主人说"X 机建图问题/建图空白/扫描地图看不...
---

# AutoLife SLAM 建图修复（v2_4 / S3 机）

> 完整描述：修复 AutoLife S1/S3（v2_4 机型）SLAM 建图：主人说"X 机建图问题/建图空白/扫描地图看不到"时用。覆盖 v2_4 配置切换、URDF 激活、build vs navigating 模式、中置3D→front 桥接、DDS 穿透验证、开机自启。触发词：建图、slam、扫描地图、ROS map、v2_4。

> 根因类：v2_4 机型**无前 2D 雷达**，前端靠**中置 3D 雷达**投影。建图空白 = 数据流没到 slam。
> 姊妹技能：`autolife-remote-repair`（SSH/凭据/机号联系统一）、`autolife-find-robot`（换 IP 定位）、`autolife-robot-dds-camp-split`（DDS 域）。
>
> 关键：**改配置与重启 gv-slam-service 是 Guarded 操作**，动手前向主人说清改什么、为什么；其余（改 settings.toml、激活 URDF、部署 bridge、enable/start 服务）普通权限直接做，但**每步都备份 + 验证**。

## 触发与目标

主人说"建图问题"、"建图空白"、"扫描地图出来吗/看不到"、"推开走一圈没有地图" → 走这套。目标是 `/map` 有**真实障碍格**（非全 -1）且数据流 `rear+front → /merged → slam → /map` 全部有帧。

## 诊断顺序（先确诊再动手，按 1→5）

1. **连上机器 + 验明正身**：`robssh.py <机号> 'hostname'`（换网段连不上 → 先 `robssh.py scan --force` 或 DNS PTR）。320 密码是 **robot_initpd**（特例，非统一 ubuntu）。
2. **看 settings.toml 当前配置**：
   - `active_robot_version` = `robot_v2_4`？（v2_4 = 中置 3D + 后雷达，无前 2D）
   - `slam_mode` = `build`？（build = 建图，navigating = 导航）
3. **gv 服务状态**：`systemctl --user status gv-slam-service`——是否 `active`、是否 `enabled`（**disabled 会不自启，改完必须 enable**）。
4. **数据流实测（穿透 DDS）**：见下方"DDS 穿透验证"。
5. **/map 内容**：订阅 /map 统计障碍格。全 -1 = slam 没吃到 scan；有 occ>0 = 建图在工作。

## 四根修法（按需组合）

### A. 切 v2_4 配置（启用中置 3D 雷达）
`active_robot_version = "robot_v2_4"` 会启用 `mod_lidar_3d_mid`（中置 3D 雷达 10Hz 出点云）。
之前 `mod_lidar_3d_mid not found` **多半是配置没切**，不是硬件缺失——v2_2 配置根本不初始化中置雷达。切完重启 gv-slam-slam 生效。

### B. 激活 v2_4 URDF（sdk 只有 .example）
症状：gv-slam-service 崩溃循环，日志 `FileNotFoundError: Cannot resolve robot URDF path from autolife_robot_sdk.ROBOT_URDF_PATH`。
原因：launcher_manager 找 `urdfs/robot_{active_version}.urdf`，但 sdk 里 v2_4 只有 `.urdf.example`（未激活），v2_2 是被"激活"过的（去掉了 .example 后缀）。
修复：把 `.example` 复制成正式名（内容一致，可与同机 v2_2 的 md5 核对）：
```bash
U=.../autolife_robot_sdk/descriptions/autolife_s1/urdfs
cp "$U/robot_v2_4.urdf.example" "$U/robot_v2_4.urdf"
cp "$U/robot_v2_4_simplified.urdf.example" "$U/robot_v2_4_simplified.urdf"
cp "$U/robot_v2_4_calibration.urdf.example" "$U/robot_v2_4_calibration.urdf"
```

### C. slam_mode 切 build（navigating 会崩）
症状：navigating 模式 `main_slam` 崩溃循环，日志 `laser_line_finder.py ... ValueError: Both input arrays must be (arrays of) 3-dimensional vectors, but they are 2 and 2 dimensional`。
原因：navigating 启用 `laser_line_finder`，它要 3D 点数组但喂进来的是 2D LaserScan → 崩。
修复：`slam_mode = "build"`（main_slam 的 build 分支只起 merger + slam_toolbox，不用 laser_line_finder，绕开崩溃）。**建图 = build 模式，和已修复的 321 一致。**

### D. 中置 3D → front 桥接（build 模式需要 front）
v2_4 build 的 merger 要 front scan 输入，但 native `pc2scan_arm_filter` **在 build 下不一定输出 front**。用单独 bridge 节点把 `/topic_gv_mid_3d_lidar_points_0_<id>` 投影成 `/topic_gv_front_lidar_0_<id>`。
脚本：`pc2_front_scan.py`（机器人上 `/home/ubuntu/pc2_front_scan.py`，robot_id 参数化，默认值改机号；z∈[-0.10,0.35]、720 束、RANGE_MAX=12m、CLEARANCE=0.25）。systemd user 服务：`pc2-front-scan.service`，`After=network.target`，ExecStart 用 `/usr/bin/python3` + source ros + RMW=rmw_cyclonedds_cpp + CYCLONEDDS_URI=127.0.0.1。**用后 `enable`（开机自启）。**

## DDS 穿透验证（关键：别被 doman 隔离骗了）

slam/merger/bridge 都 launch 在 `CYCLONEDDS_URI` `NetworkInterfaceAddress=127.0.0.1`（lo，禁多播）。**我的独立 SSH `ros2 topic` CLI 进不了它们的数据域**——`ros2 topic hz/echo` 返回空/"does not appear to be published yet" 不代表系统故障。

可靠验证：**在机器人上写个小 rclpy 订阅者**，设**和 slam 相同的 CYCLONEDDS_URI**，订阅 rear/front/merged/mid3D/map 统计 15s 帧数：

```bash
cd /home/ubuntu &&
export CYCLONEDDS_URI='<CycloneDDS><Domain><General><NetworkInterfaceAddress>127.0.0.1</NetworkInterfaceAddress></General></Domain></CycloneDDS>'
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export LD_LIBRARY_PATH=/usr/local/lib/:$LD_LIBRARY_PATH
source /opt/ros/jazzy/setup.bash
# 脚本: create_subscription 到 5 个 topic, 统计帧数
```

判据：rear≈front≈merged≈mid3D≈10Hz 且三者接近（150 帧/15s），`/map` 有帧 → 数据流通。若 rear 有但 merged=0 → merger/桥接没合成。

`ros2 topic echo /map --once --qos-reliability best_effort --qos-durability transient_local` 能拿到 /map（slam 发 transient local）；但 data 是逐行 `-1`，正则解析易漏，**用 rclpy 订阅拿 `.data` 数组最稳**。

## /map 会骗人：全 -1 不一定是死了

刚重启 slam 时 `/map` 发布但 data 全 -1（unknown 占位）。**只有 slam 吃到 scan 后才写入障碍/自由格**。判定"建图是否工作"看**有没有 occ>0 和 free>0**（如 21 occ + 299 free = 有真实地图形状）。机器人静止时地图很小——**推着走才展开**，主人以为"还是不行"很可能只是没推动。

## 开机自启铁律

gv 系服务 systemd unit `enabled` 状态可能为 **disabled**（预设 enabled 但生效 disabled）。**改完后 `systemctl --user enable gv-slam-service`（以及 bridge 服务），否则机器一重启 slam 就不自动起，表现为"又不行了/没服务自启"。**

## 验证闭环（每次都说给主人）

1. 服务 `active` + `enabled`
2. 数据流 rclpy 订阅帧数（rear/front/mid3D/merged 全 10Hz）
3. `/map` 有 occ>0 + free>0（真实形状）
4. 改了什么 / 前后对比 / 需推着走才展开

## 已知坑

- **v2_4 native 也有 pc2scan_arm_filter**：navigating 下它自己把 mid3D→front，我再加 bridge 会**重复/干扰**甚至触发 laser_line_finder 崩溃。**build 模式才需要单独 bridge。** 判断 front topic 是否已被 native 发布：rclpy 订阅 front 看有没有帧 + Publisher count。
- **Robots.json `_resolved` 会过期**：机器换网段（320 从有线 10.2 到无线 65.48）后 robssh 返回旧 IP。以 `robssh scan --force` 或 DNS PTR 重新解析为准，连上先 `hostname` 验明正身。
- **320 密码 = robot_initpd**（特例，非统一 ubuntu）。
- `/tmp` 写脚本验证时若 ImportError `OccupancyGrid` 在 sensor_msgs——它在 `nav_msgs.msg`。
