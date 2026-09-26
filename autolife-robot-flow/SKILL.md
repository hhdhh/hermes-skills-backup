---
name: autolife-robot-flow
version: 0.1.0
description: Use when 主人要做机器人巡游讲解、点位流程编排、flow-service 故障、新建/修改流程 XML 时。
---

# AutoLife S1 机器人流程编排（BehaviorTree · XML）

> 完整描述：AutoLife S1 robot BehaviorTree 流程编排系统——巡游讲解、迎宾、识别、抓取等场景的 XML 流程文件位置、提交流程、与 ROS 节点（导航/机械臂/TTS）的连接方式。Use when 主人要做机器人巡游讲解、点位流程编排、flow-service 故障、新建/修改流程 XML 时。

> 来源：2026-09-16 在 294 机实测 — `~/Documents/AutolifeRobotFlow` 源码与 `flow/*.xml` 流程定义文件存在，节点 class 在源码里可定位。本技能只记录**已验证存在的事实**和提交流程；具体场景流程（巡游讲解/迎宾/抓取）的 XML 模板**还没在生产环境跑通过**，需要在目标机器人上验证。

## 真相比猜测更重要（铁律）

不要按"AutoLife 一般怎么做"假设：
- ❌ 流程文件是 YAML / Python DSL — 实际是 **BehaviorTree.CPP 风格 XML**（`<BehaviorTree ID="MainTree">`、`<Sequence>`、`<Parallel>`、`<MoveArmToPose>` 等）
- ❌ `dataset/` 存的是"点位/路线" — 实际是**物体识别训练数据**（每个文件夹是一个物体的 RGB 图 + mask + 3D 模型）
- ❌ 机器人开机就有 SLAM 地图（`map.pgm`）— 实测 294 机 `/home/ubuntu /tmp /opt` 全局搜不到 `.pgm` 文件，**gv-control 当前不带 ROS nav2 地图**。`NavigateXYYawPose` 节点能不能走、要不要先建图，看 gv-control 内部定位方案

要拿准事实，直接上机器人查：
```bash
# 流程文件位置
ls ~/Documents/AutolifeRobotFlow/flow/
cat ~/.config/systemd/user/flow-service.service   # 看它跑哪个 XML

# 导航节点有没有
grep -rEn "class NavigateXYYawPose|class NavigatingToPose|class NavigatingPath" \
  ~/Documents/AutolifeRobotFlow/src/autolife_robot_flow/*.py

# 地图有没有
find /home/ubuntu /tmp /opt -maxdepth 6 \( -name "map.pgm" -o -name "map.yaml" \) 2>/dev/null
```

## 流程文件位置（已验证）

`~/Documents/AutolifeRobotFlow/flow/*.xml` 是**所有 BehaviorTree 流程定义**的存放点。已观察到（294 机）：

| 类别 | 例子 |
|---|---|
| 实际跑的流程 | `capsule.xml` / `kuku_ice_cream.xml` / `mp.xml` / `main.xml` / `initdb.xml` / `subtrees.xml` |
| 单点测试 | `ai_nodes_smoke.xml` / `mp_single.xml` / `arm_trajectory_test.xml` / `spin_wave.xml` / `lid_icecream_detection.xml` / `grasp_only.xml` |
| 示例模板（带 `.example` 后缀） | `delivery.xml.example` / `explain_long.xml.example` / `coffee.xml.example` / `ice_cream.xml.example` / `kuku_*.xml.example` / `capsule_ts.xml.example` / `beer.xml.example` / `langham.xml.example` |
| 子目录 | `flow/capsule/`、`flow/cupsule/`（嵌套流程） |

新建巡游讲解流程**应该从某个 `.xml.example` 改**（尤其是 `delivery.xml.example` / `explain_long.xml.example`），而不是从零写。

## 流程提交（已验证）

入口：`~/Documents/AutolifeRobotFlow/example/call_flow_once.py` — **提交一次流程、等结果退出**，不抢占已有任务。

```bash
python3 ~/Documents/AutolifeRobotFlow/example/call_flow_once.py \
  --xml ~/Documents/AutolifeRobotFlow/flow/<你的流程.xml> \
  --action /action_flow_xml_0_0          # 须与 flow-service topic_node_id 一致
```

默认 `--xml` 指向 `flow/ai_nodes_smoke.xml`（开发自测用，不是生产流程）。

生产场景下，**真正驱动流程的是 `flow-service`**（systemd user unit `flow-service.service`）。流程入口 XML 通常在 unit 的 `ExecStart` 参数里指定：
```bash
cat ~/.config/systemd/user/flow-service.service    # 看生产流程挂在哪个 XML
```

## 已发现的导航/底盘节点（已验证 class 名 + 源文件位置）

