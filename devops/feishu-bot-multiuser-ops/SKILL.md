---
name: feishu-bot-multiuser-ops
description: Use when 用户说“XX 给你发消息了你没回”、“让同事都能私信你”、“给某部门全员发通知”、“谁私聊过你”...
version: 1.0.0
---

# 飞书机器人多用户运营与排障

> 完整描述：运营/团队共用的飞书机器人（Hermes 飞书适配器）多用户运营与排障：私信白名单为何静默丢弃陌生人消息、如何查“别人发了消息但 bot 没回”、如何批量找人 open_id 并群发、为何改完 .env 必须重启 gateway、以及从 gateway 内部无法重启自己的绕法。Use when 用户说“XX 给你发消息了你没回”、“让同事都能私信你”、“给某部门全员发通知”、“谁私聊过你”、“bot 收不到消息”。

面向“一个 bot 服务整个部门/团队”的场景（多私聊会话 + 群）。适用 Hermes 的 feishu 平台适配器（`plugins/platforms/feishu/`），核心配置在 `~/.hermes/.env`。

## 1. DM 准入：`FEISHU_ALLOWED_USERS` 没有通配符

**这是“别人发消息 bot 不回”的头号根因。**

适配器的 DM 准入逻辑（`adapter.py` 的 `_admit`）：

```
not is_group 时:
  if _allow_all_dm or not _allowed_group_users: 放行
  else: 命中 allowed_group_users 才放行，否则 "dm_policy_rejected"
```

- `_allowed_group_users` = `FEISHU_ALLOWED_USERS` 按逗号切分后 **strip 字符串**，`*` 只是字面量，**匹配不到任何人**。写 `FEISHU_ALLOWED_USERS=*` 不会放行所有人，只会静默拒掉所有不在列表里的 open_id。
- `_allow_all_dm` 只由 `FEISHU_ALLOW_ALL_USERS`（或 `GATEWAY_ALLOW_ALL_USERS`）为 true 触发。想“全公司可私聊”要设这个，而不是 `*`。
- **被拒的消息不进 gateway.log**：`dm_policy_rejected` 在准入层就丢了，日志里连 raw message 都没有。看不到拒绝记录 ≠ 消息没到飞书。

**推荐做法（可控 + 可审计）**：把目标成员的 open_id 全量写进 `FEISHU_ALLOWED_USERS`，而不是一把 `FEISHU_ALLOW_ALL_USERS=true`。

```bash
# 只保留一行，避免历史追加产生多行（多行时只有最后一行生效，易误判）
grep -n "FEISHU_ALLOWED_USERS" ~/.hermes/.env
```

改 `.env` 时用脚本重写该行（去重保序），不要反复 `>>` 追加——历史上多次追加会留下 3 行同名变量，排查时看不出哪行生效。

## 2. 改完 `.env` 必须重启 gateway

`FEISHU_ALLOWED_USERS` 在适配器启动时快照（每个 profile 各读一次），**运行中改文件不生效**。

**但 agent 无法从 gateway 进程内部重启自己**：`hermes gateway restart`、`systemctl --user restart hermes-gateway`、以及 `subprocess.Popen(..., start_new_session=True)` 都会被拒绝（SIGTERM 会传播到子进程，命令自杀在半路）。

**绕法**：写一个一次性脚本交给用户在外部终端跑。

```bash
# ~/restart-hermes-gateway.sh
#!/bin/bash
systemctl --user restart hermes-gateway.service
sleep 5
systemctl --user status hermes-gateway.service --no-pager | head -5
```

写完 `chmod +x`，告诉用户“开个终端跑 `~/restart-hermes-gateway.sh`”。**不要反复重试被拒的重启命令**——它一定失败。

## 3. 排障：“有人说发了消息，但 bot 没回”

按此顺序，每步都能独立定论：

```bash
# 1. gateway 侧：有没有收到事件？（重启后按时间窗过滤）
grep -E "Inbound|Received raw" ~/.hermes/logs/gateway.log | tail -20
#    网关能收到的消息特征：先 "Received raw message"，再 "Inbound dm message received"，再 "inbound message"

# 2. 确认适配器在线
systemctl --user show hermes-gateway.service -p ActiveEnterTimestamp
tail -5 ~/.hermes/logs/gateway.log | grep -i feishu   # 期望 Connected in websocket mode

# 3. 飞书侧：对方到底发了什么、发到哪个会话（gateway 看不到时唯一真相源）
```

飞书侧取证（tenant token 见 §5）：

