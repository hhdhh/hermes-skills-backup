# 多 Agent 所有权、Memory Wiki 与 Heartbeat 配置验收

适用于 OpenClaw 已配置多个显式 agent 后，配置操作、插件发现或 ambient service 报：

```text
AgentSelectionRequiredError: Multiple agents are configured, but this operation has no explicit owner
```

## 核心判断

这通常不是 Gateway 损坏，而是多 Agent fleet 已进入显式所有权模式，但 ambient/unscoped surface 没有 owner。

优先设置：

```json5
{
  agents: {
    defaults: {
      systemAgent: { agentId: "main" },
      heartbeat: {
        agentId: "main"
      }
    }
  }
}
```

- `agents.defaults.systemAgent.agentId`：负责未显式带 `--agent` 的系统 Agent、插件发现、模型/技能/记忆状态读取等 ambient surface。
- `agents.defaults.heartbeat.agentId`：负责默认 heartbeat，避免 fleet 中 owner 不明确。
- 诊断命令仍优先显式传 `--agent main`，不要依赖 ambient fallback。

## 安全应用顺序

1. 读取当前值与 schema：
   ```bash
   openclaw config get agents.defaults.systemAgent --json
   openclaw config get agents.defaults.heartbeat --json
   openclaw config schema --json
   openclaw agents list --json
   ```
2. 检查各 agent 是否已有 heartbeat override：
   ```bash
   openclaw config get agents.entries.main.heartbeat --json
   openclaw config get agents.entries.product-agent.heartbeat --json
   openclaw config get agents.entries.dev-agent.heartbeat --json
   ```
   “valid but unset”表示继承 defaults，不是错误。要避免重复 heartbeat，应保证非 owner agent 没有显式 heartbeat。
3. 备份 `openclaw.json`。
4. 将所有目标值放进一个 JSON5 patch，先 dry-run：
   ```bash
   openclaw config patch --file /tmp/change.json5 --dry-run --json
   ```
5. 一次性应用并校验：
   ```bash
   openclaw config patch --file /tmp/change.json5
   openclaw config validate --json
   ```
6. 仅当 CLI 明确提示 restart required，或变更涉及插件加载/ambient service owner 时重启 Gateway。
7. 重启后逐路径 `config get`，再做运行态验收。

## Memory Wiki 运行态验收

只看配置文件不够。至少验证：

```bash
openclaw plugins info memory-wiki --json
openclaw wiki doctor --agent main --json
openclaw wiki status --agent main --json
```

成功标准：

- plugin 为 `loaded`、`enabled`、`activated`
- `wiki doctor` 为 `healthy: true`
- Vault path/scope/renderMode 与目标一致
- bridge flags 全部符合目标
- Obsidian official CLI 在 requested=true 时应显示 available=true

## Embedding provider readiness：先实测，后落配置

不要把“有 API key”当作“embedding 可用”。应分层验证：

1. `openclaw memory status --agent main --deep --json`：读取当前 provider、model 和 embeddingProbe。
2. 对已有凭证候选，调用其真实 embedding endpoint 做最小请求，确认 HTTP 成功且返回非空向量维度。
3. 对本地候选，检查 provider plugin/readiness；不要仅因为 schema 接受 `local` 就认为运行时已注册。
4. 只有实测返回向量的 provider 才写入 `memory.search.provider/model/remote`。
5. 没有可用候选时，保持 `memory.search.enabled=true`，明确报告 semantic/vector blocker，并实测 FTS/关键词回退：
   ```bash
   openclaw memory search --agent main --query "known term" --max-results 3 --json
   ```

不要为了通过验收擅自安装 provider plugin、增加凭证或改变用户未授权的 provider 配置。

## Heartbeat 验收注意

Gateway 重启后 heartbeat 可能立即跑一次。检查：

```bash
openclaw system heartbeat last --json
openclaw logs --plain --no-color --limit 300
```

配置正确不等于首次运行成功。若 `timeoutSeconds` 是用户明确指定值，而首次运行严格在该边界超时：

- 如实报告运行失败；
- 不擅自提高 timeout；
- 区分“owner/路由已修复”和“heartbeat agent turn 超时”两个问题。

## 易错点

- 不要把审批挂起误诊成配置未写入；先 `config get` 确认当前状态。
- 系统一次只允许一个 pending change 时，后续修改应等待批准，批准后改用单个原子 patch，避免多次审批和半配置状态。
- `rememberAcrossConversations=true` 可能让运行态状态中出现 session recall，即使 authored `sources=["memory"]`；最终以逐路径 authored 配置验证和实际搜索来源共同判断，不要擅自“纠正”用户值。
- 不要声称 heartbeat 正常送达，除非 `heartbeat last` 和日志都证实成功。
