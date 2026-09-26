---
name: autolife-robot-support
description: "Use when SSH-ing into autolife robots to triage gv-*/Nav2 services."
---

# Autolife 机器人远程支持

对 autolife 机器人（`ubuntu@192.168.65.x`，主机名 `autolife-robot-*`）做日志/服务远程诊断时的规则。与 `network-troubleshooting-ssh`（连不上时的分层诊断）互补：本技能管**连上之后**的运维诊断。

## 1. 连接

Hermes Ubuntu 机上通常只有裸 openssh（无 sshpass/expect/paramiko）。用 `scripts/sshrun.py`（纯 stdlib pty 驱动密码提示，脚本本身不含任何凭证）：

```
SSH_PW=*** python3 scripts/sshrun.py ubuntu@<robot-ip> 'journalctl --user -u gv-slam-service --since today --no-pager | tail -40' 90
```

密码一律经 `SSH_PW` 环境变量或 getpass 传入，绝不写进文件或命令行历史。

## 2. 先归因，再判病

- journal 里 `Stopping <unit>...` = systemd 收到了**显式 stop 请求**，不是崩溃。先找到是谁发的，再谈故障。
- 归因手动重启：把 `~/.bash_history` 里的 epoch 注释行（`#1789023133` → `date -d @1789023133`）与 journal 的 Started 行对时间——精确吻合 = 本机控制台有人在敲命令。`who`/`last` 可确认是 `:0` 桌面会话还是 SSH。
- 排除调度器一次即可：`systemctl --user list-timers --all`、`crontab -l`。
- 区分"单服务手动重启" vs "看门狗/整栈重启"：拉同一分钟内**所有单元**的 Started/Stopping 行——只有目标单元在动 = 人为单点重启。

## 3. 吓人但无害的行（先排除，省时间）

- `CondaError: KeyboardInterrupt` + `status=1/FAILURE`（出现在 Stopping 之后）：unit 配了 `KillSignal=SIGINT`，`conda run` 收到即以 KeyboardInterrupt 退出。前面有优雅清理日志（"所有资源已释放"）→ 关闭路径的退出码噪音，不是病。
- `selected interface "lo" is not multicast-capable: disabling multicast`：CYCLONEDDS_URI 故意钉 127.0.0.1，lo 无组播必然触发，CycloneDDS 自动降级单播。每次启动都有，忽略。

## 4. 门闸型故障的定位法（action server not available 类）

- 症状族：`navigate_to_pose action server not available` / Nav2 永远不起 / launcher 打印几行 Received 后沉默。
- **核心手法：拿当天一轮健康周期与卡死周期做 journal 对比**——缺失的那行 `Received /topic_...` 就是死掉的输入。比逆向二进制快得多。
- gv-slam 门闸链：odom + front_lidar + rear_lidar 三话题到齐 → laser_merger(`/merged`) → localization(AMCL) → navigation(Nav2)。任一话题缺席，整链不启动——**重启受害者服务（gv-slam）治不了输入断供，要修的是话题发布方（gv-control/硬件）**。

## 5. 证据陷阱

- 不要在裸 SSH shell 里跑 `ros2 topic list` 判断话题存亡：unit 把 CYCLONEDDS_URI/ROS_DOMAIN_ID/RMW 钉在 `Environment=` 里，环境不一致的 shell 发现不了任何节点，会误判"话题全没了"。要么完整复刻 unit 的环境变量，要么直接读服务自己的 journal。
- Cython 编译的 `.so` 里 grep 日志字符串可能搜不到（字符串压缩）；放弃逆向，回到 journal 对比法。
- SDK 日志的 `Available modules: [...]` 是机型配置能力表，**不代表硬件在线**。硬件死活看读数循环：`Error reading <sensor> data: module not found` 刷屏（~20 条/秒）= 该模块自驱动服务本次启动起死亡；同类只有单个报 = 单模块故障，非总线级。

## 6. 安全门（物理硬件）

- 机器人是会动的实体设备。诊断全程只读；**重启 gv-control / gv-slam / arm 类服务前必须经主人（或现场同事）确认**——底盘可能抽动。
- 传感器模块死亡时的修复顺序：先软复位（重启**驱动方** gv-control，不是消费方 gv-slam）；错误刷屏复现 → 查模块供电/线缆，必要时整机断电 30s 再上电。

## 参考

- `references/service-topology.md` — 服务清单、话题命名、启动链、故障签名速查。
- `scripts/sshrun.py` — pty 密码 SSH 驱动（无 sshpass 环境的补位方案）。
