# Codex CLI + OpenCode Go GLM-5.2 配置

> 2026-07-12 实战记录，当日修正。Codex CLI 0.144.1 / 0.145-alpha + GLM-5.2 via OpenCode Go。

## 核心问题：Codex CLI 不支持 chat_completions

**Codex CLI 的 `wire_api` 只支持 `responses`**（OpenAI Responses API 格式）。旧 `chat` 模式已移除（`wire_api = "chat" is no longer supported`），`chat_completions` 也不是合法值——直接报 `unknown variant 'chat_completions'`。

但 OpenCode Go 的 GLM-5.2 只提供 `/v1/chat/completions` 端点（标准 OpenAI Chat Completions），**不提供 `/v1/responses` 端点**（返回 404）。

**结论**：Codex CLI 无法直接对接 GLM-5.2，需要本地代理把 Responses API 转成 Chat Completions。

## Codex config.toml（指向本地代理）

```toml
model_provider = "custom"
model = "glm-5.2"
disable_response_storage = true

[model_providers.custom]
name = "OpenCode Go"
base_url = "http://127.0.0.1:8848/v1"
wire_api = "responses"
requires_openai_auth = true
```

**关键点**:
1. `base_url` = `http://127.0.0.1:8848/v1`（本地代理，不是 opencode.ai 直连）
2. `wire_api` = `responses`（Codex 唯一支持的值）
3. API key 在 `~/.codex/auth.json` 的 `OPENAI_API_KEY` 字段（Codex 自动读取）
4. `disable_response_storage = true`（OpenCode Go 不支持 response storage）
5. 代理脚本在 `scripts/responses-proxy.py`，监听 8848 端口

## 常见错误

### 错误 1: wire_api = "chat_completions"

```toml
# ❌ 不存在这个值
wire_api = "chat_completions"
# → Error loading config.toml: unknown variant `chat_completions`, expected `responses`
```

Codex 二进制 `strings` 搜索确认：唯一支持的 `wire_api` 值是 `responses`。

### 错误 2: base_url 直连 opencode.ai + wire_api = responses

```toml
# ❌ opencode.ai 没有 /responses 端点
base_url = "https://opencode.ai/zen/go/v1"
wire_api = "responses"
# → 404 Not Found (HTML page, 不是 JSON)
```

### 错误 3: base_url 多了 /models

```toml
# ❌
base_url = "https://opencode.ai/zen/go/v1/models"
# → 404 Not Found
```

### 错误 4: Codex Desktop 覆盖 config.toml

Codex Desktop 运行时会回写 `config.toml`。手动改完如果 Desktop 还开着，可能被覆盖回旧的 MiniMax 配置。**改完先关 Desktop**。

### 错误 5: auth.json 被删

Codex Desktop 同步时可能删 `~/.codex/auth.json`。改完配置后检查 `ls ~/.codex/auth.json`，没了就 `codex login --with-api-key` 重新写。

## 验证流程

```bash
# 1. 代理跑着
curl -s http://127.0.0.1:8848/health
# 期望: ok

# 2. 非流式测试
API_KEY=$(cat ~/.codex/auth.json | python3 -c 'import sys,json;print(json.load(sys.stdin).get("OPENAI_API_KEY",""))')
curl -s -X POST "https://opencode.ai/zen/go/v1/chat/completions" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"glm-5.2","messages":[{"role":"user","content":"hi"}],"max_tokens":20}'
# 期望: JSON with choices[0].message.content

# 3. Codex CLI 能加载配置
codex login status
# 期望: Not logged in（但能加载 config，不报 unknown variant）

# 4. Codex CLI 实际执行
codex exec "echo hello"
# 期望: 正常执行（代理转发到 opencode.ai）
```

## OpenCode Go 模型端点速查

来源: https://opencode.ai/docs/zh-cn/go/

| 模型 | 模型 ID | 端点 | 协议 | Codex 直连 |
|------|---------|------|------|-----------|
| GLM-5.2 | glm-5.2 | /v1/chat/completions | OpenAI-compatible | ❌ 需代理 |
| GLM-5.1 | glm-5.1 | /v1/chat/completions | OpenAI-compatible | ❌ 需代理 |
| Kimi K2.7 Code | kimi-k2.7-code | /v1/chat/completions | OpenAI-compatible | ❌ 需代理 |
| Kimi K2.6 | kimi-k2.6 | /v1/chat/completions | OpenAI-compatible | ❌ 需代理 |
| DeepSeek V4 Pro | deepseek-v4-pro | /v1/chat/completions | OpenAI-compatible | ❌ 需代理 |
| DeepSeek V4 Flash | deepseek-v4-flash | /v1/chat/completions | OpenAI-compatible | ❌ 需代理 |
| MiMo-V2.5 | mimo-v2.5 | /v1/chat/completions | OpenAI-compatible | ❌ 需代理 |
| MiMo-V2.5-Pro | mimo-v2.5-pro | /v1/chat/completions | OpenAI-compatible | ❌ 需代理 |
| MiniMax M3 | minimax-m3 | /v1/messages | Anthropic | ✅ Codex 原生支持 |
| MiniMax M2.7 | minimax-m2.7 | /v1/messages | Anthropic | ✅ Codex 原生支持 |
| Qwen3.7 Max | qwen3.7-max | /v1/messages | Anthropic | ✅ Codex 原生支持 |
| Qwen3.7 Plus | qwen3.7-plus | /v1/messages | Anthropic | ✅ Codex 原生支持 |
| Qwen3.6 Plus | qwen3.6-plus | /v1/messages | Anthropic | ✅ Codex 原生支持 |

**关键区别**:
- OpenAI-compatible 模型（GLM/Kimi/DeepSeek/MiMo）→ 只有 `/chat/completions`，Codex 需代理
- Anthropic 模型（MiniMax/Qwen）→ 有 `/messages`，Codex 原生支持（`wire_api = responses` 走 Anthropic 兼容模式）

## 代理启动

```bash
# 启动代理（需要 opencode.ai API key）
python3 ~/.codex/responses-proxy.py --port 8848 --api-key sk-...

# 或用环境变量
OPENCODE_API_KEY=sk-... python3 ~/.codex/responses-proxy.py --port 8848
```

代理脚本见 `scripts/responses-proxy.py`（纯 Python 标准库，无第三方依赖）。

## Codex config.toml patch 命令

```bash
# 备份
cp ~/.codex/config.toml ~/.codex/config.toml.bak-$(date +%Y%m%d)

# 用 patch 工具改（比 sed 安全）
# 见 SKILL.md 主文件的配置示例
```