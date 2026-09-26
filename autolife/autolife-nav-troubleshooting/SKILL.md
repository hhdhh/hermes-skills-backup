---
name: autolife-nav-troubleshooting
description: Use when 机器人能建图但导航不起、app 导航点了没反应、nav2 lifecycle_manager 卡...
metadata:
  triggers:
    - "能建图不能导航"
    - "导航卡死"
    - "nav2"
    - "participant index"
    - "导航不起"
---

# AutoLife 导航故障排查（能建图不能导航 / 导航卡死）

> 完整描述：AutoLife S1 机器人导航故障排查（能建图不能导航 / 导航卡死 / nav2 进程崩）。Use when 机器人能建图但导航不起、app 导航点了没反应、nav2 lifecycle_manager 卡 Waiting、navigate_to_pose 不可用。含 DDS participant index 耗尽修复与 nav2 诊断流程。

> 姊妹技能：`autolife-robot-dds-camp-split`（DDS 阵营分裂）、`autolife-remote-repair`（ssh 检修闭环）、`autolife-find-robot`（定位）。本技能专注**导航栈（nav2）本身的故障**，与清障拆开。

## 关键认知：建图和导航是互斥的 SLAM 模式

- SLAM 处于 **Mapping(建图)** 模式 → **不会启动 nav2 导航栈**（`ps aux` 里 nav2_* 进程数是 0，这是正常的，不是故障）。
- nav2 由 SLAM 模式切到 navigating 才拉起。**要验证导航，必须先让 app 切到「导航」模式**再盯日志。
- 所以「能建图」≠ 导航服务存在；建图正常只说明 SLAM + 底盘控制链路健康。

## 首次接入诊断（机号或 IP → robssh）

```bash
cd ~/.hermes/workspace
python3 robssh.py <机号> 20 'hostname'                    # 确认身份
python3 robssh.py <机号> 30 'systemctl --user is-active gv-slam-service gv-control-service'
python3 robssh.py <机号> 30 'ps aux | grep -E "nav2_|amcl|map_server|controller_server" | grep -v grep | wc -l'
# 0 → 在建图模式或导航根本没起；>0 → nav2 起来了，看它有没有崩
```

## 判读：nav2 起来了但卡死 → 查 participant 崩溃

**症状特征日志**（`journalctl --user -u gv-slam-service --no-pager | grep -iE "participant|died|terminate|Waiting for service|failed to create domain"`）：
```
[rmw_cyclonedds_cpp]: rmw_create_node: failed to create domain, error Error
process has died [pid X, exit code -6]   # -6 = SIGABRT，节点初始化崩
terminate called after throwing an instance of 'rclcpp::exceptions::RCLError'
[lifecycle_manager_navigation] Waiting for service planner_server/get_state...  # 一直刷，等不到已死的 planner
navigate_to_pose action server not available   # bt_navigator 起不来
```

**机制（铁证在源码）**：127.0.0.1 单播域里同机跑几十个独立进程，每个 CycloneDDS 实例（进程）自动分配 1 个 participant index，上限由 `Discovery/MaxAutoParticipantIndex` 决定——**默认 9**（见 `/opt/ros/jazzy/include/CycloneDDS/dds/ddsi/ddsi_cfgelems.h` `STRING("ParticipantIndex"...)` `INT("MaxAutoParticipantIndex"...)`）。后启动的进程拿不到空闲 index → `Failed to find a free participant index for domain 0` → SIGABRT。崩溃的是 nav2 栈**最后启动**的进程（planner_server / opennav_docking / lifecycle_manager_navigation）；SLAM 节点早启动已抢到 index 所以建图正常。**跟阵营分裂（互不可见）是两码事：这是同域内进程挤爆索引。**

## 修复：调高 MaxAutoParticipantIndex

正确层级是 `<Domain>` 下的 **`<Discovery>`** 块：
```xml
<CycloneDDS><Domain><General><NetworkInterfaceAddress>127.0.0.1</NetworkInterfaceAddress></General><Discovery><MaxAutoParticipantIndex>100</MaxAutoParticipantIndex></Discovery></Domain></CycloneDDS>
```

用 systemd override（gv-slam 负责拉起 nav2，gv-control 同域也带上）：
```bash
# 每台备份原 unit
mkdir -p ~/.config/systemd/user/gv-slam-service.service.d
cat > ~/.config/systemd/user/gv-slam-service.service.d/override.conf <<EOF
[Service]
Environment="CYCLONEDDS_URI=< 上面的 URI >"
EOF
systemctl --user daemon-reload
systemctl --user show gv-slam-service -p Environment | tr ' ' '\n' | grep CYCLONEDDS   # 校验合并
systemctl --user restart gv-slam-service gv-control-service
```

## 坑（真踩过）

1. **`ParticipantIndex` 是 `<Discovery>` 下的元素，不是 `<General>` 的**。写 `<General><ParticipantIndex>...` 会被 rmw 报 `ParticipantIndex: unknown element`，且 gv-slam 直接 crash loop 起不来——比原故障更糟。改前先验 URI。
2. **验 URI 不重启服务**：独立 shell `export CYCLONEDDS_URI=<新URI>; source /opt/ros/jazzy/setup.bash; conda activate robot_env; ros2 node list`，无 unknown element / 崩溃才算合法。
3. **`auto` ≠ 免疫**：`ParticipantIndex auto` 只是自动挑 index，一样受 `MaxAutoParticipantIndex` 上限约束；进程多了照样撞。要调高上限，不是指望 auto 自动疏散。默认上限只有 9。
4. amcl 日志 `Failed to transform initial pose in time` 不一定是 TF 错——DDS 邻居未就绪/participant 崩时也会刷，先排除崩溃再说。
5. `systemctl is-active` 在 `Restart=always` crash loop 里可能显示 active（正在快速重拉），别被它骗，看稳定进程 ELAPSED 和日志 exit-code FAILURE。
6. `systemd-analyze verify` 只接受完整 unit 名，对 override 片段报 Invalid argument 是正常，别当语法错误；`daemon-reload` 成功才算合并有效。
7. 改了 URI 后重启 gv-slam，SSH 可能瞬时断（网络接口刷新），等一下重连即可，不是机器挂了。

## 验证

切回「导航」模式后重启拉起 nav2，盯：
- nav2 进程数 >0 且不再出现 `process has died` / `failed to create domain`
- `lifecycle_manager_navigation` 不再刷 `Waiting for service planner_server/get_state...`（planner_server 活着才有这个服务）
- `journalctl` 出现 `Managed nodes are active`。
