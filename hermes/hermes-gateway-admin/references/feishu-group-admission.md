# Feishu 群消息准入 — 静默拒绝的机制、诊断与策略矩阵

## 准入管线（顺序是诊断的基础）

`_handle_message_event_data()`（websocket 与 webhook 共用）按序执行：

1. 结构校验（message/sender 存在）
2. **去重 `_is_duplicate()`** — 写 `~/.hermes/feishu_seen_message_ids.json`，**写文件发生在 admission 之前**
3. `_admit()` 准入闸门 — 拒绝原因：`self_echo` / `self_ids_unknown` / `bots_disabled` / `bot_not_mentioned` / `group_policy_rejected` / `dm_policy_rejected`，**只打 DEBUG 级日志**
4. `_process_inbound_message()` — 打 INFO "Inbound dm/group message received" 进 batch/guard 管线

推论：**seen 文件里有、日志里没有的消息，死在第 3 步**，且默认 INFO 日志级别下完全不可见。

## `_admit()` 决策树

- 发送者是 bot 自身 → `self_echo`
- 发送者是 bot 且 `FEISHU_ALLOW_BOTS=none`（默认）→ `bots_disabled`
- **单聊（p2p）**：`FEISHU_ALLOW_ALL_USERS` 开**或**白名单为空 → 放行（pairing 模式设计）；白名单非空且发送者不在 → `dm_policy_rejected`
- **群聊**：`_allow_group_message()` 策略判定不通过 → `group_policy_rejected`；`require_mention` 开但没 @ 到 bot → `group_policy_rejected`；@_all 也算 mention

白名单空 + 默认 allowlist = 群消息全拒——"单聊活着、群里死了"的最常见根因。

## 策略配置来源

| 变量 / extra | 默认 | 作用 |
|---|---|---|
| `FEISHU_GROUP_POLICY`（.env） | `allowlist` | 全局群策略：open / allowlist / blacklist / disabled / admin_only |
| `FEISHU_ALLOWED_USERS`（.env） | 空 | 白名单（open_id 或 user_id，逗号分隔）；**非空后单聊也按它过滤** |
| `FEISHU_ALLOW_ALL_USERS`（.env） | false | 单聊全开（true/1/yes）；`GATEWAY_ALLOW_ALL_USERS` 同效 |
| `FEISHU_REQUIRE_MENTION`（.env） | true | 群里必须 @ bot 才回 |
| `FEISHU_ALLOW_BOTS`（.env） | none | none / mentions / all |
| config extra `group_rules` | — | 按 chat_id 覆盖 policy / allowlist / blacklist / require_mention |
| config extra `admins` | — | 管理员 open_id，永远放行 |
| config extra `default_group_policy` | — | 无 rule 群的兜底策略 |

## 差集诊断法

```bash
# seen（admission 前写入）
python3 -c "import json,os;print('\n'.join(json.load(open(os.path.expanduser('~/.hermes/feishu_seen_message_ids.json')))['message_ids']))"
# 日志（admission 后）
grep "Inbound .* message received" ~/.hermes/logs/gateway.log | tail -20
```

差集条目 = 被拒消息。要看具体拒绝原因，临时调 DEBUG 日志级别再复现。

## 修复与验证链

1. open_id 来源：单聊日志行 `sender=user:ou_xxx`（最快），或飞书开放平台。
2. `cp ~/.hermes/.env ~/.hermes/.env.bak` 后追加 `FEISHU_ALLOWED_USERS=ou_xxx[,ou_yyy]`。
3. 重启：Ubuntu `systemctl --user restart hermes-gateway.service`（~10s 内 Lark WS 重连，journal 里看 "connected to wss://msg-frontier.feishu.cn"）；macOS 对应 LaunchAgent kickstart。
4. 群里 @ 一条，验证四段日志缺一不可：`Received raw message` → `Inbound group message received` → `Flushing text batch ... group:oc_...` → `response ready` + `Sending response`。回慢是 agent 在跑工具（查 agent.log 会话 ID），不是网关问题。

## 相邻症状区分（先定位再动手）

- **seen 文件里也没有** → 事件根本没到 gateway：查机器人是否在那个群里、事件订阅权限（im.message.receive）、WS 连接状态（gateway_state.json 的 platforms.feishu.state=connected）。
- **Inbound 有但没回复** → agent 侧：查 agent.log 对应会话是否在跑工具、errors.log 有无异常。
- **有 Sending 但群里看不到** → 发送 API 失败：查 token / 权限 / 错误码。
- **重启后仍拒** → 确认 .env 真的被当前 profile 读到（multiplex 下 secondary profile 有自己的 .env）。
