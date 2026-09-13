---
name: uumit-social
description: "UUMit 社交/互动扩展。当用户说「签到」「翻牌」「红包」「科锦」「邀请」「信用」「好友」「搭子」时使用：聚合 Agent 可读的社交状态（信用/邀请/红包/好友），并支持 API Key 可用的写动作（领红包）。签到/翻牌/时间胶囊为 JWT-only，Skill 端无法直接调用，提供大厅深链引导用户到 App/Web 完成。本扩展依赖 uumit-agent 基座。"
version: 2.7.0
user-invocable: true
homepage: https://m.uumit.com
requires-base: "uumit-agent >=2.0.0"
metadata: {"agent_skill":{"key":"uumit-social","aliases":["签到","翻牌","红包","科锦","邀请","信用","好友","搭子","social","大厅"],"version":"2.7.0","requires":{"base_skill":"uumit-agent","base_version":">=2.0.0"},"runtime":{"node":">=18","packages":[]},"permissions":["exec:node:{UUMIT_SKILL_DIR}/scripts/rest_request.js"],"output_contract":"machine: scripts emit JSON on stdout for agent parsing only; human: summarize, never paste stdout/stderr to user"}}
---

# uumit-social — UUMit 社交/互动扩展（v2.7.0）

`uumit-agent` 基座的社交扩展。聚合社交状态与互动，覆盖大厅互动、邀请、红包、信用、好友。

## 定位与边界

- **薄编排层**：API Key 可用的端点经基座 `rest_request.js` 调用（自动过安全闸门）。
- **JWT-only 走深链**：签到、翻牌、时间胶囊等需 JWT（非 API Key）的互动，Skill 端**无法直接调用**，按基座 `DEEP_LINKS.md` 引导用户到 `{APP_BASE_URL}/hall` 自行完成，**不要伪造结果**。
- **写操作需确认**：领红包等写动作虽允许，仍应先告知用户。
- **依赖基座**：需先安装 `uumit-agent >=2.0.0` 并完成授权。

## 何时加载

| 触发条件 | 动作 |
|---|---|
| 用户说「信用」「邀请」「好友」 | `status` 聚合只读状态 |
| 用户说「红包」「科锦」 | `status` 查红包；`claim-redpacket` 领取 |
| 用户说「签到」「翻牌」 | 给出 `{APP_BASE_URL}/hall` 深链 |

## 用法

前置：确保 `UUMIT_SKILL_DIR` 指向基座目录（未设置时回退到与本扩展并列的 `uumit-agent`），且基座已授权。

```bash
# 聚合社交状态（信用/邀请/红包/好友，只读）
node scripts/social.js status

# 领红包（API Key 可用的写动作）
node scripts/social.js claim-redpacket --id <batch_id>
```

## 输出契约

- 脚本 stdout 输出 JSON，仅供 Agent 内部解析；**不要把 stdout/stderr 原样粘贴给用户**。
- `status` 返回 `credit`/`invite`/`red_packet`/`buddy` 聚合 + `deep_link_only` 提示；JWT-only 互动给深链。
