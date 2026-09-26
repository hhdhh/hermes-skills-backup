---
name: feishu-ops-assistant
description: Use when 同事私信收不到/需要向同事群发私信/管理 bot 开放范围/诊断"有人发消息但没回"。
---

# 飞书运营助手 bot 运营

> 完整描述：运营助手飞书 bot 运营：DM 白名单、批量私信/广播、gateway 重启、消息投递排查。Use when 同事私信收不到/需要向同事群发私信/管理 bot 开放范围/诊断"有人发消息但没回"。

面向智动未来运营部/FAE 团队的飞书 bot（app `cli_aaf0558a8fb81cbb`，名“运营助手”）。负责私信/群发、DM 开放管理、gateway 运维。

## 核心坑 1：FEISHU_ALLOWED_USERS 的 `*` 不是通配符

- `.env` 里 `FEISHU_ALLOWED_USERS=*,ou_xxx` 的 `*` 是**字面字符串**，`_id_set()` 只做 strip，不做通配展开——匹配不到任何人。
- 非白名单用户的 DM 被 `_admit` 静默打回 `dm_policy_rejected`，**gateway 日志无任何 Inbound**，只有查飞书 API 消息历史才发现消息存在。
- 症状：自己（白名单内）消息正常，其他同事私信“发出去但没回”，且 gateway.log 完全没有他们的事件。
- 修复：把每个要放行的同事 open_id **显式**列进 `FEISHU_ALLOWED_USERS`（逗号分隔），改完重启 gateway 生效。或用 `FEISHU_ALLOW_ALL_USERS=true`（开发/全员开放，谨慎）。
- 查所有人 open_id：`lark-cli contact +get-user` / 用 tenant token 调 `contact/v3/users/find_by_department`（部门 open_department_id）。

## 核心坑 2：gateway 不能自己重启

- 从 gateway 进程内 `systemctl --user restart hermes-gateway.service` 会被安全机制拦截（SIGTERM 连坐杀掉子进程），`hermes gateway restart` 同理。
- 写独立脚本让用户在外部终端跑：`~/restart-hermes-gateway.sh`，内容 `systemctl --user restart hermes-gateway.service` + sleep + status。
- 改 .env 白名单等配置后必须重启 gateway 才生效（启动时读取）。

## 批量私信/广播（正确姿势）

- 走原生 OpenAPI：`POST /open-apis/im/v1/messages?receive_id_type=open_id`，body `{"receive_id":"<open_id>","msg_type":"text","content":"{\"text\":\"...\"}"}`。
- 用 Python urllib 批量时：`content` 用 `json.dumps({...}, ensure_ascii=False)` 且 headers 带 `Content-Type: application/json; charset=utf-8`；否则中文多行文本 400。
- token 先写入临时文件再在 Python 里读：heredoc 里 `$TENANT_TOKEN` 变量替换会拿空 → 报 `99991668 Invalid access token`。
- 发前先 `user_accessible_scope` 或已读回执验证；跳过高风险角色，先 `--dry-run` 列名单。

## 排查“有人发消息但没回”

按此顺序，别跳：
1. `grep -E "Inbound" ~/.hermes/logs/gateway.log | tail` —— 找对方的 Inbound。若在但没回 = 回复侧问题；若完全没有 = 事件没到（多半 DM 白名单，见坑 1）。
2. 用 tenant token 查该用户会话历史：`GET /open-apis/im/v1/messages?container_id_type=chat&container_id=<chat_id>` 确认消息确实发了。
3. bot 自己 `lark-cli im +chat-list --types p2p` 常为 0（对方未主动回才算激活），别拿它当“没人私聊”证据。查已读：`+message-read-users` 只支持 user 身份。

## 事件订阅关联

- 新增事件订阅（如 `im.message.receive_v1`）后必须重启 gateway 重连 WebSocket 才生效；只改飞书后台不重启 = 事件到不了。
