# TTS Providers — 10 个内置 + Custom Command（2026-07-29 立）

> 完整 skill 见 `hermes-gateway-admin` SKILL.md 第 H 段。本文是 **provider 速查** + **voice_id 清单** + **endpoint 域名差异** + **diagnostic 流程**。

## 1. 10 个内置 TTS Provider

`tools/tts_tool.py:389 BUILTIN_TTS_PROVIDERS`：

| Provider | API key env | 端点 | 中文支持 | 备注 |
|----------|-------------|------|----------|------|
| `edge` | (无) | Microsoft Edge TTS | ✅ `zh-CN-XiaoxiaoNeural` | **中文兜底首选**，免费 |
| `openai` | `OPENAI_API_KEY` | `https://api.openai.com/v1/audio/speech` | ❌ | 模型 `gpt-4o-mini-tts` |
| `elevenlabs` | `ELEVENLABS_API_KEY` | `https://api.elevenlabs.io/v1/text-to-speech` | ✅ | quality 最高 |
| **`minimax`** | `MINIMAX_API_KEY` (+ `MINIMAX_GROUP_ID`) | `https://api.minimax.chat/v1/t2a_v2`（国内）or `api.minimax.io`（国际） | ✅ | **本机当前配置** |
| `xai` | `XAI_API_KEY` | Grok voice API | ❌ | `voice_id: eve` |
| `mistral` | `MISTRAL_API_KEY` | Mistral audio API | 部分 | `voxtral-mini-tts-2603` |
| `gemini` | `GEMINI_API_KEY` | Gemini TTS | ✅ | 32k token 上下文 |
| `neutts` | (无) | local CPU | ❌ | Neuphonic 25MB 模型 |
| `kittentts` | (无) | local CPU | ❌ | 25MB 模型 |
| `piper` | (无) | local CPU | ✅ | 44 语言，VITS 模型 |

**最大文本长度**（`PROVIDER_MAX_TEXT_LENGTH[tts_tool.py:225]`）：

| Provider | 字符上限 |
|----------|----------|
| `edge` | 5000 |
| `openai` | 4096 |
| `xai` | 15000 |
| `minimax` | 10000 |
| `mistral` | 4000 |
| `gemini` | 32000 |
| `elevenlabs` | 10000 |
| `neutts` | 2000 |
| `kittentts` | 2000 |
| `piper` | 5000 |

## 2. MiniMax TTS 详细配置

### 2.1 默认值（写死在 `tts_tool.py`）

```python
DEFAULT_MINIMAX_MODEL = "speech-02-hd"
DEFAULT_MINIMAX_VOICE_ID = "English_expressive_narrator"
DEFAULT_MINIMAX_BASE_URL = "https://api.minimax.io/v1/t2a_v2"
```

⚠️ **默认 base_url 错了** — 主人 key 走 `api.minimax.chat`（国内）。直接 2049 invalid api key。

### 2.2 端点差异（**tts_tool.py 通过 URL 自动切换**）

| Base URL 包含 `t2a_v2` | 走嵌套 payload | 字段结构 |
|---|---|---|
| `https://api.minimax.chat/v1/t2a_v2` | ✓ | `voice_setting.{voice_id,speed,vol,pitch,emotion}` + `audio_setting.{sample_rate,bitrate,format,channel}` |
| `https://api.minimax.chat/v1/text_to_speech` | ✗ | 扁平 `voice_id, speed, model, text` |

**两种 endpoint 同一个 key 都通**。**t2a_v2 返回 JSON + hex-encoded audio**（更复杂但更可控），**text_to_speech 直接返回 audio/mpeg**（更简单）。tts_tool.py 内部自动处理。

### 2.3 验证 API endpoint（curl 流程）

```bash
MINIMAX_API_KEY=$(grep MINIMAX_API_KEY ~/.hermes/.env | cut -d= -f2)

# 标准测试：text_to_speech 端点 + 已知 voice_id
curl -s -X POST "https://api.minimax.chat/v1/text_to_speech" \
  -H "Authorization: Bearer $MINIMAX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"speech-02","text":"测试","voice_id":"male-qn-qingse"}' \
  -o /tmp/test_tts.mp3 -w "HTTP=%{http_code} size=%{size_download}\n"

# 期望: HTTP=200 size>1000, file=/tmp/test_tts.mp3: MPEG ADTS, layer III
```

**错误码速查**：

| 状态码 | 含义 | 解法 |
|---|---|---|
| 2049 | `invalid api key` | 换 endpoint 域名（`api.minimax.io` vs `api.minimax.chat`）或检查 key |
| 2054 | `voice id not exist` | 换 voice_id，下表是常用清单 |
| 2013 | `invalid params, empty field` | 大概率 base_url 选错，参数结构不匹配 |
| 1002 | `rate limit exceeded` | 退避 1-2 秒重试，或升级配额 |
| 1008 | `insufficient balance` | 充值 |

