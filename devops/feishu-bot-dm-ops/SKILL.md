---
name: feishu-bot-dm-ops
description: Use when 同事私聊 bot 没收到/没回复、配置 FEISHU_ALLOWED_USERS、排查 inbo...
version: 0.1.0
---

# 飞书 bot DM 运维（运营助手）

> 完整描述：飞书 bot 私聊收发与网关白名单运维。Use when 同事私聊 bot 没收到/没回复、配置 FEISHU_ALLOWED_USERS、排查 inbound 丢失、或需要以 bot 身份给同事发私信。

## 症状速查：别人私聊 bot 但 bot 没回

排查顺序（每步都有实测命令）：

1. **消息到底发没发出来** —— 拉 bot 视角的消息历史（飞书服务器侧真相）：
   ```bash
   # tenant_access_token 见 lark-shared；chat_id 是 bot↔该用户 p2p 会话
   curl "https://open.feishu.cn/open-apis/im/v1/messages?container_id_type=chat&container_id=<p2p_chat_id>&page_size=10" -H "Authorization: Bearer $TENANT_TOKEN"
   ```
   - 服务器有、gateway 日志无 inbound → 消息被本地策略丢弃或事件没送达
2. **gateway 日志有没有 inbound**：`grep Inbound ~/.hermes/logs/gateway.log | tail`
3. **白名单命中**（最常见根因，见下）
4. **事件订阅**（开放平台后台 im.message.receive_v1）改过的话要重启 gateway 才生效

## 核心坑：FEISHU_ALLOWED_USERS 的 `*` 不是通配符

- `FEISHU_ALLOWED_USERS`（~/.hermes/.env）只认 open_id 的字面列表；写 `*` 只是一个匹配不到任何人的字符串，导致**非白名单用户的 DM 被静默丢弃**（日志里几乎无痕迹，adapter 返回 `dm_policy_rejected`）。
- 要允许全员私聊：逐个写入 open_id（用 `contact/v3/users/find_by_department` 按部门拉齐），或设 `FEISHU_ALLOW_ALL_USERS=true`。
- DM 放行判定 = `_allow_all_dm` 为真 **或** sender open_id 命中白名单。群消息走另一套 FEISHU_GROUP_POLICY。
- 编辑 .env 后必须重启 gateway（见下）。多行同名变量时后行覆盖前行，历史追加会留多行——清理成一行再验证 `grep -c`。

## gateway 重启（改 .env / 事件订阅后生效）

- **不能从会话内重启**：terminal/execute_code 都会被安全机制拦（gateway 不能杀自己）。不要尝试 setsid/Popen 绕过，同样被拦。
- 正确做法：让用户在外部终端跑 `~/restart-hermes-gateway.sh`（内容为 `systemctl --user restart hermes-gateway.service` + 状态确认）。本机 gateway 是 systemd user service `hermes-gateway.service`。
- 重启后验证：`systemctl --user show hermes-gateway -p ActiveEnterTimestamp` + 日志尾部有 `Connected in websocket mode (feishu)`。

## bot 主动私聊同事

```bash
lark-cli im +messages-send --user-id <open_id> --text "..." --as bot
```
- 发送成功 ≠ 对方能回；对方回复依赖上面白名单放行。
- 已读状态：`lark-cli im +message-read-users --message-id <om_...> --as bot`（bot 可用；+messages-read-status 只支持 user）。
- bot 的 p2p 会话列表（`+chat-list --types p2p --as bot`）为空属正常——对方先发消息才形成会话。

## 排查"谁私聊过 bot"

- gateway 侧：`grep Inbound ~/.hermes/logs/gateway.log`（最准确）+ `~/.hermes/channel_directory.json` 的 feishu 会话列表。
- bot 发出去的消息用 read-users 查已读。
