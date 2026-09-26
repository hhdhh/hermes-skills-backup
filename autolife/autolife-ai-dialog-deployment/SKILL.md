---
name: autolife-ai-dialog-deployment
description: Use when 给 AutoLife 机器人部署 AI 对话全链路：对话模式选型、工具链、prompt、TTS、验证。
---

# AutoLife 机器人 AI 对话全链路部署

覆盖：对话模式选型、工具链改写、prompt 织入、TTS、端到端验证。动作库细节见 `autolife-robot-action-ops`（用户自有，冲突时以实机现状为准），prompt 规范见 `autolife-robot-prompt-ops`，SSH/文件传输见 `autolife-remote-repair`。

管理员既定偏好（适用所有机器）：
- 工具调用**全程静默**：不设 pre_execute_message，调用前后不念"正在查询/执行"，返回后直接给答案。
- 对话**反啰嗦**：不要身份确认反问（"是在和我说话吗"）、不要语种二次确认；用户直接提问就接待，背景闲聊保持静默。
- 性格按场景给（如 ENFJ 主人公型），热情但不聒噪，简洁不拖泥带水。
- 新动作设计需三视图预览+确认后才上真机；**从其它机器拷已验证动作不在此列**。

## 部署流程（按序）

1. **审计现状**：`settings.toml` 的 `realtime_api_provider`、`configs/robot_v2_2.json` 的 `audio.*.realtime.tool_call_enabled`、QWEN_API_KEY、`robot_tools/__init__.py` 的 ENABLED_TOOLS（control_robot_action 是否被注释）。
2. **模式选型（strings 探测 .so，不猜版本号）**：`strings audio_realtime_api_qwen*.so | grep -E "_handle_text_tool_calls|native_fc"`。有 `_handle_text_tool_calls` 无 native_fc → 文本 `<tool_call>` 模式（provider 留 `qwen`）；有 native_fc 配置段 → native_fc 模式。一台机器只一套，混配双触发。
3. **工具链改写**（三重备份+md5 先行，本地改好再 push）：
   - ENABLED_TOOLS 启用 control_robot_action + get_current_time / get_weather_by_gaode。
   - `control_robot_action.py` 守卫全部 `getattr(vs, "属性", 默认值)`——原厂代码引用新版 VisionService 属性（旧版 .so 无），import 不报错一调就 AttributeError，这是该工具"被历史注释掉"的常见原因。发送双通道：`vision_service._action_callbacks` 逐个回调（单个异常吞掉）→ `vision_service.node.action_publisher.publish` 兜底。
   - schema enum 与 run() 的 VALID_ACTIONS **两张表都要加**新动作；只加一张要么发不出、要么被拒。护栏动作可只进 VALID 不进 enum（不暴露给 LLM 防误触）。
   - `base_tool.py` 静默修复：无显式 pre_execute_message 时直接 return，不调 `get_default_tool_wait_message()`（编译 .so 里硬编码英文）。
4. **prompt 织入**：工具规则（静默版+触发词映射，如"握个手"→动作名）+ 活动知识（见下）。只教官方 `<tool_call>` JSON，不教自创标签。
5. **TTS**：`[app_settings.tts] TTS_PROVIDER="wav"` 只播预录文件，系统话术无对应 wav 时**静默丢弃**（journal `文件 ... 不存在`）——需要合成系统语就切 `edge`（robot_env 自带 edge-tts，先用一条短句实测能合成再重启）。
6. **重启顺序**：arm-control → vision → sleep → face-detection（动 vision 必联动 face，硬规范）；四服务 is-active 终验。
7. **验证链**：vision 日志 `Loaded external tool schema: <name>` + `Qwen realtime WebSocket connected` + 系统提示 dump 含新 enum；arm 日志 `Executing action: <名>`。

## 端到端动作实弹验证（S2/v2_2）

- 真实话题 `/topic_arm_robot_action_0_<机号>`（`/robot_action_0_<机号>` 是死话题）；枚举时排除 nav2 的 `_action` 元话题。
- 测试脚本必须与服务同 DDS 阵营：`RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` + `ROS_DOMAIN_ID=0` + `CYCLONEDDS_URI` 指向 127.0.0.1。缺 RMW_IMPLEMENTATION 时脚本走默认 fastrtps 互相不可见（症状：只枚举到 /parameter_events+/rosout）。
- ROS python 调用：`bash -c "source /opt/ros/jazzy/setup.bash && /home/ubuntu/miniconda3/bin/conda run --no-capture-output -n robot_env python /tmp/<script>.py"`（裸 conda python 无 std_msgs）。
- mock 验证工具代码路径时注意：无 ROS 环境的裸解释器测不到 publisher 兜底分支（No module named std_msgs 是环境假象非代码缺陷）。

## 活动知识注入（展会/论坛场景）

- 物料是图片 → 本地 RapidOCR 提文本（skill: local-ocr-rapidocr），不要凭图口述转录。
- 结构：活动名+时间地点头 → 时间轴议程 → 嘉宾（名-头衔）→「应答要点」Q&A 映射；指示"自然口语化，不逐字背诵"。
- 韥识随红线写入：议程之外的细节如实说不知。
- 长文本生成后**先断言锚点再 push**（新增关键词在、无乱码残留）——长 prompt 生成偶发内容污染，推送前校验是唯一防线；v3 基础上定点 patch 优于整篇重写。

## 协作与传输纪律

- 展会现场机常有现场人员并行改文件：动手前先 pull 最新版作基底，push 后隔约一分钟 md5 复查；发现并行改动方向一致时合并（如动作名双注册），不盲目回滚。
- 远端 heredoc/内联命令写长 JSON 必坏（引号嵌套转义改坏载荷）——一律 pull→本地改→锚点断言→push（md5 双端）。

## 排障速查

- AI 对话整体哑 → 先看 vision 启动日志有无 `Temporary failure in name resolution`（WiFi 未就绪时服务先起）；网络恢复后 restart vision 即愈，不是配置/密钥问题。
- face-detection 显示 failed 但无 crash 循环 → 看是否 stop-timeout 残留（手动 stop 时 final-sigterm 超时），重启即清。
- 工具被调但动作不动 → 查模式是否混配、enum/VALID 双表、`Interrupting current action` 是否说明指令到了 arm（到了不执行查硬件/电量）。
