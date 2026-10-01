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
- **直读姿势坑（2026-09-28 224/260 对照实测）**：gv 正在跑的机器上 SDK 直读必 None——reader 抢不过已注册的 gv 进程（260 实测：gv registered+话题有真实值 83%，我直读仍 None）。直读只在 gv 已停或从未成功过的机器上有意义；「直读 None」≠ 硬件坏。要拿真实值，走 DDS 话题 `/topic_gv_battery_0_<机号>`（同阵营 URI 下 echo）。
- **手动 Modbus 帧探测 BMS 无应答 ≠ 硬件死的铁证**：V2 reader 用 ZHONGXINKAI 私有 RS485 协议（非标准 Modbus，帧格式未知），猜帧全 0 应答正常；但「SDK V1+V2 reader 都读不到 + gv 全历史 0 次 registered」三证合一才能下硬件结论（224 机 2026-09-28 实测：9/8 起全历史 32 连败 0 成功，IMU/雷达同 hub 正常 → BMS 板/RS485 线硬件层故障，软件修不了，转硬件报修）。
- **★ 抓真实协议帧的黄金手法（2026-09-28 224/260 实战）**：不要猜帧！在健康机上 `strace -p <gv真PID> -e trace=read,write -f -y -s 128 -o /tmp/gvtrace.txt` 挂 20s，grep ttyACM0 即得真实查询帧与应答帧。三个坑：①gv 真 PID 用「遍历 pgrep -f autolife_robot_gv.main 找 /proc/PID/fd 里开着 ttyACM0 的那个」（conda run 会多出 wrapper 进程）；②strace 的 -y 显示真实路径 ttyACM0 而非符号链名 ttyBattery，grep 关键字用 ttyACM0；③机队 BMS 实测协议=ZHONGXINKAI/JBD 型：查询帧 `DD A5 03 00 FF FD 77`(7B)，应答 34B(`DD 03 00 26 ...`)，9600 波特率 1Hz。拿到帧后到故障机 serial.Serial 重放 6 次：应答=链路活，0 字节=链路死（224 实测 0 字节 → BMS 硬件死实锤）。
- **★ 脏关机取证法（自发断电判定）**：`journalctl -b -N` 末尾无 `Reached target Shutdown/systemd-shutdown` 且服务心跳日志戛然而止 = 突然断电非干净关机；配合 `last -a today`(零登录)+`pstore空`(非内核崩溃)+死前 CAN `Transfer aborted` 突发 → 供电硬件故障实锤（224: 9/16 起 15+ boot 全脏关机，今日 5 次+零登录）。排查时若 SSH 失联勿急判机器死：先 ping+nc -z 22 分辨「重启中」vs「真下电」；robssh 偶发握手超时，换 sshpass 直连 IP 可救。
- **gv-control 里 mod_battery_ 模块名**：成功日志是 `Battery reader registered on /dev/ttyBattery`，失败是 `Connection to battery reader failed` + `电池连接失败`（Hardware Initialization Report 里 mod_battery_ 段）。查历史用 `journalctl --user -u gv-control-service | grep -cE "Battery reader registered|Connection to battery reader failed"` 数次数定性质：偶尔败=根因C时序竞争，全败=硬件层。