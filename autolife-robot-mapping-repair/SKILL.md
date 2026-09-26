---
name: autolife-robot-mapping-repair
description: Use when a robot '建图不行' / map is blank / map won't build...
metadata:
  triggers:
    - "建图不行"
    - "地图空白"
    - "地图叠不出来"
    - "slam_toolbox Message Filter dropping"
    - "map is blank"
    - "robot can't build map"
---

# AutoLife 机器人 SLAM/建图故障修复（对照已知良机）

> 完整描述：Diagnose and fix AutoLife robot SLAM/建图 failures. Use when a robot '建图不行' / map is blank / map won't build / slam_toolbox floods 'Message Filter dropping ... queue is full'. Compare against a known-good sibling of the same model and revert to its clean config.

## 核心讲法
`slam` 疯狂刷 `Message Filter dropping message: frame 'X' ... queue is full` **不代表没扫描数据，也不代表车没动**。它表示：scan 数据到了，但 slam_toolbox 无法把 scan 变换到地图系 → 它等一个匹配时间戳的 TF → 队列塞满丢帧 → 地图空白。**问题在 TF 帧/时间戳链，不在传感器。**

最有效的诊断法是**对照同型号的已知良机**：diff 两台机器的 `slam_toolbox_sync.yaml`（odom_frame / base_frame / scan_topic）和 odom 链路，差异就是根因。

## 诊断流程（按序）

1. **确认症状在 slam 层**：
   ```bash
   journalctl --user -u gv-slam-service --no-pager --since "30 sec ago" | grep -c "Message Filter dropping"
   ```
   数量持续增长 = 帧被丢，进第 2 步。

2. **看 slam 配置的 TF 帧**：
   ```bash
   grep -iE "odom_frame|base_frame|scan_topic|mode:" <site-packages>/autolife_robot_gv/ros_ws/slam_toolbox_sync.yaml
   ```
   基线（原生）应为 `odom_frame: odom`。若被改成非原生帧（如 `odom_frame: odom_zero`），就是 hack 帧导致 TF 时间戳错配。

3. **对照已知良机（同型号）**：diff 两台的 `slam_toolbox_sync.yaml` + 对比 odom 链路（良机应无自造 odom 中转节点）。找到 320↔321 这类差异即锁定根因。

4. **若是 `odom_zero` hack 帧 → 回退到原生 odom**（见下）。

## 修复：回退到原生 odom（已真机验证）

```bash
# 1. 备份 + md5
cp <yaml> <yaml>.bak.$(date +%Y%m%d) && md5sum <yaml>
# 2. 改回原生帧
python3 -c "p='<yaml>'; t=open(p,encoding='utf-8').read();\
 n=t.replace('odom_frame: odom_zero','odom_frame: odom');\
 open(p,'w',encoding='utf-8').write(n); print('changed',n!=t)"
# 3. 停用（不删）hack 服务，可回滚
autolife 机上：systemctl --user disable odom-zero.service; systemctl --user stop odom-zero.service
# 4. 重启建图让新帧生效
autolife 机上：systemctl --user restart gv-slam-service
```

**验证**：重启后 30 秒内 `grep -c "Message Filter dropping"` 应归 0；`grep -c "Transform failure"` 也应归 0。4 个核心服务（gv-slam / gv-control / arm-control / pc2-front-scan）全 active。

**回滚**：`cp <yaml>.bak.* <yaml>` + `systemctl --user enable/start odom-zero.service` + restart gv-slam。

## 底盘 odom 残留偏置（连带修复）
若底盘 odom→base_link 僵在某个固定残留值（odom_zero 工具残留日志每秒都播同一个数），先清掉底盘里程计再改配置：**重启 `arm-control-service`**（内含 `gv_task_control` 节点，启动时走 `robot_gv_<id>/reset_odom` → 日志 `Wheel odometry reset to zero`）。`arm-control-service` 是 Guarded 高危（连带机械臂/电机重连），动手前必须跟主人确认现场安全。

## 坑（真机踩过）

1. **特例密码不是 ubuntu**：`robssh.py` 全机队写死 `${ROBOT_CREDS}`，但个别机（如 320）是特殊密码。远程连上用统一密码 `Authentication failed` 时，查记忆/过往记录找该机特例密码，用能传密码的 wrapper（如循环试密码的临时脚本）连。

2. **NetBird 注册名错位 + 死记录**：同一机号多出现 NetBird 记录（如 `autolife-robot-320` 和 `autolife-robot-320-154-122` 两条），其中一条可能是过期死 IP。**先 ping 各条，用能通的那条**；robssh 的 `nb 320` 可能命中死记录。连上仍先 `hostname` 验明正身。

3. **外部 ros2 CLI 进不了机器人的 DDS 域**：在机器人机上跑 `ros2 topic hz/info` 报 `Failed to find a free participant index` / `Failed to fini rosout` —— 机器人的 DDS participant 已占满、且服务多绑 127.0.0.1 隔离。**别依赖 ad-hoc ros2 CLI 探数**，改成看已运行服务的 `journalctl`（slam 进程自己的日志就是探测器）。

4. **pc2_front_scan bridge 空转**：`mod_lidar_3d_mid` + pc2 桥把 3D 中置投影成 front scan。若输入 PointCloud2 topic 没有 publisher，桥进程 CPU 极低（≈1%）且只打启动日志不发数。判断桥是否空转看**进程 CPU/日志增量**，别用 ros2 topic（进不了域）。端口通（TCP OPEN）≠ 有数据流。

5. **odom_zero hack 的失败模式**：加中转改 `odom_frame` 是为了清底盘 odom 残留偏置，但它用 `get_clock().now()` 时间戳广播、会跟 scan 帧时间戳错配，正是 slam queue-full 丢帧的主因。默认保持原生 `odom`；只有确需清偏置时才考虑，且要意识到它带这个病。

## 姊妹技能
- `autolife-remote-repair`：SSH 直连检修总纲（robssh 命令、权限分级、写文件标准姿势）。
- `autolife-doctor-operations`：22 项系统诊断扫描 / OTA。
- `autolife-robot-dds-camp-split`：另一类「电池恒100% / 数据僵死」根因（DDS 阵营分裂），与此技能不是同一类。
