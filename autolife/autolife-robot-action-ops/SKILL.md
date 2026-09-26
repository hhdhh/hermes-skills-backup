---
name: autolife-robot-action-ops
description: Use when 管理员要求加动作/删动作/改迎宾动作/让 AI 对话做动作/同步动作库。
---


# AutoLife 机器人动作库管理

> 完整描述："AutoLife 机器人动作库管理：添加/删除动作、AI 对话触发链路、迎宾序列编排、跨机同步。Use when 管理员要求加动作/删动作/改迎宾动作/让 AI 对话做动作/同步动作库。"

> 管理员偏好：新动作必须先出**三视图预览图（正面/侧面/俯视）**发管理员确认，回「上」才部署真机；会自碰撞的动作拆成多个子动作加安全过渡姿态；复位沿执行路径逐帧倒序退回（原路返回），不直接跳回零位。

## 核心文件（机器人上，robot_env 下 site-packages）

| 文件 | 作用 |
|------|------|
| `autolife_robot_arm/robot_action.json` | 动作库本体（30+ 动作，关键帧或 pkl 引用）|
| `autolife_robot_arm/action_pkls/*.pkl` | pkl 录制动作文件（回放型）|
| `autolife_robot_vision/robot_tools/control_robot_action.py` | AI 可调动作 enum（改 3 处：enum 列表 / enumDescriptions 中文说明 / run() 里 valid_actions）|
| `autolife_robot_vision/robot_tools/__init__.py` | ENABLED_TOOLS 工具开关 |
| `autolife_robot_vision/assets/prompt/prompt.txt` | 「动作调用规则」段触发词 |
| `autolife_robot_vision/face_detection.json` | 迎宾动作轮播序列（slideshow_mode）|
| `autolife_robot_vision/settings.toml` | realtime_api_provider 通道 |
| `autolife_robot_vision/configs/robot_v2_2.json` | audio.qwen_native_fc.realtime.tool_call_enabled 总开关 |

## 关键帧格式

```json
"动作名": [
  {"type": "move", "right_arm": [7 个度数], "duration": 1.5},
  {"type": "wait", "time": 2.0},
  {"type": "reset", "duration": 1.0}
]
```
- 手臂 7 值 = [肩内旋, 肩外展, 上臂, 肘, 前臂, 腕上, 腕下]（度）
- home 位：右臂 `[-20,0,0,-110,0,0,0]`，左臂镜像 `[20,0,0,110,0,0,0]`
- 灵巧手 6 值 0-1000（开合力度）
- 肘限位**单向**：左肘 [0,149°]，右肘 [-149°,0]——左右臂常需不同关节路径达到同一姿态，不要强制参数镜像

## AI 对话动作触发链路（三件套，缺一不可）

1. `settings.toml`：`realtime_api_provider = "qwen_native_fc"`（普通 qwen 模式 Realtime API 不发 function_call，文字检测器只认时间/搜索类触发词、无动作映射）
2. `configs/robot_v2_2.json`：`audio.qwen_native_fc.realtime.tool_call_enabled = true`（藏三层嵌套，默认 false；不开则日志一句 `Native FC tool calling disabled by config` 且一切白配）
3. `control_robot_action.py` enum 注册 + prompt 触发词（"说挥挥手→wave"）

验证链（journalctl -u vision-service）：`Qwen function call: ...` → `Qwen tool executed: 成功发送动作：X`；arm 侧：`Executing action: X`。

## 标准部署流程（加/改动作）

1. 设计关键帧 → 本地仿真安全验证（pybullet 仿真流程见姊妹技能 `autolife/autolife-robot-action-design/SKILL.md`，URDF 在 ~/robot-sim/）
2. 三视图预览图发管理员 → 等确认「上」
3. 真机：robot_action.json 三重备份 → 写入 → md5 校验
4. 同步改 enum（3 处）+ py_compile 语法校验 + prompt 触发词
5. 重启：`arm-control-service`（加载动作库）+ `vision-service` → sleep 3 → `face-detection-service`（联动硬规范：动 vision 必联动 face）
6. 四服务 is-active 终验

## 删除动作

从四处清：robot_action.json 定义、enum（3 处）、prompt 触发词、face_detection.json（若迎宾引用了它）。全部三重备份先行。

## 迎宾序列（face_detection.json）

`action[0].slideshow_mode` 是轮播列表，每项 = play 动作 + wait 秒数。改后重启 face-detection-service。示例：left_wave → salut → bow_salute 轮播间隔 10s。

