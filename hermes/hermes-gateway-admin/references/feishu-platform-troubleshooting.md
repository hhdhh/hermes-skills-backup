# 飞书平台排障 — Hermes gateway

适用：飞书机器人「无反应」「消息丢失」「群里 @ 没回复」「收到不回」「Unauthorized user」。平台无关（mac launchd / Ubuntu systemd 都适用，仅重启命令不同）。

## 消息到达路径的 4 道闸（按顺序定位）

```
飞书 WS 事件 → (1) adapter 收到 → (2) _is_duplicate 写 seen_ids → (3) _admit 策略闸 → (4) gateway 授权层
                                                                      拒绝=DEBUG 级（INFO 不可见）   拒绝=WARNING "Unauthorized user"
```

代码位置（`plugins/platforms/feishu/adapter.py`）：`_handle_message_event_data` → `_is_duplicate` → `_admit`；授权层在 `gateway/run_inbound.py` + `gateway/authz_mixin.py`（`_is_user_authorized` / `_principal_matches_allowlist`）。

## 核心诊断法：三源对账

1. **本地去重表** `~/.hermes/feishu_seen_message_ids.json` — 去重写入发生在策略闸**之前**，凡到过本机进程的消息都在。
2. **gateway.log** `grep "Inbound .* message received"` — 通过全部闸门、真正进入处理的消息。
3. **飞书服务器侧**（真相源）— tenant_access_token + `GET /im/v1/messages?container_id_type=chat&container_id=<chat_id>&sort_type=ByCreateTimeDesc`。单聊要 `im:message` scope，群要 `im:message.group_msg`。

判读：
- 服务器有、seen_ids 无 → **事件没到本机**（WS 半死，或被别处连接抢走）→ 查多机
- seen_ids 有、log 无 → **被闸门拒**（`_admit` 静默 / 授权 WARNING）→ 查白名单与策略
- 都有、无回复 → agent 侧卡住，看 `~/.hermes/logs/agent.log` 当前会话是否在跑工具

拿 token 的最小骨架：`POST /open-apis/auth/v3/tenant_access_token/internal`，body `{"app_id","app_secret"}`，凭证从 `~/.hermes/.env` 读，**不要明文打印 secret**。

## 失败模式速查

| 症状 | 根因 | 修法 |
|---|---|---|
| 群消息全部静默无响应，单聊正常 | `FEISHU_GROUP_POLICY` 默认 allowlist 且 `FEISHU_ALLOWED_USERS` 为空 → 所有群消息（含 @）被 `_admit` 拒，拒绝日志仅 DEBUG | `.env` 加 `FEISHU_ALLOWED_USERS=<id1>,<id2>`，重启 gateway |
| 消息**间歇性**丢失（同会话时通时不通） | 同一 app_id 在多台机器建 WS 长连接，飞书把事件随机分发给其中一条 | 开发者后台**重置 App Secret** → 本机 `.env` 更新 → 重启。旧 secret 换 token 立即返回 code 10014，远端下次续期 401 自动出局 |
| log 见 `Unauthorized user: <短id>`，收到不回 | 通讯录 scope 生效后 tenant user_id 取代 open_id 成为主 ID，白名单只认 `ou_` 形式 | `FEISHU_ALLOWED_USERS` **两种 ID 都列**（逗号分隔）；完整 user_id 用 `GET /contact/v3/users/<open_id>` 反查 |
| 飞书回复带思考过程 | `display.show_reasoning` 为 true | `hermes config set display.show_reasoning false` + 重启（agent 不能直接 patch config.yaml） |
| 群里冒 "No home channel is set" 英文提示 | `FEISHU_HOME_CHANNEL` 未设 | `.env` 加 `FEISHU_HOME_CHANNEL=<chat_id>`；群须纯净时指向单聊 |
| API 拉群历史报 230027 | 缺 scope `im:message.group_msg` | 开发者后台开通 + 发布版本。不影响 WS 收发 |

## 用户常设要求（每次改动前自检）

1. **飞书回复只输出结果**，不输出 reasoning / 思考过程。
2. **群只做 @ 应答** — cron 结果、启动通知、异常告警等系统消息一律走单聊（`FEISHU_HOME_CHANNEL` 指向 DM）。
3. **一个 app_id 只归一台机器**；要加第二台机器 = 新建另一个飞书应用，不共享 secret。

## 命令速查

```bash
# Ubuntu (systemd)
systemctl --user restart hermes-gateway.service
journalctl --user -u hermes-gateway --since "1 min ago" --no-pager | grep "\[Lark\]"

# 端到端验证：盯日志同时让用户发一条消息
tail -f ~/.hermes/logs/gateway.log | grep --line-buffered -E "Inbound|response ready|Unauthorized"

# 本机连接数体检（应只有 hermes gateway 一条到 msg-frontier；飞书桌面客户端不算）
getent hosts msg-frontier.feishu.cn | awk '{print $1}' | sort -u | while read ip; do ss -tnp | grep "$ip"; done
```

`.env` 相关键：`FEISHU_APP_ID` / `FEISHU_APP_SECRET` / `FEISHU_ALLOWED_USERS`（open_id + user_id 都列）/ `FEISHU_GROUP_POLICY` / `FEISHU_HOME_CHANNEL`。改任何一项都要重启 gateway。

## secret 轮换的波及面

- 同 app 凭证还会存在：lark-cli keyring（`appsecret:<app_id>`）、openclaw 等其他框架的配置文件。
- 轮换后 lark-cli 需重新 `bind`；其他框架里的旧值不修自然失效（弃用侧不用管）。
