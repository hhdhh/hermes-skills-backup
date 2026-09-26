---
name: autolife-robot-eef-config
description: AutoLife S1 机器人端执行器(EEF)模块配置：灵巧手(dexterous hand)与夹爪(gripp...
---

# AutoLife S1 EEF 模块配置（灵巧手 / 夹爪）

> 完整描述：AutoLife S1 机器人端执行器(EEF)模块配置：灵巧手(dexterous hand)与夹爪(gripper)的启用/停用/驱动型号切换。当主人说\"改灵巧手设置\"\"夹爪设置\"\"只留雷赛\"\"去掉某型号\"\"某个手/夹爪不工作\"时使用。重点是 ENABLED_MODULES 才是真正开关，不是 descriptions。

> 目标机器人：AutoLife S1（robot_v2_2）。控制服务 = `arm-control-service`（`systemctl --user`）。
> SSH 接入/文件传输走姊妹技能 `autolife-remote-repair`。

## 核心结论（最容易搞错）

**决定 arm 实际加载哪些灵巧手/夹爪模块的开关是 `ENABLED_MODULES`，在
`autolife_robot_arm/configs/robot_v2_2.json`——不是 sdk 的 descriptions 大 JSON。**

`site-packages` 里 `robot_v2_2.json` 有**多个副本**（arm/configs、sdk/descriptions/autolife_s1/configs、dashboard/configs、gv/configs、inspection/configs）。改错了那一份（比如只改 sdk 的 descriptions）重启后**毫无效果**，白折腾。

| 文件 | 作用 | 是否真正开关 |
|------|------|------|
| `autolife_robot_arm/configs/robot_v2_2.json` 的 `ENABLED_MODULES` | 决定加载哪些 EEF 模块 | **✅ 真正开关** |
| `autolife_robot_arm` 的 `settings.toml` → `sdk_settings.active_robot_version` | 决定读哪个 robot JSON（`robot_v2_2`） | 间接开关 |
| `autolife_robot_sdk/descriptions/autolife_s1/configs/robot_v2_2.json` 的 `mod_eef_/` | 每个驱动型号的电机/串口参数（port/DM4310 acc/max_speed/PID 等） | 参数层，非启用层 |
| `autolife_robot_arm/configs/robot_v2_2.json` 的 `DEXTEROUS_HAND_HOME_ANGLE`、`LEFT/RIGHT_GRIPPER_MOTOR_PID` | 回中角 / 电机 PID 等控制参数 | 参数层 |

## 灵巧手 vs 夹爪（两个不同东西）

- **夹爪 gripper**：1 DOF 钳式，DM 电机走 CAN（`can_id` 12/20，DM4310），`mod_eef_gripper_left/right_dm`。删掉即无夹爪。
- **灵巧手 dexterous hand**：22 DOF 多指，型号 4 种并存（leadtron / ro / inspire / linker），串口 `/dev/ttyLeftHand`/`/dev/ttyRightHand`。leadtron = 雷赛。

`ENABLED_MODULES` 里同一 `mod_name`（如 `mod_eef_dexteroushand_left`）可有多个驱动型号条目并存，运行时靠 `ENABLED_MODULES` 列出哪个就加载哪个——**想"只留雷赛"就把其他型号条目从 ENABLED_MODULES 里删掉**。

## 判断"真正生效"——别被 Available modules 行骗

arm 启动日志会有两行易混淆：

1. `robot_v2_2 Available modules: ['...']` —— 一大串，**往往仍带全部型号**。这是 sdk/vision 的**预扫描枚举**，不是 arm 的 ENABLED_MODULES 展开，**不代表生效**。
2. `Discovering end effectors... ['mod_eef_gripper_left_dm', ... 'dexteroushand_left_leadtron']` —— **这才是 arm 实际要加载的 EEF 清单**。看这一行确认改动生效，别看 Available modules。

随后还应有逐条 `[LeadTronHand] 连接成功 /dev/ttyLeftHand, dof=6` + `Dexterous hand ... registered on ...` 确认硬件真的连上。

## 标准流程

1. **确认形态**：主人说"灵巧手还是夹爪？"，先分清（见上表）。
2. **确认型号**：`journalctl --user -u arm-control-service` 里刷 `[LeadTronHand] device not connected` / `read failed` → 看实际硬件是哪个型号（串口符号链接 `/dev/ttyLeftHand -> ttyACM1` 存在 = 设备挂了）。
3. **改 `ENABLED_MODULES`**（真正开关）：备份原文件（带时间戳 `.bak.only<型号>.<ts>`）→ 删掉非目标型号条目 / gripper → 写回 JSON → `python3 -c "import json;json.load(open(...))"` 校验。保留 `.bak.*`（90 天内不删）。
4. **改 sdk descriptions**（可选，对齐参数）：同型号名的 `mod_eef_/` 条目删掉其它型号（无副作用，但非必需——不影响启用；保持两处一致可避免混淆）。
5. **重启 arm-control-service** 生效。
6. **验证**：等初始化完成后看 `Discovering end effectors...` 行只剩目标型号 + 逐条 `registered on` 确认连上。

## 写文件的姿势（避免远程内联引号地狱）

改 JSON 用**本地写脚本 → sftp 上传 → 远端执行**，不要用 `ssh 'python3 - <<EOF ... EOF'` 或 f-string 内嵌多行 heredoc——嵌套引号/换行在 remote exec 链路必炸（本会话踩了多次 SyntaxError）。

```python
# 本机 build <修改>.py，sftp 传到 /tmp，然后 exec('python3 /tmp/<修改>.py <目标json>')
sftp = c.open_sftp(); sftp.put("/本机/fix_x.py", "/tmp/fix_x.py"); sftp.close()
_
```

顺序：先只读检查脚本确认 `mod_eef_`/`ENABLED_MODULES` 定位正确 → 再跑修改脚本（脚本里先备份再改、改完校验写回、打印删了什么留了什么）。

## 坑

- **arm-control 重启脆弱**：`Restart=always` 会自动拉起，但重启过程中可能经历"初始化 60s 超时 → died"的瞬时空窗，之后秒自愈。**改完配置重启后至少等 30~40s 再验证**，别看到一步 ERROR 就以为表坏了。
- **找不到 CONFIGS_ROOT 别慌**：`autolife_robot_arm/__init__.py` 里 `CONFIGS_ROOT` 优先取 `PROJECT_ROOT/configs`，否则取包内 `configs/`。PROJECT_ROOT = site-packages 再上一级；editable 包要 source ROS（`/opt/ros/jazzy/setup.bash`）才能 import。纯文件系统判断用 `trace`，别 import 包（缺 rclpy 会崩）。
- **delete 前先 read-only 定位**：用探针脚本打印 `mod_eef_` 容器路径 + 全部条目 + driver_model，确认定位到的是目标容器，再执行删除。
- 备份文件是 root 拥有时（`root root`），当前用户可能没法写——看 `stat -c '%U %G %a'`，ubuntu 拥有（664）可直接改，root 拥有先 sudo。
