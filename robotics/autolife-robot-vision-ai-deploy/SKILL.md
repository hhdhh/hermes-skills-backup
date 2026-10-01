---
name: autolife-robot-vision-ai-deploy
version: 1.0.0
description: Use when 给 AutoLife 机器人部署视觉 AI（YOLO 检测/抓取引导）—— 全链路真机验证流程。
---

# AutoLife 机器人视觉 AI 部署（YOLO 类检测 + 臂抓取）

目标：在 S2（robot_v2_2）机型上部署独立视觉推理服务，不碰现有 vision/face-detection 服务，真机验证闭环。首例：304 YOLOv8n 瓶子识别→自动抓取。

## 标准流程（按序执行）

### 1. 勘机（只读，直接做）
- SSH 连入（机号定位/凭据见 skill:autolife-remote-repair）。
- `nvidia-smi` 查 GPU；`ls /home/ubuntu/miniconda3/envs/` 看已有 env（`cuda_env`=torch cu130+onnxruntime-gpu 可参考但别动）。
- `systemctl --user list-unit-files | grep -iE 'vision|face'` + `systemctl --user cat <unit>` 抄环境变量（ExecStart、CYCLONEDDS_URI、ROS_DOMAIN_ID、ROBOT_ID）——后面自建服务全部对齐。
- 相机数据源：`ls /dev/shm/ | grep camera`。RGBD 头部相机=`camera_image_buffer_rgbd_head_color/depth` + `camera_intrinsics_struct_*`；5 路单目=head_left/right/rear+hand_left/right（_jpeg 后缀）。

### 2. 建独立环境（不动 robot_env）
```bash
conda create -y -n <my_env> python=3.12
<env>/bin/pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
  onnxruntime-gpu==1.23.2 numpy opencv-python-headless posix_ipc toml pyyaml
# CUDA EP 运行库（机器人有外网时直接装；onnxruntime-gpu 不自带这些）:
<env>/bin/pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
  nvidia-cublas-cu12 nvidia-cudnn-cu12 nvidia-cufft-cu12 nvidia-curand-cu12 \
  nvidia-cusolver-cu12 nvidia-cusparse-cu12 nvidia-cuda-runtime-cu12
```
- CUDA 报 `libcublasLt.so.12/libcufft.so.11 not found` 就是这套库不全，缺哪个补哪个，别换 onnxruntime 版本。
- 大包网络断续：pip 加 `--resume-retries 20`，nohup 后台跑，轮询 log。
- 验证：`export LD_LIBRARY_PATH=$(ls -d <env>/lib/python3.12/site-packages/nvidia/*/lib | tr '\n' ':')$LD_LIBRARY_PATH` 后 InferenceSession providers 首位必须是 CUDAExecutionProvider（4090 上 yolov8n 640 约 5.7ms；CPU 回落约 100ms）。

### 3. 模型准备（工作站侧）
- 工作站 GitHub 直连超时：下载权重用 `https://gh-proxy.com/https://github.com/...` 前缀（ghfast.top 不稳）。
- 导出 ONNX：`ultralytics` 用 `m.export(format="onnx", imgsz=640, simplify=True, dynamic=False)`；新 torch 要先装 `onnx` (<1.18)+`onnxscript`，opset 转换警告可忽略，只要输出 shape 正确（YOLOv8 `[1,84,8400]`）。
- 部署前在工作站用 onnxruntime CPU 跑一次随机输入验证 shape，再 push 上机（md5 校验）。
- COCO 类别：bottle=39。后处理：letterbox 逆变换 + cv2.dnn.NMSBoxes；输出布局 [84,8400]→转置 [8400,84]（cx,cy,w,h + 80 类分）。

### 4. 相机取帧（借用 face_detection_env 的驱动，不重造）
- `sys.path.insert(0, "/home/ubuntu/miniconda3/envs/face_detection_env/lib/python3.12/site-packages")` 后 `from autolife_robot_face_detection.drivers.rgbd_camera import RGBDCamera`；`RGBDCamera(config=load_control_config())` → start → get_frame() 得 (color, depth)，get_intrinsics() 得 fx/fy/ppx/ppy。
- 深度图单位可能是 mm：中值 >10 就除以 1000。
- 深度取值：目标中心 5×5 邻域中值，有效像素过半才算数。

