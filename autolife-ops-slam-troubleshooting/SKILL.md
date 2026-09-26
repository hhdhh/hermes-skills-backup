---
name: autolife-ops-slam-troubleshooting
description: |
  Use when 建图空白/地图无形状/推着走不出图/slam_toolbox 崩溃循环//merged 无数据/nav2 failed to create domain—— 先排除 DDS 阵营再沿雷达数据流定位（merger 硬编码/机型配置差异/numpy 崩溃/参与者上限四类根因）。 v2_4/S3 无前雷达是正常配置不是故障。
metadata:
  cangjie.generated-by: cangjie-tools v2.5.0
  cangjie.capability-id: cap.autolife-ops.slam-troubleshooting
  cangjie.capability-revision: 1
  cangjie.bundle-id: bundle.autolife-feishu-corpus
  cangjie.source-title: AutoLife 飞书运维语料全集
  cangjie.tags: robot, slam, lidar, troubleshooting
---
# SLAM 建图空白排查修复

<!-- capability_id: autolife-ops.slam-troubleshooting | revision: 1 | status: active -->
<!-- 来源: 案例003 v2_4建图空白 + 320建图导航全失效 + 案例005 numpy2 崩溃循环（飞书语料） -->

## R — 原文

> 第一步排除DDS阵营分裂→第二步逐层查雷达数据流（front 0 publisher，rear 正常10Hz，mid_3d正常，/merged空）→第三步定位机型配置差异（v2_4无mod_lidar_front）→第四步确认合并器硬编码→第五步验证3D点云可替代。
> —— 《案例003 · v2_4 机型建图空白》

> 修复：在robot_env写sitecustomize.py兼容shim（出错时自动垫3维），重启gv-slam即恢复，不动包、不降级numpy。
> —— 《案例005 · numpy 2.x》

## I — 自述

建图空白的排查是"先排除已知同类病，再沿数据流找断点，再 diff 机型配置"的三段式。已知病优先排除 DDS 阵营分裂（对称测试），因为它是同症状最常见根因。然后逐层查雷达数据流：哪个 topic 空指向哪段断——front 空+rear 正常指向机型差异，/merged 空指向合并器。机型差异用 ENABLED_MODULES diff 确认，最后读源码验证硬编码假设。

v2_4/S3 机型没有前 2D 雷达，但 laser_merger 硬编码订阅 front+rear 两路，front 恒空导致 /merged 恒空，slam 收不到激光。修法 B 不动 slam/merger/服务：新增 pc2_front_scan.py 桥接节点，把 3D 中置点云按高度带投影成 2D LaserScan 发到 front topic。

另一类建图崩溃是 numpy 2.x 移除 2 维向量 np.cross 支持，gv 的 laser_line_finder.py 用 2D 调用必抛 ValueError 崩溃循环。修法是 sitecustomize.py 无侵入 shim：解释器启动时自动加载，monkey-patch np.cross 在 2D 输入时自动垫 3 维。不动包不降级。

同型机有好坏两台时（320 案例），逐项 diff 权威基线比猜测快得多：unit/yaml/参数/CYCLONEDDS_URI（含 Discovery/ParticipantIndex=auto 段——缺它时默认参与者上限 10，nav2 14+ 进程必爆）。

## A1 — 书中案例

**案例类型：书中亲历案例**（案例003 v2_4 建图空白）

- 输入/问题：v2_4 机型推着走建图，地图恒空白
- 方法执行：排除 DDS → 数据流逐层查（front 0 publisher）→ ENABLED_MODULES diff（v2_4 无 mod_lidar_front）→ 源码确认 laser_merger 硬编码 → 验证 3D 点云投影可行
- 结论：部署 pc2_front_scan 桥接节点（systemd user service），front 话题恢复供给，建图正常

**案例类型：书中亲历案例**（320 全失效）

- 输入/问题：320 建图导航全失效，slam 崩溃循环（重启 70+ 次）
- 方法执行：NRestarts 采样 → journalctl 首异常 = np.cross ValueError → sitecustomize shim 修复；随后发现 CYCLONEDDS_URI 缺 Discovery 段 → nav2 参与者爆上限 → 对照 002 补齐
- 结论：话题数 2→113，导航恢复