| 节点（在 XML 里用的名字） | 源码位置 | 用途 |
|---|---|---|
| `<NavigateXYYawPose>` | `~/Documents/AutolifeRobotFlow/src/autolife_robot_flow/ai_nodes.py:3459` | **直接给 (x, y, yaw) 走到目标** — 巡游讲解的主要节点 |
| `<NavigatingToPose>` | `~/Documents/AutolifeRobotFlow/src/autolife_robot_flow/base_nodes.py:652` | 同类导航节点，参数可能不同 |
| `<NavigatingPath>` | `base_nodes.py:960` | **走一串路径点** — 高级巡游（弯路线 / 多点串联） |
| `<WaitNavigateComplete>` | `base_nodes.py:749` | **等导航到位** — 到了再 TTS 讲，否则边走边讲会听不清 |
| `<TransformObjectNavigatePose>` | `ai_nodes.py:3397` | 先识别物体再导航过去（讲解场景里"找到柜子再讲"） |

⚠️ 节点在 XML 里的**真实参数名 / 必填字段 / 坐标系单位** — 这部分没读到源码具体行，需要在目标机器人上 `grep -nA 30 "class NavigateXYYawPose"` 或读源码 def `execute()` 函数确认。**不要拍脑袋编参数**。

## 已发现的 TTS / 动作节点（XML 里能用）

| 节点 | 用途 |
|---|---|
| `<MoveWaistToAngles>` | 腰部转角（pitch/yaw/duration） |
| `<MoveArmToPose>` | 单臂姿态到位（hand_side + pos + rpy_deg + duration） |
| `<Print>` | 日志/调试输出 |
| `<Wait duration="N">` | 等 N 秒 |
| `<Sequence>` / `<Parallel policy="...">` | 串行/并行组合 |

`<Speak>` / `<TTS>` / `<Say>` — 还没在源码里搜到确切 class 名，要做 TTS 播报需在目标机器人上 `grep -rEn "class.*Speak|class.*TTS|class.*Say" ~/Documents/AutolifeRobotFlow/src/` 确认。

## 巡游讲解"场景调研"决策树

主人要做巡游讲解 → **先调研，不要直接动手写 XML**：

```
1. 看目标机的 flow-service 现在跑什么
   cat ~/.config/systemd/user/flow-service.service
   # 看 ExecStart / --flow-file 指向哪个 XML

2. 看现有流程定义文件列表
   ls ~/Documents/AutolifeRobotFlow/flow/
   # 找 .example 模板（不要从零写）

3. 看 gv-control 当前状态（决定能不能走底盘）
   systemctl --user is-active gv-control-service
   # inactive → 机器人没装/没启用底盘，巡游做不动

4. 看 SLAM 地图有没有
   find / -maxdepth 6 \( -name "map.pgm" -o -name "map.yaml" \) 2>/dev/null | head
   # 0 结果 → 当前没有 ROS nav2 地图，要先 SLAM 建图才能用基于地图的导航

5. 验证导航节点 class 在源码里存在
   grep -rEn "class NavigateXYYawPose" ~/Documents/AutolifeRobotFlow/src/

6. 读懂现成 XML 示例节点参数
   head -100 ~/Documents/AutolifeRobotFlow/flow/<选定的 example>.xml.example
   # 抄节点名 + 参数格式，不要瞎猜
```

## 已知坑

- **`dataset/` 不是点位** — 是物体识别数据集（每个文件夹一个物体的 ref/ + .obj 模型）。想找点位 / 巡游路线应该看 `flow/` 和 `<autolife_robot_arm>/scripts/action/`（机械臂动作库 `.pkl` 在那）
- **导航节点参数容易拍错** — `NavigateXYYawPose` 真实参数名 / 必填字段要读源码 `execute()`，**不要按 ROS nav2 通用习惯猜**（框架是 BehaviorTree，不是 nav2 action client）
- **没有 SLAM 地图时 `<NavigateXYYawPose>` 能不能用，取决于 gv-control 内部定位**（里程计 / 视觉 SLAM / 都不是）。如果它内部需要 `/map` topic，没地图就 Observable 起不来
- **TTS 节点 class 名还没确认** — `<Speak>` 是猜测。**先 grep 源码确认再写 XML**，否则服务端报 "unknown node"
- **`flow/` 里很多 `.example` 是 2.x 时代版本** — 直接抄可能跟当前节点定义对不上。抄之前先用 grep 验一遍 class 还在不在

## 操作约定

- 修改/新建 XML 前先 `cp <原文件> <原文件>.bak.<时间戳>` 备份（保 90 天，跟随 autolife-doctor-operations 备份规则）
- 改了 XML 必须 `systemctl --user daemon-reload && systemctl --user restart flow-service.service`
- **不要盲目 trust `.example` 文件** — 它们可能对应被废弃的节点；先 grep 源码确认节点还在
- 提交一次看效果用 `example/call_flow_once.py`；正式运行靠 `flow-service.service`