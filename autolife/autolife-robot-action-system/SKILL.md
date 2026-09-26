---
name: autolife-robot-action-system
version: 1.0.0
description: Use when 主人要求机器人做动作/新增动作/删除动作/AI 对话配动作/动作不执行排查/动作预览图。
metadata:
  requires:
    bins: ["ssh"]
  triggers:
    - "机器人做动作"
    - "给机器人加动作"
    - "点赞动作"
    - "AI 对话动作"
    - "动作不执行"
    - "control_robot_action"
---

# AutoLife 机器人动作系统

> 完整描述：AutoLife 机器人动作系统操作：动作库结构、AI 对话触发动作（qwen_native_fc 工具调用链）、动作创建/删除全流程、本地 pybullet 仿真安全验证、开机自愈。Use when 主人要求机器人做动作/新增动作/删除动作/AI 对话配动作/动作不执行排查/动作预览图。

> 动作本体在 `autolife_robot_arm/robot_action.json`，AI 对话经 `control_robot_action` 工具触发，播放端是 arm-control-service 里的 ROS2 节点 `node_robot_action_service_0_<机号>`。本技能管：查/改动作库、修 AI 触发链、新建/删除动作（含仿真安全验证）。

## 架构 30 秒版

```
用户语音 → vision(ai_chatbot_manager) → Qwen Realtime function call
  → control_robot_action 工具 → DDS action 消息
  → arm-control(node_robot_action_service) → 按 robot_action.json 播放关键帧
```

| 组件 | 位置 |
|---|---|
| 动作库 | `<robot_env>/lib/python3.12/site-packages/autolife_robot_arm/robot_action.json` |
| 对话工具 | `<vision>/robot_tools/control_robot_action.py`（TOOL_SCHEMA 的 enum + valid_actions 两处都要加） |
| 工具启用表 | `<vision>/robot_tools/__init__.py` 的 ENABLED_TOOLS |
| prompt 动作段 | `<vision>/assets/prompt/prompt.txt` 的「动作调用规则」节 |
| 播放节点 | arm-control-service 内（改库后须重启该服务才加载） |

## AI 触发链排障（动作不执行的分层定位）

按日志逐层验证，vision 日志是主战场：

1. **AI 调没调**：`journalctl --user -u vision-service | grep "Qwen function call"`——有 `control_robot_action, {"action_name": ...}` 才算上层通。
2. **发没发**：同日志 `Published action message: <动作名>`。
3. **arm 收没收**：`journalctl --user -u arm-control-service | grep <动作名>`。
4. **播放炸没炸**：arm 日志里动作名后跟 Python 异常栈 = 播放失败。

### 坑 1：Qwen Realtime 不支持标准 function call
普通 `realtime_api_provider = "qwen"` 模式下 Qwen Realtime API 不发 function_call 事件。系统兜底是**文字触发词检测**（`_check_qwen_transcript_tools`），但那个词表只含时间/搜索类词，**没有动作类映射**——动作请求被 AI 回复文字带过但永不执行。

**正解**：切原生 FC 通道，开关藏两层：
- settings.toml `[app_settings.ai_chatbot]`：`realtime_api_provider = "qwen_native_fc"`（此模式用 qwen3.5-omni-**plus**-realtime，比 flash 强）
- `configs/robot_v2_2.json`：`audio.qwen_native_fc.realtime.tool_call_enabled` 默认 **false**——改成 true。验证：重启 vision（联动 face）后日志不再出 `Native FC tool calling disabled by config`。

### 坑 2：pkl 型动作播放必炸
`wave/left_wave/right_wave` 等出厂是 `{"type":"pkl"}` 录制回放型。回放中抛异常（pkl 轨迹数据问题），报错又触发 rclpy 线程安全 bug `Logger severity cannot be changed between calls` → 动作线程死亡，臂不动——AI 侧日志全绿极具迷惑性。

