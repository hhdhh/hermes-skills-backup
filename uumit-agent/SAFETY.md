# SAFETY — UUMit Agent v2.7.0

本文件定义 UUMit Skill 的安全边界。脚本 stdout 仅供 Agent 内部解析；面向用户必须自然语言总结。

## 1. 风险等级

| 等级 | 类型 | 默认行为 |
|---|---|---|
| L0 | 本地说明、只读文档 | 可直接回答 |
| L1 | 平台只读查询 | 可直接调用 |
| L2 | 低风险写入 | 需要幂等键，按场景提示 |
| L3 | 付费调用 | 受 `spend.auto_spend_max_ut` 和余额闸门控制 |
| L4 | 发布/上架/外发数据/授权 | 必须用户确认 |
| L5 | 高风险或未知能力 | 阻断，转待适配/人工确认 |

## 2. 自动扣费阈值

唯一配置来源：

```text
memory/runtime/agent-autonomy-config.json
spend.auto_spend_max_ut   # 单次上限，默认 100 UT
spend.daily_max_ut        # 单日累计上限，默认 5000 UT（本机软提醒）
```

默认值：单次 `100` UT，单日累计 `5000` UT。

自动执行前必须满足：

1. 路由在 `scripts/rest_request.js` allowlist 内；
2. 可读到预估费用或标价；
3. 费用不超过 `spend.auto_spend_max_ut`（单次上限）；
4. 当日累计加本次费用不触顶 `spend.daily_max_ut`（单日累计上限）；
5. `GET /api/v1/wallet` 显示余额充足；
6. 不是议价购买；
7. 不涉及发布、上架、外发数据、授权、预约真人、webhook/callback 配置。

### 2.1 单日累计上限（本机软提醒）

单日累计上限（`spend.daily_max_ut`）是**本机花费软提醒，不是权威消费风控**：由 skill 在 `spend.daily_ledger_path`（默认 `memory/runtime/spend-daily-ledger.json`）本地按 Asia/Shanghai 自然日记账，跨日归零。重装、换设备、清空 `memory/` 会导致累计重置，本地文件可被查看或修改，多客户端各自独立不汇总——这些是设计边界而非缺陷。**付费能否放行由后端令牌校验独立负责，与本额度职责正交。** 记账只统计实际发生扣费的成功调用；preview/quote 询价、探测换令牌、待确认响应、失败或被拦截的请求一律不计入；`execute-plan` 与取不到估价（`price_unavailable`）经确认放行的付费不纳入本地记账。

预判本次调用会使当日累计触顶（`spent_ut + 本次费用 ≥ daily_max_ut`）时，向用户呈现「当日已花、本次费用、单日上限、剩余额度」，口头二选一：

1. **授权本次继续**：带 `--confirmed` 放行本次；本次仍计入累计，允许越过上限（属知情放行）。
2. **修改单日上限并继续**：用户给新值后直接编辑 `agent-autonomy-config.json` 的 `spend.daily_max_ut`（须为有限数字且 `> 0`），再带 `--confirmed` 放行本次。

脚本侧的 `exceed_daily_max_ut` 阻断（退出码 2）仅为 Agent 未前置授权时防止未授权扣费的兜底。

## 3. 必须确认的动作

以下动作不得自动执行：

- 超过单次自动扣费阈值（`spend.auto_spend_max_ut`）；
- 使当日累计触顶单日上限（`spend.daily_max_ut`），见 §2.1；
- 钱包余额不足或余额不可读取；
- 议价成交购买；
- 发布、上架、修改公开资料；
- 配置第三方 endpoint、鉴权、headers、callback 或 webhook；
- 适配器沙箱试调，因为样例输入、请求模板或 schema 映射会发送给第三方服务；
- 外发用户文件、私有数据或企业数据；
- 暴露 MCP 工具、Agent Card、webhook 或 callback；
- 真人服务委托、预约时间、取消付费订单；
- 钱包资金变动：提现（`POST /api/v1/wallet/withdraw`、`POST /api/v1/wallet/withdraw-cash`）、创建充值订单（`POST /api/v1/wallet/recharge`）、绑定收款账户、取消提现；
- 能力上架与管理：创建（`POST /api/v1/capabilities`）、修改、删除、提交审核、上下架自有能力；
- 账号类商品上架：创建库存/共享商品、确认发布、追加或编辑库存（`account-inventory`/`account-shared`/`account-publish`/`inventory-items`）；
- 知识资产创建：从文件创建资产、更换封面媒体（`quick-upload`/`{asset_id}/media`）；
- 订单售后：确认收货放款、取消订单、申请返工、提交评价、发起投诉、提交争议证据；
- 未注册、schema 不完整、价格未知或责任主体未知的能力。

## 3.1 上架候选排除与意图收敛

- **上架候选排除护栏**：无论上架技能（`POST /api/v1/skills`）还是能力（`POST /api/v1/capabilities`），已装的 UUMit 套件文件、任何宿主 skills 目录下的 Skill 包，**一律不作为上架候选**；不得扫描宿主本地 skills 目录充当候选。上架对象的分诊规则见 `SKILL.md`「显式意图优先」。
- **意图收敛**：同一意图被用户重复 / 强化表达 ≥2 次时，必须停止分流 / 搜索绕道，直接执行用户明确要求的写动作（仍保留本节的确认闸门，不因此跳过确认或扣费门槛）。

## 4. 确认模板

向用户请求确认时，必须展示：

```text
动作：
能力/资产/订单：
提供方：
预计费用：
当前余额：
执行后余额：
数据流向：
数据将发送给：
风险等级：
幂等键：
是否继续：
```

