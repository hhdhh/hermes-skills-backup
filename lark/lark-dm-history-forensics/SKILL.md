---
name: lark-dm-history-forensics
description: Use when 查「今天谁私聊了/XX和你聊了啥」或识别断网漏回同事消息。
---

# 同事私聊记录查证（运营助手）

用户定期会问「今天谁私聊了」「XX和你聊了啥」。数据源有三层，按序使用：本地 state.db（最快、不依赖外网）→ gateway.log（归因发送者）→ Feishu API（核对）。答案必须给出：谁、几条、时间范围、话题摘要；发现漏回要单独列出。

## 先校准时钟

先跑 `date` 确认当天实际日期，再算「今天零点」——对话间隔多天时，按记忆里的日期查库会查错天，日志/DB 里没有那天才是常态而非异常。

## 第一层：state.db 直查（首选）

位置 `~/.hermes/state.db`（sqlite3）。表结构坑：

- `sessions.started_at` / `last_activity_at` / `messages.timestamp` 全是 **unix 浮点时间戳**，不是 ISO 字符串。用 `datetime.date(Y,M,D).timestamp()` 算当日零点再数值比较；字符串比较（`>= '2026-09-22'`）恒为空，不要因此误判「无人私聊」。
- `messages` 表时间列名是 `timestamp`，没有 `created_at`；role 取值 user/assistant/tool。
- `sessions.id` 与 `messages.session_id` 必须是完整串（如 `20260915_120237_85319255`）。先 `SELECT DISTINCT session_id FROM messages ORDER BY rowid DESC LIMIT 10` 拿全量样本再查；手敲截断版 id 查询不报错但恒空。
- 会话可能跨多天复用同一 session（`last_activity_at` 很新但 `started_at` 很旧）——按 timestamp 过滤消息而不是只看 session 起始日。
- user 消息常带 `Gateway message origin (JSON...)` 包装头，提取正文时剥掉，否则摘要全是元数据。

查询模板：按 chat_id 分组当日消息数，`sender` 方向用 role='user' 计数；当前管理员的 chat_id 要排除（他的会话是主通道不是「同事私聊」）。

## 第二层：gateway.log 归因

`grep 'sender=user:ou_' ~/.hermes/logs/gateway.log` 每行含 chat_id、发送者 open_id、正文前缀。用途：①快速统计哪些 chat 有入站；②chat_id → open_id 归因（P2P 会话的 members API 返回 400，不能用 API 反查姓名，只能从历史消息 sender.id 对）；③判断消息是否被处理。注意 gateway.log 在网关重启后重新开始，更早的记录在 journalctl 或 agent.log 里。

journalctl 保留期有限，且日志按网关启动时间分段——查历史事件先看日志文件 mtime 再选源。

## 第三层：Feishu API 核对（需要外网时）

- tenant_access_token 缓存在 `/tmp/feishu-token.txt`，但 /tmp 会被清，kernel 重启后先重取 token 再读缓存。
- `im/v1/messages?container_id=chat` 默认倒序返回**最早的一页**——查最近消息必须翻页（跟 `has_more`/`page_token`）或用 `start_time`/`end_time`（毫秒、本地时区）过滤；只看第一页会得出「最近没消息」的错论。
- `lark-cli +chat-messages-list --as user` 对 P2P 常返回 0 条，不能用它下「无人私聊」的结论。
- 直连 open.feishu.cn 超时（Connection timed out）时走 Clash 代理 `127.0.0.1:7890`（urllib 的 ProxyHandler）。

## 断网窗口漏回识别（重要）

工作站断网时飞书 WS 断开（journal 特征：`NameResolutionError`、`keepalive ping timeout`），重连后**断网窗口内入站的消息不会补投处理**。判定：API/日志里看得到同事发来、但同 chat 无对应 assistant 回复且之后再无交互——即为漏回。

发现漏回应主动列清单（时间/内容/请求人）报给管理员，补处理或请示是否代发回复；对同事发消息前必须经管理员确认。

## 输出格式

表格：人名 | 条数 | 时间范围 | 话题一句话。多天前的事先声明日期再报内容，避免「今天」错位。
