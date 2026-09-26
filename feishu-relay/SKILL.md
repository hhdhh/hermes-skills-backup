---
name: feishu-relay
version: 0.1.0
description: Use when 用户说"把这个分享给@某某""发给@某某""转发给TA""同步给某某"。
---

# 飞书内容转发/分享

> 完整描述：把会话里产出的内容（技能介绍/报告/总结）分享或转发给飞书联系人私聊。Use when 用户说"把这个分享给@某某""发给@某某""转发给TA""同步给某某"。

把本会话产出的内容送到某位同事的飞书私聊。四步：定位收件人 → 取源内容 → 改写 → 确认后发送。

## 1. 定位收件人 open_id

- 用户在飞书里 @了人 → 会话上下文开头有 `[Mentioned: 姓名 (open_id=ou_xxx)]`，直接用这个 open_id，连 lark-contact 搜索都跳过。
- 只给了姓名没 @ → 走 lark-contact `+search-user --query "姓名" --as user`；命中多条且后续有副作用时列候选让用户挑，不要擅自选第一条。

## 2. 取源内容（源是本会话里我之前的回复时）

```bash
lark-cli im +messages-mget --message-ids om_xxx --as user
```

- 正文在返回 JSON 的 `data.messages[].content`，不在 `body.content`——字段路径猜错会拿到空串，白跑一趟。
- 会话上下文的 thread 标签给的是 om_ 消息 ID，不保证能当 thread_id 喂给 `+threads-messages-list`（会报 not found）；已知 om_ ID 要正文，直接 mget，不走 thread 列表。
- post 类型消息的 content 是整段富文本，💭 Reasoning 块也包含在内。

## 3. 改写成收件人版

发给第三方的稿不是原文照搬，过三刀：

- **删**：💭 Reasoning 块、我的操作过程叙述（权限验证、读回验证、调试过程）、对话指代（"你刚才说"）。
- **换视角**：第二人称改第三人称——"你可以直接说222号什么状态" → "丁祥浩的助手可以直接查222号状态"。
- **留干货**：地址、能力清单、坑位提醒原样保留。

## 4. 确认后发送

- 发第三方私聊是外部副作用，必停门口：把改写后的稿完整亮出来，只问真正开放的问题——以用户名义 `--as user` 还是以 bot 名义发。
- **用户已经定过的不要再问**：收件人、源内容都是用户点名过的，重问一遍是打扰，用户反感反复被打扰选档。
- 署名跟着身份走：bot 名义 → 稿首注明"来自丁祥浩的运营助手"；user 名义 → 不署名。
- 发送命令可能被审批门拦下等确认——**被拦就停**，把稿摆给用户等回复；不要换身份、换参数、换命令绕门禁重试（被 user 身份拦了换 `--as bot` 重发 = 绕门禁，禁止）。

```bash
lark-cli im +messages-send --user-id ou_xxx --markdown "$(cat draft.md)" --as user
```

## 坑

- `+chat-messages-list` 的排序参数是 `--order asc|desc`；flag 拿不准先 `--help`，不要按直觉猜参数名。
