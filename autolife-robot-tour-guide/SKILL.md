---
name: autolife-robot-tour-guide
version: 0.1.0
description: Use when 用户要做展厅/园区巡游讲解、点位讲解、循环导览。
---

# AutoLife S1 巡游讲解（FAE 落地指南）

> 完整描述：AutoLife S1 巡游讲解（B 场景）落地方案选择与决策树。当用户提"机器人做播报导览/巡游讲解/路线讲解/点位讲解"时进入本技能。优先用现成 flow-service（方案 1），不行再写独立 ROS2/TWS 脚本（方案 2）。Use when 用户要做展厅/园区巡游讲解、点位讲解、循环导览。

## 决策树

```
用户要做巡游讲解 →
  flow-service 能起来吗？
    ├─ yes → 走【方案 1：flow-service 编排】（最稳、不写代码）
    └─ no  → 走【方案 2：写 patrol.py 独立脚本】+ gv-control nav + kiosk TTS
```

## 方案 1：flow-service（推荐）

### 流程定义（YAML 模板）

```yaml
name: <任务名>
loop: true                                          # 循环 / 单次
points:
  - id: <点位 id>
    pose: { x: <m>, y: <m>, theta: <rad> }          # SLAM 地图坐标
    arrive_threshold: 0.3                            # 到达判定（米）
    actions:
      - type: speak
        text: "<TTS 文本>"
      - type: gesture
        action: <动作库动作名>                       # autolife_robot_arm .pkl 名
        duration: 2.0
    wait_after: 8                                    # 讲完+动作后停 N 秒再走
```

Python DSL 版本（更灵活）：

```python
from autolife_robot_flow import Flow, Point, Action
flow = Flow(name="<任务名>", loop=True)
flow.add(Point(pose=(x, y, theta),
               actions=[Action.speak("<文本>"), Action.gesture("<动作>")],
               wait_after=8))
flow.run()
```

### 落地 3 步

1. **写流程文件**：`~/Documents/autolife-flow/conf/tours/<任务>.yaml`（实际路径以机器人代码为准）
2. **改 flow-service unit 加载流程**：编辑 `~/.config/systemd/user/flow-service.service` 的 `ExecStart` 加 `--flow-file <路径>`
3. **生效**：`systemctl --user daemon-reload && systemctl --user start flow-service`

### 验证命令
```bash
journalctl --user -u flow-service -f          # 看实时日志
ros2 topic info /<flow-status> 2>/dev/null    # 流程状态 topic
systemctl --user status gv-control-service    # 底盘导航服务必须 active
```

## 方案 2：独立脚本（flow-service 起不来时）

脚本结构：

```python
import asyncio, time, json
import rclpy
from rclpy.node import Node
# from autolife_gv_control.srv import NavigateTo  # 实际接口以代码为准
# import websockets

POINTS = [
    (0.0, 0.0, "大家好，欢迎光临..."),
    (3.5, 0.0, "这里是产品展示区..."),
    # ...
]

async def patrol():
    for x, y, text in POINTS:
        await navigate_to(x, y)            # 调 gv-control 服务
        await speak(text)                   # 推文本到 kiosk WS（TTS）
        await asyncio.sleep(8)              # 等讲完
```

## 前置铁律（不满足就先做这些）

1. **gv-control-service 必须能起 + 机器人有 SLAM map** —— 没建图先 SLAM（让机器人在场地走一圈）
2. **点位坐标必须从 RViz 拾点 / 或已知** —— 不能瞎猜
3. **TTS 已配置** —— 查 `~/Documents/rust-web-server/conf/config.yaml` 或 prompt 相关配置（见 autolife-robot-prompt-ops）

## 排查坑

- **DDS 阵营分裂**：flow-service 与 gv-control 的 `CYCLONEDDS_URI` 必须一致（详见 autolife-robot-dds-camp-split），否则底盘不响应
- **TTS 不发声**：检查 kiosk WebSocket 是否能连、TTS provider 是否配（qwen/openai/kokoro）
- **动作库找不到动作**：机械臂动作文件是 `.pkl` 在 `~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_arm/scripts/action/`

## 部署后沉淀

- 修完写飞书文档到「机器人故障/案例记录库」文件夹 `M7CrfNeZrl26eAdbJkrcCEREnCe`，署名"运营助手"（流程见 autolife-doctor-operations "故障记录闭环"段）
- 新点位/巡游路线沉淀到本技能案例库