### 5. 坐标变换（不依赖机器人上的 PyKDL）
- 机器人 face_detection_env 缺 PyKDL/pinocchio，CameraTransformer 用不了 → 工作站离线算：拉 `autolife_robot_sdk/descriptions/autolife_s1/urdfs/robot_v2_2.urdf`，urdf_parser_py 做 Link_Zero_Point→Link_Camera_Head_Forehead 的零位静态 FK（固定关节+转动关节零位=origin 串联），得 4×4 矩阵硬编码进服务。
- 前提：头部俯仰零位。抓取前先归位（发 standing 姿态）保证 FK 一致。
- 像素+深度→基座坐标：`x=(u-ppx)*z/fx, y=(v-ppy)*z/fy` → 相机系齐次坐标左乘 T_base_cam。

### 6. 服务进程架构（双进程解耦，重要）
- **检测进程**跑自建 env（onnxruntime/opencv），**臂执行进程**跑 robot_env（官方 ArmController 依赖 SDK）——环境混用必炸（下述坑 1/2）。
- 通信：全部 std_msgs/String JSON 载荷 topic（照 face_detection 模式）：检测进程发 `/topic_<名>_detection_0_<机号>`，执行进程发 `/topic_<名>_grasp_cmd_0_<机号>` 触发、`_status_` 回报阶段。
- 环境对齐（两个进程都要）：先 source `/opt/ros/jazzy/setup.bash` + robot_env 下三个 local_setup.bash（msgs/srvs/actions），再 export 目标服务的 CYCLONEDDS_URI 原文（lo 多播 + ParticipantIndex none 阵营），否则 DDS 互不可见且**不报错**（详见 skill:autolife-robot-dds-camp-split）。
- 执行进程启动必须 `conda run --no-capture-output -n robot_env python ...`（与官方 unit 同款），直接调 env 内 python 会 RMW typesupport/SSL 冲突。

### 7. 臂控制（官方示例即 API 文档）
- 位置：`autolife_robot_arm/examples/`（robot_env site-packages 内），`robot_controllers/` 下 ArmController（trajectory_pub/whole_body_pub/move_to_height）、GripperController（set_gripper_mode("position")→publish_joint_positions）、ServiceProvider（IK/FK/motion_planning 服务客户端）。
- IK：`call_inverse_kinematics(pos_left, quat_left, pos_right, quat_right)` 返回 JSON 含 22 关节（左11+右11，前 4 位共享腰腿）→ q_end18 = left[0:4]+left[4:11]+right[4:11]。
- **motion_planning 必须直调服务带 `max_step_size`（0.06）**，官方 ServiceProvider.call_motion_planning 封装缺这个参数，服务端 KeyError 'max_step_size'。返回 JSON 里取 `trajectory` 列表，再以 `{"traj_deg": traj, "duration": 秒}` 发 trajectory_pub。
- 夹爪：position 模式 0°=全开，360°=全闭。
- 多线程：MultiThreadedExecutor 后台线程 spin，主线程干活；服务调用用 spin_until_future_complete。

### 8. 安全（写进执行器，不靠人肉）
- 双侧可达盒校验（检测进程+执行器各一遍）：目标基座坐标超盒直接拒绝并回报 out_of_reach。
- DRY_RUN 环境变量门：默认 1 只解算不动臂；管理员授权后 0 真机执行。
- 目标新鲜度检查（>10s 丢弃），cmd 触发去抖（3s 冷却）。
- 首真机跑完必须查 `journalctl --user -u arm-control-service` 确认无 protection/fault。

