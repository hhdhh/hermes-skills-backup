# 相机/臂/服务接口速查（S2 robot_v2_2 系）

> 实测来源 304。其余 S2 机一致性好；S1（kiosk/logo 65/66 段）不适用本表。

## SHM 相机（不走 ROS）

| 缓冲 | 内容 |
|---|---|
| `/dev/shm/camera_image_buffer_rgbd_head_color` | 头部 RGBD 彩色 640×480 BGR |
| `/dev/shm/camera_image_buffer_rgbd_head_depth` | 深度（mm/m 双轨，>10 视为 mm） |
| `camera_intrinsics_struct_rgbd_head_color/depth` | 内参结构体 |
| `camera_image_buffer_{hand_left,hand_right,head_left,head_right,head_rear}[_jpeg]` | 其余相机（JPEG 版给 kiosk/relay） |

取帧（借 face_detection_env 驱动，零新依赖）：
```python
import sys
sys.path.insert(0, "/home/ubuntu/miniconda3/envs/face_detection_env/lib/python3.12/site-packages")
from autolife_robot_face_detection.drivers.rgbd_camera import RGBDCamera
from autolife_robot_face_detection import load_control_config
cam = RGBDCamera(config=load_control_config())
cam.start()
color, depth = cam.get_frame()          # (480,640,3), (480,640)
intr = cam.get_intrinsics()["color"]    # fx,fy,ppx,ppy,coeffs
cam.stop()
```
304 实测内参 fx=606.754 fy=606.274 ppx=325.497 ppy=252.383——每机从 SHM intrinsics 自读，别硬编码。

## ROS topic 协议（全 String/JSON）

- 命名 `/topic_<名>_{domain}_{机号}`；CycloneDDS，`ROS_DOMAIN_ID=0`，`RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`。
- 臂轨迹：`/topic_arm_move_whole_body_joints_by_planning_0_304`，JSON `{"traj_deg": [...18], "duration": 5}`
- 关节目标/命名姿态：`/topic_arm_whole_body_target_joints_position_0_304`（`{"target_joint_config": "zero"|"standing"}`）
- 夹爪：`/topic_arm_set_gripper_vr_cmd_0_304`
- 臂状态：`/topic_arm_whole_body_and_gripper_current_joints_status_0_304`
- 点云：`/robot_point_cloud_topic_0_304`（可能 0 publisher，别依赖）
- 检测输出参照：`/topic_face_detection_0_304`

## 臂控制（官方示例=事实文档）

路径：`robot_env .../site-packages/autolife_robot_arm/examples/`
- `example_02_ros_task_space_control.py`：IK/FK/motion_planning/升降 `move_to_height(-0.56~0.0)`
- `example_03_ros_gripper_control.py`：夹爪位置模式 0（全开）→360（全合）；力矩模式防长时间堵转（发完闭合及时归零力矩）
- 封装在 `examples/robot_controllers/`：ArmController / ServiceProvider(`enabled_services=['inverse_kinematics','forward_kinematics','motion_planning']`) / GripperController；初始化必须 `wait_for_initialization()` + MultiThreadedExecutor
- 18 DoF 顺序：leg_waist[4] + left_arm[7] + right_arm[7]（Joint_* 全名表见 example_02 头部）
- 运行环境：`source /opt/ros/jazzy/setup.bash` + robot_env

## URDF 与相机→基座变换

- URDF：`autolife_robot_sdk/descriptions/autolife_s1/urdfs/robot_v2_2.urdf`（另有 _simplified/_calibration）
- 机器人 env 缺 PyKDL → 工作站 urdf_parser_py 做 BFS 零位 FK 硬编码 4×4：
```
T_base_cam (Link_Zero_Point → Link_Camera_Head_Forehead, 零位):
[[ 0.3746, -0.0001,  0.9272,  0.0741],
 [-0.0000, -1.0000, -0.0001, -0.0015],
 [ 0.9272, -0.0000, -0.3746,  1.6181],
 [ 0, 0, 0, 1]]
```
- 像素→相机系：`x=(u-ppx)*z/fx, y=(v-ppy)*z/fy`；→基座系：`T_base_cam @ [x,y,z,1]`
- 仅头部零位（无俯仰）时准——抓取前先发 zero/standing；头会动的场景改用 vision 包 CameraTransformer（需 KDL，机器人上没装则工作站算）

## Conda env 布局

| env | 用途 |
|---|---|
| robot_env | 生产服务（arm/gv/vision/kiosk），禁装新包 |
| face_detection_env | 人脸/手势（mediapipe+opencv-contrib，含 autolife_robot_sdk 2.2.7）——借 SHM 驱动从这里 import |
| cuda_env | torch cu130 + onnxruntime-gpu（TensorRT/CUDA EP 齐全），参考用不共用 |
| 自建 env | 新感知服务一律独立建 |

## YOLO 细节

- COCO：bottle=39、cup=41、person=0
- yolov8n ONNX 静态 640 输出 `[1,84,8400]`（84=4 框+80 类）；ONNX 不含后处理，letterbox/NMS 自写
- 工作站导出：ultralytics 新导出器缺 onnxscript 会炸 → `uv pip install onnx==1.17.0 onnxscript`；请求 opset 13 会被抬到 18（Resize 无降级 adapter），onnxruntime 1.23 能吃，不纠结
- 推理输入：RGB、/255 归一化、CHW；输出转置 [8400,84] → 类别 argmax + conf 过滤 + NMS
