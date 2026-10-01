# S2 臂服务集成细节（robot_v2_2，304 机验证）

## IK（inverse_kinematics）
- 经官方 `ServiceProvider(TOPIC_NODE_ID="0_<机号>", enabled_services=['inverse_kinematics','motion_planning'])`
- 请求 JSON：`{"pos_left_in_robot":[x,y,z], "quat_left_in_robot":[x,y,z,w], "pos_right_in_robot":[...], "quat_right_in_robot":[...]}`
- 响应字段：`left_arm_body_target_joints` / `right_arm_body_target_joints`，各 11 关节
- **q18 映射**：q18 = left[0:4] + left[4:11] + right[4:11]（前 4 是共享腰腿关节）

## motion_planning
- 直接调服务：请求 `{"q_end": [18 度数], "max_step_size": 0.06}`（max_step_size 必须显式带，服务侧 KeyError 不兜底）
- 响应：`resp.result` 是 JSON 字符串，`json.loads(...)['trajectory']` 是 waypoint 列表
- 低层备选通道：`/topic_arm_move_whole_body_joints_by_planning_0_<机号>` 发 `{"traj_deg": [...], "duration": N}`

## DDS URI（与 arm-control 同阵营，否则 IK/motion 服务不可见）

```xml
<CycloneDDS><Domain Id="any"><General><Interfaces><NetworkInterface name="lo" multicast="true"/></Interfaces><AllowMulticast>true</AllowMulticast><EnableMulticastLoopback>true</EnableMulticastLoopback></General><Discovery><ParticipantIndex>none</ParticipantIndex></Discovery></Domain></CycloneDDS>
```

vision-service 的 127.0.0.1 单播变体是另一阵营——用它看不到 IK/motion 服务。

## 夹爪（GripperController）
- position 模式：0.0=全开，360.0=全闭（空爪全闭堵转，见 SKILL.md 坑⑤）
- torque 模式：±10.0
- `publish_joint_positions({"left_gripper_target_joints_position":[v], "right_gripper_target_joints_position":[v]})`

## 安全参数起点（按机型标定）
- reach box：x(0.15,0.6) y(-0.4,0.4) z(-0.15,0.45)（基座系，米）
- GRASP_ABOVE_M=0.08；TRAJ_DURATION=4（下降/抬起段 3）

## 头部 RGBD 相机（SHM）
- buffer：`camera_image_buffer_rgbd_head_color/depth`（双缓冲；color 1843200B = 2×921600）
- 内参起点：fx≈606.75 fy≈606.27 ppx≈325.50 ppy≈252.38，零畸变，640×480
