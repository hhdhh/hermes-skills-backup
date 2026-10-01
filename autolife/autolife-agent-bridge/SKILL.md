---
name: autolife-agent-bridge
description: Use when 机器人 AI 对话接外部 agent 大脑，或排障 agent-bridge/sidecar。
---

# AutoLife 机器人外部大脑（agent-bridge）

代码在 `~/.hermes/workspace/agent-bridge/`。已验证机型：260（全程接管 v1）与 304（混合模式 v2）。网关 systemd 单元 `agent-bridge`（bridge_v2.py，ws:8765/http:8790/ctrl sock）。

## 混合模式 v2（304 部署 2026-09-28，ROBOT-304-NOTES.md；224 部署 2026-09-28，ROBOT-224-NOTES.md）

平时=原厂：网关把机器人 WS 会话透明转发阿里 dashscope（base_url 劫持到网关，网关再连真 dashscope），人设/音色/工具全原厂。同时旁路影子 ASR（qwen3-asr-flash）只听唤醒词。
听到「小智小智」→ response.cancel+伪 speech_started 掐上游 → 本地 glm-5.3 agent 接管 → 45s 无互动自动回 proxy。三条路径均已 E2E 实弹验证（原厂直通/唤醒接管/超时回原厂）。

### 机型差异坑（224 部署实测 2026-09-28）
- **「不收音」诊断锁序**：①先 diff 正常机 settings.toml：`enable_hybrid_vad=true`会让音频门控依赖 face-detection 跨进程 DDS，链路不通=音频永不发送（网关侧 audio_rx_bytes=0）；`asr_enabled=true`会触发 `No module named audio.asr` 启动错；`start_conversation_on_launch=false`会话不激活。224 实例：三项对齐304后立刻收流（VAD rms 17000+，影子ASR转录到现场人声）。②音频0上行时优先查配置开关再动声卡。
- **网关 v3 遥测诊断法**（bridge_v3.py 2026-09-28）：`/status` 看每机器人 audio_rx_bytes/rx_events/last_rms/max_rms/vad_starts/asr_ok/asr_empty/agent_turns + sidecar健康度(age_s<120)+动作清单；`/log?n=50` 尾部日志；`POST /wake {robot_id,text}` 强制接管测 agent+TTS 回路。不 SSH 判障：rx_bytes=0=机器人没推流（查配置/门控）；字节大但 max_rms<500=麦哑（查声卡/增益）；VAD起话但 asr_empty 高=ASR网络问题。'main' 解析到 gadget 卡——无 gadget 硬件的机型会初始化崩；但 'auxiliary' 只到 3.5mm 空孔恒静音。224 实例：真麦=PC320532 USB 板（logical=main），但工厂 ENABLED_MODULES 漏配 mod_microphone_pc320532——修法=启用该模块+input='main'+hybrid_vad_by_input_microphone 补档（克隆 gadget 档）。验证标志：vision 日志 `Microphone registered on hw:1,0` + `resolved=mod_microphone_pc320532 logical=mod_microphone_main`。另一坑：音频流是人脸门控的（无人脸时 WS 上行 0 B/s 属正常，304 正常机同此）；裸 arecord 独占卡会失败=被占用信号。
- **动作库不同名**：各机 robot_action.json 动作集不同（224 有 wave 无 right_wave；304 反之）。网关已改智能解析：sidecar 注册时上报本机动作清单，resolve_action() 按清单映射别名，清单里没有就发原名。手工改 ACTION_ALIAS 硬映射的做法已废弃。
- **arm 报错被 rclpy logger bug 吞**：动作 not found 的原始错误会被 `ValueError: Logger severity cannot be changed between calls` 盖住；复现时补丁 `rcutils_logger.RcutilsLogger.error` 打印原始 message。
- **掉电循环机型（224）sidecar 必须 systemd user unit 自启**：agent-bridge-sidecar.service，Restart=always，enable 后掉电重启自动回连。
- 网关 HTTP /ask 端点支持 robot_id 定向触发 agent（运维免 ctrl 全局广播）。

