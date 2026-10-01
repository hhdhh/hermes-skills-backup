---
name: autolife-boot-auto-reset
version: 1.0.0
description: Use when adding or removing robot arm auto-reset on boot.
---

# AutoLife 开机自动复位机械臂

> 首装 2026-09-17，经网线直连 IP 192.168.10.2 装到当时在线的 316 机。端到端验证：unit exit 0 + arm-control 日志 `stability profile -> RESET` + 机械臂实际复位。
> **2026-09-19 321 暴露时序坑**（见"已知坑"第 6 条），unit 模板已加 `ExecStartPre=/bin/sleep 20`。
> **2026-09-19 321 曾装 v2 自愈版后整体撤销**：v2（`~/.local/bin/auto-reset-v2.sh`，轮询 communication_lost + 失败自动 restart arm-control）在该机不适用，主人拍板暂时取消整机功能。撤销方式=disable --now + unit 移入 `~/.config/systemd/user/holds/arm-auto-reset.service.off` + 双文件备份 `~/backup_autoreset_off_20260919_114059/`；`~/.local/bin/auto-reset-v2.sh` 原地保留（无引用，惰性）。恢复三行：`mv ~/.config/systemd/user/holds/arm-auto-reset.service.off ~/.config/systemd/user/arm-auto-reset.service && systemctl --user daemon-reload && systemctl --user enable arm-auto-reset.service`。
> **当前装机清单：316（v1 内联版 + sleep 20）、323（robox 官方版）、320（v1 SDK example 版 + 硬件就绪门控，2026-09-30 装机验证通过：RESET 日志+exit 0+心跳0风暴。S3 机型 robot_env 无 robox-auto-reset.sh，直接用 arm 包 examples/example_00_ros_reset_robot.py，环境变量整段抄同机 arm-control unit，base64 直写防 root 属主）**。316 尚未升级 v2。2026-09-22 323 装机实测：脚本本体不改；unit 改 ROBOT_ID=323、去重复行、加 ExecStartPre=/bin/sleep 90；手动验证 sleep90→等read_count_→robot_reset()→RESET日志→重启face→exit 0 全链通过，复位后 8min 心跳风暴 0 条。323 新坑：robssh push 落地文件为 root 属主（push 通道用 dd/cp 或传输后 chown），脚本必须 base64 直写保证 ubuntu:ubuntu + x 位。
> **2026-09-19 11:35 真机开机实测通过**（321 当时，boot 24926654）：开机 → sleep 20 → comm ready after 20s → 发复位 → `stability profile -> RESET` + unit exit 0，链路全自动走通，无需人工。判定标准同 5 步法三条。
> **2026-09-19 11:35 真机开机实测通过**（321，boot 24926654）：开机 → sleep 20 → comm ready after 20s → 发复位 → `stability profile -> RESET` + unit exit 0，链路全自动走通，无需人工。v2 判定标准同 5 步法三条。
> **2026-09-19 321 换装 robox-auto-reset 官方版**（同事方案，取代 v2）：unit `robox-auto-reset.service` + 脚本 `~/.local/bin/robox-auto-reset.sh`。比 v2 多了：GV 前雷达缺失监控自动重启（最多 3 次）、等 Vision 就绪后重启 face-detection、`ConditionPathExists=!%t/robox-auto-reset.done` 每开机仅一次。复位本体改用 `robot_env` 的 `autolife_robot_inspection.actions.robot_reset.robot_reset()`（编译 .so）。`%t` 在 321 展开为 /run/user/**1001**（ubuntu uid 1001，不是 1000）。11:50 手动验证通过：RESET 日志 + 轨迹执行 + exit 0。v2 的 `auto-reset-v2.sh` 脚本仍在机上但无 unit 引用。旧 skill 5 步法的 unit 模板已被此方案取代。
> 触发场景：主人说"加开机自动复位"、"开机复位怎么装的"、"查/取消复位配置"。systemd user oneshot + SDK 官方复位示例。

## 原理（30 秒版）

- 复位本体 = SDK 官方示例 `example_00_ros_reset_robot.py`：向 `/control_reset_<domain>_<robot_id>` 发一条 String 空消息；脚本自带"等订阅者上线才发"循环，不会空发。
- 出厂开机流程**没有**自动复位：arm-control-service 直接起，臂停在断电前任意姿势。
- 方案：user 级 oneshot unit，`After=arm-control-service.service`，开机跑一次复位脚本即退出。

## 通用装机 5 步（换任何一台机都走这个）

### 1. 验明正身 + 查 ROBOT_ID
每台机 ROBOT_ID 不同，unit 里必须对应改：
```bash
hostname
grep ROBOT_ID ~/.config/systemd/user/arm-control-service.service
```

### 2. 确认脚本与 python 实际路径
python 小版本可能不是 3.12：
```bash
ls ~/miniconda3/envs/robot_env/lib/python*/site-packages/autolife_robot_arm/examples/example_00_ros_reset_robot.py
```

### 3. 写 unit：`~/.config/systemd/user/arm-auto-reset.service`
```ini
[Unit]
Description=Auto arm pose reset once after arm-control is up (boot)
After=arm-control-service.service

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'source /opt/ros/jazzy/setup.bash && exec %h/miniconda3/bin/conda run --no-capture-output -n robot_env timeout 180 python /home/ubuntu/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_arm/examples/example_00_ros_reset_robot.py'
Environment="PYTHONUNBUFFERED=1"
Environment="ROS_DOMAIN_ID=0"
Environment="ROBOT_ID=316"
Environment="RMW_IMPLEMENTATION=rmw_cyclonedds_cpp"
Environment="CYCLONEDDS_URI=<CycloneDDS><Domain><General><NetworkInterfaceAddress>127.0.0.1</NetworkInterfaceAddress></General><Discovery><ParticipantIndex>auto</ParticipantIndex><MaxAutoParticipantIndex>255</MaxAutoParticipantIndex></Discovery></Domain></CycloneDDS>"

