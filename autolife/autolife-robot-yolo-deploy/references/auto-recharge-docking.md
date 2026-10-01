# AutoLife S2 自动回充对接栈（现状勘察）

适用：评估/实现「自动回充」「YOLO 找桩」类需求。S2/robot_v2_2 系通用（软件栈随 robot_env 的 autolife_robot_gv 包下发）。

## 已有组件

- **opennav_docking（docking_server）**：Nav2 官方对接框架，lifecycle node，由 gv-slam 的 `ros_ws/navigation.launch.py` 拉起；经 conditional_launcher 按需启动，平时不常驻（节点列表看不到是正常的）。
- **配置**：`<robot_env site-packages>/autolife_robot_gv/ros_ws/nav2_params.yaml` 的 docking_server 段：
  - `dock_plugins: ['autolife_dock']`（opennav_docking::SimpleChargingDock）
  - `use_external_detection_pose: true` → 消费 `/detected_dock_pose`
  - dock 实例 `home_dock`：frame=map，pose=[0.506, 1.53, 1.45]，倒车对接（backward），staging 点桩前 0.5m
- **桩检测**：`laser_line_finder`（Cython .so，autolife_robot_gv 包内）从 `/merged` 激光扫描提取线段 → 发布 `/detected_dock_pose`（geometry_msgs/PoseStamped）。gv-slam 导航模式启动时自动拉起。
- **电池**：`/topic_gv_battery_<nid>`（voltage/current/charge/capacity 字段齐全），低电触发回充可直接订阅。
- **导航**：`/robot_navigation_<nid>/go` 等话题 + `navigate_to_pose` action；Nav2 全套（controller/planner/bt_navigator/velocity_smoother）由 conditional_launcher 按需拉起。

## YOLO 接入点

- docking_server 走 external_detection_pose：YOLO 检测桩只需往 `/detected_dock_pose` 发 PoseStamped 即可替换/互补激光线检测——与现有对接控制器无缝对接。
- 触发链：电池阈值（<20%）→ NavigateToPose 到 staging → DockRobot action。docking_server 不在跑时先确认 conditional_launcher 已激活 Nav2 再调 action。

## 待现场确认

- 现场是否真有充电桩硬件——nav2_params 里的桩坐标是厂家测试值，桩不在场则回充链路无从谈起。
- DockRobot action 是否暴露：conditional 拉起 Nav2 后 `ros2 action list` 确认。
