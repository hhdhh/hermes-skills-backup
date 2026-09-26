---
name: feishu-bot-messaging
description: Use when 同事说给 bot 发私信没回复、要查谁私聊过、要给同事发私信测试、或 bot 收不到 inbou...
version: 0.1.0
---

# 飞书 bot 私聊收发诊断

> 完整描述：运营助手飞书 bot 私聊收发诊断与恢复。Use when 同事说给 bot 发私信没回复、要查谁私聊过、要给同事发私信测试、或 bot 收不到 inbound 消息事件。

## 能发 ≠ 能收：两层独立链路

- **发**：`lark-cli im +messages-send --user-id <open_id> --as bot` → 飞书 im/v1 API，不依赖事件订阅。发送成功仅证明投递到飞书服务器。
- **收**：飞书把新消息作为 `im.message.receive_v1` 事件推到 gateway 的 WebSocket 长连接。**事件订阅是在 WebSocket 建立时协商的**——订阅是事后才配的话，存量连接收不到，必须重启 gateway 重建连接（重启前先向用户确认，不擅自动服务）。

## 诊断流程（按序）

1. **查 gateway 日志有没有 inbound**：`grep "Inbound dm message" ~/.hermes/logs/gateway.log | tail`。日志里有 → 事件链路正常，问题在会话/白名单层。
2. **确认 WebSocket 在线**：`grep "Connected in websocket mode" ~/.hermes/logs/gateway.log | tail -1` 看最近一次连接时间；晚于用户在开放平台配置事件订阅的时间才会生效。
3. **白名单**：查 `~/.hermes/.env` 的 `FEISHU_ALLOWED_USERS`（`*` = 允许所有人；群另有 `FEISHU_GROUP_POLICY`）。
4. **主动拉取消息历史兜底**（用户说"给你发了私信但没回复"时，先拉消息再答复）：
```bash
TENANT_TOKEN=$(curl -sS -X POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal -H 'Content-Type: application/json' -d '{"app_id":"...","app_secret":"..."}' | python3 -c "import json,sys;print(json.loads(sys.stdin.read())['tenant_access_token'])")
curl "https://open.feishu.cn/open-apis/im/v1/messages?container_id_type=chat&container_id=<chat_id>&page_size=20" -H "Authorization: Bearer $TENANT_TOKEN"
```
bot→用户的 chat_id 从发送返回值里拿；消息按时间序排，user/app 字段区分方向。拉到的问题要**先回复对方**再解释原因。

## 回执与会话查询

- 谁读了我的消息：`lark-cli im +message-read-users --message-id om_xxx --as bot`（返回 user open_id 列表；空 = 未读）。
- `+chat-list --types p2p --as bot` 通常返回空——**p2p 会话要对方先发过消息才可见**，不能用"列表为空"证明没人私聊。真正的会话注册表在 `~/.hermes/channel_directory.json`。
- `+messages-read-status` 只支持 user 身份，bot 不可用。

## 已验证的模式

- 三个部门（运营/广州FAE/深圳FAE）各挑一人发测试消息即可验证全员私聊可用；发送 230013 "Bot has NO availability to this user" = 开放平台应用可用范围未含该用户，需管理员调整，不是代码问题。
- 部门成员清单：原生 API `GET /open-apis/contact/v3/users/find_by_department?department_id=<open_department_id>&department_id_type=open_department_id`（tenant token）；部门树 `GET /open-apis/contact/v3/departments?department_id=0&fetch_child=true`。
- 回复拉到的历史消息：直接用 im/v1 messages API 按聊天回复（receive_id_type=chat_id），绕过事件链路。
