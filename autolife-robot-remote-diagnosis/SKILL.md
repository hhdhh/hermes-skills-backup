---
name: autolife-robot-remote-diagnosis
version: 1.0.0
description: Use when 机器人前端显示不对/话题没发布者/跨服务收不到数据/传感器数据可疑。
metadata:
  requires:
    bins: ["python3"]
    pypi: ["paramiko"]
  triggers:
    - "机器人电量显示不对"
    - "机器人前端数据不更新"
    - "ros2 topic 没有发布者"
    - "机器人收不到话题"
    - "机器人数据链路排查"
---

# AutoLife S1 机器人远程诊断

> 完整描述：SSH 远程诊断智动未来 AutoLife S1 机器人的数据链路与服务问题：前端数据卡默认值、ROS 2 话题断流、DDS 发现隔离、服务假活。Use when 机器人前端显示不对/话题没发布者/跨服务收不到数据/传感器数据可疑。

## 车队速查

| 机器人 | IP | 主机名 | 备注 |
|---|---|---|---|
| 274 | 192.168.10.2 | — | prompt/RAG 操作见 `autolife-robot-prompt-ops` |
| 309 | — | — | 小梅沙项目机 |
| 402 | 192.168.65.66 | autolife-robot-402 | DDS 隔离案例首发机 |

登录 `ubuntu@<ip>` 密码 `ubuntu`。话题名带机器人编号后缀：`/topic_gv_battery_0_402`。

## 架构速记（诊断用）

- **gv-control-service**（user systemd）：底盘驱动，发布电池/IMU/雷达/robot_state 等 `topic_gv_*_0_<id>` 话题，1Hz 级
- **logo-backend.service**：跑 `autolife_robot_kiosk.main`（kiosk_bridge），把 ROS 数据喂给 Chrome kiosk 前端
- 其余 user 服务（vision / flow / arm / face-detection / dashboard 等）各自订阅发布
- conda env `robot_env`；ROS 2 Jazzy + `rmw_cyclonedds_cpp`

## 标准流程

### Step 0 准备 SSH 通道
- 本机缺 sshpass 时用 paramiko：`pip install paramiko -i https://pypi.tuna.tsinghua.edu.cn/simple`
- 用 `scripts/robssh.py <host> <timeout> '<cmd>'` 跑远端命令
- **坑**：远端命令含引号或 `$(...)` 时不要在 terminal 里内联拼 shell——嵌套转义必翻车。把命令写进本地 .py（用 `r'''...'''` 原始字符串整段包住）再执行

### Step 1 定位现象
- `ros2 topic info -v <topic>`：**Publisher count: 0 = 数据断流**（订阅者可能还在）
- `systemctl --user list-units --type=service` 列 autolife 相关服务
- **坑**：服务 `active (running)` ≠ 在发数据——`conda run` 包装下 MainPID 是 conda 进程，真 python 是子进程。判断数据流只看话题发布者数，不看服务状态
- **坑**：话题名存在但发布者 0 ≠ 没人发——可能是你的 shell 的 DDS 环境跟发布方不同阵营，见 Step 3/4

### Step 2 前端"卡初始值"判定
- 前端收不到数据时显示 JS 里写死的初始值（如 kiosk 前端 dist 里 `battery:{percent:100,charging:!1}`），不是硬件读数
- 先修数据链路，别急着怀疑电池/传感器硬件

### Step 3 对比进程真实环境（最快定位配置分裂）
```bash
tr '\0' '\n' < /proc/<pid>/environ | grep -E "^ROS_|^RMW_|^CYCLONE"
```
- 拿疑似发布方 vs 订阅方两边的 `CYCLONEDDS_URI` / `ROS_DOMAIN_ID` / `RMW_IMPLEMENTATION` 对比
- `/proc/environ` 是生效值，比翻 service 文件快且不会漏 bashrc 注入
- 任一不同 → DDS 发现隔离，深入排查见 `references/ros2-dds-discovery.md`

### Step 4 决定性测试
分别 export 两套配置订阅同一话题，谁收得到一目了然：
```bash
export ROS_DOMAIN_ID=0 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI="<A 套或 B 套，从 /proc/environ 抄>"
source /opt/ros/jazzy/setup.bash
timeout 12 ros2 topic echo --once /topic_gv_battery_0_<id>
```
- 电池消息字段：`percentage`（0-100）、`voltage`、`current`（负值=放电）、`temperature`，约 1Hz

### Step 5 汇报 + 等确认再动手
- 修法通常是改 systemd unit 的 `CYCLONEDDS_URI` + `daemon-reload` + restart
- **改 unit / 重启机器人服务前必须主人确认**（前端会黑几秒再回来）

## 坑清单

1. 远端复杂命令内联拼 shell 必翻车 → 写本地 .py 跑（Step 0）
2. `NetworkInterfaceAddress` 是 CycloneDDS 废弃写法，会禁 lo 组播 → 两阵营互相看不见（references/ros2-dds-discovery.md）
3. 日志指纹 `selected interface "lo" is not multicast-capable: disabling multicast` = 废弃配置在跑
4. `ros2 topic list` 能列出话题名（订阅方也在广播）但 `topic info` 发布者 0——别据此断定驱动死了

## 支撑文件

- `references/ros2-dds-discovery.md` — DDS 两阵营隔离的机制、阵营扫描命令、修复模板
- `scripts/robssh.py` — paramiko 密码登录跑远端命令的 helper