[Install]
WantedBy=default.target
```
要改两处：`ROBOT_ID=`（第 1 步查到的值）、`python3.12` 路径（第 2 步实际路径）。**环境变量整段抄自同机 arm-control-service**——两台机器的 DDS 配置可能不同（阵营分裂史），不要跨机复制。

### 4. 启用
```bash
systemctl --user daemon-reload
systemctl --user enable arm-auto-reset.service
```

### 5. 手动验证（不等重启）
```bash
systemctl --user start arm-auto-reset.service
systemctl --user status arm-auto-reset.service --no-pager
journalctl --user -u arm-control-service.service --since "2 min ago" | grep -i reset
```
判定标准（三条同时满足）：
- status 显示 `status=0/SUCCESS`
- arm-control 日志出现 `stability profile -> RESET`
- 机械臂实际做了一次复位动作

⚠️ 验证会让臂真的动一次——动手前确认臂边无人无障碍，先说一声再 start。

## 回滚
```bash
systemctl --user disable --now arm-auto-reset.service
rm ~/.config/systemd/user/arm-auto-reset.service
systemctl --user daemon-reload
```

## 已知坑（首装机踩过）

- **192.168.10.2 = 全机队网线直连固定 IP（lan0），接哪台就是哪台**（2026-09-18 主人明确）：不是某台机的专属身份，也不是“机器被重装”。经此 IP 连入先 `hostname` 验明正身、ROBOT_ID 按实查为准——连错台就把 unit 装错了机器。
- **`timeout 180` 兜底别删**：脚本会死等订阅者；万一 arm-control 起不来，没 timeout 会卡住后续开机链。
- **环境变量不一致 = 静默失效**：ROS_DOMAIN_ID / ROBOT_ID / CYCLONEDDS_URI 不匹配会把复位发到别的 DDS 域，复位无效且**无任何报错**（脚本照样 exit 0）。验证必须看 arm-control 侧日志，不能只看 unit 成功。
- **oneshot 失败不自动重试**：验证失败查 `journalctl --user -u arm-auto-reset`，修完重新 start。
- **user unit 依赖用户会话**：机队机器人默认 GNOME 自动登录，开机即拉起 user services（首装机实测成立）；若某台改过自动登录设置，复位会等登录才跑。
- **开机时序坑（2026-09-19 321 实测）**：`After=arm-control-service.service` 只保证 arm-control **启动**，不保证**就绪**。实测 arm-control 启动后初始化耗时 ~45s，其中真正执行回 home 的 `node_robot_action_service` 在启动后 ~48s 才 "Initializing components"。复位脚本等订阅者上线就发（脚本内置等待），消息发给 stability 控制成功但**动作服务还没就绪把回 home 执行吞了**——表现为：unit SUCCESS + 日志有 `stability profile -> RESET` 但手臂没动。**修复：unit 加 `ExecStartPre=/bin/sleep 20`**（在脚本自身"等订阅者"等待的基础上再多等，覆盖初始化窗口）。验证失败时手动 `systemctl --user start arm-auto-reset.service` 可单独复验链路。
- **过早复位致关节僵死（2026-09-30 320 事故）**：把 sleep 从 90 缩到 45 并加 `PartOf=+RemainAfterExit=` 重启联动后，arm-control 重启时复位在**硬件初始化未完成**时执行——腰部/腿部关节被打僵（`Failed to get position for joint Joint_Waist_Yaw/Knee/Ankle` 刷屏，重启前为 0），臂悬空不动。修复三原则：① sleep 保持 90 不缩；② **禁止 PartOf/重启联动**——oneshot+联动在 arm-control 反复重启场景必然再踩竞速，功能定位回归"仅开机一次"；③ 复位前必须过**硬件就绪门控**：等 `journalctl -u arm-control --since <本次ActiveEnter>` 出现 `Stability Scale` 行（说明控制环真跑起来了）才准发复位。320 现行方案=`sleep 90` + `wait_arm_ready.sh`（轮询 Stability Scale，最多 40×3s）+ 仅开机触发。事故恢复=干净重启 arm-control → 等就绪 → 手动复位一次，关节错误清零验证。
- **同事方案两个装机必查点（2026-09-19 321 首装踩过）**：① 脚本 scp 上去没有可执行位 → `status=203/EXEC`（systemd 报 EXEC 错误先 `ls -la` 查 x 位）；② unit 里 `ROBOT_ID=234` 是模板机残留 + 环境变量重复行——换机必改 ROBOT_ID（对照 `grep ROBOT_ID ~/.config/systemd/user/arm-control-service.service`），不改则复位发到别的机器人域，静默失效。
- **`%t` 展开按实际 uid**：robox-auto-reset 的 done 标记在 321 是 `/run/user/1001/robox-auto-reset.done`（ubuntu uid=1001）。验证时先 `id -u` 再拼路径，别想当然 1000。
- **心跳风暴与早发复位强相关（2026-09-19 321 全 boot 对账）**：10:28~11:33 五次开机，风暴全部在复位发布后 1-2 秒爆发（例：11:35:18 发复位→11:35:19 风暴）；而 +8 分钟的晚发手动复位（11:50）零风暴；无复位方案的两次开机（11:42/11:53）也零风暴。结论：复位发太早会触发 SDK 心跳保护连锁（lost_count_to_protect=1 过敏）→ protection 锁死→现场硬断电循环。robox unit 已加 `ExecStartPre=/bin/sleep 90` + TimeoutStartSec=600 对冲；2026-09-19 12:16 开机端到端验证：复位正常触发 + 全 boot 心跳风暴 0 条，方案定稿。真根因在 SDK .so 里，无源码不改。
- **多会话并行操作同一台机器人会互相踩（2026-09-19 321 实锤）**：一个会话 11:50 装好并验证通过，另一会话 11:52:30 按用户更早的"改回原本样子"指示整包回滚+重启。动工前先 session_search 查近期是否有同机的相反指示；装机被莫名清掉先查这个。

## 与其它技能的衔接

| 需求 | 去处 |
|------|------|
| 连不上机器 / 解析 IP | `autolife-find-robot` |
| SSH / robssh.py 用法 | `autolife-remote-repair` |
| 复位之外的系统性诊断 | `autolife-doctor-operations` |


## 补充（patch，审批积压恢复）

> **2026-09-19 321 撤销自动复位 + v2/错峰方案全部回滚（机器已回出厂状态）**：当天 321 心跳风暴根因未定为软件层判定问题，现场先后上了三层方案：v2 自愈脚本（10:44）→ arm-control 错峰 `ExecStartPre=/bin/sleep 45`（11:03）→ robox-auto-reset 编排器（11:28，含复位+重启 face+监控 GV）。主人拍板"放弃 v2 方案改回原本的样子"，已全部回滚：robox unit+脚本删除、arm-control 还原（diff 与备份 IDENTICAL）、auto-reset-v2.sh 删除。四份备份在 `~/backup_v2_revert_20260919_115230/`，arm-auto-reset v2 unit 另存 `~/.config/systemd/user/holds/arm-auto-reset.service.off`。回滚后验证：三个 reset unit 全 not-found、arm-control active 未受影响、本轮 boot 无心跳风暴（fps 正常）。**教训：321 心跳风暴与复位/错峰无关（10:28 前的 boot -4 无风暴且动作正常，装了方案后风暴照发），根因在 SDK .so 内部的心跳判定，lost_count_to_protect=1 极敏感，未解**。
