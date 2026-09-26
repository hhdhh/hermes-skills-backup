---
name: feishu-message-content-recovery
description: Use when a Feishu message body shows a placeholder not text.
---


# Feishu 消息内容恢复（占位符 → 全文）

> 完整描述：Use when a Feishu message shows no body ([Merged forward message], unexpanded card, placeholder). Pull the full content via lark-cli instead of asking the user to resend.

## 判断

会话/事件订阅里出现 `[Merged forward message]` 占位、卡片（`interactive`）无正文、其它"看似空内容"的消息时，**不是内容丢失**——是事件侧不展开该消息类型。占位符 ≠ 收不到：消息本体在服务端完整存在，先拉取再下结论。

## 恢复流程

1. 定位 chat_id（P2P 即当前会话的 `oc_xxx`，上下文已给出就直接用）。
2. 拉最近消息（bot 在会话内即可，P2P 也够用）：

```bash
lark-cli im +chat-messages-list --as bot --chat-id oc_xxx --sort desc --limit 10
```

3. 按 `msg_type` 找到目标消息（如 `merge_forward`）。其 `content` 字段是 `<forwarded_messages>` XML 块，逐条列出转发消息的发送人、时间戳和**全文**——直接以此为准回复用户。
4. 消息在 thread 里时：用户消息带 `thread_id`（`omt_xxx`），用 `+threads-messages-list --thread-id omt_xxx`，或从主 chat 列表里找 thread 根消息（带 `thread_replies`）。

## Pitfalls

- **不要让用户重发、复制要点或"以文件形式发送"**——重发只是浪费一轮往返；拉取一次即得全文。曾因此误答"接收不到转发内容"。
- `--sort desc` + 小 `--limit` 就够：目标消息几乎总是最新几条之一。
- `interactive`（卡片）事件侧同样只回原始数据；用同样的拉取方式拿 `content`。
- 拉取输出可能很长，先在命令里 `| head` 截断定位 message_id，再按需看全量。

## 关联

消息拉取/下载细节见 `lark-im`（`+chat-messages-list` / `+threads-messages-list` / `--download-resources`）。本技能只解决"事件侧不展开 → 主动拉取恢复"这一类场景。
