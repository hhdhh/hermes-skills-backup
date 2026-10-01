---
name: autolife-perception-service-deploy
version: 1.0.0
description: Use when 给 AutoLife 机器人部署 YOLO/视觉感知服务(相机取帧+GPU推理+臂抓取联动)。
---

# AutoLife 感知服务部署（YOLO 检测 → 臂抓取类）

给机器人加自定义视觉能力（识别瓶子/抓取/客流检测等）的部署套路。接口速查（SHM 相机、topic 协议、臂控制、URDF/FK 矩阵）在 `references/camera-arm-interfaces.md`。

## 架构铁律（每次都适用）

1. **独立 conda env**（如 `yolo_grasp_env`），绝不往 robot_env / face_detection_env 装包——生产服务共环境，装错全服务陪葬。借 SDK 只用 `sys.path.insert` 指到 face_detection_env 的 site-packages，不动它。
2. **相机帧不走 ROS**：在 `/dev/shm/camera_image_buffer_*`，用 face_detection_env 的 `RGBDCamera` 驱动取（RGBD + 内参一次拿全）。
3. **结果/触发走 DDS topic，仿 face-detection 模式**：`std_msgs/String` + JSON 载荷，topic 名 `/topic_<名>_0_<机号>`。
4. **DRY_RUN 先行**：检测+坐标链路全验证后才接臂执行；真动臂前必须归零位（静态 FK 只有零位才准）且现场有人。
5. **可达安全盒**：基座系坐标先过 x/y/z 范围检查再发臂指令，超界直接放弃并日志。

## 部署流程

```
1. 勘机     nvidia-smi / ls ~/miniconda3/envs / arm-control-service 状态 / ros2 topic list
           机器人外网实测: curl -sI https://pypi.tuna.tsinghua.edu.cn/simple/ （别假设有无）
2. 建环境   机器人上建(有外网走清华源): conda create -y -n <env> python=3.12
           pip install -i 清源 onnxruntime-gpu numpy opencv-python-headless posix_ipc toml
           pip 断流 → 重跑加 --resume-retries 20
3. 模型     工作站: 权重走 gh-proxy.com 代理(ghfast.top 常超时, 换着试);
           uv venv + ultralytics 导 ONNX 静态 640 → onnxruntime 冒烟 [1,84,8400] → push 上机
4. 真机冒烟 一次性小脚本(别直接起服务): SHM 取帧 shape → 内参 → ONNX 推理 →
           实际检出目标类别 + 存一帧 jpg 人肉复核
5. 坐标     像素+深度 → 相机系(内参) → 基座系(URDF 零位静态 FK, 工作站 urdf_parser_py
           离线算 4×4 硬编码; 机器人 env 没有 PyKDL)
6. 服务化   触发 topic + 检测结果 topic + dry-run 日志 → 真抓接官方 ArmController
7. 常驻     systemd --user unit, Environment 里带 LD_LIBRARY_PATH(nvidia pip 库路径)
```

## SSH 通道坑（详规在 autolife-remote-repair，此处要领）

- `robssh.py push/pull` 无 NetBird 兜底（exec 子命令才有）：机号无内网缓存 IP 时直接挂。绕法：先 `robssh.py scan --force`，或写临时 paramiko 助手直连 mesh 名（裸 scp 不通——无 sshpass/密钥，卡 askpass）。
- 远程跑复杂命令别嵌套引号/heredoc：本地写 .sh → push → `robssh.py <机号> N 'bash /tmp/x.sh'`。
- 长安装命令必须 `nohup ... > /tmp/x.log 2>&1 &` 后台化再轮询 tail，SSH 通道长输出会 PipeTimeout。

## 关键坑

- **LD_LIBRARY_PATH 必须进程启动前就位**：ld.so 启动时快照库搜索路径，运行中改 `os.environ` 对本进程后续 dlopen 无效——onnxruntime CUDA EP 找不到 `libcublasLt.so.12` 就静默回落 CPU（provider_bridge 报错但不崩）。写进启动脚本/systemd unit 的 Environment，路径=env 的 `site-packages/nvidia/{cublas,cudnn}/lib`。CPU 兜底 yolov8n@640 约 90ms/帧，联调够用。
- **pip CUDA 库版本配对**：onnxruntime-gpu 1.23 要 CUDA 12 系（nvidia-cublas-cu12 + nvidia-cudnn-cu12）；装 cu13 的库不认（报错明示 cuDNN 9.* / CUDA 12.*）。
- **工作站 GitHub 直连超时**：权重/资产走 `https://gh-proxy.com/https://github.com/...` 前缀代理；机器人有外网时大文件让机器人自己 curl 拉，比 SSH push 快。
- **机器人 env 缺 PyKDL**：URDF FK 别想在机器人上跑 KDL——工作站 urdf_parser_py 离线算零位 4×4 硬编码；代价是抓取前必须归零位（头会动就失准，届时改 vision 包 CameraTransformer，需 KDL）。
- **深度单位双轨**：Orbbec 深度可能 mm 也可能 m——取 k×k 中值后 >10 就 /1000。
- **ros2 topic echo 无输出≠坏**：publisher 不在线 echo 挂到超时；先 `ros2 topic info <t>` 看 publisher count。
- **模型放自管目录**（如 `/home/ubuntu/<服务名>/`），别进任何 site-packages。

## 与其它技能的衔接

| 需求 | 去处 |
|------|------|
| SSH 连接/push 文件 | `autolife-remote-repair`（含 push 无 mesh 兜底的坑） |
| 机号定位 | `autolife-find-robot` |
| vision/对话故障诊断 | `devops:autolife-robot-vision-diagnostics` |
| 动作/关键帧设计 | `autolife-robot-action-ops` |

## 部署现场状态（304，S2/robot_v2_2）

检测链路 SHM→YOLO(CPU 92ms)→基座坐标 真机验证通过；臂执行未联调（dry-run 止步）。机器人侧 `/home/ubuntu/autolife_yolo_grasp/`（模型+服务脚本），工作站 `~/.hermes/workspace/yolo_grasp_service.py` + `deploy304.py`（mesh 直连助手）。续做顺序：CUDA EP 验证（unit Environment 带 LD_LIBRARY_PATH）→ 服务 dry-run → ArmController 真抓。
