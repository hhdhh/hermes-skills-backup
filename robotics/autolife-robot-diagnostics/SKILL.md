---
name: autolife-robot-diagnostics
version: 1.0.0
description: Use when 主人要 ssh 上机器人排查电量/传感器/前端显示/ROS 话题/服务异常。
metadata:
  requires:
    bins: ["ssh", "python3"]
  triggers:
    - "机器人 电量 不对"
    - "机器人 电池 显示"
    - "机器人 前端 显示异常"
    - "机器人 话题 没数据"
    - "autolife 机器人 诊断"
---

# AutoLife S1 机器人远程诊断

> 完整描述：AutoLife S1 机器人远程诊断。Use when 主人要 ssh 上机器人排查电量/传感器/前端显示/ROS 话题/服务异常。

> 场景：SSH 上智动未来 AutoLife S1 机器人（用户 ubuntu），排查 ROS 2 数据链路 / systemd 服务 / kiosk 前端显示异常。
> 平台事实：Ubuntu 24.04 + ROS 2 Jazzy + miniconda `robot_env` + systemd --user 单元 + CycloneDDS（RMW=rmw_cyclonedds_cpp，ROS_DOMAIN_ID=0）。
> 姊妹技能：改 prompt/RAG 走 `autolife-robot-prompt-ops`；本技能管"查病 + 修数据链路"。

## 标准流程（先侦察后动手；改 unit / 重启服务前先报备主人，批准才动）

### Step 0 打通 SSH
- `sshpass` 通常没装，兜底：`pip install paramiko -i https://pypi.tuna.tsinghua.edu.cn/simple`，写本地 `robssh.py`（`run(host, cmd, timeout)`，AutoAddPolicy + 密码登录）复用。
- **远端命令一律写成本地 .py 文件执行**：整段脚本放 raw 三引号字符串。paramiko `exec_command` 里手转义嵌套引号必炸（`unexpected EOF while looking for matching`），不要在命令行里叠引号。

### Step 1 侦察
- `hostname` / `ros2 topic list | grep -iE "batt|power|imu|lidar"` 定位目标话题。命名规律 `/<名称>_0_<ROBOT_ID>`，后缀来自 unit 的 `Environment=ROBOT_ID`。
- `systemctl --user list-units --type=service` + `ps aux` 找服务与真实进程。`conda run` 会套两层：systemd MainPID 是外层 conda，真驱动是内层 `python -m autolife_robot_*.main` 孙进程——读 /proc 环境、看 CPU 都要对内层。

### Step 2 判定数据断点（最关键，别被 0 骗）
- **`ros2 topic info` 显示 Publisher count: 0 只反映你 shell 的 DDS 环境**——机器上各服务 CYCLONEDDS_URI 分裂成互不可见的阵营时，发布者活着你也看不见。先怀疑配置分裂，再怀疑驱动死了。
- 权威配置来源是进程本身：`tr '\0' '\n' < /proc/<发布方PID>/environ | grep CYCLONEDDS_URI`，export 它再 `timeout 12 ros2 topic echo --once <topic>`。
- **对称测试**：分别用发布方 URI 和消费方 URI 各订阅一次——哪边收不到，断点就在哪边。
- 开机自检报告（Hardware Initialization Report）是时点性检查，"未检测到问题"不代表 ROS 数据链路通；以 echo 实测为准。

### Step 3 找阵营分裂证据
- `grep -l "NetworkInterfaceAddress" ~/.config/systemd/user/*.service`（旧单播阵营）vs `grep -l "EnableMulticastLoopback" ...`（组播阵营）。
- `journalctl --user -u <unit> | grep -iE "multicast|deprecated"`：废弃写法 `NetworkInterfaceAddress 127.0.0.1` 会让 CycloneDDS **静默禁用组播**（一行 `selected interface "lo" is not multicast-capable: disabling multicast`），与组播阵营互相发现不了。两套模板见 references/dds-config-camps.md。

### Step 4 修复
- 备份 unit（`cp x x.bak-<时间戳>`）→ 替换 CYCLONEDDS_URI 为组播模板（注意 systemd 转义，XML 内引号写 `\"`）→ `systemctl --user daemon-reload && systemctl --user restart <unit>`。
- 只动确诊的那个 unit；同阵营其他服务等主人发话再统一对齐。

### Step 5 端到端验证（不要信 node list）
- `ros2 node list` 在这类机器上是噪音：进程活、数据流也可能不显示。验证必须走真实数据路径。
- kiosk 前端通道 = WebSocket `ws://127.0.0.1:8000/ws`：把 scripts/ws_battery_check.py 推到机器人，用 `~/miniconda3/envs/robot_env/bin/python` 跑，直接看前端收到的 JSON。
- **前端默认值陷阱**：前端 JS 硬编码初始值（如 `battery:{percent:100}`，在 `autolife_robot_kiosk/frontend/dist/assets/index-*.js` 里 grep）——读数卡死在固定值 = 桥收不到数据，不是硬件真满。修完后前端数字应随实时读数变化。

## 深度参考
- references/dds-config-camps.md — 两套 CYCLONEDDS_URI 模板、分裂机理、阵营测试命令
- references/robot-service-map.md — 服务表、话题命名、conda 包路径、进程层级
- scripts/ws_battery_check.py — kiosk WebSocket 端到端验证脚本（推到机器人上跑）
