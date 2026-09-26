---
name: autolife-robot-troubleshooting
description: Use when 机器人前端数据僵死/电池恒100%/话题0发布者/服务互相看不见，或任何需 SSH 上 S1 排...
---

# autolife-robot-troubleshooting

name: autolife-robot-troubleshooting
version: 1.0.0
description: "AutoLife S1 机器人远程排障标准流程（SSH+paramiko），含 DDS 阵营分裂统一修复。Use when 机器人前端数据僵死/电池恒100%/话题0发布者/服务互相看不见，或任何需 SSH 上 S1 排查的任务。"
metadata:
  robots: ["S1 同型均可，已验 402/192.168.65.66"]
  triggers: ["机器人前端不刷新", "电池显示100%", "topic 0 publisher", "DDS 阵营", "S1 排障"]
---

# AutoLife S1 机器人远程排障

## 环境与连接

- SSH `ubuntu@<ip>`，密码 `ubuntu`；本机无 sshpass，用 paramiko（助手脚本 `~/.hermes/workspace/robssh.py`）。
- 复杂命令写成多行字符串经 paramiko 执行，避免 shell 引号转义地狱（单行 `python3 robssh.py <ip> <timeout> '<cmd>'` 只适合简单命令）。
- 话题名带机器人编号后缀（`_0_402`），换机先用 `grep ROBOT_ID ~/.config/systemd/user/gv-control-service.service` 取编号。
- ROS Jazzy + rmw_cyclonedds_cpp，所有服务为 systemd **user** unit，在 `~/.config/systemd/user/`。
- 前端链路：底盘驱动(ROS 话题) → kiosk_bridge(logo-backend.service, :8000) → WebSocket /ws → Chrome kiosk 页面。

## 排障总流程：从数据源向消费端逐层验

1. **验数据源**：用组播阵营 URI（见 references/dds-camp-unify.md）export 后 `ros2 topic echo --once <话题>`。有数据 = 硬件驱动正常，问题在中间/消费层。
2. **对称测试**：从 `/proc/<pid>/environ` 抓消费方进程的 CYCLONEDDS_URI，用它再订阅同一话题。收不到 = 阵营分裂确诊。
3. **找铁证**：`journalctl --user -u <服务> | grep -i multicast`，出现 `disabling multicast` = 实锤。
4. **修后验证必须端到端**：连 `ws://127.0.0.1:8000/ws` 看真实数据流（脚本在 references/dds-camp-unify.md），不要只看 topic info。

## 核心坑（省下几小时）

- **`ros2 node list`/`topic info` 的可见性由执行命令自身的 DDS 配置决定**——跨阵营查询永远显示 0 publisher，但数据其实在流。诊断前必须先 export 对应阵营的 CYCLONEDDS_URI。
- **前端不动的数值是 JS 初始默认值**（如 battery percent:100），不是任何真实读数。数值不变先怀疑"僵尸初始值"，别急着查硬件。
- **ai/vision 等消息是事件驱动**（有人说话/露脸才推新帧）——自动化测试只验得到话题 publisher 恢复 + 高频消息（如 agent 音频律动 ~20 条/s）回流，最终验收需现场互动。
- systemd unit 改完必须 `daemon-reload`，否则改了白改。
- data-logger-service 缺模块 crash-loop 是包版本老毛病，与 DDS 无关，别被它带偏。

## 修复 DDS 阵营分裂

详细模板与脚本见 [references/dds-camp-unify.md](references/dds-camp-unify.md)。要点：

- **必须全机统一**：把所有含 CYCLONEDDS_URI 的 unit 一次全部对齐组播版。只改单个消费方会修好一条链路、切断其余所有跨阵营链路（电池通了、AI/人脸/点单全断）——这个副作用在下次整机重启后才暴露。
- 逐个备份（`cp unit unit.bak-$(date +%Y%m%d-%H%M%S)`）→ 只替换 CYCLONEDDS_URI 整行 → 统一 daemon-reload → 批量 restart。
-gv-control/gv-slam 本就是组播阵营参照物，不动它们。
- 无 CYCLONEDDS_URI 的 unit（rust-web-server/autolife-relay/pipewire 等）无阵营属性，不碰。

> 完整描述：AutoLife S1 机器人远程排障标准流程（SSH+paramiko），含 DDS 阵营分裂统一修复。Use when 机器人前端数据僵死/电池恒100%/话题0发布者/服务互相看不见，或任何需 SSH 上 S1 排查的任务。