### 2.4 常用 voice_id（已验证可用）

中文男声：
- `male-qn-qingse` — 清澈男声（中文，**主人 7/29 验证过**）
- `audiobook_male_1` — 男声旁白，有故事感
- `presenter_male` — 主持人男声，端正

中文女声：
- `female-shaonv` — 少女音，清亮嫩
- `female-tianmei` — 甜美，软萌
- `female-yujie` — 御姐，成熟低音（**主人 7/29 选定的默认**）
- `female-chengshu` — 成熟，沉稳
- `presenter_female` — 主持人女声，端正
- `audiobook_female_1` — 女声旁白，有故事感

**幻觉 voice_id（不要用）**：`mature_man` / `wise_woman` / `Chinese (Mandarin)_Gentle_Woman`（带空格） — 返回 2054 not exist。

### 2.5 听感差异诊断

6 个不同 voice_id 的 MP3 文件：
- **md5 全不同**（各 voice_id 各 ProduceID）
- **文件大小差异显著**（30K-54K bytes 不等）
- **时长差异**（`female-yujie` 6.7s vs `female-tianmei` 7.6s，10% 波动）

如果听感觉得"全是男声"或"全是同一种声音"，**大概率是**：
1. 文本太短（"测试"两个字 → 任何 voice 都没发挥空间）
2. 用的是 `text_to_speech` 工具但**没改 voice_id**（致命坑，工具不接受 voice_id 参数）
3. 32kHz mono MP3 编码压缩让细节磨平

**正解**：用 ≥ 2 句有情绪变化的中文长文本 + 改 `voice_id` 后 curl 直发验证。

## 3. 切到 MiniMax TTS 完整 3 步（7/29 实战）

```bash
# 1. 改 provider 指向
hermes config set tts.provider minimax

# 2. 改 provider 自己的参数（API key 走 .env, 不写这里）
hermes config set tts.minimax.model speech-02-hd
hermes config set tts.minimax.voice_id female-yujie     # 主人选定
hermes config set tts.minimax.base_url https://api.minimax.chat/v1/t2a_v2
hermes config set tts.minimax.speed 1.0
hermes config set tts.minimax.vol 1.0
hermes config set tts.minimax.pitch 0
hermes config set tts.minimax.emotion neutral
hermes config set tts.minimax.sample_rate 32000
hermes config set tts.minimax.bitrate 128000

# 3. 端到端验证
MINIMAX_API_KEY=$(grep MINIMAX_API_KEY ~/.hermes/.env | cut -d= -f2) \
  /Users/kk/miniconda3/bin/python3.13 \
  /Users/kk/skills/hermes/hermes-gateway-admin/scripts/verify-tts.py minimax
```

**期望输出**：`{"success": true, "provider": "minimax", "file_path": "/Users/kk/.hermes/cache/audio/tts_<timestamp>.mp3"}` + 真实 MP3 (32kHz 128kbps)。

## 4. 切回中文兜底 edge

```bash
hermes config set tts.provider edge
hermes config set tts.edge.voice zh-CN-XiaoxiaoNeural
# 立刻生效，无需重启 gateway
```

## 5. Custom Command Provider（PR #17843）

`10 个内置 provider` 不够用时，Piper / VoxCPM / Kokoro CLI 等走 `tts.providers.<name>: type: command`。

```yaml
tts:
  provider: piper-en
  providers:
    piper-en:
      type: command
      command: "piper -m ~/model.onnx -f {output_path} < {input_path}"
      output_format: wav
```

**支持的占位符**：`{input_path}` / `{text_path}`（alias）/ `{output_path}` / `{format}` / `{voice}` / `{model}` / `{speed}`。Use `{{` / `}}` for literal braces.

**placeholder 安全**：路径自动 shell-quote，有空格安全。

## 6. 完整决策树

```
TTS 配错 → curl 验 endpoint (2049 invalid api key = 域名错)
        → curl 验 voice_id (2054 not exist = ID 错)
        → hermes config set 改 (patch 工具拒)
        → verify-tts.py 端到端 (调工具 vs curl 看路径)
        → 听 / 看 ProduceID 确认
```

## 7. 参考的关联资源

- SKILL.md 第 H 段 — TTS 配置完整流程
- `scripts/verify-tts.py` — 端到端验证脚本
- `references/codex-opencode-go-config.md` — OpenCode Go 端点格式（不直接相关但 LLM provider 速查同样套路）
