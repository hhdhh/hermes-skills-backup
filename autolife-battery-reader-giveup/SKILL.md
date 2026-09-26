---
name: autolife-battery-reader-giveup
description: "Use when 电池恒100%但 ttyBattery 在且 SDK 直读正常——gv reader 失败后永久放弃。"
---

# 电池恒100%根因C：gv battery reader 一次性失败后永久放弃

电池恒100%有三个独立根因，按决策树排查（另两个见 `autolife-battery-udev-mapping` 根因A、`autolife-robot-dds-camp-split` 根因B）：

```
1. ls /dev/ttyBattery
   ├─ 不存在 → 根因A（udev devpath 不匹配）
   └─ 存在 ↓
2. SDK 直读验证硬件：
   from autolife_robot_sdk.hardware.battery import BatteryV2RS485Reader
   r = BatteryV2RS485Reader(port="/dev/ttyBattery", baudrate=9600)
   print(r.read_data(force_refresh=True))
   ├─ 报错 → 串口被占或硬件问题（fuser /dev/ttyBattery 查占用）
   └─ 读出真实值（硬件健康）↓
3. journalctl --user -u gv-control-service --since today | grep -i battery
   ├─ "Connection to battery reader failed" 且无 "registered" → 本技能（根因C）
   └─ 按根因B（DDS 阵营）继续查
```

## 机制

gv-control 的 battery reader 在服务启动阶段初始化：若连接失败一次（串口未就绪/时序竞争——机器刚开机时其他服务同抢 USB），reader **不重试、直接放弃**，之后进程生命周期内电池话题永远发布默认值 100%。串口本身和电池硬件完全正常——SDK 直读可证。

## 判定特征（日志三联）

```
Battery reader serial port closed successfully     ← 只有 close，没有 open 成功
（数秒后）Hardware Initialization Report:
  mod_battery_:
    1. Connection to battery reader failed          ← 一次失败，永久放弃
```

修复后成功的日志对照：`Battery reader registered on /dev/ttyBattery`。

## 修复

```bash
systemctl --user restart gv-control-service.service
```

重启时其他服务已稳定、串口无竞争，reader 注册成功。

## 验证

1. 日志出现 `Battery reader registered on /dev/ttyBattery`
2. `curl -s http://127.0.0.1:9001/robot/status` 的 `battery` 字段变真实值（非 100）
3. 前端电池显示恢复

## 坑

- 诊断时先用 SDK 直读确认硬件健康再动服务——否则容易误判为电池/串口硬件故障返厂。
- 该问题常在开机后首次出现（多服务启动竞争串口）；若机器重启后又复现，考虑给 gv-control 加 ExecStartPre 延时错峰（参考 arm-control 的 sleep 45 错峰方案）。
- 9001 API 无响应时先确认 rust-web-server 是否在跑，别把 API 不通误当电池问题。