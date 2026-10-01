---
name: autolife-robot-yolo-deploy
version: 1.0.0
description: Use when S2 机器人部署 YOLO 视觉服务(抓取/找桩)或排障.
metadata:
  requires:
    bins: ["ssh"]
---

# AutoLife S2 YOLO 视觉服务部署

> 触发：在 S2/robot_v2_2 机器人上部署 YOLO/ONNX 检测驱动的功能（瓶抓取、找充电桩、客流识别），或已部署 yolo_grasp 链路排障。铁律：独立服务，不改 vision/arm 官方服务行为。

## Procedure

1. **先定两进程架构**
   - detector：独立 conda env（如 yolo_grasp_env）装 onnxruntime-gpu + opencv-headless；CUDA 用 pip nvidia 全家桶（cublas/cudnn/cufft/curand/cusolver/cusparse/nvjitlink），进程启动前 LD_LIBRARY_PATH 注入全部 nvidia lib 目录。4090 上 yolov8n 单帧 <10ms。
   - executor：必须 robot_env 且 `conda run --no-capture-output -n robot_env python xxx.py`（直跑 python 报 typesupport fastcdr 符号错），对齐官方 systemd unit。
   - 通信：std_msgs/String JSON 话题 `/topic_<name>_<domain>_<robot_id>`。

2. **detector 进程环境顺序（最易踩）**
   - detector 只 source `/opt/ros/jazzy/setup.bash`（rclpy 唯一来源），且必须在 source 任何 robot_env local_setup.bash **之前**启动——local_setup 会把 robot_env site-packages 塞进 PYTHONPATH，detector 会 import 到 robot_env 的 CPU 版 onnxruntime。
   - 同一脚本起两个进程时顺序：source 基础 ROS → 起 detector → source msgs/srvs/actions 三个 local_setup → 起 executor。
   - 启动必看 `YOLO ready provider=`，必须是 CUDAExecutionProvider；出现 "provider not in available names" 警告 = 环境污染，查 import 来源而不是重装 CUDA。

3. **相机接入**
   - face_detection SDK 读 SHM：`sys.path.insert(0, face_detection_env的site-packages)` + `RGBDCamera(config=load_control_config())`。
   - import 铁律：face_detection SDK 在 rclpy 之前（rclpy dlopen ROS libssl 毒化 conda ssl，redis 会挂）。
   - 相机→基座坐标转换用 URDF 零位静态 FK 硬编码（工作站 urdf-parser-py BFS 算 Link_Zero_Point→Link_Camera_Head_Forehead），yolo_grasp_env 里没有 PyKDL。
   - v2 detector 是 **cmd 触发式**（收 GRASP cmd 才检测+发布 detection）："无 detect 日志" ≠ 相机死，先发个 cmd 或直查 SHM 再下结论。

4. **执行链各段（已真机验证）**
   - IK：request `{"pos_left_in_robot":[x,y,z],"quat_left_in_robot":[x,y,z,w],"pos_right_in_robot":...}`；响应取 left/right_arm_body_target_joints（各 11 关节）；q18 = left[0:4]+left[4:11]+right[4:11]（前 4 共享腰腿）。
   - motion planning：官方 ServiceProvider 包装漏参数必须直调 service——request 必须带 `max_step_size`（0.06），否则服务端 `KeyError: 'max_step_size'`；响应 JSON 取 `trajectory` 列表。
   - 夹爪：position 模式 0=开 360=全闭。空爪禁用 360°（堵转大电流，曾引发全机 motor heartbeat lost 保护态），闭合用 250°；力矩模式 ±10 备选。
   - 安全盒 detector/executor **双端重复校验**：基座系 x(0.15,0.6) y(−0.4,0.4) z(−0.15,0.45) 米；先到目标上方 8cm 再下降。IK 对不可达目标照样解出极端关节角，不能只信一端。

5. **DDS（决定服务可见性）**
   - 用 arm-control 阵营的 CYCLONEDDS_URI（lo multicast + `ParticipantIndex none`），否则 IK/motion 服务不可见。完整机制见 skill: autolife-robot-dds-camp-split。
   - 固定 export：ROS_DOMAIN_ID=0 ROBOT_ID=<机号> RMW_IMPLEMENTATION=rmw_cyclonedds_cpp。

6. **全自动演示编排**
   - 全自动链 = heartbeat 触发器 + detector + executor：trigger 周期发 grasp cmd → detector 检测并发布 detection → executor 只在"新鲜(<10s)且进安全盒"目标时动臂（自带 3s cmd 防抖，心跳不会连环触发）。
   - 死锁陷阱：任何只订阅 detection topic 等目标的组件都会饿死——detection 只在收到 cmd 后才发布，链路里必须有人发 cmd。

7. **文件传输**：工作站→机器人用 paramiko SFTP helper（robssh push 对 NetBird-only 机器不可用），push 后两端 md5 校验。

## Pitfalls

- vision-service 会僵尸化：unit active 但内部 ROS context 已死（journal 刷 "publisher's context is invalid"），相机 SHM 流随之冻结。验证 SHM 真死与否：连读两次 `/dev/shm/camera_metadata_struct_<cam>` 帧计数，或对 image buffer 双缓冲两半各取 md5——数据在变就是活的。修复 = 重启 vision 连带 face-detection；vision 重启会重建 SHM 文件，所有旧 reader 进程抱孤儿映射，必须一并重启。
- 远端 `pkill -f <脚本名>` 会匹配到 ssh 下发的 `bash -c` 命令行自身，把远端 shell 一起杀掉（表现为返回空输出）——用 pgrep 拿 PID 精确 kill，pattern 锚定行尾 `$`。

## 支撑文件
- `references/auto-recharge-docking.md` — 自动回充对接栈现状（opennav_docking / laser_line_finder / 桩配置），YOLO 找桩场景的接入点。
