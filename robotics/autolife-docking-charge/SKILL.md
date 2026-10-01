---
name: autolife-docking-charge
description: |
  Use when 自动回充/充电验证/docking成功不充电/充电后底盘锁死/采集前验底盘可动. 
---

# AutoLife 机器人自动回充与充电链路

覆盖：回充链路逐段验证、真充电判据、止停偏差量化、充电锁诊断、采集/训练防呆。机型以 S2/robot_v2_2 为实测基准（cmd_vel 话题名带 `_0_<机号>` 后缀）。

## 铁律：运动指令闭环验证

- 底盘运动指令（cmd_vel/drive/turn）执行后必须读 odom 前后差验证，开环计时输出（"DROVE x m"、速度×时长推断）是假象——底盘被锁时照样打印成功。
- turn 类脚本 `err = ±全额目标角` = 根本没转（yaw 纹丝不动，误差等于整个目标）。
- 充电态（battery current > 0）下底盘被厂商控制层硬锁：指令静默丢弃、无报错、无日志。
- 声称"已完成采集/移动"前必须采样 AMCL/odom 对比位置；位置无变化 = 数据全部同机位（训练即背题，val 高分无意义）。用户对未验证的采集零容忍。

## 回充链路验证顺序（沿链找首个断点）

1. **地图标注验真**：读 `maps_index.json` 的 active_map → dock_pose → `nav_goto.py <x> <y> <yaw_deg> <timeout>` 导航到点（RESULT|error_code=0）→ 激光 `/detected_dock_pose` 见桩 <0.5m = 标注真实（例：bgs 图 [0.014, -0.008, 3.06]）。
2. **对接**：dock_probe fullinplace 走 DockRobot action，观察 states 链（INITIAL_PERCEPTION→CONTROLLING→WAIT_FOR_CHARGE）。
3. **充电验证（唯一可信判据）**：采样 `/topic_gv_battery_0_<id>` 的 charge(Ah) ×3-4 次、间隔 ~60s。Ah 上升（+0.5Ah/3min ≈ 11A）= 真充；完全持平 = 假对接。电流传感器 fleet 缺陷不可信（放电时 current 为负仍正常显示）。
4. **止停偏差量化**：对接后读激光桩距。报 success 但 Ah 平 = 止停早：自动止停在桩后 ~0.67m，真接触 ~0.27m，差 ~0.4m 即需补偿量（对照 docking 配置 `nav2_params.yaml` 的 `docking_server` 段：staging_x_offset/docking_threshold；改前备份）。
5. **人工摆正的黄金位姿**：用户手推入桩后记录 AMCL 位姿 + 激光桩距（0.25-0.27m 接触态）+ Ah 上率，留作补偿基准与验收对照。
6. **脱桩**：先 UndockRobot，再用运动探针验证真解锁（见下）。

## 充电锁快速诊断

1. **真伪探针**：发 0.1m/s × 3s，前后 odom 差。dx=0.000 = 硬锁实锤。电机佐证：`/topic_gv_current_motors_status_0_<id>` 的 `gv_motor_state.position` 6s 零变化；speed/torque 有非零悬浮值，不作运动证据。
2. **undock 两态判定**：docking_server WAIT_FOR_CHARGE 态锁（未真充电时）→ UndockRobot 可解；充电真锁（current>0）→ action 返回 success=True error_code=0 但不执行。**undock success ≠ 解锁，唯一标准是 odom 动没动。**
3. **清僵尸**：挂死的 dock_probe/nav_goto 各持一个 DockRobot goal，`pgrep -af "dock_probe|nav_goto"` 全杀再诊断。
4. **深挖**：锁点在 node_robot_task_control_service（宿主 autolife_robot_arm.main，不在 gv 包）→ 详见 [references/charging-lock-deep-dive.md](references/charging-lock-deep-dive.md)。

## 采集与训练防呆

- 采集编排每步后验证 AMCL 位置变化，无变化立即停——机器人在桩上充电时一切移动指令均无效，继续拍只会产出同机位废数据。
- 多样性采集 = 距离（0.8/1.4/2.0m）× 朝向（0/±30°）× 颈部视角（0/±40°）；颈部扫视角勿整机乱晃（Joint_Neck_Yaw ±71° + 相机半 FOV≈±99°）。
- 自动标注用 YOLOE 视觉提示（predictor=YOLOEVPSegPredictor，visual_prompts={"bboxes","cls"}）：conf≥0.6 收、<0.6 弃（低置信框坐标不准会污染训练）；无检测帧留作真负样本。
- 视觉提示参考框必须用**机器人自拍图**（conf 0.93-0.99）；手机照片域差异迁移失败。提示框本身会被以 ~0.91 检出，标注取最高分框并跑跟踪滤波。
- CLIP 依赖走代理：`uv run --with ultralytics --with "git+https://gh-proxy.com/https://github.com/openai/CLIP.git"`（ghfast.top 解析失败时换 gh-proxy.com）。

## 核心坑

- CYCLONEDDS_URI 必须与目标机阵营一致 export，否则 0 publisher 假象（详见 autolife-robot-dds-camp-split）。
- `ros2 topic info -v` 订阅者列表可能过期：`ros2 daemon stop && ros2 daemon start` 后重查。
- pkill 匹配到自身命令行会自杀：用括号法 `pkill -f "collect_doc[k]"`。
- 经 SSH 桥跑长命令：nohup + 日志落盘 + 轮询，不阻塞等。
- CAN/PCAN 设备单进程独占：SDK HWAPI 直连 mod_motor_gv 报 "Motor not responding on PCAN_USBBUS*"；持有者用 `fuser /dev/pcanusbfd*` 查。
- bash -c 命令串里 echo 文本含未转义 `()` 会 syntax error，去括号或引号包裹。

## 边界

- DDS 阵营分裂（数据僵死/0 publisher）走 autolife-robot-dds-camp-split，本卡只在充电锁/回充链路。
- 建图/导航故障走 autolife-ops-slam-troubleshooting。
- 五层健康模型整机体检走 autolife-ops-robot-diagnosis；本卡专注回充链与充电锁深挖。
- 相邻旧技能（autolife-robot-troubleshooting / autolife-ops-robot-diagnosis 等）为用户自管，后台不可改；如内容与本卡冲突，以本卡实测结论为准，并建议用户 `hermes curator adopt <name>` 后同步。
