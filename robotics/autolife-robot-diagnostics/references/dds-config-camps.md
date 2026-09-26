# CycloneDDS 阵营分裂（两套模板）

机器人上常见两套 CYCLONEDDS_URI 并存，互不可见。ROS_DOMAIN_ID 一致也没用——分裂在 DDS URI 层，不在 domain 层。

## 组播阵营（底盘驱动 gv-control / gv-slam 用，修复目标模板）

```
Environment="CYCLONEDDS_URI=<CycloneDDS><Domain Id=\"any\"><General><Interfaces><NetworkInterface name=\"lo\" multicast=\"true\"/></Interfaces><AllowMulticast>true</AllowMulticast><EnableMulticastLoopback>true</EnableMulticastLoopback></General><Discovery><ParticipantIndex>none</ParticipantIndex></Discovery></Domain></CycloneDDS>"
```

要点：`Interfaces/NetworkInterface name="lo" multicast="true"`（新写法）+ 显式 AllowMulticast + 组播回环 + ParticipantIndex=none（不限参与者数）。实测该配置能同时看到两个阵营，不会丢单播阵营的现有连接。

## 废弃单播阵营（老应用层服务常见，会静默禁组播）

```
Environment="CYCLONEDDS_URI=<CycloneDDS><Domain><General><NetworkInterfaceAddress>127.0.0.1</NetworkInterfaceAddress></General><Discovery><ParticipantIndex>auto</ParticipantIndex><MaxAutoParticipantIndex>255</MaxAutoParticipantIndex></Discovery></Domain></CycloneDDS>"
```

## 为什么分裂致命

- `NetworkInterfaceAddress` 是废弃元素；CycloneDDS 解析后检测 lo 不支持组播 → 日志一行 `disabling multicast`，静默降级。
- 单播阵营内部勉强互通，但与组播阵营互相发现不了 → 跨阵营话题全断（电池/IMU/雷达/robot_state 一起断，不止一个话题）。
- 症状侧：消费该阵营话题的前端拿不到数据，卡在硬编码默认值（如电量恒 100%）。

## 修复步骤

1. `cp <unit> <unit>.bak-<时间戳>`
2. 替换 CYCLONEDDS_URI 行为组播模板（XML 内引号写 `\"`）
3. `systemctl --user daemon-reload && systemctl --user restart <unit>`
4. 验证：journal 里 multicast 警告消失 + 新进程 `/proc/PID/environ` 里 URI 已更新 + WebSocket 收到真实数据

## 测试某阵营能否收到某话题

```bash
export ROS_DOMAIN_ID=0 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI='<对应阵营的 XML>'
source /opt/ros/jazzy/setup.bash
timeout 12 ros2 topic echo --once /topic_gv_battery_0_<ROBOT_ID>
```

对称测试：发布方 URI 能收到、消费方 URI 收不到 → 病在消费方配置；两边都收不到 → 病在发布方驱动/硬件。
