---
name: autolife-robot-vision-inference-stack
description: 机器人视觉推理栈摸底与YOLO部署. Use when 问 vision 后端/GPU 闲置/上 YOLO.
---

# AutoLife 机器人视觉推理栈审计与检测模型部署

> 实测基线（S2 / robot_v2_2 机型，逐层验证）：**全机视觉推理在 CPU 上，NVIDIA GPU 默认完全闲置**。机器人无 github 直连，模型/权重经工作站中转 push。

## 架构基线（先记牢，再逐机验证）

视觉是**两个独立 systemd user 服务 + 各自独立 conda env**，不是一个进程：

| 服务 | unit | conda env | 推理后端 | 模型 |
|---|---|---|---|---|
| 主视觉/对话 | `vision-service.service` | `robot_env` | `onnxruntime` **纯 CPU 版**（providers 只有 Azure/CPUExecutionProvider）；torch 是 `+xpu` 构建（Intel GPU 版，NVIDIA 卡用不上） | 本地唯一 onnx 是 Piper TTS（zh_CN-huayan-medium）；视觉感知走云端 Qwen realtime API，本地无视觉模型 |
| 人脸/手势检测 | `face-detection-service.service`（常为 disabled，启用 AI 对话才开） | `face_detection_env`（依赖仅 opencv-contrib-python） | OpenCV DNN **CPU** | 人脸=Res10-300x300-SSD caffemodel fp16；手势/关键点=MediaPipe gesture_recognizer.task |

推论：机器即使带 RTX 4090 16GB，nvidia-smi 显存占用也会是 ~18MiB 量级（只有桌面）——GPU 闲着是常态，不是故障。

## 审计流程（逐台摸底，全部只读）

按顺序拉五层证据，一台机器一轮 robssh 批量做完：

1. **服务层**：unit 怎么起、跑在哪个 env：
```bash
systemctl --user cat vision-service.service | grep -E 'ExecStart|Environment='
systemctl --user list-unit-files | grep -iE 'face|detect'   # face-detection 是独立 unit，容易漏
```
2. **硬件层**：`nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv`——占用 <100MiB 即推理没用 GPU。
3. **包层**（每个 env 单独查，别只查 robot_env）：
```bash
<env>/bin/pip list | grep -iE 'onnx|torch|opencv|ultralytics|yolo|ncnn|openvino|insightface|mediapipe'
<env>/bin/python -c 'import onnxruntime as ort; print(ort.get_available_providers())'  # 判 CPU/GPU 版的决定性证据
```
4. **模型层**：`find /home/ubuntu -name '*.onnx' -o -name '*.pt' -o -name '*.engine'`（排除 site-packages 的框架自带）；face-detection 的模型在 `autolife_robot_face_detection/models/` 下（caffemodel + .task + onnx）。
5. **代码层**：业务逻辑大都在编译的 `.so` 里，grep .py 抓不到别急着下结论——用 `strings <so> | grep -iE 'yunet|yolo|FaceDetectorYN|caffe|mediapipe'` 定位实现；`__init__.py` 里的 `load_vision_models()` 会明写每个模型文件的路径和格式。

结论按表格式汇报：每个服务 → 引擎/EP/模型文件/GPU 占用，一眼看清谁在 CPU 谁在 GPU。

## 新增检测模型（YOLO 等）的路线

- **隔离部署**：仿 face-detection-service 模式——新建独立 conda env + 独立 systemd user unit + DDS topic 出检测结果，完全不碰 robot_env（robot_env 被 arm/gv/kiosk/vision 四个服务共用，动它风险最高）。这是架构规则不是风格偏好。
- env 里装 `onnxruntime-gpu`（或 TensorRT engine）才吃得到闲置 GPU；装 CPU 版 onnxruntime 会重蹈现状。
- unit 文件照抄同机现有服务的 Environment 块（`ROS_DOMAIN_ID` / `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` / `CYCLONEDDS_URI` loopback 段），少一个 DDS 就跨进程不可见。
- 模型文件不现场下载：机器人在无外网/github 掐断环境，模型经工作站下载（github 走 ghfast.top 代理）后 `robssh.py push` 上去。
- 上述部署路线是设计指导，尚未整机落地验收；首次实施后把实测步骤回写本技能。

## 坑

- **face-detection 是独立服务容易被漏判**：在 vision 的 settings.toml 里只看到 `face_detection_enabled` 开关，会误以为检测跑在 vision 进程里；实际是独立 unit + 独立 env，查模型/后端要进 `face_detection_env`。
- **`.so` 里的实现 grep 不到**：包内 .py 只有路径常量，检测实现在编译 so 里；用 strings 扒，别靠 import dir() 猜。
- **`python -c` 输出带 SDK banner**：import autolife 包会先打 `Successfully imported ssl...` 前缀行，解析 stdout 前先剔掉。
- **onnxruntime 有没有 GPU 看 providers 不看版本号**：`get_available_providers()` 列表里没有 CUDA/TensorrtExecutionProvider 就是 CPU 版包，装错包 GPU 永远闲置。
- **远程命令引号嵌套翻车**：for+if+grep 组合经 robssh 转发会报 EOF 引号错，复杂诊断脚本写本地 .sh push 上去 bash 跑，别硬拼一行。

## 衔接

- 连接/凭据/push-pull：`autolife-remote-repair`（robssh.py 全集）
- vision 语音对话故障（非推理栈问题）：`devops:autolife-robot-vision-diagnostics`
- 机型定位：`autolife-find-robot`
