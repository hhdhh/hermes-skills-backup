---
name: autolife-battery-udev-mapping
version: 1.0.0
description: "AutoLife 机器人电池恒100%第二根因：udev devpath 与 USB 拓扑不匹配，/dev/ttyBattery 及 IMU/lidar/超声波符号链接全缺失。Use when 前端电池恒100%、battery reader 打不开 /dev/ttyBattery、ttyBattery 不存在、gv 因 RPLidar segfault 崩溃。"
metadata:
  triggers:
    - "电池恒100%"
    - "ttyBattery 不存在"
    - "could not open port /dev/ttyBattery"
    - "RPLidar cannot getRPLIDARDeviceInfo"
    - "Segmentation fault gv"
---

# AutoLife 机器人 udev USB 映射失效（ttyBattery 缺失 → 电池恒100%）

> 来源：2026-09-15 320 机（192.168.10.2，密码 robot_initpd 特殊）实测排查，与姊妹技能 `autolife-robot-dds-camp-split`（S1 DDS 阵营分裂）是**不同的电池恒100%根因**。

## 病因

`/etc/udev/rules.d/99-gv-usb-port.rules` 用 **USB 端口拓扑 `devpath`** 精确匹配，把各硬件映射成稳定符号链接：

```
ttyACM* 1a86:55d4 devpath=5.2.2 → ttyIMU
ttyACM* 1a86:55d3 devpath=5.3   → ttyBattery
ttyUSB* 10c4:ea60 devpath=5.4   → ttyLidarRear
ttyUSB* 1a86:7523 devpath=5.2.1/5.2.4 → ttyUltrasonic*
```

**当机器实际 USB 拓扑的 devpath 与规则写死值不一致时**（例如本应 6.x 写成 5.x，或换 hub/换 USB 控制器），**udev 规则一条都不匹配 → 所有 tty 符号链接都不建立**：

- `/dev/ttyBattery` 不存在 → SDK battery reader（RS485, bitrate 9600, bus_prefix /dev/ttyBattery）打不开 → 前端电池显示默认值 100%
- 连带 `/dev/ttyIMU`、`/dev/ttyLidarRear`、`/dev/ttyUltrasonic*` 全缺失

## 诊断（关键命令）

```bash
# 1. 检查 tty 符号链接是否建立（缺失 = udev 失效）
ls /dev/ttyBattery /dev/ttyIMU /dev/ttyLidarRear /dev/ttyUltrasonic* 2>&1

# 2. 看规则写死的 devpath
cat /etc/udev/rules.d/99-gv-usb-port.rules

# 3. 对照实际设备 USB 拓扑（看 devpath 属性）
udevadm info --query=property --name=/dev/ttyACM0 | grep -E 'ID_VENDOR_ID|ID_MODEL_ID|DEVPATH'
# 或 python 枚举所有 tty 的 vid/pid+devpath，对照规则：规则写 5.x，实际 3-6/6.3 → 应为 6.3
# 参考脚本：每 tty 的 DEVPATH 里 usbX/ 后第一段就是端口链
```

**判定规律**：规则 devpath 前缀与实际 `DEVPATH` 的端口链段不一致（如规则 `5.2.2`，实际 `...usb3/3-6/3-6.2.2/`）。同一台车其他 udev 规则（hand/sensor/force 用 `6.x`）与实际一致，唯独 gv 规则用 `5.x` 时，几乎可以断定 gv 规则写错了。

## 修复

把 `99-gv-usb-port.rules` 里 `ATTRS{devpath}=="X.Y.Z"` 改成实际值（sed 注意 `"5.` 转义坑，用 python re 替换更稳）：

```bash
cp /etc/udev/rules.d/99-gv-usb-port.rules /etc/udev/rules.d/99-gv-usb-port.rules.bak.$(date +%Y%m%d)
# python: re.sub(r'(ATTRS\{devpath\}==")5\.', r'\g<1>6.', txt)  # 5.x → 6.x
udevadm control --reload-rules
udevadm trigger --subsystem-match=tty
udevadm settle
ls -la /dev/ttyBattery /dev/ttyIMU /dev/ttyLidarRear /dev/ttyUltrasonic*  # 应全部建立
```