确认后调用脚本时使用 `--confirmed`。付费能力（smart-invoke）由后端签发签名 `confirm_token`（绑定调用方/能力/费用，5 分钟有效）作为放行凭证：`rest_request.js` 在 `--confirmed` 时会**自动**向后端换取该 token 并回填请求体 `confirm_token`，Agent 无需手动处理；若手动重试，则把响应 `confirmation.confirm_token` 原样填入下次请求体 `confirm_token`。**严禁**自造 token、把 `confirmation.action`（`confirm_invoke`）当 token、或绕过确认直连 `/playbooks/runs`。

### 4.1 人话摘要兜底范围

确认响应缺 `confirmation.human_summary` 时，`rest_request.js` 会用已有字段兜底拼一句自然语言摘要注入（如「你将支付 2 UT 购买《…》，余额将变为 … UT」）；后端提供权威 `human_summary` 时**原样透传优先**。兜底**只覆盖有真实数据支撑的部分**：费用取 `confirmation.estimated_cost_ut`、付后余额取 `confirmation.balance_ut`（或余额减费用算出）、能力名取确认响应内真实字段，关联不到能力名时**只拼费用、不编造能力名**；退换/退款/交付时效等风险与售后信息底层无真实数据，**一律不呈现、不编造文案**（仅当后端提供 `confirmation.risk_notice` 时由端上展示）。

## 5. 已覆盖闸门路径

### 5.1 扣费闸门（价格+余额+阈值）

`rest_request.js` 的 `enforceAutoSpendGate` 覆盖：

- `POST /api/v1/capability-runtime/smart-invoke`
- `POST /api/v1/capability-runtime/invoke`
- `POST /api/v1/data-marketplace/{api_id}/call`
- `POST /api/v1/digital-assets/{asset_id}/purchase`
- `POST /api/v1/playbooks/runs`

### 5.2 资金变动确认闸门（L4，需 `--confirmed`）

`rest_request.js` 的 `enforceWalletWriteConfirmation` 覆盖（未带 `--confirmed` 返回 `wallet_funds_change_requires_confirm` 并以退出码 2 阻断）：

- `POST /api/v1/wallet/withdraw`
- `POST /api/v1/wallet/withdraw-cash`
- `POST /api/v1/wallet/withdraw/{order_id}/cancel`
- `POST /api/v1/wallet/recharge`
- `POST /api/v1/wallet/payment-accounts`

### 5.3 能力上架确认闸门（L4，需 `--confirmed`）

`rest_request.js` 的 `enforcePublishWriteConfirmation` 覆盖（未带 `--confirmed` 返回 `capability_publish_requires_confirm` 并以退出码 2 阻断）：

- `POST /api/v1/capabilities`
- `PUT /api/v1/capabilities/{cap_id}`
- `DELETE /api/v1/capabilities/{cap_id}`
- `POST /api/v1/capabilities/{cap_id}/submit-review`
- `POST /api/v1/capabilities/{cap_id}/offline`
- `POST /api/v1/capabilities/{cap_id}/online`

### 5.4 订单售后确认闸门（L4，需 `--confirmed`）

`rest_request.js` 的 `enforceOrderAftersaleConfirmation` 覆盖（未带 `--confirmed` 返回 `order_aftersale_requires_confirm` 并以退出码 2 阻断）：

- `POST /api/v1/orders/{order_id}/confirm`
- `POST /api/v1/orders/{order_id}/cancel`
- `POST /api/v1/orders/{order_id}/rework`
- `POST /api/v1/orders/{order_id}/rating`
- `POST /api/v1/orders/{order_id}/disputes`
- `POST /api/v1/disputes/{dispute_id}/evidence`

订单沟通（`chat/messages`、`chat/read`）为低风险写，不强制确认。

### 5.5 外发确认闸门（L4，需 `--confirmed`）

`rest_request.js` 的 `enforceExternalDataConfirmation` 覆盖 `capability-adapters` 创建/更新/沙箱/注册。

### 5.6 账号类商品上架确认闸门（L4，需 `--confirmed`）

`rest_request.js` 的 `enforceAccountAssetPublishConfirmation` 覆盖（未带 `--confirmed` 返回 `account_asset_publish_requires_confirm` 并以退出码 2 阻断）：

- `POST /api/v1/digital-assets/account-inventory`
- `POST /api/v1/digital-assets/account-shared`
- `POST /api/v1/digital-assets/{asset_id}/account-publish`
- `POST /api/v1/digital-assets/{asset_id}/inventory-items/bulk`
- `PATCH /api/v1/digital-assets/inventory-items/{item_id}`
- `POST /api/v1/digital-assets/inventory-items/{item_id}/toggle-disable`

`payload`（卡密/账号明文交付内容）禁止粘贴到聊天。查看库存/售卖统计为只读，不强制确认。

### 5.7 知识资产创建确认闸门（L4，需 `--confirmed`）

`rest_request.js` 的 `enforceKnowledgeAssetWriteConfirmation` 覆盖（未带 `--confirmed` 返回 `knowledge_asset_publish_requires_confirm` 并以退出码 2 阻断）：

- `POST /api/v1/digital-assets/quick-upload`
- `PATCH /api/v1/digital-assets/{asset_id}/media`

`cover_image_url` 必填，不得用纯文字占位图。

## 6. Fail-closed 原则

价格不可知、余额不可知、路由未登记、凭证缺失、请求异常时，默认拒绝自动执行，不得绕过确认。
