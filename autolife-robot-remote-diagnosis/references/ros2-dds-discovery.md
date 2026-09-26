# ROS 2 / CycloneDDS 发现隔离排查（AutoLife S1）

## 现象签名

- `ros2 topic info -v` 显示 Publisher count: 0，但发布方服务 systemd 状态 running
- 相关进程日志或手动跑 ros2 CLI 出现：`selected interface "lo" is not multicast-capable: disabling multicast`
- 前端字段永远停在写死的初始值（如电池 100%）

## 机制

机器人上两套 `CYCLONEDDS_URI` 并存，DDS 图谱完全隔离、话题互不可见：

| 阵营 | 配置要点 | 服务（402 实测分布） |
|---|---|---|
| A 组播回环 | `<Interfaces><NetworkInterface name="lo" multicast="true"/></Interfaces>` + `AllowMulticast>true` + `EnableMulticastLoopback>true` + `ParticipantIndex>none` | gv-control、gv-slam（**底盘话题数据源**） |
| B 废弃单播 | `<General><NetworkInterfaceAddress>127.0.0.1</NetworkInterfaceAddress></General>` + `ParticipantIndex>auto` | logo-backend(kiosk)、vision、flow、arm、face-detection、dashboard-backend、rosbag-record、ai-grasp |

B 写法的 `NetworkInterfaceAddress` 是废弃元素，触发 lo 上禁组播，只能单播发现；A 阵营走组播回环——两边互相看不见。B 阵营内部彼此能通，所以 vision/kiosk 之间的正常功能不报错，只有跨阵营数据（底盘→前端）悄悄断流。

## 阵营扫描命令

```bash
cd ~/.config/systemd/user
grep -l "EnableMulticastLoopback" *.service   # A 阵营
grep -l "NetworkInterfaceAddress" *.service   # B 阵营
```

## 确认隔离方向

用 A 套配置 `ros2 topic echo` 能收到数据、用 B 套收不到，且默认 shell 环境通常也看不到 A 阵营发布者——即证实发布方在 A、消费方在 B。

## 修复（改前必须主人确认）

把 B 阵营服务的 `Environment="CYCLONEDDS_URI=..."` 换成 A 阵营写法。CLI 实测 A 配置能同时看到两个阵营的节点，不会切断 B 阵营现有互联；但 restart 后服务行为未在本机验证过，改完盯着日志确认：

```ini
Environment="CYCLONEDDS_URI=<CycloneDDS><Domain Id=\"any\"><General><Interfaces><NetworkInterface name=\"lo\" multicast=\"true\"/></Interfaces><AllowMulticast>true</AllowMulticast><EnableMulticastLoopback>true</EnableMulticastLoopback></General><Discovery><ParticipantIndex>none</ParticipantIndex></Discovery></Domain></CycloneDDS>"
```

```bash
systemctl --user daemon-reload && systemctl --user restart <service>
```

## 注意

- 一次只改与症状相关的服务（如只改 logo-backend 修电量显示），其余 B 阵营服务有跨阵营需求时再逐个对齐
- 改 unit 前备份原文件；重启会让对应前端黑几秒
- 修完用 `ros2 topic echo --once` + 前端实际显示双重验证