## A2 — 未来触发 ★

**情境：**

1. 建图模式推着走不出图 / 地图恒空白 / RViz 看不到激光轮廓
2. slam_toolbox 反复重启 / Registering sensor 却不产图
3. /merged 或 /scan 无数据但前后雷达单测正常
4. 新机型（v2_4/S3 双臂）首次建图失败
5. nav2 全家桶启动后互相看不见、failed to create domain

**语言信号：**

- "建图空白" / "地图没形状" / "推着走不出图"
- "/merged 空" / "front 没 publisher" / "slam 收不到雷达"
- "Registering sensor 不产图" / "slam_toolbox 崩溃循环"
- "failed to create domain" / "参与者上限"
- EN: "blank map" / "slam no laser input" / "laser_merger empty"

**区分：**

- ≠ autolife-dds-split：本卡 Step 1 只是用它的对称测试**排除** DDS，主战场是雷达数据流/merger/机型配置
- ≠ autolife-slam-blank-map / autolife-slam-build / autolife-slam-mapping-blank（旧技能群）：本卡是案例库全量融合版，一张卡覆盖三类根因（merger 硬编码/numpy 崩溃/参与者上限）
- ≠ autolife-robot-diagnosis：那是通用流程；本卡是 SLAM 专项的完整因果链与修法

## E — 可执行步骤

**输入契约**：机号/hostname（必填）；机型（必填：S1/v2_2/v2_4/S3——决定 ENABLED_MODULES 基线）；建图模式确认（必填）。机型未知先 `hostname` 验身。

**Step 1 排除 DDS 阵营分裂**：跑 autolife-ops-dds-split 卡的对称测试；两套 URI 都能收到 → 排除，进 Step 2
**Step 2 雷达数据流逐层查**：
```
ros2 topic hz /front_lidar/scan   # 预期10Hz；0 publisher=front断
ros2 topic hz /rear_lidar/scan
ros2 topic hz /mid_3d/points
ros2 topic hz /merged             # 空=merger没产出
```
断点定位：单路空→Step 3；全路正常但 /merged 空→Step 4；slam 崩溃循环→Step 5
**Step 3 机型配置 diff**：`systemctl --user show <gv-unit> -p ExecStart` 解析 ENABLED_MODULES；对照机型基线（v2_4/S3 无 mod_lidar_front 属正常配置，非故障）
**Step 4 merger 硬编码确认与桥接**：读 laser_merger 源码确认订阅 front+rear；v2_4/S3 → 部署 pc2_front_scan.py（3D 点云按高度带 z∈[-0.10,0.35] 投影成 2D LaserScan 发 front topic）→ systemd user service 常驻
**Step 5 numpy 崩溃循环**：journalctl 找 np.cross ValueError → robot_env 写 sitecustomize.py shim（2D 输入自动垫 3 维）→ restart gv-slam
**Step 6 参与者上限**（nav2 报 failed to create domain）：CYCLONEDDS_URI 补 Discovery 段：ParticipantIndex=auto + MaxAutoParticipantIndex=255 → 全家桶 restart
**判停点**：Step 2 全路正常且 /merged 正常但图仍空白 → 查 slam_mode/地图保存链，不在本卡范围

**输出契约**：断点层定位（话题级）+ 根因（阵营/merger/机型/numpy/参与者）+ 修复动作 + 修复前后话题数对比。

## B — 边界

- **不适用**：导航偏差/定位漂移（点位标定问题）；纯 kiosk 前端显示故障；S2 首次装机建图（走 s2-robox-wizard 全流程）
- **反场景**：v2_4/S3 没有 front 雷达是**正常配置**，不要当作故障去"修"
- **失败模式**：不先排除 DDS 就深挖 merger（同类症状白忙）；shim 写进系统 site-packages 而非 robot_env（升级丢失）；改 URI 不带 Discovery 段（给 nav2 埋雷）
- **相邻易混**：电池僵尸数据（autolife-ops-dds-split）；整机服务僵死（autolife-ops-robot-diagnosis）