```bash
# bot 参与的所有会话（含 p2p）——判断对方发的是不是这个 app
curl -sS "https://open.feishu.cn/open-apis/im/v1/chats?page_size=50" -H "Authorization: Bearer $T"

# 某个会话的消息历史（用第 3 步拿到的 chat_id）
curl -sS "https://open.feishu.cn/open-apis/im/v1/messages?container_id_type=chat&container_id=<chat_id>&page_size=20" -H "Authorization: Bearer $T"
```

**读结论**：

| 现象 | 含义 |
|---|---|
| 日志有 raw message，无 inbound | 适配器收到了但被 `_admit` 拒（查 §1 白名单） |
| 日志完全无 raw message，飞书侧有消息 | 对方发的不是这个 app（改了名、搜到同名机器人），或没真正发出 |
| 日志有 inbound，无回复 | 是 agent 侧问题，不是平台问题 |

## 4. 批量找人 + 群发

部门/成员不在 contact 技能覆盖范围（那是 hub 的 lark-cli 技能），用原生 OpenAPI：

```bash
# 部门树（fetch_child=true 拿全量；department_id=0 是根）
curl -sS "https://open.feishu.cn/open-apis/contact/v3/departments?department_id=0&page_size=50&fetch_child=true" -H "Authorization: Bearer $T"

# 某部门成员（必须 department_id_type=open_department_id 搭配 od- 开头的 id）
curl -sS "https://open.feishu.cn/open-apis/contact/v3/users/find_by_department?department_id=<od-xxx>&page_size=50&department_id_type=open_department_id" -H "Authorization: Bearer $T"
```

- 缺 `department_id_type` → HTTP 400。
- `job_title` 常为空，别依赖它做分组；用部门归属。
- 拿到 open_id 后**立刻落盘**（写成 `姓名 → open_id` 表），后续群发和加白名单都复用它。

批量私信发文本消息（Python 一次循环，比逐条 curl 可靠）：

```python
import json, urllib.request
TOKEN = open('/tmp/feishu-token.txt').read().strip()
for name, uid in people:
    payload = json.dumps({
        "receive_id": uid, "msg_type": "text",
        "content": json.dumps({"text": text}, ensure_ascii=False)
    }, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
        data=payload,
        headers={"Authorization": "Bearer " + TOKEN,
                 "Content-Type": "application/json; charset=utf-8"})
```

**坑**：
- `obtain token` 后**写进临时文件再让 Python 读**。在 bash heredoc 里内插 `$TENANT_TOKEN` 常在多层引号中被吃掉，症状是 `code 99991668 Invalid access token`（token 为空）。
- `ensure_ascii=False` + `.encode('utf-8')` + `charset=utf-8`，三者缺一中文内容会 HTTP 400。
- 按人名逐条报告成功/失败，别只说“发完了”——漏发要能看出是谁。

## 5. tenant_access_token

```bash
curl -sS -X POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal \
  -H "Content-Type: application/json" \
  -d "{\"app_id\":\"$APP_ID\",\"app_secret\":\"$APP_SECRET\"}" \
  | python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('tenant_access_token',''))" > /tmp/feishu-token.txt
```

有效期约 2 小时，长流程（扫描 + 群发）开始前重新取一次。App Secret 只在 `~/.hermes/.env` 的 `FEISHU_APP_SECRET` 里读，不要写进命令历史。

## 6. 应用名/描述改不了都正常

`PATCH /open-apis/application/v6/applications/<app_id>` 需要 `application:application` 或 `admin:app.category:update` scope，自建应用通常没开——会返回 `99991672 Access denied`。**应用名/描述/头像一律让用户在开放平台后台改**，别在这条路上耗时间。

**顺带**：如果同事“找不到 bot / 发错对象”，先确认应用名是不是变成了大家认不出的名字——应用改名后旧会话仍在，但新搜的人容易搜错。

## 7. 谁能私聊过 bot

- bot **无法主动列出**“谁私聊过我”的历史（`im/v1/chats` 只列 bot 已在的群；p2p 会话要对方先发消息且经准入放行才会出现）。
- `im +chat-list --types p2p` 为空不代表没人发过——被 `_admit` 拒的不会出现。
- 可行证据：`im/v1/messages` 查已知 chat_id 的历史 + `message-read-users`（仅 bot 身份可查自己发出消息的已读人）。
- 结论：**“有谁私聊过”要主动问或看已有会话，别把它当可靠查询能力承诺给用户。**

## 与其它技能的衔接

| 需求 | 去处 |
|------|------|
| lark-cli 安装 / OAuth / 身份模式 | `lark-feishu-cli` |
| 飞书云文档读写、云盘、多维表格 | `lark-doc` / `lark-drive` / `lark-base` 等 |
| gateway 生命周期（launchd/systemd、profile） | `hermes-gateway-admin` |
