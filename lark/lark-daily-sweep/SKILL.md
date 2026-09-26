---
name: lark-daily-sweep
version: 1.0.0
description: Use when 用户说「检查飞书情况/看下飞书/飞书有什么待办」——审批·任务·群聊·私聊·@提及一站式巡查并报...
metadata:
  requires:
    bins: ["lark-cli"]
---

# 飞书日常巡查（一站式）

> 完整描述：Use when 用户说「检查飞书情况/看下飞书/飞书有什么待办」——审批·任务·群聊·私聊·@提及一站式巡查并报出待处理项

用户一句"检查飞书情况"= 扫全量会话 + 待办，报出**需要用户处理/回复的项**。不是逐域深查，是快速全景。

## 巡查流程（按序）

1. **认证**：`lark-cli auth status` — user 身份 `needs_refresh` 不用处理（下次调用自动刷新）；**记下自己的 openId**，后面判定私聊最后一条是谁发的要用。
2. **审批待办**：`lark-cli approval tasks query --params '{"topic":"1"}' --as user`
3. **任务待办**：`lark-cli task tasks list --as user`（子命令是 `tasks`，没有单数 `task`）
4. **会话清单**：`lark-cli im +chat-list --types=p2p,group --page-all --as user > /tmp/chats_all.json`
5. **群聊动态**：每个 group `lark-cli im +chat-messages-list --chat-id <cid> --limit 8~15 --as user`，落在文件里再解析。
6. **私聊排序**：每个真人 p2p 先 `--limit 1` 拿最后一条，按时间倒序；只对"最后一条是对方发的"候选再拉 4-5 条看语境。
7. **@提及**：`lark-cli im +messages-search --query "@丁祥浩" --as user`
8. **日历**：`lark-cli calendar +agenda --as user`（见坑：默认缺 scope）

## 判定规则

- **待回私聊** = 最后一条消息 `sender.id ≠ 自己 openId` 且 `msg_type != system`。
- **系统/机器人单聊不参与待回判定**：名字含"助手/伙伴/中心"或为功能号（假勤、审批、工资单、邮箱、日历、云文档、账号安全、联系人、开发者小助手、智能伙伴、豆包工作伙伴、Feishu CLI、自聊天）。
- **群活跃度**按最后一条**非 system** 消息的时间算——很多群最后几条全是入群通知，别误判为活跃。

## 报账格式（用户习惯的输出形态）

1. 待办全清与否（审批 N / 任务 N）
2. 可能需要回的私聊：人名 + 时间 + 内容摘要，只列真待回的
3. 群动态要点：只挑对用户有用的（指派任务、@、流程/制度通知、与用户工作相关的技术动态）
4. 环境状态一句话收尾（token / CLI 版本 / 缺的授权），有新版提一句不催

## 坑（cost real time）

- **ID 一律不截断**：`oc_`/`ou_` 完整约 33 字符。打印或中转时 Python 切片（如 `[:26]`）会让后续 API 调用报 `invalid container_id`——会话列表先存文件，用时取全量字段。
- **消息字段形状**（`+chat-messages-list` 返回值）：`create_time` 是 `"YYYY-MM-DD HH:MM"` 字符串，别 `int()`/`fromtimestamp()`；发送者在 `m['sender']['id']`（嵌套对象，无顶层 `sender_id`）；文本在顶层 `m['content']`（无 `body.content`）。
- **先落盘再解析**：CLI 输出重定向到文件后用 python 解析，不要在管道里接 head/tail——管道会吞真实退出码，JSON 解析失败时看不到原始错误。
- **@提及搜索有噪音**：命中会包含机器人单聊里的终端转录、自动补发消息；报账时排除已知 bot 会话，只报真人群里对用户的提及。
- **日历默认缺 scope**：`calendar:calendar.event:read` 不在默认授权集。缺 scope 时先跳过日历继续巡查其他项，末尾问用户要不要授权：`lark-cli auth login --scope "calendar:calendar.event:read" --no-wait --json` 拿授权链接给用户，下一轮 `auth login --device-code <code>` 完成。