## 跨机同步动作

- pkl 动作 = 复制 action_pkls/*.pkl 文件 + robot_action.json 条目；关键帧动作 = 只拷 json 条目
- **先验证源机 pkl 文件真实存在**：json 条目可能是僵尸（有注册无文件），拷过去播放必报错
- 精录版 pkl（6-7MB）与普通版（2MB）同名不同质，同步时整组拷避免混搭

## 端到端动作验证（S2/v2_2）
- 真实动作话题：`/topic_arm_robot_action_0_<机号>`（8 publishers，arm 侧 node_robot_action_service_0_<机号> 消费）；`/robot_action_0_<机号>` 是死话题（0 publisher），别发错。nav2 的 `_action/feedback` 话题是 action-server 元话题，不是机器人动作，枚举时排除 `_action`。
- 测试脚本必须与服务同 DDS 阵营，否则话题列表为空：`RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` + `ROS_DOMAIN_ID=0` + `CYCLONEDDS_URI` 指向 127.0.0.1（与服务 unit 一致）。缺 RMW_IMPLEMENTATION 时脚本走默认 fastrtps，互相不可见（症状=只枚举到 /parameter_events+/rosout）。
- 成功标志：arm-control 日志 `Executing action: <名字>`。

## 已知坑

1. **pkl 动作播放崩溃**：回放异常 + rclpy `ValueError: Logger severity cannot be changed between calls` 连锁杀动作线程，手臂僵住。同文件其他 pkl 可能正常——个案处理，治法是把该动作重定义为关键帧。idle 系列通常稳定。
2. **重启 arm-control 不会自动回位**：它只重置控制状态；回 home 要走复位通道（`/control_reset_<domain>_<robot_id>` 话题，或触发 arm-auto-reset unit）。
3. **开机自愈**：开机四服务抢占 USB/CAN 总线可致全身 heartbeat lost（复位/动作全部失效但 USB 层正常）——重启 arm-control 单服务即可恢复握手；开机错峰方案见 skill: autolife-boot-auto-reset。
4. **低电量做大幅动作可能触发保护**：动作不执行时先查 battery percentage。
5. **`robot/status` 的 communication_lost 是判断电机通信的第一现场**（9001 端口 `curl http://127.0.0.1:9001/robot/status`）。
6. **普通 qwen 模式的 `<tool_call>` 文本通道是另一套可用方案**（部分机器如 316 在用）：prompt 附 `<tools>` XML 块 + vision 的 `_handle_text_tool_calls` 解析文本标签——与 native_fc 二选一，不要混配（混配会双触发或抑制语音）。若一台机器动作突然不响应，先查 `settings.toml` 的 provider 是哪种模式再对症。
7. **prompt 里教动作输出格式时**：给触发词映射即可，不要教模型自创标签格式（如 `<action>wave</action>`）——解析器只认 native_fc 的事件或 `<tool_call>` 官方格式，自创格式会被静默丢弃且日志只显 `tool_detected=False`。
8. **native FC 模式调动作冒英文**（2026-09-20 修于 321）：native FC 传不了 `pre_execute_message`，`base_tool.py` 兜底调 `ai_mgr.get_default_tool_wait_message()`（藏在编译 .so 里）返回硬编码英文 "One moment, I will check that for you." → 中文对话中英夹杂。修法：在 `robot_tools/base_tool.py` 的 `pre_execute()` 里，tool_name==control_robot_action 或 arguments 含 action_name 且无显式 pre_execute_message 时直接 return（动作瞬时完成+模型必配解说，占位话术多余）；显式 pre_execute_message 与非动作工具（搜索类）行为保持不变。日志关键词：`Played tool pre-execute speech: One moment`。**v2 升级（同日）**：只拦动作不够——问时间调 get_current_time 也冒 "One moment, I will check the time"。改为：无显式 pre_execute_message 一律不播（静默优于英文填充）；工具都秒回，模型自己解说结果，兜底英文彻底废弃。


## 相关技能
- `autolife-robot-prompt-ops`：prompt 修改规范与备份流程
- `autolife-boot-auto-reset`：开机复位 v2 自愈版详情（含"9001 早期 comm=false 假象"与四服务 CAN 竞争细节）
- `autolife-remote-repair` / `autolife-doctor-operations`：SSH 与机队诊断

> 注：prompt-ops 与 boot-auto-reset 两个技能为用户自有（curator 不可写），若发现与本技能冲突以实机现状为准。
