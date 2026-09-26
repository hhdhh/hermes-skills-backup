---
name: hermes-feishu-dm-ops
description: Use when 同事私聊 bot 没反应/收不到消息、配置 FEISHU_ALLOWED_USERS 白名单、排...
version: 0.1.0
---

# 飞书 bot 私聊 / gateway DM 放行运维

> 完整描述：飞书 bot 私聊接入与网关 DM 放行运维。Use when 同事私聊 bot 没反应/收不到消息、配置 FEISHU_ALLOWED_USERS 白名单、排查 inbound 事件、需要重启 gateway、或验证私聊链路。

## 症状→定位速查

| 症状 | 根因 | 验证手段 |
|---|---|---|
| bot 能发出私信，但对方回复我收不到 | DM 白名单没命中（`dm_policy_rejected` 静默丢弃，**无任何日志**） | 拉飞书 API 消息历史对比 gateway.log |
| 飞书 API 里有消息、gateway.log 完全无事件 | 事件订阅（`im.message.receive_v1`）未生效或 WS 建连早于订阅 | 后台核对订阅 + 重启 gateway |
| 只有管理员（approved user）能聊 | DM pairing 模式：仅 `hermes pairing list` 里 approved 的用户放行 | `hermes pairing list` |

## DM 白名单规则（关键坑）

- `FEISHU_ALLOWED_USERS` 里的 `*` **不是通配符**——`_id_set` 只做 strip，`*` 是字面字符串，匹配不到任何人。要放开某人必须写其 `ou_` open_id 全量。
- DM 放行条件（adapter `_admit`）：`_allow_all_dm`（`FEISHU_ALLOW_ALL_USERS=true`）或 sender open_id 在 `_allowed_group_users` 命中。二者其一。
- 白名单是启动时快照——改 `.env` 后必须重启 gateway 才生效。
- 被拒的消息**静默丢弃，日志里查不到**。判断是否被白名单拒：用飞书 API 拉 chat 消息历史（`/open-apis/im/v1/messages?container_id_type=chat&container_id=<chat_id>`），若消息存在于飞书侧但 gateway.log 无 `Inbound dm message received`，即是放行层问题。

## 验证/排查流程

1. gateway 侧：`grep "Inbound" ~/.hermes/logs/gateway.log | tail`——看有没有目标用户的消息事件。
2. 飞书侧：tenant_access_token + `/open-apis/im/v1/messages` 拉对方 chat 历史，确认消息确实发出。
3. `hermes pairing list`——确认不是 pairing 审批问题。
4. 两侧都有但没进 → 白名单/事件订阅 → 改 `.env` → 重启。
5. 两侧都没有 → 用户发错对象（发到别的会话/群/同名机器人），让用户直接点开 bot 发过的历史私信回复。

## gateway 重启（外部终端）

- **不能从 agent 会话内重启 gateway**——agent 跑在 gateway 进程树里，命令会被安全机制拦截（SIGTERM 连坐）。`systemctl --user restart`、`hermes gateway restart`、subprocess+setsid 全部会被挡。
- 正确方式：让用户在外部终端跑 `~/restart-hermes-gateway.sh`（已存在的脚本：`systemctl --user restart hermes-gateway.service` + 状态确认）。
- 重启后验证：`systemctl --user show hermes-gateway.service -p ActiveEnterTimestamp` + 日志出现 `Connected in websocket mode`。

## bot 能力边界（lark-cli / API）

- bot 的 p2p 会话列表通常查不到（对方没先发过消息时）——`im +chat-list --types p2p --as bot` 返回 0 不代表坏了。
- `im +messages-read-status` 只支持 user 身份；bot 查已读用 `im +message-read-users`。
- bot 主动给同事发私信用 `lark-cli im +messages-send --user-id <ou_xxx> --as bot`；深格式（reply/富文本）也可用 tenant_access_token 直调 `/open-apis/im/v1/messages`。
- 运维中给同事回消息的两条路：lark-cli bot 身份，或原生 API（前者优先）。

## 常用数据

- 飞书 App：`cli_aaf0558a8fb81cbb`（tenant token 用 app_id+secret 换取）。
- 白名单当前 = 公司全员 open_id 列表（运营部/广州FAE/深圳FAE 21 人）+ 管理员。人员 open_id 来源：通讯录部门接口 `contact/v3/users/find_by_department?department_id=<open_department_id>`。
- 新同事入职要私聊 bot：把 open_id 追加进 `FEISHU_ALLOWED_USERS`（保持一行，防多行重复），然后重启 gateway。