**修法**：重定义为关键帧动作（同 bow_salute 机制），结构：
```json
"wave": [
  {"type":"move","right_arm":[30,5,0,-60,0,0,0],"duration":1.2},
  {"type":"move","right_arm":[45,10,0,-80,-20,15,0],"duration":0.6},
  {"type":"move","right_arm":[45,10,0,-80,-20,-15,0],"duration":0.6},
  {"type":"move","right_arm":[30,5,0,-60,0,0,0],"duration":0.8},
  {"type":"move","right_arm":[-20,0,0,-110,0,0,0],"duration":1.2}
]
```
关键：以 home 位收尾（安全复位），过渡帧逐级收回。改库 → 重启 arm-control。

## 新增动作标准流程

1. **拉模型**：机器人 `<sdk>/descriptions/autolife_s1/` 打包（urdfs + meshes，~45MB）拉到本地 `/home/kk/robot-sim/`。关节限位表从 URDF 读，存 `joints.json`。
2. **本地仿真验证**（pybullet，先 `pip install pybullet`，不走系统 pip 默认源用清华镜像）：
   - 加载 `urdfs/robot_v2_2.urdf`，`flags=p.URDF_USE_SELF_COLLISION`
   - 逐关键帧 resetJointState → `performCollisionDetection` → `getContactPoints`
   - **过滤假阳性**：灵巧手相邻连杆接触（`Gripper`↔`Gripper`）是机械结构本身；URDF 零位有 2 对静态重叠（颈部/腰部连接件）零位就有，与动作无关——先跑 home 姿态记 baseline，再逐帧比对增量。
   - 动作库角度是度数，URDF 是弧度——`math.radians` 转换；`right_arm` 7 值顺序 = Shoulder_Inner/Outer/UpperArm/Elbow/Forearm/Wrist_U/L。
3. **渲染预览图**（三视图规范）：正面 yaw=45 + 侧面 yaw=130 + **俯视**（主人 2026-09-19 定）。无 GPU 用 `renderer=p.ER_TINY_RENDERER`；取景先遍历各 link AABB 求总包围盒（base 的 AABB 常返回 0）；`computeProjectionMatrixFOV` 参数**位置传参**（kwarg 名大小写敏感会炸）。
4. **发图给主人确认**（飞书 post 富文本 + im/v1/images 上传，image_type=message；token 过期重取）。
5. **部署**（主人说「上」之后）：robot_action.json 三重备份 → 写入新动作 → control_robot_action.py 同步改 enum/描述/valid_actions 三处（改完 `py_compile` 验语法）→ prompt 动作规则节同步 → 重启 arm-control + vision（联动 face）。
6. **删动作**同理反向：库删键 + 工具文件清引用 + prompt 清引用，三处都 `grep -c <动作名>` 确认 0 残留，重启生效。备份保留可随时恢复。

## 动作设计安全规则（主人 2026-09-19 定）

- **危险动作拆分**：设计的关键帧轨迹若会自碰撞，拆成多个子动作、插入安全中间姿态作过渡，逐段执行完成整个动作。
- **安全复位（原路返回）**：动作结束不直接 reset 跳回零位，沿执行路径的中间姿态逐步退回，每一步过碰撞校验，最终回到初始位。
- 所有新动作末帧必须是 home 位（右臂 [-20,0,0,-110,0,0,0] / 左臂 [20,0,0,110,0,0,0]）。
- 关节角度硬校验 URDF 限位（±0.05 rad 容差），超限即拦截。

## 开机自愈（联动姊妹技能）

四服务开机同秒启动会挤崩 arm-control 的 CAN/USB 通信（全身 heartbeat lost 且不自愈），所有动作/复位失灵。修复与装机见 `autolife-boot-auto-reset`（arm-control 错峰 sleep 45 + v2 自愈复位脚本）。

## 调试速查

- 复位/动作验证后看实际关节：`curl http://127.0.0.1:9001/robot/status` 的 `joint_status`（`neck_joint_state.position` 等；`communication_lost` 数组=[True...] 表示该组电机掉线，通信问题不是动作问题）。
- 头歪不回正且 yaw 缓慢转动 = face-detection 人脸跟踪正常行为，不是故障。
- prompt 教模型的动作格式写自然语言规则即可（qwen_native_fc 模式下系统自动注册工具）；出厂 prompt 里的 `` 标签格式是厂商给文字兜底模式的，native_fc 下不需要。