### v2 关键坑（实测踩过）
- 机器人 input_vad 滤静音 → 上游 server_vad 永不收口：网关话尾检测后必须**向上游补 ~1.5s 静音**，否则原厂永远不回话（补静音在 vad_watchdog → pad_silence_upstream）。
- 上游重连后 dashscope 会发新 session.created：不透传（机器人只认首次握手），session.update 存原文重放。
- dashscope 空闲会话会被服务端关闭（1007）：upstream_manager 3s 自动重连+重放，属正常自愈。
- sidecar DDS 阵营：**CYCLONEDDS_URI 必须抄目标机 arm 进程 environ**（304 是 Interfaces lo multicast+ParticipantIndex=none，与 260 硬编码 URI 不同阵营）；sidecar v1 已自动抓取 /proc/*/environ。
- pub_action.py 的 rclpy 兼容：部分机型无 Publisher.get_publisher_count() → try/except AttributeError。
- 部署前审计发现 304 provider 原值 openai 且无任何 key（原厂对话本来就哑）→ 修成 qwen+key 才有「平时原厂」体验。现场人员会翻配置，改前必查现状。

### 机器人侧只改 2 处 + 加 1 目录
settings.toml（provider=qwen + QWEN_API_KEY）+ robot_v2_2.json（base_url 三处→ws://100.98.198.205:8765）+ /home/ubuntu/agent-bridge/（sidecar）。备份在机器人 ~/agent_bridge_backup/，回滚见 ROBOT-304-NOTES.md。

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

## 唤醒词门控（2026-09-26 加）
- CFG：wake_word=小智小智，wake_regex=`小[智志]`（ASR 变体兼容），wake_window_s=45，wake_ack=哎，我在！
- 逻辑在 handle_turn ASR 之后：睡眠态无唤醒词→静默丢弃；唤醒词+指令连说→剥词直入 agent；只喊唤醒词→播应答语待命；唤醒后 45s 内免唤醒续窗
- 剥重复唤醒词：`re.sub(r'^(?:[，。？！,.?\s]*小[智志])+', '', ...)`，否则「小智小智」残留第二个进 agent
- 端到端自测：test_wake_inject.py 本机 WS 连 8765 注入合成音频，完整走 ASR→门控→agent→TTS

## 关键坑（2026-09-26 实战）
- **现场会远程关 ai_chatbot_enabled**：settings.toml 被运营管理端改回 false（12:33 有人关的）→ vision 起来但不初始化 chatbot 不连网关，症状=日志静默无「Initializing AI Chatbot」；先 grep settings.toml 再怀疑崩溃
- 现场并行改动纪律：动手前 md5 对比备份，发现被改回不要盲回滚，理解意图后重开（本次唤醒词上线正是为了解决它乱搭话）
- vision 重启卡在 chatbot 初始化前≠死机：py-spy dump 看主线程 spin 正常即可判是配置开关问题，187% CPU 是正常干活不是死循环
- NetBird SSH 连续失败可能是连接数冷却，等 45s 恢复；期间 sidecar HTTP 仍通可作备用通道
- robssh awk 内嵌 $ 符号要 \\\$ 转义，否则远端 awk 语法错

## 踩坑记录
- pkill -f 'sidecar' 会连带杀 robssh 传输链自身（命令行匹配），用 ps+kill <pid>
- 坏 JSON 发到动作 topic 会把 ArmActionControl 进程干崩（有自愈但需确认）
- NetBird 新建 SSH 连接偶发抖动超时，存量 WS 连接不受影响；等几秒重试即可
- vision 2.2.14 初始化后段有非阻断 bug：`info() takes exactly 1 positional argument`，WS 已连、对话正常，忽略
- 独立 ASR 服务报 `No module named audio.asr` 与 realtime 对话管线无关，忽略
