---
name: feishu-bot-dm
version: 1.0.0
description: Use when 同事私聊 bot 没回、要主动给同事发私信、排查谁私聊过、配置 DM 白名单。
---

# 飞书 bot 私聊(DM)操作

> 完整描述：操作 Hermes 飞书 bot 的私聊(DM)链路:收/读/主动发。Use when 同事私聊 bot 没回、要主动给同事发私信、排查谁私聊过、配置 DM 白名单。含 FEISHU_ALLOWED_USERS `*` 非通配符陷阱与 `POST /im/v1/messages` 发送规范。

## 收消息链路与“没回”的根因排查顺序

飞书 bot 收到别人私聊,消息走的链路:飞书服务器 → WebSocket 事件(im.message.receive_v1) → gateway 日志 `Inbound dm message received`。排查“有人发消息但没回”,按此顺序:

1. **gateway 日志**能否看到该用户消息: `grep 'Inbound dm message received' ~/.hermes/logs/gateway.log | grep <open_id>`。看到 = WS 收到;没看到 = 事件层就被吞了。
2. **DM 白名单**: `FEISHU_ALLOWED_USERS=<open_id 逗号列表>`。**列表里的 `*` 只是字面字符串,不是通配符,匹配不到任何人**。不在列表的 open_id 被静默记 `dm_policy_rejected`,网关丢消息且不报错。这是“有人发消息但完全没有 inbound 日志”的第一嫌疑。
3. **事件订阅**: 飞书后台应用需订阅 `im.message.receive_v1` 并在连接建立后生效。连接建立后修改订阅 → 需重启 gateway 重建 WebSocket 才生效。
4. **重启**: 白名单/订阅改动都靠 `systemctl --user restart hermes-gateway.service` 生效。在 gateway 进程内跑会连坐被杀 → 写好 `/home/kk/restart-hermes-gateway.sh` 让用户在外部终端执行,或 `start_new_session=True` 脱离进程组。

## 主动给同事发私信

写权限验证过,两种方式:

- **简单**: `lark-cli im +messages-send --user-id <open_id> --text "..." --as bot`(返回 chat_id + message_id)。
- **批量/代码**: 走原生 `POST /open-apis/im/v1/messages?receive_id_type=open_id`,headers `Authorization: Bearer <tenant_access_token>`。body:`{"receive_id":"<open_id>","msg_type":"text","content":"<json.dumps({'text':...,}, ensure_ascii=False)>"}`,整段再 `json.dumps(..., ensure_ascii=False).encode('utf-8')`(**content 是双层 JSON 编码**;ensure_ascii=False 保中文,漏了会 400 或乱码)。成功 `code=0` 返回 `data.message_id`。
- tenant token:`POST /open-apis/auth/v3/tenant_access_token/internal` body 带 `app_id`+`app_secret`,token 落盘 `/tmp/feishu-token.txt` 复用(常只活几分钟,别重复拉pipelines)。

给同事发通知/答复时,附带 bot 能力清单(查排班/机器人状态/云文档/故障排查/写文档)让他知道怎么用。

## 查谁和 bot 私聊过 / 读某个用户的对话

- **谁发过消息**: `grep -E "inbound message:|Inbound dm message received" ~/.hermes/logs/gateway.log | grep "$(date +%F)" | grep -oE "user=([^ ]+)" | sort | uniq -c`。排除自己(user=丁祥浩)。
- **某用户完整对话**: 先从日志找到他的 `chat_id`(inbound 行的 `chat_id=` 字段),再 `GET /open-apis/im/v1/messages?container_id_type=chat&container_id=<chat_id>&page_size=N`。
- **已读回执**: `lark-cli im +message-read-users --message-id <om_...> --as bot` 返回读过该消息的用户(只支持 user/BOT 强类型;空 items = 未读)。

## 常见坑

- bot 的 p2p 会话列表(`+chat-list --types p2p --as bot`)通常为空 —— bot 只能看到自己发出的 DM,不能枚举所有私聊;要靠日志拉。
- `lark-cli im +chat-messages-list` 对 bot 不返回他人历史(需对方先回复激活/权限限制),读历史走原生 `GET /im/v1/messages`。
- 改 app 名称/描述需 `application:application` 权限,API 会 99991672;后台手动改,改完可能需发新版。
- token 拉取若有环境变量陷阱(heredoc/pipes),先落盘再 Python 读,避免变量替换拿到空串导致 99991668 invalid token。
