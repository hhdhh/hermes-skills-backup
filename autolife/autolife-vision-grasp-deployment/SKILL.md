---
name: autolife-vision-grasp-deployment
description: Use when 给 S2 机器人部署独立视觉抓取服务(YOLO→IK→臂)或排查其集成故障.
---

# AutoLife 独立视觉抓取部署（YOLO 全链路）

给 S2(robot_v2_2) 机器人加「相机识别目标→机械臂自动抓取」能力的标准架构与集成坑。核心铁律：**独立进程、独立环境，绝不改动既有 vision/arm 服务的行为**。

## 架构：两进程双环境

| 进程 | 环境 | 职责 |
|---|---|---|
| 检测器 | 专用 conda env（onnxruntime-gpu + pip nvidia 全家桶） | SHM 相机 → YOLO → 深度 → 基座坐标 → 发 detection topic |
| 执行器 | 官方 robot_env，必须 `conda run --no-capture-output -n robot_env python` | 订阅 detection/cmd → IK → 规划 → 臂+夹爪 |

- 通信用 std_msgs/String JSON：`/topic_yolo_detection_0_<机号>`、`/topic_yolo_grasp_cmd_0_<机号>`
- 执行器直跑 robot_env 的 python 会报 typesupport fastcdr symbol error；`conda run` 是官方 unit 同款姿势，别绕。
- 臂/IK/motion 服务调用细节（请求格式、q18 映射、夹爪模式、DDS URI）见 `references/arm-service-integration.md`。

## 部署流程

1. **模型**：工作站 ultralytics 导出 ONNX opset 18（[1,3,640,640]→[1,84,8400]），yolov8n 足够（RTX 4090 单帧 <6ms）；COCO class 39 = bottle。
2. **检测 env**（机器人上，tuna 镜像）：onnxruntime-gpu + opencv-headless；CUDA EP 靠 pip 装 nvidia 全家桶（cublas/cudnn/cufft/curand/cusolver/cusparse/cuda_runtime/nvjitlink）。
3. **CUDA 激活**：shell 层 `LD_LIBRARY_PATH` 注入 nvidia `*/lib`（必须发生在 import onnxruntime 前），进程内 os.environ 补写不可靠。起进程后看日志 `YOLO ready provider=CUDAExecutionProvider`——出现 CPUExecutionProvider = 环境被污染（坑①）。
4. **相机**：`sys.path` 注入 face_detection_env 的 site-packages，`RGBDCamera(config=load_control_config())`（构造必须传 config，裸构造 TypeError）。**SDK import 必须在 rclpy 之前**——rclpy 会 dlopen ROS 的 libssl，毒化 conda ssl 后 redis 崩。
5. **坐标变换**：URDF 零位 FK 算 T_base_cam（基座→相机 link）硬编码进服务；工作站用 urdf-parser-py BFS 求运动链。
6. **执行器进程**：`source /opt/ros/jazzy/setup.bash` + robot_env/share 的 msgs/srvs/actions 三个 local_setup + `ROS_DOMAIN_ID=0 ROBOT_ID=<机号> RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` + arm-control 同款 CYCLONEDDS_URI（见 references）。
7. **启动顺序**：同一脚本里先起检测进程、后 source local_setup 起执行器——顺序反了检测器会加载 robot_env 的 CPU 版 onnxruntime（坑①）。

## 集成坑（真机踩实）

1. **PYTHONPATH 污染**：robot_env 的 local_setup.bash 把它的 site-packages 塞进 PYTHONPATH，之后启动的检测进程会 import 到 robot_env 的 CPU 版 onnxruntime。修法=启动顺序（检测器先起）；`env -u PYTHONPATH` 不行——rclpy 恰恰靠 ROS 的 PYTHONPATH 进来，会一起被删掉。
2. **检测服务是 cmd 触发式**（收到 GRASP 才检测+发布 detection）：触发器若设计成「订阅 detection 才发 cmd」= 互相等待死锁。触发器必须主动发 cmd（心跳式周期发），执行器靠「目标新鲜度（数秒内）+ 可达盒」过滤无目标心跳。
3. **motion_planning 请求必须显式带 `max_step_size`**（官方封装会漏传）：缺了服务侧直接 KeyError，规划全拒。请求 `{"q_end": [...18 关节度], "max_step_size": 0.06}`，响应从 `json.loads(resp.result)["trajectory"]` 取。
4. **IK 会把不可达目标解成极端关节角**：可达盒检查在检测器和执行器两处都做（执行器 IK 前再验一次）。安全盒起点 x(0.15,0.6) y(±0.4) z(-0.15,0.45) m。
5. **空爪 360° 全闭 = 堵转**：大电流疑似拉垮全机电机心跳（轨迹完成后数秒全模块 heartbeat lost，可自恢复）。闭爪角收敛到 ~250° 或用力矩模式。
6. **抓取序列**：张爪 → 移到目标上方 8cm → 下降 → 闭爪 → 抬回上方；每段轨迹后等 duration+1.5s 再进下一段。
7. **SHM 相机流会静默冻结**（vision 内部 ROS context 崩、unit 仍 active）：验证流用 mmap 双缓冲 slot 的 md5 间隔采样看变化，**别信 mtime**（mmap 写不更新时间戳）；恢复=重启 vision+face-detection，消费进程也要重启（vision 重建 SHM 后老进程抱孤儿映射）。诊断细节见 skill: autolife-robot-vision-diagnostics。
8. **远端 `pkill -f <pattern>` 会自杀**：远端 `bash -c` 命令行本身含 pattern 字符串。按 PID kill 或锚定 `\.py$`。
9. **长命令别在 SSH 通道里同步等**：跑超过 ~60s 的远端命令会报 paramiko PipeTimeout 而命令仍在跑。统一模式 = nohup 后台 + 落盘日志，另起连接轮询日志。

## 验证链（真机验收顺序）

1. det.log：`provider=CUDAExecutionProvider`、`detect XXms bottles=N`、基座坐标输出
2. exec.log：q18_above/q18_at 各 18 关节值
3. arm-control journal：`Starting trajectory execution: N waypoints` / `Trajectory execution completed`（三段：上方/下降/抬起）
4. gripper_controller 日志：position 0→~250
5. 安全复查：arm-control journal 无持续 protection / heartbeat lost

## 相关技能

- `autolife-robot-vision-diagnostics`：SHM 流冻结诊断
- `autolife-robot-dds-camp-split`：DDS 阵营分裂
- `autolife-remote-repair`：SSH / 传输 / 远端清理
