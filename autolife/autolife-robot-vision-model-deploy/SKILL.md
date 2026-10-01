---
name: autolife-robot-vision-model-deploy
version: 1.0.0
description: Use when 机器人要跑YOLO/ONNX识别或识别抓取;独立服务+双进程全链路部署。
---

# AutoLife 机器人视觉模型部署（YOLO→识别→抓取 全链路）

> 核心原则：新增能力一律**独立进程 + 独立 conda env + 自有 DDS topic**，绝不改存量 vision/arm/gv 服务。
> 首个全链路实例：304（S2/robot_v2_2, RTX 4090）yolov8n 瓶子抓取，注入目标全序列真机执行通过。
> 相关用户自建技能（不可代改，需要时自己读）：autolife-robot-vision-diagnostics、autolife-robot-dds-camp-split、autolife-remote-repair。
>
> **选型分流**：本 skill 适用于本地模型推理/臂抓取联动（低延迟、离线、坐标输出）；若只是给**对话**加"看一眼回答"能力（我手里拿的啥/这是什么），不要建独立服务——用 robot_tool + 云端 VL 的轻量路径，见 skill: autolife-ai-dialog-deployment 的「对话内视觉识别」节。

## 触发词

"在机器人上跑 yolo/视觉模型"、"加识别抓取功能"、"部署 onnx 推理到机器人"。

## 标准流程

1. **选型+导出（工作站）**：独立 venv 装 ultralytics；GitHub 直连不通时权重走 `gh-proxy.com/` 前缀。`yolo export model=yolov8n.pt format=onnx opset=18 imgsz=640`，核对输入 [1,3,640,640] 输出 [1,84,8400]。COCO bottle=class 39。
2. **建独立 env（机器人）**：`conda create -n <proj>_env python=3.12` + 清华源 pip：onnxruntime-gpu opencv-python-headless posix_ipc pyyaml toml。机器人有外网（pypi 通，GitHub 不通）。
3. **CUDA 启用**：pip 装 nvidia 全家桶（cublas/cudnn/cufft/curand/cusolver/cusparse/cuda-runtime/nvjitlink）；进程起动时把 env 内 `nvidia/*/lib` 拼进 `LD_LIBRARY_PATH`（必须在 import onnxruntime 前生效）。验收标准：日志 `provider=CUDAExecutionProvider`（4090 上 yolov8n 约 6ms/帧，CPU 版 90ms+）。
4. **相机读取**：复用 face_detection SDK——`sys.path.insert` face_detection_env 的 site-packages，`RGBDCamera(config=load_control_config())`。SHM：`camera_image_buffer_rgbd_head_color/depth`，640×480，内参从 `get_intrinsics()` 取。
5. **双进程架构**：检测进程（自建 env，用 env 的 python 绝对路径直接起）+ 执行进程（robot_env 官方 env，**必须** `conda run --no-capture-output -n robot_env python x.py`）。自有 topic 命名 `/topic_<proj>_<用途>_<slot>_<机号>`，std_msgs/String 装 JSON。
6. **坐标变换**：URDF 拉回本地，urdf-parser-py 从 Link_Zero_Point BFS 到 Link_Camera_Head_Forehead 算零位静态 FK 得 T_base_cam 硬编码（PyKDL 不保证可用）。像素+深度→相机系→基座系。零位 FK 未经外参标定，首次真机用已知位置物校验。
7. **IK**：ServiceProvider(enabled=['inverse_kinematics'])；请求 `{"pos_left_in_robot":[x,y,z],"quat_left_in_robot":[...],"pos_right_in_robot":...}`；响应 22 关节（11+11，前 4 共享腰腿）→ **q18 = left[0:4] + left[4:11] + right[4:11]**。
8. **轨迹执行**：**绕开官方 call_motion_planning 封装直调服务**，请求必须含 `{"q_end": q18, "max_step_size": 0.06}`——官方 ServiceProvider 封装漏传该参数，服务端直接 `KeyError: 'max_step_size'`。响应 JSON 取 `data["trajectory"]`。兜底路径：发 `/topic_arm_move_whole_body_joints_by_planning_0_<机号>` `{"traj_deg":[...],"duration":N}`（未验证）。
9. **安全设计**：可达盒 x(0.15,0.6) y(−0.4,0.4) z(−0.15,0.45) 在检测端和执行端**双复检**（IK 会把超可达目标解成极端关节角、规划器只报错不拦）；先移到目标上方 8cm 再下降；DRY_RUN 环境变量门禁，默认 1。
10. **验证顺序**：单帧检测→深度→坐标→DRY 检测→DRY 执行（注入近目标坐标）→真机（先注入坐标，再放真瓶子）。真机后查 `journalctl --user -u arm-control-service | grep -ciE "protection|heartbeat"`。

## 关键坑（真机验证过）

