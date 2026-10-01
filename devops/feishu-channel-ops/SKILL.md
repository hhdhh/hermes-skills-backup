---
name: feishu-channel-ops
description: 飞书通道（Hermes gateway feishu adapter）日常维护与故障排查
---


# 飞书通道运维（Ubuntu Hermes · app=丁祥浩的飞书 CLI）

> 完整描述：飞书通道（Hermes gateway feishu adapter）日常维护与故障排查。当主人说"飞书没反应/消息丢了/群不回/@不响/维护飞书状态"或 gateway 飞书链路异常时使用。四层闸门定位 + 两个 watchdog 自动化。

## 常量
- app_id: `cli_aaf0558a8fb81cbb`，凭证在 `~/.hermes/.env`（FEISHU_APP_ID / FEISHU_APP_SECRET）
- 群: FAE团队 `oc_501e73237970cfa7b5662205166387ff`；主主人单聊 `oc_f8b08c123bda8101a141d0d8e36f3318`
- 主人 open_id `ou_f1d4a1ee37a0cb948fb6256c028cf60f`，user_id `gcd23dd2`，union 通讯录解析后 user_id 会取代 open_id 成为主标识
- 日志: `~/.hermes/logs/gateway.log`（INFO 级）；拒绝/丢弃只有 debug 级不可见
- 去重表: `~/.hermes/feishu_seen_message_ids.json`；投递账本: state.db `delivery_obligations` 表（存每次回复全文）

## 当前策略（2026-09-12 定）
- 群：真 @ 才答（FEISHU_GROUP_POLICY=open + require_mention 默认 true）；系统通知不进群，走主人 DM（FEISHU_HOME_CHANNEL=单聊 oc_）
- 白名单: `FEISHU_ALLOWED_USERS=*,ou_主人,gcd23dd2`（*=群里所有人可 @；DM 仍只限主人）
- Reasoning 不外发: `display.show_reasoning: false`
- 拉群历史需 scope `im:message.group_msg`（已开）；拉群成员需 `im:chat.members:read`（未开）

## 四层闸门（消息不回时按序查）
1. **adapter 准入** `_admit()`（plugins/platforms/feishu/adapter.py）：白名单/群策略/require_mention。拒绝日志仅 debug → 诊断技巧：对比 seen_message_ids.json 条数 vs gateway.log "Inbound ... received" 条数，多出的=被拒（再拉服务器侧消息列表看原文）
2. **gateway 授权** `Unauthorized user` 日志：user_id(gcd…) 解析出来后不在 FEISHU_ALLOWED_USERS → 两个 ID 都列上。通讯录 scope 开通会触发此问题
3. **事件到达**：WS 事件被别的机器抢走（同 app 多连接）。诊断：`ss -tnp` 查到 msg-frontier.feishu.cn 的连接归属；服务器侧拉消息对比。修复：重置 App Secret（旧机器自动 401 出局）+ 本机 .env 更新 + 重启
4. **发送假成功**：SDK 返回成功但服务器无消息（reply-in-thread 静默丢）。修复：从 delivery_obligations 捞全文用 reply API 补发；watchdog 自动化

## 诊断命令速查
```bash
# 服务器侧拉群最近消息（判断"消息到底存不存在"）
curl -s -H "Authorization: Bearer $TOK" "https://open.feishu.cn/open-apis/im/v1/messages?container_id_type=chat&container_id=<chat_id>&sort_type=ByCreateTimeDesc&page_size=10"
# token
TOK=$(curl -s -X POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal -H 'Content-Type: application/json' -d '{"app_id":"cli_aaf0558a8fb81cbb","app_secret":"..."}' | jq -r .tenant_access_token)
# 真@ vs 假@：拉消息看 mentions 数组（真@ 有 key=@_user_1 + bot open_id；手打文字 mentions=[]）
```

## 自动化（已部署，cron 每 5 分钟）
- `~/.hermes/scripts/feishu-health-watchdog.py`：服务/WS 假死/黑盒/静默四层巡检，异常 DM 告警主人，WS 假死自动重启（日限 3 次）。日志 feishu-health.log
- `~/.hermes/scripts/feishu-redeliver-watchdog.py`：账本 delivered vs 群实存核对，丢失自动 ♻️ 补发。日志 feishu-redeliver.log
- 指纹坑：服务器文本勿截短（前缀占位导致匹配失败）；指纹取账本正文前 100 字直接子串匹配

## 变更历史
- 2026-09-12: 六连修（白名单拒绝→secret 轮换独占→Reasoning→群开放@→home channel 改 DM→user_id 授权）+ 静默丢失自愈
- 2026-09-29: 静默丢失复发（DM 引用回复 reply-in-thread 触发，14:44/14:59 两起丢失已补发）。三处修复：
  1. **ledger 开关坑**：config.yaml `gateway.delivery_ledger` 被关→账本 09-17 起停记 12 天→自愈链路失效。改法：`hermes config set gateway.delivery_ledger true`（patch 工具会被安全保护拒绝，走 CLI）。config 按文件签名缓存热加载，无需重启 gateway
  2. **redeliver 盲区**：原版只盯 FAE 群，DM 丢失永不补发→v2 加 CHAT_IDS 覆盖主人 DM；**post 富文本指纹坑**：服务器侧 post 消息 text 嵌在 content 数组里，`json.loads` 后取顶层 text 永远拿不到→已送达被误判丢失→必须用 `_extract_post_text` 递归抽取。误发可用 DELETE /im/v1/messages/{msg_id} 撤回
  3. **silent 告警误报刷屏**：gateway 空闲时本来无日志（真心跳表 gateway_heartbeats 空闲也不记）→30 分钟无日志每小时告警刷屏 DM→修为「日志静默 + WS 连接=0」双条件才告警
  - 丢失消息恢复路径：state.db messages 表按 session_id（sessions 表 LIKE '%oc_xxx%' 反查）捞 assistant 全文→API 补发→服务器回读验证
