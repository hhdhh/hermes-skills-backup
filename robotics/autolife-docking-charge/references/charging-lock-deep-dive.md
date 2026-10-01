# 充电锁底层架构与深挖通道

锁现象：充电态发 `/topic_gv_target_cmd_vel_0_<id>` 指令，odom/电机零响应，undock action 假成功。

## 控制链架构（S2/robot_v2_2 实测）

- cmd_vel 唯一订阅者 = `node_robot_task_control_service_0_<id>`，同时发布 `/topic_gv_wheel_odom_0_<id>`。
- 该节点宿主**不在 gv 包**：进程树为 `conda run -n robot_env python -m autolife_robot_arm.main`（Python 进程）→ multiprocessing spawn 子进程。同树还有 node_arm_vr_control_service、mod_motor 控制进程。
- 锁点：`autolife_robot_arm/gv_task_control.cpython-*.so`（Cython 编译，无法直接读源码）的 `GvTaskControl.target_vel_callback`——充电态丢弃速度指令，无日志。符号表可用 `strings` 提取（方法、reset_odom、set_target_joint_velocity、SharedStateManager 等可见）。
- 电机驱动在 `gv_joint_control.so`：`GvJointControl._move_gv_motors` / `_update_gv_motors_state`。
- 明文可读的关键文件：`autolife_robot_arm/utils.py`（JointState/SharedStateManager/ControlState 全定义）、`autolife_robot_arm/main.py`（run_gv_service 线程）、`autolife_robot_arm/settings.toml`（robot_control_settings，含 allow_actions_during_navigation 等）。

## CAN 独占

- 底盘 4 电机（DM8006，can_id 1-4，PCAN）由 arm.main 子进程独占。
- SDK 直连失败模式：`HWAPI().initialize(['mod_motor_gv'])` → "Motor ID N not responding on PCAN_USBBUS5"（随机占用的总线号）。
- 查持有者：`fuser /dev/pcanusbfd32` …（设备号 32-41 逐一 fuser）。
- 厂商官方轮速换算（examples/sdk_example_05）：麦轮 4 轮 `wd=[1,-1,1,-1] × [fl,fr,rl,rr] × 520`，WHEEL_SEP=0.36。

## SHM 旁路通道（架构确认，直写未验证）

- `autolife_robot_arm/utils.py` 的 `SharedStateManager.gv_joint_state = JointState(num_joints, lock_prefix=f"shared_state_<hex>_gv")`：SHM 段存 `/dev/shm/`，`FastLock`（文件锁）保护。
- `JointState.set_target_joint_velocities()` 写目标速度数组；`GvJointControl._move_gv_motors` 从该 SHM 读速驱动电机——理论直写 SHM 可绕过 ROS 层充电锁。
- 未实测。若走此路：先枚举 `/dev/shm/` 找 `shared_state_*` 段、复用 JointState 布局（target_pos/target_vel/target_tor 顺序偏移）、低速 0.05m/s 试探、随时写零停。属实验级操作。
- 停/重启 arm.main 属用户确认级操作（会连带臂/颈/腰控制全下线）。

## undock 两态判定表

| 状态 | 触发条件 | undock action | 验证结果 | 解法 |
|---|---|---|---|---|
| docking_server 态锁 | fullinplace 后 WAIT_FOR_CHARGE（Ah 平，未真充电） | success=True | 底盘释放，转身一次到位 | UndockRobot action 即可 |
| 充电真锁 | battery current > 0（Ah 上行） | success=True error_code=0 | odom 仍零响应 | 人工推离 / SHM 通道 / 停服务 |

判定依据只有一条：undock 后立刻跑运动探针看 odom——action 返回值在两种锁下完全相同。

## 诊断命令速查

```
# 运动真伪探针（发0.1m/s×3s看odom差）
probe_cmd.py  # 发指令前后 /topic_gv_wheel_odom_0_<id> 差值

# 电机位置 6s 稳定性（佐证）
ros2 topic echo /topic_gv_current_motors_status_0_<id> --field data --once

# 僵尸 goal 清理
pgrep -af "dock_probe|nav_goto"  # 逐个 kill

# CAN 持有者
fuser /dev/pcanusbfd36

# 进程树定位宿主
ps -ef | grep autolife_robot_arm.main
```