- **import 顺序**：先 `sys.path.insert` + import face_detection SDK（redis→ssl 用 conda 的 OpenSSL），再 import rclpy（rclpy 会 dlopen ROS 的 libssl 污染 conda ssl）——反了则 ssl.VerifyMode 变 None、redis 崩。
- **PYTHONPATH 污染吃掉 CUDA**：source robot_env 的 local_setup.bash 之后再起检测进程 → PYTHONPATH 带上 robot_env site-packages → 检测进程加载到 robot_env 的 CPU 版 onnxruntime（日志 provider=CPU 即中招）。检测进程起动前**只 source `/opt/ros/jazzy/setup.bash`**（rclpy 来源），robot_env 的 local_setup 挪到检测进程拉起之后。`env -u PYTHONPATH` 不可取——rclpy 靠 ROS 的 PYTHONPATH 解析，会 ModuleNotFoundError。
- **robot_env 直跑 python 会挂**：typesupport fastcdr 符号错误；必须 `conda run --no-capture-output -n robot_env python`（与官方 systemd unit 同款）。
- **DDS 阵营**：检测/执行进程要用 arm-control 的 lo 多播 CYCLONEDDS_URI，否则 IK/motion 服务不可见（详见 autolife-robot-dds-camp-split）。
- **空爪 360° 全闭合堵转**：夹爪 position 模式 0=开、360=全闭；空爪全闭堵转大电流，疑引发全模块 motor heartbeat lost（轨迹完成后数秒、自恢复）。保守闭合角 250°，或力矩模式（`set_gripper_mode('torque')` + `publish_joint_torques`，±10 级）。250° 已部署、待真机复测。
- **检测服务是 cmd 触发式**：收到 GRASP cmd 才检测+发布 detection。要做"放瓶子自动抓"，触发节点必须是周期发 `{"cmd":"grasp"}` 的心跳源；只订阅 detection 的触发器会死锁（detection 永远不来）。心跳方案见 auto_trigger.py v2（设计完成，待回验）。
- **相机帧拿不到先验证 SHM 流真死假死**：mmap 写入不更新 mtime，`ls -la /dev/shm/...` 时间戳停旧 ≠ 流死；读 metadata 帧计数递增或 image 槽 md5 变化才是可靠判据。若流真死且 vision 刷 `publisher's context is invalid (rcl/publisher.c:423)`，是 vision 进程内 ROS context 崩（壳仍 active 甚至反复自重启）——按硬规范重启 vision+face-detection 双服务，重启后用帧计数复验。
- **远端杀进程别用 `pkill -f <pattern>`**：deploy/robssh 的命令在远端以 `bash -c` 执行，命令串自身就含 pattern → 把自己的 shell 一并杀掉，表现为输出为空/连接中断且无报错。先 `pgrep -af` 列 PID（排除 bash -c 自身那行）再按 PID kill；给 pattern 加 `$` 锚定也未必躲得开。
- **写远端启动脚本别用 `set -u`**：裸 shell 无 LD_LIBRARY_PATH/AMENT 变量时 `set -u` 直接炸（unbound variable），且 ROS setup.bash 内部依赖未导出变量同样会炸；普通 `set -e` 或不设即可。
- **paramiko 长命令读超时**：远端命令含长 sleep/前台长跑时 exec_command 的读会超时断链；改 nohup 后台拉起 + 短轮询日志。

## 远端环境通道速查

- NetBird 状态：`netbird status -d`，只有 `Connected` 是当下可达；`Connecting`=对端大概率关机/断电（SSH/ping 同步验证）；`Idle`=lazy 未激活，ping 即唤醒。找在线机：`netbird status -d | awk '/netbird.selfhosted:/{name=$1} /Status: Connected/{print name}'`。
- 文件传输用 paramiko 封装（如 deploy304.py，push 带 md5 校验）；机队凭据 ${ROBOT_CREDS}（见 memory）。

## 已部署实例

- 304：`/home/ubuntu/autolife_yolo_grasp/`（yolo_grasp_service.py 检测 / yolo_grasp_executor.py 执行 / yolov8n_640.onnx / auto_trigger.py）
- 工作站：`~/.hermes/workspace/yolo_grasp_*.py`、`auto_trigger.py`、`deploy304.py`（paramiko push/cmd，push 自带 md5 校验）
- 已验证里程碑：注入目标全序列执行（张爪→上方→下降→闭合→抬起，3 条轨迹 30Hz）；真瓶子 2m 外被可达盒正确拒绝。
- 待回验项：夹爪 250° 防堵转；auto_trigger 心跳触发；真瓶子全链路（需现场把瓶放臂前 ~40cm）。
- 拓展方向（已评估）：YOLO 自动回冲 = ①检测桩(可行，bbox 粗定位即可) + ②Nav2/gv-slam 回桩(中) + ③毫米级精对接(高，需 AprilTag/位姿模型)；前提是现场有充电桩硬件，低电触发可用现有电池读取链路加阈值零硬件依赖。