---
name: autolife-bilingual-voice
version: 1.0.0
description: Use when 主人要给 AutoLife S1 机器人配多语言/中英双语语音对答（展会/接待/迎宾场景）：Qw...
metadata:
  requires:
    bins: ["paramiko", "ffprobe"]
  triggers:
    - "机器人英语应答"
    - "双语语音"
    - "中英互答机器人"
    - "展会机器人"
    - "wav 备用语音"
---

# AutoLife S1 多语言/双语语音对答部署

> 完整描述：Use when 主人要给 AutoLife S1 机器人配多语言/中英双语语音对答（展会/接待/迎宾场景）：Qwen realtime 多语 TTS/ASR 架构、双语 prompt 规则、wav 离线备用资产的生成与启用。区别于 autolife-robot-prompt-ops（那只管 prompt/RAG 文本）。

> 补位：prompt 文本的编辑/备份/上传细节见 `autolife-robot-prompt-ops`（user-owned，需 `hermes curator adopt`）。本 skill 专载**语音架构与双语规则**——prompt-ops 没覆盖的部分。

## 关键架构（321 实测，2026-09-16）

AI 对答跑在 **vision-service**（`autolife_robot_vision.main`），不是 logo-backend。管线：

| 组件 | 配置键 | 默认值 | 多语能力 |
|------|--------|--------|---------|
| AI 对话 | `realtime_api_provider` | `qwen` | ✅ 任意语种 |
| ASR | `asr_provider` | `gummy_chat` | ✅ |
| TTS | `TTS_PROVIDER` | `qwen`（在线 qwen3-tts-flash, voice=Tina） | ✅ 按文本语言自动发声 |
| prompt | `assets/prompt/prompt.txt` | system_prompt | 需引导 |

**TTS 不需要换引擎做多语**：`TTS_PROVIDER=qwen` 时 Qwen LLM 输出什么语言，TTS 就自动说什么语言。"英文问回英文 + 英文语音"只在 prompt 引导 LLM 输出英文即可，无需动 TTS。

## 双语 prompt 规则（写进 prompt 顶部，标注"最高优先"）

```
# 双语规则（最高优先）
- 自动检测访客使用的语种，并用同一种语种回答：中文问用中文答，英文问用英文答。
- 访客明确要求换语种（如 "English, please" / "speak English"）→ 立即切换英文。
- 中英文都表达自然，尊重用户使用的语言。
```

展台场景额外：身份保留（如"我叫小智/Sage"）+ 欢迎语按开场自动选 + 结束语双语。知识段注入中英双语 Q&A 即可（prompt-ops B 档）。

## 多语会话是否要真 RAG？

Qwen realtime 会初始化 KnowledgeRetriever（0 embeddings）、注册 `search_knowledge_base` 工具。这些只是辅助，**主知识在 system_prompt 里就够**。日志 `No knowledge source or cache file found` + `0 embeddings` 是正常警告，不影响主对话——判成功应看 `session.created ... model=qwen3.5-omni-flash-realtime` + `TTS initialized` + 无致命 traceback，**不要**被 0 embeddings 吓到。

## wav 离线备用资产（断网可用话术集）

主人常要"wav 备用"——离线/降频时仍能播欢迎和关键问答。流程：

1. **生成**：用本机 `text_to_speech`（dashscope 音色，跟 Qwen 同生态）逐个生成中英双语话术短音频。
2. **格式核对**：必须 **16bit PCM / 24000Hz / 单声道**（跟机器人现有 `assets/tts/wav/*.wav` 一致）。用 ffprobe 验真时长（Python `wave.getnframes()/getframerate()` 读 RF64 会假报 ~44739s，别信；文件大小几百 KB + ffprobe 秒级时长才是真）。
3. **上传**：SFTP 到 `assets/tts/wav/南航备用/`（或按主题建子目录，md5 校验）。
4. **启用方式**（两选一）：
   - 纯备用资产：保持 `TTS_PROVIDER=qwen`，wav 用于人工/脚本触发。
   - 断网兜底：改 `TTS_PROVIDER=\"wav\"`，机器人 speak 某文本 → 播 `assets/tts/wav/<文本>.wav`；`face_detection.json` 的待机循环 `speak text` 换成南航欢迎文案（中英交替）即可循环播。

## 验证（端到端）

- 改 prompt → 重启 vision-service → 日志查 `Successfully loaded system prompt from .../prompt.txt`
- Qwen 实际已在对答：`Qwen response done (completed): tokens=...` + `Qwen audio playback completed`（说明新 prompt 已生效在跑）
- 无致命 traceback（camera hand overlay / conda entry point / zstandard warnings 均无害）

## 连接注意

- 新机先查 `robssh.py list`；机号没登记时用主人给的 IP paramiko 直连（密码统一 ubuntu），连上先 `hostname` + `ip` 验明正身。
- 定位成功后把 `机号:IP` 写进 `~/.hermes/workspace/robots.json`，方便下次。
- 321 NetBird relay 建不起来时内网 SSH 直连最稳（重启前确认机器在现场）。