---
name: uumit-compute
description: "UUMit 算力共享扩展。当用户说「算力」「共享算力」「模型调用」「BYOK」「算力收入」「共享我的 Key」时使用：算力共享市场的搜索、调用、凭证共享上架、代管与结算。本扩展无独立脚本——算力共享的全部端点均为 JSON、可经基座 uumit-agent 的 rest_request.js 直接调用（自动过安全闸门）。本 SKILL.md 仅作能力引导，指导 Agent 调用哪些端点。"
version: 2.7.0
user-invocable: true
homepage: https://m.uumit.com
requires-base: "uumit-agent >=2.0.0"
metadata: {"agent_skill":{"key":"uumit-compute","aliases":["算力","算力共享","共享算力","模型调用","BYOK","算力收入","compute share","compute-share"],"version":"2.7.0","requires":{"base_skill":"uumit-agent","base_version":">=2.0.0"},"runtime":{"node":">=18","packages":[]},"permissions":["exec:node:{UUMIT_SKILL_DIR}/scripts/rest_request.js"],"no_scripts":true,"output_contract":"machine: base rest_request.js emits JSON on stdout; human: summarize, never paste stdout/stderr to user"}}
---

# uumit-compute — UUMit 算力共享扩展（v2.7.0）

`uumit-agent` 基座的算力共享能力引导。**本扩展无独立脚本**：算力共享的端点均为 JSON、API Key 可用，由基座 `rest_request.js` 直接调用即可，无独立运行模式或安全边界（收敛开放问题 1）。

## 定位与边界

- **纯引导，无脚本**：本扩展只提供"何时进入算力共享、调哪些端点"的引导。实际调用走基座 `node scripts/rest_request.js <METHOD> <PATH>`，自动过 allowlist + L0-L5 安全闸门。
- **凭证敏感**：BYOK / Token 包 API Key 为敏感字段，Agent 内部处理后**禁止**粘贴到聊天。
- **写操作需确认**：共享上架、撤销凭证、绑定官方 Key 等会改变资产/资金状态，须先向用户确认。
- **依赖基座**：需先安装 `uumit-agent >=2.0.0` 并完成授权。

## 何时加载

| 触发条件 | 动作 |
|---|---|
| 用户说「算力」「共享算力」「模型调用」 | 查状态/摘要，按需调用 |
| 用户说「共享我的 Key」「BYOK」 | 凭证创建/上架流程 |
| 用户说「算力收入」 | 查调用流水/收益 |

## 核心入口端点（经基座 rest_request.js 调用）

| 用途 | 方法与路径 | 说明 |
|---|---|---|
| 功能开关状态 | `GET /api/v1/compute-share/status` | 无需认证；先确认功能开启 |
| 我的算力摘要 | `GET /api/v1/compute-share/my/summary` | 聚合视图 |
| 我的调用流水 | `GET /api/v1/compute-share/calls` | 供给/消费视角收入 |
| 我的凭证列表 | `GET /api/v1/compute-share/credentials` | 只读 |
| 创建共享凭证 | `POST /api/v1/compute-share/credentials` | BYOK / 官方 Key；写操作须确认 |

> 完整端点（凭证测试、模型同步、官方通道、代管、结算等）见服务端《算力共享Skill接入落地方案》；新增端点按需补进基座 allowlist 与 `API_REFERENCE.md`。

## 用法示例

前置：确保 `UUMIT_SKILL_DIR` 指向基座目录，且基座已授权。

```bash
# 先确认算力共享功能开启
node "$UUMIT_SKILL_DIR/scripts/rest_request.js" GET /api/v1/compute-share/status

# 查我的算力摘要
node "$UUMIT_SKILL_DIR/scripts/rest_request.js" GET /api/v1/compute-share/my/summary
```
