---
name: autolife-docking-recharge
description: Use when 机器人自动回充/对接充电桩/docking 报成功不充电/回充后底盘锁死。S2 尾部对接全链+坑。
---

# 机器人自动回充（docking）实操

## 触发词

"自动回充"、"自动回冲"、"对接充电桩"、"docking"、"充不上电但报成功"、"机器人转不动了（刚对接过）"、"没地图能自己回桩吗"。

## 回充全链与分工

```
地图桩位标注 → Nav2 导航到标注点 → 激光 /detected_dock_pose 锁桩(<2m) →
docking_server 对接（倒车入桩）→ 充电判定（Ah 趋势，勿信 current 传感器）
```

1. **桩位标注**：`<robot_env>/site-packages/autolife_robot_gv/ros_ws/maps/maps_index.json` 的 `dock_pose` 字段（世界坐标 x,y,yaw-rad）。标注存疑时验真：Nav2 导航到标注点 → 激光看是否见桩（`/detected_dock_pose`，frame=base_link）。dock_pose 贴 (0,0) 可能是占位值，必须实地验证。
2. **导航到点**：nav_goto.py（NavigateToPose action）。到点判据 error_code=0 + amcl 位姿误差 <0.3m。
3. **激光锁桩**：`/detected_dock_pose` 是 base_link 相对坐标（x 负=桩在身后）→ **docking 链路不依赖地图**，跨房间可加视觉寻桩补中距。
4. **对接**：dock_probe.py fullinplace（跳过 staging 导航，原地感知+倒车）。返回 success=True + WAIT_FOR_CHARGE。
5. **充电判定（关键）**：见坑 1。

## 关键坑（按代价排序）

1. **「报成功不充电」**：docking_server 返回 success=True + WAIT_FOR_CHARGE，但倒车止停点距桩可能差 ~0.4m，电极未接触。**必须用电池 Ah 趋势判真伪**：充电中 Ah 应持续上行（+10A 时每分钟 +0.16Ah 量级）；电流传感器机队性故障恒 +10.8A 不可信，勿单独采信 current；电压持续上行可作辅证。接触位基准：激光测桩在身后 ≈0.27m；停点 ≈0.67m 即未接触。查询：`ros2 topic echo /topic_gv_battery_0_<机号>` 取 charge 字段，间隔 1-5 分钟采样对比。
2. **充电锁定底盘**：docking_server 进充电态后锁底盘，外部 cmd_vel 旋转只剩斜坡抖动（表现：左右晃、转不动、odom yaw 不变）。**先调 UndockRobot 解锁**（`nav2_msgs.action.UndockRobot`，goal 空）→ success 后底盘释放。每次调完 DockRobot 后要移动底盘，都先 undock。注意：离桩很近时可能再次上锁，移动前重验 odom 是否响应。
3. **相机节点 import 顺序坑（SSL）**：先 import face_detection SDK（redis→conda OpenSSL），再 import rclpy（ROS libssl）；反了 `ssl.VerifyMode=None` 崩。自写相机脚本头部按此顺序。已验真参考：yolo_grasp_service.py 头部注释。
4. **视觉寻桩提示词域差异**：零样本文本提示（'charging dock'）conf 仅 ~0.19 且多假阳性（左右横跳）；visual_prompts 参考框必须用**机器人自拍图**（同相机同视角 conf 0.93+），手机拍的同物体照片迁移不动。多框提示会把参考框自身当目标（同位置同分），提示框须准且唯一。视觉结果需几何交叉验证：bbox 中心 u 换算 yaw（`atan((u-PPX)/FX)`）与激光 bearing 比对，差值 <5° 才可信。
5. **cmd_vel 多发布者抢线**：`/topic_gv_target_cmd_vel_0_<机号>` 有 ~8 个发布者（velocity_smoother/docking_server/dashboard_gv_io 等），自研节点只在厂商状态机空闲时有效。判断被锁：发指令后看 odom yaw 是否变化，纹丝不动=被锁。

## 颈部扫描（代替整机转向找桩）

- 控制：`/topic_arm_whole_body_target_joints_position_0_<机号>`（std_msgs/String，JSON），键 `neck_target_joints_position`（3 元数组，[0]=Joint_Neck_Yaw，弧度，绝对位置）。发后按状态回读 |pos-target|<0.05rad 判到位。
- 状态回读：`/topic_arm_whole_body_and_gripper_current_joints_status_0_<机号>`，键 `neck_target_joint_state.position`。**ros2 topic echo 会截断长 JSON**——解析要 python 订阅落盘再 json.loads，勿在 shell 管道里直接解析。
- 可达范围：Yaw ±71° + 相机半视场 ≈ ±99°，原地不动覆盖几乎整个水平面。
- **扫描策略（用户明确要求）**：颈部步进（如 ±45°、±30°、0）拍帧 → 检测到桩后激光测距 → **确定位置和路线后才动底盘**。勿用整机左右晃动找桩。

## 一次完整回充的执行顺序

```
1. undock（防上次遗留充电锁） → 2. Nav2 导航到 dock_pose 标注点 →
3. 验证激光见桩（/detected_dock_pose） → 4. dock_probe.py fullinplace 对接 →
5. 采 Ah 基线 → 隔几分钟再采 → Ah 上行=真充（不动=坑1，人工推入或调止停参数） →
6. 汇报：对接状态 + Ah 趋势 + 停点距离
```

## 环境与工具

- SSH：deploy304.py（cmd/push）模式（304 NetBird 100.98.53.33，${ROBOT_CREDS}）；robssh push 有 bug 用 deploy 绕。
- 工具目录目标机 `~/autolife_yolo_grasp/`：dock_probe.py（5 模式）、undock.py、turn_deg.py（odom-yaw 闭环原地转）、neck_scan.py（颈部控制）、cam_snap.py（拍帧）、nav_goto.py（导航到点）。
- ROS 查询四件套缺一即 0-publisher 假象：source /opt/ros/jazzy/setup.bash + ROS_DOMAIN_ID=0 + RMW_IMPLEMENTATION=rmw_cyclonedds_cpp + CYCLONEDDS_URI（lo 组播）。
- 双 python 环境：机器人控制用 robot_env，视觉/yolo 用 yolo_grasp_env，勿混。
- 长远程命令 nohup 落盘 + 分次轮询日志，勿单命令内 sleep 等待。

## 边界

- 不适用：SLAM 建图（autolife-ops-slam-troubleshooting）、AI 对话动作、FAE 排班。
- 止停参数（backup_dist 类）属厂商 nav2_params：改前备份，属于 guarded 操作。
- 电流传感器硬件故障：远程修不了，Ah 计数器可用即以 Ah 为准。
