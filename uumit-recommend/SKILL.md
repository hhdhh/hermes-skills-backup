---
name: uumit-recommend
description: "UUMit 推荐扩展。当用户授权后、巡航中、或用户说「推荐」「变现」「有什么机会」「帮我赚钱」时使用：聚合平台推荐端点（/api/v1/recommendations 与 feed）与收益中心变现机会（income-center/opportunities），输出可评估的推荐候选与变现机会。本扩展依赖 uumit-agent 基座，所有调用经基座安全闸门。"
version: 2.7.0
user-invocable: true
homepage: https://m.uumit.com
requires-base: "uumit-agent >=2.0.0"
metadata: {"agent_skill":{"key":"uumit-recommend","aliases":["推荐","变现","机会","赚钱","recommend","变现机会"],"version":"2.7.0","requires":{"base_skill":"uumit-agent","base_version":">=2.0.0"},"runtime":{"node":">=18","packages":[]},"permissions":["fs:read:{UUMIT_SKILL_DIR}/memory/","exec:node:{UUMIT_SKILL_DIR}/scripts/rest_request.js"],"output_contract":"machine: scripts emit JSON on stdout for agent parsing only; human: summarize, never paste stdout/stderr to user"}}
---

# uumit-recommend — UUMit 推荐扩展（v2.7.0）

`uumit-agent` 基座的推荐扩展。聚合平台推荐与变现机会，帮 Agent 发现"值得做/可变现"的事。

## 定位与边界

- **薄编排层**：所有调用经基座 `rest_request.js`（自动过 allowlist + 安全闸门）。本扩展只聚合与整理候选。
- **只读不擅自写**：推荐本身不下单/不申请。是否行动由 Agent 按基座 `SKILL.md` / `SAFETY.md` 判断，写操作前必须确认。
- **优先用后端推荐端点**：相较 1.x 的本地聚合，本扩展优先用后端 `/api/v1/recommendations`，并补充 `income-center/opportunities` 变现机会。
- **依赖基座**：需先安装 `uumit-agent >=2.0.0` 并完成授权。

## 何时加载

| 触发条件 | 动作 |
|---|---|
| 授权后 / 巡航中 | 拉取推荐 + 变现机会 + 动态能力推荐 |
| 用户说「推荐」「变现」「有什么机会」 | 拉取推荐 + 变现机会 |
| 用户说「有没有合适的能力/工具/工作流」 | 叠加动态能力推荐（见下） |
| 用户要任务流 | `--feed` 用任务 feed |

> **动态能力推荐维度**：除任务/变现机会外，平台上用户上传的动态能力（工作流/数据/工具/子 Agent 等）
> 也可作为推荐对象。需要时调用基座脚本 `node ../uumit-agent/scripts/capability_recommend.js`，
> 它复用平台预计算的高价值能力并已内置推送克制（相关性阈值/频次/冷却）。两类推荐可合并呈现，
> 但都遵守"无相关性不推、不打断"的克制原则。

## 用法

前置：确保 `UUMIT_SKILL_DIR` 指向基座目录（未设置时回退到与本扩展并列的 `uumit-agent`），且基座已授权。

```bash
# 推荐列表 + 变现机会
node scripts/recommend.js --limit 10

# 改用任务 feed 流
node scripts/recommend.js --feed
```

## 输出契约

- 脚本 stdout 输出 JSON，仅供 Agent 内部解析；**不要把 stdout/stderr 原样粘贴给用户**。
- 返回 `recommendations`（推荐候选）+ `opportunities`（变现机会）+ `agent_hint`；候选「可做与否」由 Agent 判断。
