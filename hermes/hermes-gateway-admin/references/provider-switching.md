# Provider 切换 / 加 API key 完整诊断流

> 2026-07-12 主人切 OpenCode Go 实战。
> 作者：慧慧 / 灰灰 · 三化身同步

## 背景

OpenCode Go 是 OpenCode 官方推出的低成本开源编程模型订阅：
- 首月 $5，之后 $10/月
- 5h 限额 $12 / 周 $30 / 月 $60
- 模型托管美/欧/新加坡
- 零保留政策

主人 7/12 拿到了 OpenCode Go API key（`sk-zHo...lzFs`），要切默认 provider 从 MiniMax 直连 → OpenCode Go。

## 真实故障树

主人执行 `mcp__hermes_studio_use__hermes_studio_use_provider_add`：

```
Error: fetch failed
```

根因：MCP 工具在 agent 进程内调用，受 sandbox 网络限制（hermes agent 自身进程在 sandbox 内，外部 HTTPS 出站受 curl 之外的额外 ACL 限制）。

**Fallback**: 不用 MCP 工具，直接改 .env + config.yaml。

## 完整步骤（OpenCode Go 切 provider）

### Step 1: 改 `~/.hermes/.env`

```bash
# 注释掉旧 key（不要删，留作回滚）
# ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
# ANTHROPIC_API_KEY=sk-cp-...0-bo
# MINIMAX_API_KEY=sk-cp-...0-bo

# 新加
ANTHROPIC_BASE_URL=https://opencode.ai/zen/go
ANTHROPIC_API_KEY=sk-zHo...lzFs
OPENCODE_GO_API_KEY=sk-zHo...lzFs    # 备份, 某些路径走这个
ANTHROPIC_PROXY_API_KEY=sk-zHo...lzFs  # 之前已配, 保留
```

**注意**：`ANTHROPIC_BASE_URL` 和 `ANTHROPIC_API_KEY` 是 Hermes CLI 实际读的字段。`OPENCODE_GO_API_KEY` 是某些工具层 fallback 路径。`ANTHROPIC_PROXY_API_KEY` 是 Codex++/其他工具的。

### Step 2: 改 `~/.hermes/config.yaml`

```yaml
model:
  provider: anthropic          # 留 anthropic — base_url 决定走哪
  default: minimax-m3          # 或主人想用的 model id
  base_url: https://opencode.ai/zen/go   # 也可写这里, 优先 .env
```

CLI 改法（agent 友好）：
```bash
hermes config set model.default minimax-m3
hermes config set model.base_url https://opencode.ai/zen/go
# provider 留 anthropic
```

### Step 3: 直接 curl 验 API 通（**这是最可靠的验证**）

```bash
curl -s -X POST https://opencode.ai/zen/go/v1/messages \
  -H "x-api-key: sk-zHo...lzFs" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{"model":"minimax-m3","max_tokens":50,"messages":[{"role":"user","content":"hi"}]}'
```

期望返回：
```json
{"id":"...","type":"message","role":"assistant","stop_reason":"end_turn","model":"minimax-m3","content":[{"type":"text","text":"Hi! How can I help you today?"}],"usage":{"input_tokens":50,"output_tokens":9,...}}
```

**返回 = API key 有效，端点对，模型存在。** 此时切 provider 实质已经成功。

### Step 4: 看 `hermes doctor` 验收

```bash
hermes doctor
```

期望看到：
```
◆ API Connectivity
  ✓ OpenCode Go          (key configured)
  ⚠ Anthropic API (couldn't verify)    # 正常 — base_url 是 opencode, CLI 直验失败
  ✗ MiniMax              (invalid API key)   # 正常 — 旧 key 注释了
```

`Anthropic API (couldn't verify)` 和 `MiniMax invalid` 都是**正常的**——主人用 OpenCode Go，base_url 不是官方 Anthropic，MiniMax 旧 key 已注释。

### Step 5: CLI 跑模型 — 可能 401/403

```bash
hermes -m minimax-m3 -z "say hi in chinese"
# 可能: HTTP 401: invalid api key
# 或:   HTTP 403: Request not allowed
```

**根因**: 同 session 的 hermes CLI 进程在启动时读了 .env，缓存了旧 key / 旧 base_url。改完 .env 后 CLI 不重新读。

**两种解法**:
1. 主人 `/new` 开新 session（最稳）
2. 临时绕：`env -i ANTHROPIC_BASE_URL=https://opencode.ai/zen/go ANTHROPIC_API_KEY=sk-zHo...lzFs hermes -m minimax-m3 -z "hi"`

**不要**:
- 死磕 `hermes -m opencode-go/minimax-m3`（CLI 不认 OpenCode 的 providerKey 命名格式，403）
- 重装 hermes（不是 CLI 的问题）

## 故障对照表

| 现象 | 根因 | 修法 |
|------|------|------|
| MCP `provider_add` 报 `fetch failed` | agent sandbox 限网络 | 改 .env + config.yaml |
| `hermes -m <m>` 401 invalid api key | CLI 缓存旧 .env | `/new` 或 `env -i` 绕 |
| `hermes -m opencode-go/<m>` 403 | CLI 不认这个 providerKey | 改用 `hermes -m <m>`（base_url 走 .env） |
| `doctor` 报 `Anthropic API couldn't verify` | base_url 不是官方 | 正常，看 OpenCode Go 那行 |
| `doctor` 报 `MiniMax invalid` | 旧 key 注释后还在 .env | 正常，或彻底删那行 |
| 直接 curl 也失败 | key 错 / 端点错 / 协议错 | 查 `https://opencode.ai/zen/go/v1/models` |

## OpenCode Go 协议速查

- 端点 base: `https://opencode.ai/zen/go`
- Anthropic 兼容（minimax 系列）: `POST /v1/messages`
  - Headers: `x-api-key` + `anthropic-version: 2023-06-01`
  - Body: 标准 Anthropic messages 格式
- OpenAI 兼容（GLM/Kimi/DeepSeek/Qwen/MiMo）: `POST /v1/chat/completions`
- 模型列表: `GET /v1/models` — `Authorization: Bearer sk-...`

## 关键学习

1. **agent sandbox 内的网络出站 ≠ terminal 工具** — 终端 `curl` 通不等于 MCP 工具通
2. **CLI 缓存 .env 是 Hermes 设计, 不是 bug** — 改 .env 后必须 /new
3. **MCP 工具失败时, fallback 永远存在** — 直接改配置文件即可, 不必死磕工具
4. **API 直通测试比 doctor 报告更可靠** — doctor 是 hint, curl 是 truth
5. **OpenCode Go 比 MiniMax 直连便宜且稳** — $10/月 vs 按 token 计费, 5h/周/月限额是软上限
