---
name: autolife-robox-slam-mapping
description: 诊断 robox_combined（S2/S3，双臂+AGV 底盘合成平台）机器人「建图不行/图空白/推不动/地图...
metadata:
  triggers:
    - 建图不行
    - 地图空白
    - slam 推不动
    - odom 僵死
    - reset_odom
    - odom_zero
    - gv_task_control
    - 320 建图
    - 321 建图
---

# robox_combined SLAM 建图诊断（S2/S3 平台）

> 完整描述：诊断 robox_combined（S2/S3，双臂+AGV 底盘合成平台）机器人「建图不行/图空白/推不动/地图偏移」类问题。走 odom 里程计初始化→TF 链路→slam_toolbox 丢帧这串因果链定位根因，而不是只看 sensor 有没有数。触发词：建图不行、建不出来、图空白、slam 推不动、地图偏移、320/321 建图。

> 平台：`robox_combined` 型机器人 = arm-control-service（autolife_robot_arm.main，机械臂/灵巧手/腰腿）+ gv-control-service（autolife_robot_gv.main，底盘/传感器）+ gv-slam-service（autolife_robot_gv.main_slam，建图/导航）。三服务各持 ROS_DOMAIN_ID=0。arm 包里的 `gv_task_control.cpython-*.so`（C 扩展）提供**底盘** task control：`node_robot_task_control_service_<id>` 节点、`robot_gv_<node>/reset_odom` 服务、wheel odometry 清零。
> 授权：主人"ssh 到哪台就检修哪台"，凭据多数统一 ${ROBOT_CREDS}，S3 的 320 特例 `robot_initpd`。Guarded（arm/gv-slam/gv-control restart）动手前必须确认现场安全——机械臂服务重启会连带电机整体重新初始化。

## 快速通道：建图不行 → 先查这条因果链

建图空/推不动的病灶九成在**底盘 odom 里程计链路**，不在雷达本身。按序核查：

```bash
# 1. slam 是否在丢帧（核心症状：queue full = 有激光但没运动/没对时）
journalctl --user -u gv-slam-service --no-pager -n 40 | grep -iE "Message Filter|dropping|queue|Registering sensor"
# Registering sensor 出现 = slam 已订阅激光；随后刷 dropping queue full = 运动/TF 断了

# 2. odom_zero 广播的位姿是否恒定（slam 的运动来源）
journalctl --user -u odom-zero.service --no-pager -n 20 | grep -oE "odom[_a-z]*->base=\([^)]*\)" | sort -u
# 多行同一值 = 底盘 odom→base 僵死 → 车在推但 odom 不更新，或 reset 没归零

# 3. main_slam 的 reset_odom 有没有调通（建图模式启动时必调）
journalctl --user -u gv-slam-service --no-pager -n 60 | grep -iE "reset_odom|Wheel odometry"
# 'reset_odom service ... not available within 3s' = 底盘 odom 提供者没起来，里程计没归零

# 4. 底盘 task control 节点这轮到底起没起（reboot 前后对比）
journalctl --user -u arm-control-service --no-pager | grep -oE "\[[a-z_]+_[0-9_]+" | sort | uniq -c
systemctl --user show arm-control-service -p NRestarts -p ActiveEnterTimestamp
# node_robot_task_control_service 出现并打 'Wheel odometry reset to zero' = odom 链路正常；
# NRestarts=0 且该节点零日志 = 这轮没 init（竞态：gv-slam 早于底盘 task control 就调 reset_odom）
```

## 根因判定表

| 症状 | 根因 | 修向 |
|------|------|------|
| slam 刷 `Message Filter dropping ... queue is full` | 激光进得来但运动/TF 链路断 | 走 odom 链（下） |
| odom_zero 广播位姿恒定不变 | 底盘 odom 没在更新，或 reset 没归零 | 确认底盘 task control 起没起 |
| `reset_odom service not available within 3s` | 底盘 `robot_gv_*` 节点没提供该服务 | 重启 arm-control（它内部重 init gv_task_control） |
| `node_robot_task_control_service` 本轮零日志但上一轮有 | 启动时序竞态，底盘 odom init 被跳过 | 重启 arm-control-service |
| 所有服务 NRestarts=0 都 active | 不是服务崩，是某个 init 步骤没走到 | 别查 crash，查「这轮少了哪条 init 日志」 |

