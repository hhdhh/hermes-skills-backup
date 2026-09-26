---
name: autolife-slam-build-recovery
description: Use when 建图空白、slam 服务崩溃循环、Registering sensor 却不产图、URDF 找不到。
---

# AutoLife S1 SLAM 建图修复（Build 模式）

> 完整描述：AutoLife S1 SLAM 建图修复：阻塞建图的四类可诊断问题（配置/URDF/模式/数据流）。Use when 建图空白、slam 服务崩溃循环、Registering sensor 却不产图、URDF 找不到。

> 建图空白/不产图的根因是多层的，先按序诊断，每层都可能单独阻塞。
> 完整建图链路：sensor(雷达硬件) → topic 数据流 → merger(/merged) → slam_toolbox → /map。

## 症状速查

| 症状 | 第一怀疑 | 关键验证 |
|------|---------|---------|
| `Publisher count: 1` 但 hz 空 | 有 publisher 但**发不出数据**（硬件没接/配置没启用模块） | `ros2 topic hz` 实测，别信 publisher count |
| slam 服务 `activating (auto-restart)` 崩溃循环 | 见下方"三根因" | journalctl 找退出码/ValueError/URDF |
| `FileNotFoundError: ROBOT_URDF_PATH` | sdk 缺 `robot_<version>.urdf`（只有 `.example`） | 见"激活 URDF" |
| `ValueError: arrays are 2 and 2 dimensional` | slam_mode=navigating 启用了 laser_line_finder，它要 3D 点但喂 2D scan | `grep slam_mode settings.toml` |
| slam_toolbox Registering 但不产 /map | 见"数据流接错" | 查 merger 报 TF 缺失 |

## 三根因（slam 崩溃循环）——按序排查

1. **配置没启用对的传感器硬件**：`active_robot_version` 写错（v2_2 vs v2_4）。sensor 报 `Lidar module mod_lidar_front not found` 是**硬化配置在等一个不存在的硬件**。改成对机型的 v2_4 并**重启 gv 服务**后，中置 3D 雷达才会被启用并出数据。
   - 判定：SDK 日志 `robot_vX_X Available modules` 列表里有没有该模块；`api.initialize([...])` + `get_mid_3d_lidar_data()` 实测，`not found` = 配置未启用 或 硬件未接。

2. **sdk 缺目标机型的 URDF**：切机型后 `FileNotFoundError: Cannot resolve robot URDF path from autolife_robot_sdk.ROBOT_URDF_PATH`。sdk 目录里只有 `robot_<v>.urdf.example`（未激活），`ROBOT_URDF_PATH` 找的是不带 `.example` 的主文件名。
   - **激活**：`.example` → 去后缀改名/复制成正式名（v2_0/v2_1 大部分机型都预置了 `.example`，激活只是纯改名）。验证：`python -c "from autolife_robot_sdk import ROBOT_URDF_PATH as p; os.path.exists(p)"`。

3. **slam_mode 用错**：`navigating` 模式会 `launch_laser_line_finder_node()`，该节点要 3D 点（`np.cross` 等要求 3 维数组），喂 2D LaserScan 报 `ValueError: Both input arrays must be (arrays of) 3-dimensional vectors, but they are 2 and 2 dimensional` → 崩溃循环。
   - **修法**：建图目标一律切 `slam_mode = "build"`——build 分支只 `launch_laser_merger()` + `launch_slam_mapping()`（slam_toolbox），**不启动 laser_line_finder**。

## 数据流接错（slam_toolbox 起来却不产图）

`async_slam_toolbox_node` `Registering sensor: [Custom Described Lidar]` 只表示建图节点激活，不代表吃到数据。卡点常在 merger：

- `Transform failure, Laser 2: ... not part of the same tree`——merger 要 rear 的 `frame_calibrated`，但 static TF 发的是 `rear_laser_frame`，TF 树断。
- 但 TFM 断常有**瞬态**：重启切换瞬间报，`/tf_static` 就绪后自愈。**验证：`ros2 topic info /tf_static` 看 Publisher count 达标（10 个左右）+ 等几秒再看 merger 日志是否还报**。

## 数据流验证的 DDS 坑

SSH 到机器人用 `ros2 topic echo/hz` 验证时，**DDS 接口必须和观测对象一致**，否则看到"does not appear to be published"是假象：

- slam 各 launch 用 CYC `lo` 非多播接口（日志 `selected interface lo is not multicast-capable: disabling multicast`）。
- 从 SSH 新开会话默认用 enp 多播接口 → **DDS 域隔离，看不到 robot 的 topic**。
- **别在 SSH 会话里硬配 `NetworkInterface name="lo"`**——lo 无多播共享，会 `Failed to find a free participant index for domain 0`，node 都创建不了。
- **可靠的验证口径**：看进程健康（build 节点全 active 无崩溃）+ `/tf_static` Publisher 达标 + merger 日志无持续 TF failure，而**不要依赖 SSH 侧 topic echo 的帧数**。

## 部署计划 Check

1. 备份：`settings.toml.bak.<ts>`、URDF 用 sdk 自带 `.example` 激活（不动原文件）
2. 改配置 → daemon-reload + restart gv 服务
3. 验证不再崩溃：`systemctl --user is-active gv-slam-service` = active（不是 activating/auto-restart）
4. 重启后 journalctl 确认 `SLAM 模式: build` + `Registering sensor [Custom Described Lidar]`

## 复用模板

- PC2→front scan 桥接节点：`~/.hermes/workspace/pc2_front_scan.py`（robot_id 参数化，换机号复用；订阅 mid_3d 点云 → z∈[-0.10,0.35] 高度带投影 720 束 → 发布 front topic；systemd 用户服务，CYCLONEDDS_URI 必须与合并器同阵营）
