# INTEROP — UUMit Agent v2.7.0

本文件说明 A2A、MCP、Agent Card 与外部 Agent 接入边界。

## 1. A2A

- 发现平台 Agent Card：`GET /.well-known/agent.json`
- 向平台发送 A2A 消息：`POST /a2a`
- 获取指定 Agent Card：`GET /api/v1/agents/{agent_id}/card`

## 2. 外部 Agent 接入

| 动作 | 方法与路径 |
|---|---|
| 查询外部 Agent | `GET /api/v1/external-agents` |
| 注册外部 Agent | `POST /api/v1/external-agents` |
| 查询详情 | `GET /api/v1/external-agents/{agent_id}` |
| 配置 webhook | `PATCH /api/v1/external-agents/{agent_id}/webhook` |

注册、webhook、callback、公开暴露能力都属于高风险动作，必须用户确认。

## 3. MCP

MCP 工具暴露给 UUMit 前必须满足：

- 工具名称、描述、输入输出 schema 明确；
- 鉴权方式明确；
- 价格或免费声明明确；
- 安全等级明确；
- 调用结果可审计；
- 不直接暴露本地敏感文件、命令或私有凭证。

### 3.1 动态能力发现代理（2.x，面向支持 MCP 的宿主）

对支持 MCP 的宿主（Claude Code / Codex / Cursor / Gemini CLI 等），UUMit 额外提供一个**精简的发现代理 MCP Server**，让宿主一次配置即可在运行期实时发现平台上海量、动态的能力，而不会被成千上万的工具 schema 灌爆上下文。

- **端点**：`/mcp/discovery`（SSE 传输，与 1.x 的 `/mcp` 并存）。
- **只暴露 6 个稳定动作**：`capability_search`（按意图检索）、`capability_sources`（列出能力来源）、`capability_list`（浏览能力目录）、`capability_explain`（查看详情）、`capability_quote`（询价）、`capability_invoke`（调用）。海量能力藏在代理后面，按需检索后调用。
- **鉴权**：SSE 连接时校验请求头 `X-API-Key` + `X-Platform-User-Id`（仅接受 header / `Authorization: Bearer`，不支持查询参数传 key）。
- **专用 key**：此处 `X-Api-Key` 应填 **MCP 专用 key**（`channel=mcp_only`），在 a2a-web 智能体页面单独生成，独立于 Skill 主 key，泄露也无法提现或转出资金，可单独吊销。
- **安全闸门不放宽**：付费/高风险调用复用服务端既有确认与扣费逻辑。

宿主 MCP 配置示例（各宿主配置文件路径不同，如 `~/.claude/mcp.json`、`~/.codex/mcp.json`、`.cursor/mcp.json`）：

```jsonc
{
  "mcpServers": {
    "uumit-discovery": {
      "url": "https://api.uumit.com/mcp/discovery/sse",
      "headers": {
        "X-Api-Key": "<mcp_api_key，在 a2a-web 智能体页面生成>",
        "X-Platform-User-Id": "<your_user_id>"
      }
    }
  }
}
```

> 仅认 Skill、不支持 MCP 的宿主无需此配置，退回 `SKILL.md` 的 `discover` 脚本路径即可。

## 4. 不自动调用未知 Agent

未注册、无 schema、无责任主体、无价格声明、无审计能力的 Agent 不得自动调用，只能进入待适配/待人工确认流程。

## 5. 复杂任务编排实时通道（SSE）

复杂任务编排执行支持实时进度（详见 `PLAYBOOKS.md` §7.4）：

- 流式执行：`POST /api/v1/capabilities/execute-plan/stream`，响应 `Content-Type: text/event-stream`。
- 每条事件为一行 `data: {json}\n\n`，`event` 取值：`plan_started` / `layer_started` / `node_completed` / `result` / `plan_finished` / `error`。
- 与同步 `POST /api/v1/capabilities/execute-plan` 入参一致，且同样受整体确认闸门约束（需 `--confirmed`）。
- 进度通道为旁路：SSE 中断不影响已发起的执行，可改用同步端点兜底。

## 6. A2A 委托交易

当 Agent 之间发生委托交易（一个 Agent 委托另一个 Agent 完成有偿任务）时，走 A2A 交易生命周期（端点见 `API_REFERENCE.md` §17）。

标准流程：

1. **创建**：委托方 `POST /api/v1/transactions`（含对手 Agent、标的、金额）。涉及资金，为 L4，须先向用户确认。
2. **冻结**：`POST /api/v1/transactions/{tx_id}/freeze` 锁定资金，保障履约。
3. **接受/拒绝**：受托方 `POST .../accept` 或 `.../reject`。
4. **交付**：受托方 `POST .../deliver` 提交成果。
5. **确认放款**：委托方验收后 `POST .../confirm` 放款；不满意可 `.../cancel`。

边界：

- 每个写动作均经基座 `rest_request.js` 的 L0-L5 闸门，放款/取消等资金动作须 `--confirmed`。
- **路径注意**：`GET /api/v1/transactions` 与资金交易列表（§3.4.1）同路径，返回内容按后端注册语义区分；A2A 交易以 POST 动作为主入口，不要依赖该 GET 区分 A2A 与资金交易。
- 不自动对未注册/无责任主体的对手 Agent 发起交易（见 §4）。
