---
name: autolife-agent-bridge
description: Use when 机器人 AI 对话接外部 agent 大脑，或排障 agent-bridge/sidecar。
---

# AutoLife 机器人外部大脑（agent-bridge）

代码在 `~/.hermes/workspace/agent-bridge/`。已验证机型：260（vision 2.2.14+build3，provider=qwen 文本 tool_call 代）。

## 架构（全部实测验证 2026-09-26）

```
机器人 vision 服务 ──WS(ws://100.98.198.205:8765，仍说 Dashscope Realtime 协议)──> 工作站 agent-bridge
    上行：session.update(instructions=机器人 prompt.txt 人设) + input_audio_buffer.append(b64 PCM)
    下行：session.created / session.updated / response.audio.delta(b64 PCM 24k) / response.*
工作站 agent-bridge = VAD(能量法+无片超时) → qwen3-asr-flash(dashscope MultiModal) → glm-5.3(sub2api，工具循环) → edge-tts → 回播
机器人 sidecar(HTTP:8791，/home/ubuntu/agent-bridge/) ← 网关 HTTP 调用 → rclpy 发布动作
```

## 机器人端接入（仅改 2 个文件，三重备份+md5）

1. `configs/robot_v2_2.json`：`audio.qwen.realtime.base_url` + `regions.cn/sg` 三处 → `ws://100.98.198.205:8765`
2. `settings.toml`：ai_chatbot/asr/tts_enabled 三开关全 true
3. 重启顺序：vision → sleep 8 → face-detection（硬规范）
4. 备份在机器人 `~/agent_bridge_backup/`，回滚见 agent-bridge/ROBOT-260-NOTES.md

关键认知：**qwen realtime 客户端全吃自定义 base_url，连上后等服务器先发 session.created，收到后立刻 session.update 上传完整人设**。机器人侧 enable_input_vad=true 会滤静音：安静时零音频流，有人说话才发片——网关 VAD 用「in_speech 后 900ms 无新片=话轮完」判定，不能靠收静音片。

## 部件真相
- 输入音频：JSON `input_audio_buffer.append`，b64 PCM 单声道（片大小 296/592 b64 交替），格式字段填 pcm
- ASR：`qwen3-asr-flash` 走 dashscope MultiModalConversation.call，audio 传 data URI WAV，**text 必须空字符串**（非空报 400 dedicated task）；key 用机器人自己的 QWEN_API_KEY
- LLM：sub2api glm-5.3 必带 `"thinking":{"type":"disabled"}`（思考型默认吃光 max_tokens 返回空 content）；工具循环标准 OpenAI tools 格式
- TTS：edge-tts mp3 → ffmpeg 转 24k s16le → 4800B/100ms 片 → response.audio.delta，0.1s 节奏下发
- 动作：topic `/topic_arm_robot_action_0_<机号>`（std_msgs/String），**payload {"action_name":x,"action_type":"play"}**（不是 {"action":x}）；必须 rclpy 发布（ros2 topic pub 的 YAML 引号会坏 JSON 且崩 ArmActionControl）；成功标记 arm-control-service journal `Executing action:`
- 动作名映射：口语名→动作库真名（wave→right_wave, bow→bow_salute, love→love2, thumbs_up→win_an_award）在网关 ACTION_ALIAS
- unit 名是 **arm-control-service**（不是 arm-control）

## 运维
- 网关：工作站 `systemctl --user status agent-bridge`（日志 journalctl --user -u agent-bridge，协议流 /tmp/ws_probe.log）
- 控制通道：`python3 -c "...connect('/tmp/agent-bridge.sock')"`，命令 status / say <文本> / ask <文本>（ask=跳过 ASR 直入 agent）
- sidecar 自注册周期 60s（网关重启后最多等 60s 才有身体控制）
- 会话记忆：agent-bridge/state/robot_<id>_memory.json（remember/recall 工具读写）

## 踩坑记录
- pkill -f 'sidecar' 会连带杀 robssh 传输链自身（命令行匹配），用 ps+kill <pid>
- 坏 JSON 发到动作 topic 会把 ArmActionControl 进程干崩（有自愈但需确认）
- NetBird 新建 SSH 连接偶发抖动超时，存量 WS 连接不受影响；等几秒重试即可
- vision 2.2.14 初始化后段有非阻断 bug：`info() takes exactly 1 positional argument`，WS 已连、对话正常，忽略
- 独立 ASR 服务报 `No module named audio.asr` 与 realtime 对话管线无关，忽略
