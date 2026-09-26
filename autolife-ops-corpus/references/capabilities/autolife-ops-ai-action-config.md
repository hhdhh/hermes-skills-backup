# AI 对话动作配置与新动作部署

<!-- capability_id: autolife-ops.ai-action-config | revision: 1 | status: active -->
<!-- 来源: AutoLife 机器人 AI 对话动作控制手册（飞书语料） -->

## R — 原文

> 配置1：settings.toml切qwen_native_fc（必须）；配置2：robot_v2_2.json开tool_call_enabled（藏三层嵌套默认false）；配置3：control_robot_action.py改3处enum；配置4：prompt.txt写触发词映射。
> —— 《AutoLife 机器人 AI 对话动作控制手册》

> 会自碰撞的动作→拆成多个子动作，插入安全中间姿态；结束复位→沿执行路径逐帧倒序退回（原路返回），不直接跳回零位。
> —— 同上 · 管理员要求

## I — 自述

让"说什么动作就做什么"生效是一条四件套配置链，缺一环整条链白做：①settings.toml 的 realtime_api_provider 切到 qwen_native_fc（普通 qwen 模式 Realtime API 不发 function call）②robot_v2_2.json 里藏三层嵌套的 tool_call_enabled=true（不开它配置①白做，日志只一句提示）③动作 enum 三处同步（TOOL_SCHEMA enum + enumDescriptions + run() valid_actions）④prompt.txt 写触发词映射。改完 restart vision → sleep 3 → restart face-detection（硬规范联动，少一步 face 起不来）。

新动作部署是五步：设计关键帧（right_arm 7 值，home 位 [-20,0,0,-110,0,0,0]）→ pybullet 仿真验证（关节限位+自碰撞+三视图）→ 三视图发管理员确认 → 三重备份写入 robot_action.json + md5 校验 → 重启验证日志链（Qwen function call → tool executed → arm Executing）。

安全是硬规则：会自碰撞的动作必须拆子动作插安全中间姿态；复位沿执行路径逐帧倒序退回（原路返回），直接跳零位会路径失控。肘限位单向（左肘 [0,149°] 右肘 [-149°,0]），左右臂关节路径不强制镜像。

## A1 — 书中案例

**案例类型：书中亲历案例**（321 南航空厨机 AI 动作配置，来源：动作控制手册）

- 输入/问题：321 需要语音"挥手/比心"触发实体动作
- 方法执行：四件套逐项配置——provider 切 qwen_native_fc → 开 tool_call_enabled → enum 三处加新动作 → prompt 写"挥手=wave_hand"映射 → vision+face 联动重启
- 结论：语音说"跟观众挥挥手"→ arm 日志 Executing action: wave_hand，全链生效

**案例类型：反例警示**（tool_call 坑）

- 只改了 settings.toml 没开 robot_v2_2.json 的 tool_call_enabled → AI"嘴上说挥手"但工具不调用 → journalctl 搜 "Native FC tool calling disabled by config" 实锤

## A2 — 未来触发 ★

**情境：**

1. 新机器人要配"说话带动作"（AI 对话触发实体动作）
2. 已配好的机器人 AI 光说不动（工具不调用）
3. 管理员/客户要求新增一个动作（比心/抱拳/点头）
4. 动作部署后不执行/执行到一半卡住
5. 换机型部署同款动作配置

**语言信号：**

- "让机器人做新动作" / "加动作" / "AI 对话带动作"
- "qwen_native_fc" / "tool_call_enabled" / "function call"
- "AI 光说不动" / "动作不触发"
- "关键帧" / "robot_action.json" / "pybullet 仿真"
- EN: "robot action on voice command" / "tool call not triggering"

**区分：**

- ≠ autolife-robot-action-creation / autolife-robot-action-ops / autolife-robot-action-system（旧技能群）：本卡是案例库全量融合版（四件套+五步+安全规则一张卡）
- ≠ autolife-robot-motion-design：那支专讲关键帧设计美学；本卡是配置链+部署验证全流程
- ≠ autolife-voice-action-deploy：那支讲跨机复制；本卡从零配置
- ≠ autolife-robot-diagnosis：动作不执行但配置链正常时，才转诊断卡查 arm 服务

## E — 可执行步骤

**输入契约**：机号（必填）；机型（必填，决定 robot_vX_X.json 文件名）；动作需求描述（新动作时必填）；是否已有部分配置（可选）。

**Step 1 四件套配置链**（新机/修复光说不动）：
1. vision settings.toml [app_settings.ai_chatbot] realtime_api_provider="qwen_native_fc"
2. robot_v2_2.json audio.qwen_native_fc.realtime.tool_call_enabled=true（三层嵌套）
3. control_robot_action.py 三处 enum 同步：TOOL_SCHEMA enum + enumDescriptions 中文说明 + run() valid_actions
4. prompt.txt 动作调用规则段写触发词映射（"挥手"→wave_hand）
**Step 2 联动重启**：`systemctl --user restart vision && sleep 3 && systemctl --user restart face-detection`（硬规范：vision 重启必连带 face）
**Step 3 新动作五步**：
1. 关键帧设计：right_arm 7 值（肩内旋/肩外展/上臂/肘/前臂/腕上/腕下），home=[-20,0,0,-110,0,0,0]
2. pybullet 仿真：URDF 加载 → 关节限位校验 → 逐帧自碰撞检测（排除灵巧手内部连杆）→ 三视图渲染
3. 三视图发管理员，回「上」才部署
4. robot_action.json 三重备份（cp 带日期×3）→ 写入 → md5sum 校验 → 同步 enum 3 处 → prompt 加触发词
5. `systemctl --user restart arm-control` + Step 2 联动 + 四服务 is-active 终验
**Step 4 验证日志链**：vision 日志出现 "Qwen function call" → "Qwen tool executed" → arm 日志 "Executing action: <name>"。缺任一环按链回溯
**判停点**：日志见 "Native FC tool calling disabled by config" → 直接回配置②；仿真自碰撞 → 拆子动作或加过渡姿态，不带伤部署；管理员未确认 → 停在 Step 3.3

**输出契约**：配置清单（四件套状态表）+ 新动作（关键帧表+三视图文件+md5）+ 验证日志链摘录。

## B — 边界

- **不适用**：动作已有且正常，只是对话 prompt 调教（走 autolife-robot-prompt-ops）；纯语音识别问题（ASR）；VR 遥操（autolife-vr-teleop）
- **反场景**：跳过仿真直接上机（碰撞风险）；跳过管理员确认（流程违规）；复位跳零位（路径失控）
- **失败模式**：只改 provider 不开 tool_call_enabled（最常见）；enum 只改一处（三处必须同步）；vision 重启不连带 face（shm 错）；改 json 不备份（回不去）
- **相邻易混**：play_song 唱歌方案已整体下线（321 教训），不要再走 TTS 合成唱歌路线
