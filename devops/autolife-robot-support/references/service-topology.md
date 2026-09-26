# 服务拓扑与故障签名速查

## 服务分层（systemd --user，全部 Restart=always）

| 层 | 单元 | 职责 | 故障时表现 |
|---|---|---|---|
| 驱动层 | `gv-control-service` | 底盘控制 + 传感器读取（雷达/IMU/里程计），SDK 模块初始化 | `Error reading <sensor> data: module not found` 刷屏 |
| SLAM 层 | `gv-slam-service` | conditional launcher + AMCL + Nav2 + 地图/点位管理 | 卡在 `Received /topic_...` 后沉默 |
| 应用层 | `ai-grasp-service` / `arm-control-service` / `face-detection-service` / `flow-service` / `dashboard-backend` / `autolife-relay` | 抓取/手臂/人脸/业务流/看板 | 各自独立 |

## gv-slam 门闸链（navigating 模式）

```
gv-control 发布:
  /topic_gv_wheel_odom_<domain>_<robot>   (e.g. _0_277)
  /topic_gv_front_lidar_<id>
  /topic_gv_rear_lidar_<id>
       │ 三话题到齐（conditional launcher 门闸）
       ▼
  laser_merger → /merged
       ▼
  localization (AMCL + map_server) → /initialpose → TF ready
       ▼
  navigation (bt_navigator/controller/planner/smoother/behavior/
              waypoint_follower/velocity_smoother/docking + lifecycle)
       ▼
  /costmap 出现 = 全链健康
```

健康一轮的 journal 特征（用于对比基准）：
`Conditional launcher started` → 三行 `Received /topic_*` → `Launching laser merger` → `Launching localization` → amcl `Received a WxH map` → `Launching navigation` → `Received /costmap`。

## 故障签名 → 病根对照

| 日志签名 | 病根位置 | 动作 |
|---|---|---|
| `Stopping gv-slam...` + 同秒再启动 + bash_history 对上时间戳 | 人为 restart，非故障 | 归因即可 |
| Stopping 之后 `CondaError: KeyboardInterrupt` / `status=1` | KillSignal=SIGINT 的退出码噪音 | 忽略 |
| launcher 收到 2/3 话题后沉默 | 缺的话题在 gv-control 侧死亡 | 查 gv-control 的 sensor 错误刷屏 |
| `Error reading rear lidar: mod_lidar_rear not found` 刷屏 | 后雷达模块未初始化（供电/线缆/驱动未恢复） | 先重启 gv-control，无效则断电查硬件 |
| `navigate_to_pose action server not available` | Nav2 没起（门闸未过）| 回溯上面的门闸链，别重启 gv-slam |
| Nav2 各进程 `process has died exit code -2/-11` 成批出现 | 上轮 stop 时的正常清场（SIGINT 波及）| 看是否伴随新一轮启动 |

## 话题/环境约定

- 话题名带后缀 `_<ROS_DOMAIN_ID>_<ROBOT_ID>`（如 `_0_277`），ROBOT_ID 从主机名尾号来。
- unit `Environment=` 钉死：`ROS_DOMAIN_ID=0`、`ROBOT_ID`、`RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`、`CYCLONEDDS_URI=...NetworkInterfaceAddress=127.0.0.1`（回环单播，跨机 shell 发现不了节点）。
- `NetworkInterfaceAddress` 是 CycloneDDS 已废弃写法；哪天要跨机通信改 `NetworkInterfaces` 语法。
- 雷达不走 USB 串口（ttyUSB 是 PEAK CAN）；雷达挂主控板，供电/线缆问题在整机层面查。
- 停止时的 `PeriodicTimer error ... InvalidHandle` traceback 是 SIGTERM 关闭竞态，非独立故障。