验证电池真实值（绕过 ROS，直接 sdk 读）：
```bash
# robot_env python:
from autolife_robot_sdk.hardware.battery import BatteryV2RS485Reader
r = BatteryV2RS485Reader(port="/dev/ttyBattery", baudrate=9600)
print(r.read_data(force_refresh=True))   # → 真实 capacity_percentage（320 机实测 85%）
```

> 注意：可能还有其他 udev 规则文件（`99-hand-usb-port.rules`、`99-sensor.rules`、`99-force-sensor.rules`）用正确的 `6.x`，只有 gv 规则写错 `5.x`——改前先对照全部规则文件。

## gv-control 崩溃（连带坑）

`gv-control-service.service`（ROS jazzy, domain 0, CYCLONEDDS_URI 绑 127.0.0.1 单播）在**打不开 `/dev/ttyLidarFront`（mod_lidar_front）时 RPLidar C 库会 `Segmentation fault (core dumped)`** → crash loop（NRestarts 上百）。这是 RPLidar 驱动的 bug（打不开串口直接段错误）。

- 若机器**实际只有一台后雷达**（无 front），需把 sdk config `robot_v2_2.json` 的 `mod_lidar_` 组里 `mod_lidar_front` 定义删除，gv 才不再 segfault 崩溃。但这会引出**代码硬编码引用**：gv 的 `ground_vehicle_sensors.py read_rear_lidar` 等仍硬编码找 front lidar，报 `Lidar module mod_lidar_front not found`（不崩但刷屏 + 可能阻塞 battery topic 发布）。
- **前端电池显示的最终恢复需要研发改 gv 代码**跳过硬编码的 front-lidar 依赖；FAE 侧能确定修的只是 udev 链接电池可读 + gv 不再崩溃这两层。

## 坑

1. `udevadm test /sys/class/tty/ttyACM0` 能模拟验证规则匹配（即使物理链接未实时建），成功会打印 `Added SYMLINK 'ttyBattery'` + `DEVLINKS=/dev/ttyBattery`。
2. 改 udev 规则后 `udevadm trigger` 在非交互环境不一定立刻建链接，要 `udevadm trigger --subsystem-match=tty` + `udevadm settle`。
3. sysfs 里 tty 串口设备的 vid/pid/devpath 不在 `ttyX/device/` 直接读得到，用 `udevadm info --query=property` 最可靠。
4. 电池真实值验证直接 sdk 读（上面），别依赖 ros2 echo（gv 没发布话题时 echo 不到，但不代表电池本身坏）。
5. **同机多套 USB hub 拓扑**：一台 robot 常有两条 hub（如 320 机 usb3 下 `3-5` 与 `3-6` 两套），**gv 设备（电池/IMU/lidar/超声）在一条、arm 的机械手/力传感在另一条**。不同 udev 规则文件（99-gv-* / 99-hand-* / 99-force-sensor-*）往往按不同 hub 的 devpath 写死，且厂家规则本身会写错（5.x vs 6.x 对调）。**排查时逐条用 `udevadm info --query=property` 对实际设备，别假设规则正确，也别用官方规则文件盲覆盖**——官方模板 vs 某台实机拓扑可能对调，覆盖会回退已修好项。
6. **arm-control-service crash loop 的连锁根因**（320 机 2026-09-15 复现）：arm 服务在初始化阶段（约30s内）若任一启用模块找不到对应硬件就**致命退出**（exit 1），且**连带杀掉 gv-control-service**（同进程树 gv_task）。判断：`journalctl` 看到每 ~30s 一次 systemd Started→`robot_arm_service 0_320 exit`，`ps` 见 arm+gv 反复重生。**根本治法 = 把 arm config 的 `ENABLED_MODULES`（site-packages/autolife_robot_arm/configs/robot_v2_2.json）精简成只留该机实际硬件**：机械手按实际型号（如 leadtron）留 `mod_eef_dexteroushand_left/right_<型号>`，删掉不存在的型号（ro/inspire/linker/gripper_dm/tactile/force）——因 sdk descriptions 只有 `Available modules` 候选全量会扫，但 `ENABLED_MODULES` 才是实际启用开关；未启用型号不再初始化也就不触发致命退出。验证：`Discovering end effectors... ['mod_eef_dexteroushand_left_leadtron']`（只出现实际型号）+ 手 `连接成功 doF=6` + `read_count_*_dexteroushand fps ~10` 心跳 + NRestarts 归零。