## 关键机制（为什么 odom 断了就建不了图）

- slam_toolbox 配置 `slam_toolbox_sync.yaml`：`odom_frame: odom_zero`、`scan_topic: /merged`、`base_frame: base_link`。建图模式 `main_slam.run_gv_slam` 在 slam_mode==build 时先 `_reset_odom()` 清零底盘里程计，再 `launch_laser_merger` + `launch_slam_mapping(reset=True)`。
- 底盘 odom→base_link TF 由 arm 包里的 `gv_task_control.so` 发布（`node_robot_task_control_service` + `robot_gv_<node>/reset_odom` 服务）。它没 init → odom 带着上次残留偏置（如 `(0.555, 0.052, -1.506)`）→ slam 以为车没动 → map 空白。
- odom_zero_node.py 每秒 `lookup_transform('odom','base_link')` 采样并广播 odom_zero→base，值恒定 = 它就是忠实转发一个僵死的底盘 odom。它采样失败会静默 return 不广播，所以**有稳定广播值 ≠ odom 正常**，值变不变才是判据。
- 上一轮 boot 有 `Wheel odometry reset to zero`、这一轮没有，是最干净的「init 被跳过」铁证。

## 坑

1. **`ros2 topic hz / echo` 查不了 robot 实时数据**：在远端跑 `CYCLONEDDS_URI` 绑 `127.0.0.1`（机器人各服务都这么绑）会自建隔离域看不到真节点；不绑则可能 `Failed to find a free participant index for domain 0`（域里已很多参与者）。**别依赖自己起 `ros2 topic` 探活**——要判断 topic 有没有数，看**已跑节点的日志**（odom_zero 的广播、slam 的 Registering/dropping），这比加不进域的 CLI 可靠。
2. 排查「odom 死没死」别只信 `systemctl --user is-active`——服务 active ≠ 内部 odom 初始化完成了。对照日志里「node 有没有打 init/odom 日志」才是真的。
3. 机械臂服务日志会被 `left_arm/right_arm/leg_waist/Stability/VR disconnected` 刷屏，`gv_task_control` 的 odom 日志被淹没——grep 时**专挑 `task_control|odom|wheel|gv_task`**，别一把抓电机/灵巧手行。
4. 建图空不是只有「雷达没数」一种；雷达有数（Registering sensor 出现）但图仍空 = 运动/TF 链路，走 odom 链。

## 跨机参照

同平台另一台能正常建图 = 金标准对照。对比「正常机 odom_zero 广播值在变」vs「故障机恒定」就能快速定位是不是 odom 链；对比「正常机 arm 日志有 `node_robot_task_control_service` + reset to zero」vs「故障机没有」直接锁定缺的 init。对照机若 NetBird 打洞不通（Status: Connecting / ping 丢包），别耗在唤醒上——基于故障机自身日志已能确诊（reboot 前后对比那段）。

## 联网与凭据

- 320 的 NetBird 有多条注册记录（`autolife-robot-320` 死 IP 100.98.147.40 vs `autolife-robot-320-154-122` 活 IP 100.98.154.122）。**对多记录机：`netbird status --detail | grep <机号>` 列全部 + 逐个 ping 挑可达的直连**，别信 `nb <机号>` 自动选对。
- 密码特例 S3/320=`robot_initpd`。`robssh.py` 写死 ubuntu——认证失败时用临时 paramiko 脚本试特例密码验身份，区分「超时(没通)」vs「Authentication failed(密码错)」。
- 修复方向（重启 arm-control-service 重 init gv_task_control → 底盘 odom 归零 → 建图恢复）是 **Guarded**，动手前必须主人确认现场安全（机械臂可能动作）。