## 坑位清单（真机验证过）
1. **import 顺序：face_detection SDK（redis→ssl）必须在 rclpy 之前**。rclpy 先 import 会 dlopen ROS 的 libssl，之后 SDK 里 `ssl.VerifyMode` 变 None，redis 导入炸 AttributeError——自建检测服务里 SDK 放最前。
2. **robot_env 直接跑 python 会双重库冲突**：RMW typesupport（fastcdr 符号）+ SSL 都会炸，必须 conda run 方式 + 先 source 全部 local_setup.bash。
3. **外部进程看不到 arm 的 IK/规划服务 ≠ 服务没起**：先 `journalctl -u arm-control-service | grep -i kinematic` 确认 enabled，再查自己进程的 CYCLONEDDS_URI 阵营是否对齐。
4. **robssh.py push/pull 不走 NetBird 兑底**（exec 子命令才走）：机号无内网缓存时 push 报"没有解析到的 IP"。绕法：自写 paramiko 脚本直连 mesh 名，凭据从 robssh.py 常量取。
5. **夹爪空载全闭 360° 会堵转大电流**，可拉低全机供电导致全部电机 heartbeat lost（保护态，自恢复）——闭爪用 ~250° 或力矩模式限流；真机测试日志里看到全模块心跳瞬丢先查是不是堵转拉的。
6. paramiko 长命令超时（channel timeout）：>60s 的远程任务一律 nohup 后台 + 落盘 log，再轮询 cat。
7. 远程脚本里嵌 python 代码：用 heredoc 写文件再执行，别 sed 拼接（引号地狱）；sys.path 注入写在 python 文件内而非 bash 行。

## 交付物模板（304 实例，可复制改机号）
- `/home/ubuntu/autolife_yolo_grasp/yolo_grasp_service.py`（检测进程：SHM 相机+YOLO+坐标+topic）
- `/home/ubuntu/autolife_yolo_grasp/yolo_grasp_executor.py`（执行进程：IK+规划+夹爪，DRY_RUN 门）
- 工作站镜像：`~/.hermes/workspace/yolo_grasp_*.py` + `deploy304.py`（mesh 直连 push/run 辅助）

## 相机取帧与 VL 识别（看一眼/识物类，不建独立服务）

给对话栈加"看一眼"能力（robot_tools 外部工具 + qwen-vl）走轻量路数，不动服务架构：
1. 新建 `robot_tools/look_and_describe.py`：模块级 `TOOL_SCHEMA`（**扁平结构**：`type`/`name`/`description`/`parameters` 顶层）+ `run(arguments, ai_mgr=None)`。加载器（.so）只认扁平 schema，嵌套 OpenAI 式 `function.name` 会**静默跳过**——无报错，只是日志少了 "Loaded external tool schema" 行。
2. `robot_tools/__init__.py` 的 ENABLED_TOOLS 列表加名。
3. prompt.txt 工具规则区插触发规则段（何时调/怎么答/看不清怎么说）。
4. 联动重启后 `journalctl --user -u vision-service | grep "Loaded external tool schema"` **逐个点名**：加载了 N-1 个而新工具不在列表 = schema 结构不对，别只看服务 active。
5. 验证命令链：`grep -c` 数 schema 行数须等于 ENABLED_TOOLS 长度；远端单测 `importlib` 导入模块取 TOOL_SCHEMA["name"] 确认可加载。

**SHM 帧源三坑（以颜色互换/旧帧症状反推）**：
- jpeg 段按需编码：无视频客户端时只留服务 init 时写的一帧旧图，识别结果永远停在过去——必须读 `rgbd_head_color` 原始段（face-detection 依赖它，常开）。
- **rgbd_head_color 字节序实为 BGR**（metadata 标 RGB888/fourcc=3 不可信）：直接按 RGB 解会红蓝互换、黄变蓝。解码后必须 `arr = np.ascontiguousarray(arr[..., ::-1])` 反转 R/B，再交 PIL RGB 模式。
- 判帧源死活用「3 秒内 md5 变化」，勿信负帧龄（跨 boot 残留时间戳）；双槽环形 buffer 取活跃槽=metadata u32@12，连读两次一致才取防撕裂。

**通道顺序判定法**（无标定物时）：同一帧分别按 RGB/BGR 解码各生成一张图送 VL——肤色发青、暖色全变冷色的那个就是错的；正确解码下人脸肤色 R>G>B 单调递减。

## 与其它技能的衔接
- 对话栈外接工具（robot_tools+ENABLED_TOOLS+prompt）复刻配方：references/vision-tool-recipe.md
- 机号定位/SSH/push-pull：skill:autolife-remote-repair
- DDS 阵营分裂原理：skill:autolife-robot-dds-camp-split
- 排障七步/五层健康：skill:autolife-ops-robot-diagnosis
- 停止线判断：skill:autolife-ops-shutdown-conditions
