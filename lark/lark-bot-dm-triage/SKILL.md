---
name: lark-bot-dm-triage
description: Use when 用户说「给XX发私信/测试私聊」「谁和你私聊过」「XX给你发消息没回」，或需要验证 bot 私聊...
version: 0.1.0
---

# bot 私聊收发与排查（运营助手）

> 完整描述：运营助手 bot 与同事私聊的收发与排查。Use when 用户说「给XX发私信/测试私聊」「谁和你私聊过」「XX给你发消息没回」，或需要验证 bot 私聊投递、找回同事发来但未收到回复的消息。

## 发私信

```bash
lark-cli im +messages-send --user-id ou_xxx --text "..." --as bot
```
- 收件人 open_id 用部门拉取（原生 OpenAPI `/contact/v3/users/find_by_department?department_id=od-xxx&department_id_type=open_department_id`）或 lark-cli contact 搜。
- 返回的 `chat_id` 要留存——后续查该会话历史全靠它。

## 验证投递与已读

```bash
# 谁读了这条消息（bot 身份可用）
lark-cli im +message-read-users --message-id om_xxx --as bot
# 读回执聚合查询仅支持 user 身份，--as bot 会被拒
```

## 排查「同事发消息给 bot 但没回复」

**不要信 `+chat-list --types p2p --as bot`**——返回 0 不代表没人私聊；对方未先回复时会话不进列表。

真实检查步骤：用 tenant_access_token 直接拉会话历史：

```bash
TOKEN=$(curl -sS -X POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal \
  -H "Content-Type: application/json" \
  -d '{"app_id":"...","app_secret":"..."}' | jq -r .tenant_access_token)

curl -sS "https://open.feishu.cn/open-apis/im/v1/messages?container_id_type=chat&container_id=oc_xxx&page_size=20" \
  -H "Authorization: Bearer $TOKEN"
```

- `sender_type=user` 的消息就是同事发来的。看完用同一 chat_id 的 `im/v1/messages` POST 回复（msg_type=text，content 是 JSON 字符串）。
- **根因模式**：若 gateway 显示 feishu connected 但用户消息从未出现在 channel_directory.json，多半是开放平台后台未订阅 `im.message.receive_v1` 事件（事件与回调页）。发送 API 不受影响，只有接收断。修复需管理员在 open.feishu.cn/app/<app_id> 后台开事件订阅。

## 每次私聊类任务后的固定动作

发完或排查完，报给用户一张表：收件人 / 时间 / 消息 ID / 投递与已读状态。凭据（App Secret、token）不回显在回复里。
