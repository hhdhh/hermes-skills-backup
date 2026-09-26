---
name: feishu-channel-admin
description: Use when 飞书机器人没反应、@不回复、群消息丢、Unauthorized user。
---

# feishu-channel-admin

> 完整描述：Hermes gateway 飞书平台通道管理：@ 无响应分层排查、群策略/白名单、app_secret 轮换驱逐多机抢事件、静默丢回复的账本捞回。Use when 飞书机器人没反应、@了不回复、群消息丢、Unauthorized user、FEISHU_ALLOWED_USERS、FEISHU_GROUP_POLICY、secret 轮换、多机抢事件、home channel、群只答@。

管 Hermes gateway 飞书通道（WS 事件接收 + 授权 + 发送）的**健康**。与 lark-* 技能分工：lark-cli 管文档/IM 内容操作，本技能管通道本身。Ubuntu 上 gateway 是 systemd user service（`systemctl --user restart hermes-gateway`），日志在 `~/.hermes/logs/gateway.log` + `journalctl --user -u hermes-gateway`。

## 常开规则（既定策略，维持不动）

1. **群只答真 @**：`FEISHU_REQUIRE_MENTION` 默认 true。手打的「@机器人名」文字**不是真 @**（mentions 数组空、正文无 `@_user_1` 占位符）——被忽略是正确行为，不是故障。
2. **系统通知不进群**：cron 结果/启动通知/异常告警走 `FEISHU_HOME_CHANNEL`（指 owner 单聊）；群保持纯问答。
3. **飞书回复只出结果不输出思考过程**：`display.show_reasoning: false` 已设，别改回。
4. agent 不能直接 patch/write_file `~/.hermes/config.yaml`（安全敏感拒绝）——用 `hermes config set <key> <value>` 一次一字段，幂等。
5. 改 `.env` 后必须重启 gateway 才生效。

## 排查总流程（先定位丢失层，再修）

症状「@ 了不回复」→ 第 0 步先判层：对比 `~/.hermes/feishu_seen_message_ids.json` 条数 vs gateway.log `Inbound ... message received` 行数（去重写入**先于**准入检查，所以差集=被拒或未达）：

- **seen_ids 有、log 无** → 死在 `_admit()` 准入闸门，拒绝日志是 DEBUG 级（INFO 下不可见）→ 层 1
- **seen_ids 就没有** → 事件根本没到本机（多机抢事件/WS 半死）→ 层 2
- **都有、且 log 有 `Sending response`** → 回复发出后静默丢失 → 层 3

### 层 1 · 策略闸门拒绝

常见因：`FEISHU_GROUP_POLICY` 未配（默认 **allowlist**）且 `FEISHU_ALLOWED_USERS` 空 → 所有群消息（含真 @）被拒；或事件带 tenant user_id 而白名单只有 open_id → gateway 授权层报 `Unauthorized user: <短id>`（通讯录权限开通后 user_id 取代 open_id 成为主标识，授权只按主标识匹配）。修法：`.env` 的 `FEISHU_ALLOWED_USERS` 同时列 owner 的 open_id 和 user_id，逗号分隔。开放全群 @ 的配方与两层闸门语义见 `references/channel-config.md`。

### 层 2 · 事件未达（多机抢事件）

同一 app_id 多机建 WS 长连接时，飞书把事件**随机分发给其中一条**——本机无感知无日志。确认法：用 tenant_access_token 直调 `im/v1/messages?container_id=<chat_id>` 拉服务器侧真实消息列表，与 seen_ids 求差；本机自查 `getent hosts msg-frontier.feishu.cn` + `ss -tnp` 逐 IP 看连接归属（应只有 gateway 进程一条）。实锤多机 → **轮换 App Secret**（无需碰远端机器）：开发者后台重置 → `.env` 更新（先备份）→ 验证新 secret 换 token code=0 且旧 secret code=10014 → 重启 gateway。波及：lark-cli keyring 的 `appsecret:<app_id>` 变 stale，需重新 bind；其他配置文件里的旧值不用动（已死无害）。

### 层 3 · 回复静默丢失（假成功）

gateway 日志只记发送**意图**（`Sending response`），SDK 返回成功、delivery ledger 标 delivered，消息也可能没落服务器——**必须拉服务器侧列表核验才算发出**。丢失时全文永远捞得回：`state.db` 的 `delivery_obligations` 表 content 列存每次最终回复全文，用 reply API 补发（message_id 从日志逐字复制）。自愈 watchdog 已部署：`~/.hermes/scripts/feishu-redeliver-watchdog.py`（crontab */5，日志 `~/.hermes/logs/feishu-redeliver.log`），每 5 分钟核对账本 vs 群消息、丢失自动带 ♻️ 前缀补发。完整剧本 + 指纹去重规则见 `references/message-loss-recovery.md`。

## 诊断 API 速查（HTTP 直调，绕开 gateway）

```python
# token（凭证从 ~/.hermes/.env 读，别硬编码）
POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal  {app_id, app_secret}
# 拉某会话消息（**start_time 和 end_time 必须同时给**，毫秒；只给 start_time 报 230001）
GET /im/v1/messages?container_id_type=chat&container_id=<oc_...>&sort_type=ByCreateTimeDesc&start_time=<ms>&end_time=<ms>
# 单条详情（查 mentions / root_id / 撤回）
GET /im/v1/messages/<om_...>
# 回复指定消息（message_id 逐字对，错一位报 invalid open_message_id）
POST /im/v1/messages/<om_...>/reply  {msg_type, content}
# open_id 反查 user_id/姓名
GET /contact/v3/users/<ou_...>?user_id_type=open_id
```

`create_time` 是**毫秒**，转秒再格式化。撤回消息的 body 是 `"This message was recalled"`。所需 scope：群历史 `im:message.group_msg`，成员列表 `im:chat.members:read`。

## Pitfalls

1. **准入拒绝静默**——`_admit` 拒绝日志 DEBUG 级；用 seen_ids 条数 vs log 行数的差集定位，别等日志。
2. **别信 `Sending response` = 已送达**——外发状态以服务器侧列表为准；每次「发了但用户说没收到」都先拉 API 核验。
3. **通讯录权限的连带效应**——发布带新权限的版本会改变事件的 ID 层级，原白名单立即失效（`Unauthorized user: <tenant user_id>`）。白名单同时挂两种 ID 形态可免疫。
4. **list API 只传 start_time 会 400**——参数校验报「end_time earlier than start_time」，两个时间戳（毫秒）一起给。
5. **假 @ 不是 @**——正文含字面 `@机器人名` 但 mentions 数组空 = 用户手打的文字；向用户解释要用输入框弹出列表选中的高亮 @。
6. **多机同 app_id 的消息丢失是随机间歇的**——同一连接前后两条一条到一条不到，别被「刚才还好好的」误导。
7. **补发消息判重时服务器文本不要截断**——补发带前缀，截断后前缀吃掉匹配窗口永远比不中；指纹取账本正文纯文本前 100 字对服务器全文做子串匹配。

## 关联资源

- `references/channel-config.md` — env 变量语义表、两层闸门模型、ID 三层体系、全群开放配方、home channel 路由
- `references/message-loss-recovery.md` — 三层丢失完整诊断剧本、secret 轮换步骤、账本捞回与 watchdog 指纹规则、API 怪癖清单
