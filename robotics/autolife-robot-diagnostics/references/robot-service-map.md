# AutoLife S1 服务与路径速查

> 阵营归属以 grep 实测为准（见 SKILL.md Step 3），不要背这张表——不同机器人/版本可能不一致。

## systemd --user 单元（~/.config/systemd/user/）

| 单元 | 作用 | 备注 |
|---|---|---|
| gv-control-service.service | 底盘驱动 `autolife_robot_gv.main` | 发 battery/imu/lidar/robot_state；组播阵营 |
| gv-slam-service.service | SLAM `autolife_robot_gv.main_slam` | 额外 source ~/Documents/teb/setup.bash；组播阵营 |
| logo-backend.service | kiosk 桥 + 前端 `autolife_robot_kiosk.main` | WebSocket :8000（KIOSK_APP_PORT）；ExecStartPre sleep 5 |
| vision-service.service | 视觉 `autolife_robot_vision.main` | |
| flow-service.service | 流程 `autolife_robot_flow.main` | |
| arm-control-service.service | 机械臂 | |
| autolife-relay.service | 中继二进制 ~/Documents/autolife-relay | 无 CYCLONEDDS_URI |
| rust-web-server.service | Web 服务 ~/Documents/rust-web-server | 无 CYCLONEDDS_URI |
| autolife-admin-build.service | 管理端 SvelteKit build | |

## 话题命名

`/<名称>_0_<ROBOT_ID>`，如 `/topic_gv_battery_0_402`。ROBOT_ID 来自各 unit 的 `Environment=ROBOT_ID`。电池消息类型 sensor_msgs/msg/BatteryState，典型 1Hz。

## 关键路径

- unit 文件：`~/.config/systemd/user/*.service`
- python 包：`~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_{gv,kiosk,vision,flow,...}/`
- kiosk 前端 dist：`.../autolife_robot_kiosk/frontend/dist/assets/index-*.js`（前端默认值如 `battery:{percent:100}` 在这里 grep）
- 前端数据通道：`ws://127.0.0.1:8000/ws`
- Chrome kiosk 全屏：`/opt/google/chrome/chrome --lang=en --start-fullscreen`

## 进程层级

systemd → `conda run --no-capture-output -n robot_env`（外层，systemd MainPID）→ bash → `python -m autolife_robot_*.main`（内层真进程）。/proc 环境、CPU 占用、信号目标都看内层 PID。

## 开机自检报告

journalctl 里各服务启动时打 Hardware Initialization Report（mod_battery_ / mod_imu_ / mod_lidar_ ...）。时点性检查："未检测到问题"不代表 ROS 发布正常；"Connection to battery reader failed" 只代表当时失败，不代表现在。数据链路以 topic echo 实测为准。
