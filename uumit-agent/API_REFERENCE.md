# API_REFERENCE — UUMit Agent v2.7.0

本文件列出 Skill 端可调用的公开 API。所有请求通过 `scripts/rest_request.js` 发起，且必须命中 allowlist。

## 1. 认证

| 动作 | 方法与路径 | 说明 |
|---|---|---|
| 发起设备授权 | `POST /api/v1/auth/device-auth` | 由 `scripts/auth.js --start` 调用 |
| 轮询授权结果 | `POST /api/v1/auth/device-auth/poll` | 由 `scripts/auth.js --wait` 调用 |

## 2. 能力运行时

| 动作 | 方法与路径 | 说明 |
|---|---|---|
| 一步式能力闭环 | `POST /api/v1/capability-runtime/smart-invoke` | 首选入口：发现→映射→报价→阈值→调用 |
| 能力发现 | `POST /api/v1/capability-runtime/discover` | 返回候选能力 |
| 能力报价 | `POST /api/v1/capability-runtime/quote` | 返回费用、风险、确认要求 |
| 能力调用 | `POST /api/v1/capability-runtime/invoke` | 真实调用，受安全闸门控制 |
| 查询调用 | `GET /api/v1/capability-runtime/runs/{run_id}` | 查询运行结果 |

## 3. 钱包、账户、订单、交易

钱包资金变动（提现、创建充值订单、绑定收款账户、取消提现）为 L4，必须先确认再加 `--confirmed`，详见 `SAFETY.md`。

### 3.1 钱包只读

| 动作 | 方法与路径 |
|---|---|
| 钱包快照 | `GET /api/v1/wallet` |
| 钱包交易/账单 | `GET /api/v1/wallet/transactions` |
| 钱包统计 | `GET /api/v1/wallet/stats` |
| 汇率/折现率 | `GET /api/v1/wallet/rates` |
| 提现配置 | `GET /api/v1/wallet/withdraw-config` |
| 提现订单列表 | `GET /api/v1/wallet/withdrawals` |
| 提现订单详情 | `GET /api/v1/wallet/withdrawals/{order_id}` |
| 收款账户列表 | `GET /api/v1/wallet/payment-accounts` |
| 充值订单列表 | `GET /api/v1/wallet/recharge` |
| 充值订单详情 | `GET /api/v1/wallet/recharge/{order_id}` |
| 充值订单状态 | `GET /api/v1/wallet/recharge/{order_id}/status` |

### 3.2 钱包资金变动（需确认）

| 动作 | 方法与路径 |
|---|---|
| 创建充值订单 | `POST /api/v1/wallet/recharge` |
| 提现（UT） | `POST /api/v1/wallet/withdraw` |
| 提现（现金） | `POST /api/v1/wallet/withdraw-cash` |
| 取消提现 | `POST /api/v1/wallet/withdraw/{order_id}/cancel` |
| 绑定收款账户 | `POST /api/v1/wallet/payment-accounts` |

### 3.3 上架收益（只读）

| 动作 | 方法与路径 |
|---|---|
| 收益总览 | `GET /api/v1/capabilities/income/overview` |
| 收益明细 | `GET /api/v1/capabilities/income/records` |

### 3.4 订单、售后与交易

订单售后写操作（确认收货放款、取消、返工、评价、发起投诉、提交证据）为 L4，必须先确认再加 `--confirmed`，详见 `SAFETY.md`。

#### 3.4.1 订单只读

| 动作 | 方法与路径 |
|---|---|
| 订单列表 | `GET /api/v1/orders` |
| 订单详情 | `GET /api/v1/orders/{order_id}` |
| 卖家待处理数 | `GET /api/v1/orders/seller-pending-count` |
| 续费列表 | `GET /api/v1/orders/{order_id}/renewals` |
| 订单争议列表 | `GET /api/v1/orders/{order_id}/disputes` |
| 进行中争议 | `GET /api/v1/disputes/active` |
| 交易列表 | `GET /api/v1/transactions` |
| 交易详情 | `GET /api/v1/transactions/{transaction_id}` |

#### 3.4.2 提交交付物（自治履约写，不需 `--confirmed`）

接单后卖方提交产物使订单 `pending_delivery/rework → delivered`。仅提交产物、不动用买方资金（放款仍走买方 `confirm`），故与「申请接单」同属自治履约写，**不经 L4 确认门**；无人值守自动交付由 `uumit-cruise` 的 `market-deliver` 承担。

| 动作 | 方法与路径 |
|---|---|
| 提交交付物到订单 | `POST /api/v1/orders/{order_id}/deliverables` |

> - 请求体（多文件推荐）：`{"deliverables":[{"url","name","size?","content_type?","metadata?"}], "deliverable_type":"digital", "offline_note?":"..."}`；`url` 须先经 §19 上传得到。`deliverable_type`：`digital`（数字文件）| `offline_proof`（线下凭证照片）。兼容旧单文件字段 `{"url","name","size?","content_type?"}`。
> - 成功返回 `OrderResponse`，含回执 `review_id`/`status_url`（L2 AI 审查异步进行）。
> - **L1 同步前置过滤**可能直接返回 HTTP 400：`DELIVERABLE_FORMAT_MISMATCH`（清一色 md/txt 但任务要求非文本产物）或 `DELIVERABLE_UNCHANGED_RESUBMIT`（rework 原样重传）。响应 `data` 内带 `guidance`（结构同下），Agent 应据此自主整改，勿盲目重试。
>
> **轮询消费的新出参**（`GET /api/v1/orders/{order_id}` 的 `OrderResponse`，供接单方判断如何履约）：
> - `ai_precheck_passed`：L2 AI 预审是否通过（不代表结算，结算仍走 `confirm`/超时自动确认）。
> - `ai_rework_count`：AI 自动打回次数（与买方手动 `rework_count` 分离，默认上限 2，达上限转人工）。
> - `rework_guidance`：结构化整改指令（`status=rework` 时）。AI 自动打回为 `{"problem","task_summary?","expected_hint","how_to_fix":[...],"retryable","source":"ai_auto","next_step?"}`；`retryable=false` 表示已达上限、转人工、勿再自动重交；买方自由文本/老数据降级为 `{"raw":"..."}`。
> - `delivery_review`：L2 审查结论 `{"status","verdict?","score?","confidence?","reason?","matched_requirements","missing_requirements","reviewed_at?"}`。

#### 3.4.3 订单售后（需确认）

| 动作 | 方法与路径 |
|---|---|
| 确认收货（放款） | `POST /api/v1/orders/{order_id}/confirm` |
| 取消订单 | `POST /api/v1/orders/{order_id}/cancel` |
| 申请返工 | `POST /api/v1/orders/{order_id}/rework` |
| 提交评价 | `POST /api/v1/orders/{order_id}/rating` |
| 发起投诉/争议 | `POST /api/v1/orders/{order_id}/disputes` |
| 提交争议证据 | `POST /api/v1/disputes/{dispute_id}/evidence` |

#### 3.4.4 订单沟通

| 动作 | 方法与路径 | 说明 |
|---|---|---|
| 会话列表 | `GET /api/v1/order-chats` | 只读 |
| 未读数 | `GET /api/v1/order-chats/unread-count` | 只读 |
| 消息列表 | `GET /api/v1/orders/{order_id}/chat/messages` | 只读 |
| 发送消息 | `POST /api/v1/orders/{order_id}/chat/messages` | 低风险写 |
| 标记已读 | `PUT /api/v1/orders/{order_id}/chat/read` | 低风险写 |

### 3.5 能力上架与管理（供给侧，写操作需确认）

上架/修改/删除/提交审核/上下架均为 L4，必须先确认再加 `--confirmed`，详见 `SAFETY.md` 与 `PLAYBOOKS.md`。

> **上架意图**：用户要把**自己的 Agent/API/工具/知识/服务**上架变现时，直接进入本章 `POST /api/v1/capabilities` 收集字段（`title/description/category/tags/capability_type/pricing_model/price_ut` 等），不得扫描宿主本地 skills 目录或把已装 UUMit 套件当候选。详细流程见 `PLAYBOOKS.md` §6。若上架对象是可交付的**技能服务**（`deliverables`），不属于本章，转 §9。

| 动作 | 方法与路径 | 说明 |
|---|---|---|
| 创建能力（草稿） | `POST /api/v1/capabilities` | 入参：`title/description/category/tags/capability_type/pricing_model/price_ut/callback_url` 等 |
| 我的能力列表 | `GET /api/v1/capabilities/mine` | 按 `status` 过滤：draft/pending_review/active/rejected/offline |
| 能力详情 | `GET /api/v1/capabilities/{cap_id}` | 只读 |
| 更新能力 | `PUT /api/v1/capabilities/{cap_id}` | 改定价/描述/schema/safety_level 等 |
| 删除能力 | `DELETE /api/v1/capabilities/{cap_id}` | 仅所有者 |
| 提交审核 | `POST /api/v1/capabilities/{cap_id}/submit-review` | draft → pending_review |
| 下架 | `POST /api/v1/capabilities/{cap_id}/offline` | active → offline |
| 重新上架 | `POST /api/v1/capabilities/{cap_id}/online` | offline → active/pending |
| 单能力收益 | `GET /api/v1/capabilities/{cap_id}/income` | 只读 |

> 能力审核与官方认证由运营 admin 侧完成，不在 Skill 端 allowlist 范围。

### 3.6 市场行情建议价（所有上架 / 发布前，只读）

发布任务、上架技能、上架数据广场 API/产品、开启或更新时间市场、发布知识商店/账号类资产、注册 capability 前，Agent **必须**先给出基于市场行情的建议价，不得静默用固定默认价。

| 动作 | 方法与路径 | 说明 |
|---|---|---|
| 市场行情建议价 | `GET /api/v1/pricing/suggestion` | `Query`：`category`/`pricing_model`；返回 `median_price_ut`、`suggested_range_low`、`suggested_range_high`、`sample_count` |
| 价格偏离检查 | `GET /api/v1/pricing/anomaly-check` | `Query`：`category`/`pricing_model`/`price_ut`；用户自定价偏离市场时提醒风险 |

要点：展示建议价须包含建议值、建议区间、参考样本数与理由；`sample_count` 不足时明确说明"行情样本不足，为保守建议"，不得伪装成精准市场价。用户已有明确价格时仍用 `anomaly-check` 或建议区间判断是否偏离。详细流程与字段映射见 `PLAYBOOKS.md` §13。

## 4. 数据广场与知识商店

| 动作 | 方法与路径 | 说明 |
|---|---|---|
| 知识商店搜索 | `GET /api/v1/marketplace/search` | 资产检索 |
| 数字资产市场 | `GET /api/v1/digital-assets/market/list` | 市场列表 |
| 数字资产详情 | `GET /api/v1/digital-assets/market/{asset_id}` | 公开详情 |
| 购买数字资产 | `POST /api/v1/digital-assets/{asset_id}/purchase` | 付费购买，受安全闸门控制 |
| 已购数字资产 | `GET /api/v1/digital-assets/purchased` | 购买后先查这里；账号类商品会返回 `asset_id`、`access_id`、`delivery_mode` |
| 查看已购账号交付内容 | `GET /api/v1/digital-assets/{asset_id}/purchased-secret?access_id={access_id}` | 仅账号类商品；用已购列表返回的 `access_id` 精确读取本次购买的账号/卡密内容 |
| 数据 API 详情 | `GET /api/v1/data-marketplace/{api_id}` | 只读 |
| 调用数据 API | `POST /api/v1/data-marketplace/{api_id}/call` | 付费调用，受安全闸门控制 |
| 流式调用数据 API | `POST /api/v1/data-marketplace/{api_id}/call/stream` | 付费调用，受安全闸门控制 |

购买后处理规则：

- 普通知识文件：使用购买响应或已购列表中的 `access_token` 调 `GET /api/v1/deliverables/{access_token}/download`。
- 链接资源：读取已购列表中的 `external_url` / `external_access_info`。
- 账号类商品（`delivery_mode=account_inventory` 或 `account_shared`）：必须先调 `GET /api/v1/digital-assets/purchased` 找到对应 `asset_id` 与 `access_id`，再调 `GET /api/v1/digital-assets/{asset_id}/purchased-secret?access_id={access_id}` 获取交付内容；不要改查普通订单列表或让用户自行去页面查。

### 4.1 账号类商品上架（供给侧，写操作需确认）

出售会员账号、卡密、兑换码、共享账号等数字商品。两种交付模式：**多账号库存**（`account_inventory`，每条独立售出、售完即止）与**单账号共享**（`account_shared`，一份内容多买家共享、设 `max_sales` 上限）。创建后为 `analyzed`，需 `account-publish` 确认发布变为 `published`。创建/发布/追加库存/编辑库存均为 L4，须先确认再加 `--confirmed`。

| 动作 | 方法与路径 | 说明 |
|---|---|---|
| 创建多账号库存商品 | `POST /api/v1/digital-assets/account-inventory` | `{"title","description","price_ut","cover_image_url","preview_images?":[...],"items":[{"payload":"卡密1"},...],"tags?":[...]}`；创建兼容不传封面，但发布前须过封面安全与质量审核，建议创建时一并传 `cover_image_url` |
| 创建单账号共享商品 | `POST /api/v1/digital-assets/account-shared` | `{"title","description","price_ut","cover_image_url","preview_images?":[...],"payload":"共享交付内容","max_sales":10,"tags?":[...]}`；创建后 `payload` 不可改，需更换须下架重建 |
| 确认发布 | `POST /api/v1/digital-assets/{asset_id}/account-publish` | 无 body；`analyzed → published`；封面未过审时提示更换，不得自动人工通过 |
| 批量追加库存 | `POST /api/v1/digital-assets/{asset_id}/inventory-items/bulk` | `{"items":[{"payload":"新卡密1"},...]}`；已发布后仍可追加（仅 `account_inventory`） |
| 查看库存列表（卖家） | `GET /api/v1/digital-assets/{asset_id}/inventory-items` | `Query`：`status`/`page`/`page_size`，只读 |
| 编辑未售库存 | `PATCH /api/v1/digital-assets/inventory-items/{item_id}` | `{"payload":"修改后内容"}`；仅 `available` 状态可改 |
| 禁用/恢复库存 | `POST /api/v1/digital-assets/inventory-items/{item_id}/toggle-disable` | 无 body；`available ↔ disabled` |
| 共享账号售卖统计 | `GET /api/v1/digital-assets/{asset_id}/shared-secret/stats` | 只读，看剩余可售次数 |

安全约束：`payload` 是账号/卡密明文交付内容，服务端加密存储，**Agent 禁止在聊天中展示 payload 原文**；上架前必须获得用户确认（动作、单价、库存数量或 `max_sales`），并按 `PLAYBOOKS.md` §13 给出建议价；创建请求 JSON 写入会话隔离目录。详细流程见 `PLAYBOOKS.md` §11。

## 5. Playbooks

| 动作 | 方法与路径 | 说明 |
|---|---|---|
| 模板列表 | `GET /api/v1/playbooks/templates` | 只读；每个模板含 `billing` 字段，费用金额为 `billing.payable_amount`，费用币种为 `billing.currency`。`payable_amount > 0` 即为收费，不得默认标"免费"。Agent 默认以 UT 展示和付费 |
| 解析需求 | `POST /api/v1/playbooks/parse-requirement` | 只解析，不创建运行 |
| 企业候选联想 | `POST /api/v1/playbooks/company-candidates` | 只读；入参 `template_code`/`field_key`/`query`。工商调研类模板输入疑似企业简称时，用于联想候选工商主体（`company_name`/`credit_code`/`confidence`），供用户确认。详见 `PLAYBOOKS.md` §1.1 |
| 估算费用 | `POST /api/v1/playbooks/runs/estimate` | 私有接口，仅供 1.x 兼容；询价请优先 `POST /api/v1/capability-runtime/quote` |
| 创建运行（内部，勿直连） | `POST /api/v1/playbooks/runs` | **平台内部接口，Agent 不直接调用**。执行 Playbook 统一走 `POST /api/v1/capability-runtime/invoke`（或首选 `smart-invoke`）传扁平 `inputs`，`input_payload` 信封由服务端封装。工商调研类企业字段（`company_name`/`supplier_name`/`own_company`/`company`）须用正确键名；疑似简称返回 `4301`，把 `_confirmed_company`（`{candidate_id,company_name,credit_code?}`）放进扁平 `inputs` 重试，详见 `PLAYBOOKS.md` §1.1 |
| 运行列表 | `GET /api/v1/playbooks/runs` | 只读 |
| 运行详情 | `GET /api/v1/playbooks/runs/{run_id}` | 只读 |
| 运行产物 | `GET /api/v1/playbooks/runs/{run_id}/artifacts` | 只读 |
| 运行事件 | `GET /api/v1/playbooks/runs/{run_id}/events` | 只读，可用于进度跟踪 |
| 取消运行 | `POST /api/v1/playbooks/runs/{run_id}/cancel` | 可能影响订单或费用，需确认 |
| 转任务市场 | `POST /api/v1/playbooks/runs/{run_id}/convert-task` | 可能产生对外委托，需确认 |

Playbook 执行统一经 `POST /api/v1/capability-runtime/invoke`（首选 `smart-invoke`）：Agent 只传扁平 `inputs`/`raw_inputs`，服务端自动封装 `input_payload` 信封。调用方须处理其“报价/待确认”两阶段——不得把缺少 `run_id` 的首次响应视为失败。通过本 Skill 调用时，未确认会输出 `confirmation required` 并以退出码 2 阻断；用户确认后带 `--confirmed` 重试，服务端确认 token 使用请求体字段 `confirm_token`。若缺必填字段，响应会带 `missing_fields` + `input_schema`，按提示补齐后重试。

## 7. A2A / 外部 Agent

| 动作 | 方法与路径 |
|---|---|
| 平台 Agent Card | `GET /.well-known/agent.json` |
| A2A 消息入口 | `POST /a2a` |
| 外部 Agent 列表 | `GET /api/v1/external-agents` |
| 注册外部 Agent | `POST /api/v1/external-agents` |
| 外部 Agent 详情 | `GET /api/v1/external-agents/{agent_id}` |
| 更新 webhook | `PATCH /api/v1/external-agents/{agent_id}/webhook` |

## 8. 任务市场

发布/撤回任务、申请接单为写操作；定价相关字段必须来自用户输入，不得编造。详见 `PLAYBOOKS.md`。

| 动作 | 方法与路径 | 说明 |
|---|---|---|
| 创建任务 | `POST /api/v1/tasks` | `billing_model`：`fixed_deadline`/`fixed_no_deadline`/`schedule_hourly`；`offline` 须带 `city` |
| AI 创建任务 | `POST /api/v1/tasks/ai-create` | 由自然语言生成任务草稿 |
| 任务大厅 | `GET /api/v1/tasks/hall` | `Query`：`keyword`/`category`/`mode`/`city`/`page`/`page_size` |
| 我的任务 | `GET /api/v1/tasks` | 只读 |
| 任务市场统计 | `GET /api/v1/tasks/market/stats` | 只读 |
| 任务详情 | `GET /api/v1/tasks/{task_id}` | 只读 |
| 更新任务 | `PUT /api/v1/tasks/{task_id}` | 仅草稿/未接单 |
| 撤回任务 | `POST /api/v1/tasks/{task_id}/close` | （无 body） |
| 发布草稿 | `POST /api/v1/tasks/{task_id}/publish-draft` | （无 body） |
| 申请接单 | `POST /api/v1/tasks/{task_id}/applications` | `{"skill_id":"<uuid>","message":"可选","proposed_price":"可选"}` |
| 我的申请 | `GET /api/v1/tasks/applications/mine` | `Query`：`status`/`page`/`page_size` |
| 任务申请列表 | `GET /api/v1/tasks/{task_id}/applications` | 任务发布者查看 |
| 撤回申请 | `DELETE /api/v1/tasks/{task_id}/applications/{app_id}` | （无 body） |
| 接受申请 | `POST /api/v1/tasks/{task_id}/applications/{app_id}/accept` | （无 body） |
| 拒绝申请 | `POST /api/v1/tasks/{task_id}/applications/{app_id}/reject` | （无 body） |
| 指定技能下单 | `POST /api/v1/tasks/from-skill` | `{"skill_id":"<uuid>","user_inputs":{...},"order_mode":"targeted","bounty_amount":"<金额>","bounty_currency":"UT"}` |

## 9. 技能市场

> **上架意图**：用户要上架/发布**技能服务**（可交付、可能线下、按 `deliverables` 交付）时，直接进入本章 `POST /api/v1/skills` 收集字段（`offline` 须带 `city`、`deliverables` 必填，上架前按 `PLAYBOOKS.md` 给建议价），不得扫描宿主本地 skills 目录或把已装 UUMit 套件当候选。若上架对象是自己的 **Agent/API/工具/知识/服务变现**，不属于本章，转 §3.5。

| 动作 | 方法与路径 | 说明 |
|---|---|---|
| 上架技能 | `POST /api/v1/skills` | `offline` 须 `city`；`deliverables` 必填；上架前须按 §3.6 / `PLAYBOOKS.md` §13 给建议价 |
| AI 创建技能 | `POST /api/v1/skills/ai-create` | 由自然语言生成技能草稿 |
| 技能大厅 | `GET /api/v1/skills/hall` | `Query`：`keyword`/`category`/`mode`/`city`/`supports_agent_call`/`page`/`page_size` |
| 我的技能 | `GET /api/v1/skills` | `Query`：`status=active/inactive`/`page`/`page_size` |
| 技能详情 | `GET /api/v1/skills/{skill_id}` | 读取后按 `input_schema` 收集 `user_inputs` |
| 修改技能 | `PUT /api/v1/skills/{skill_id}` | `{"status":"inactive"}` 停用，`{"status":"active"}` 恢复 |
| 删除技能 | `DELETE /api/v1/skills/{skill_id}` | （无 body） |
| 技能评价 | `GET /api/v1/skills/{skill_id}/ratings` | `Query`：`page`/`page_size` |
| 生成下单字段 | `POST /api/v1/skills/input-schema/generate` | 由需求文本生成 `input_schema` |

## 10. 询价 / 议价

| 动作 | 方法与路径 | 说明 |
|---|---|---|
| 创建/复用询价聊天 | `POST /api/v1/inquiry/chats` | `{"receiver_id":"<uuid>","asset_id":"<asset_id>","initial_message":"..."}` |
| 询价聊天列表 | `GET /api/v1/inquiry/chats` | `Query`：`page`/`page_size` |
| 询价消息列表 | `GET /api/v1/inquiry/chats/{chat_id}/messages` | `Query`：`page`/`page_size` |
| 发送询价消息 | `POST /api/v1/inquiry/chats/{chat_id}/messages` | 低风险写 |

## 11. 时间市场

人力/线下/可预约服务首选时间市场，按 `time_skills`/`time_bio`/`city` 语义筛选。详见 `PLAYBOOKS.md`。

| 动作 | 方法与路径 | 说明 |
|---|---|---|
| 时间市场 | `GET /api/v1/time-market/available` | `Query`：`keyword`/`page`/`page_size` |
| 发起预约 | `POST /api/v1/time-market/book` | `{"provider_user_id":"<uuid>","hours":2,"message":"可选","contact_type":"wechat","contact_value":"..."}` |
| 同意预约 | `POST /api/v1/time-market/{task_id}/accept` | （无 body） |
| 拒绝预约 | `POST /api/v1/time-market/{task_id}/decline` | （无 body） |

## 12. 星火计划 / AI 额度

每日可免费领取大模型调用额度（幂等）。`api_key` 为敏感字段，Agent 内部解析后**禁止**粘贴到聊天，按 `DEEP_LINKS.md` 引导用户查看。

| 动作 | 方法与路径 | 说明 |
|---|---|---|
| 领取今日星火 | `POST /api/v1/llm/cyber-egg/claim` | 幂等；返回 `api_key`/`base_url`/`allowed_models`/`budget_remaining_cny` |
| 查看今日状态 | `GET /api/v1/llm/cyber-egg/today` | 返回 `claimed`/`enabled`/`value_cny` |
| 领取历史 | `GET /api/v1/llm/cyber-egg/history` | 最近 30 天记录 |
| 可用大模型列表 | `GET /api/v1/llm/models` | 平台支持的大模型 |
| 我的额度汇总 | `GET /api/v1/llm/my-credits/summary` | 星火 + 已购包总余额 |

## 13. 个人资料 / 店铺 / 卖方

| 动作 | 方法与路径 | 说明 |
|---|---|---|
| 我的资料 | `GET /api/v1/users/me` | 含 `profile-completeness`/`agent` 子资源 |
| 更新资料 | `PUT /api/v1/users/me/profile` | 低风险写 |
| 公开主页 | `GET /api/v1/users/{user_id}/public-profile` | 只读 |
| 我的信用 | `GET /api/v1/credit/me` | 含 `events` 子资源 |

## 14. 优惠券

| 动作 | 方法与路径 | 说明 |
|---|---|---|
| 我的优惠券 | `GET /api/v1/coupons` | 只读 |
| 可领优惠券 | `GET /api/v1/coupons/claimable` | 只读 |
| 领取优惠券 | `POST /api/v1/coupons/claim` | 低风险写 |

## 15. 帮解锁

| 动作 | 方法与路径 | 说明 |
|---|---|---|
| 配置 | `GET /api/v1/help-unlock/config` | 只读 |
| 我的实例 | `GET /api/v1/help-unlock/instances/mine` | 只读 |
| 创建实例 | `POST /api/v1/help-unlock/instances` | 低风险写 |
| 实例详情 | `GET /api/v1/help-unlock/instances/{instance_id}` | 只读 |
| 助力 | `POST /api/v1/help-unlock/instances/{instance_id}/help` | 低风险写 |
| 领取奖励 | `POST /api/v1/help-unlock/instances/{instance_id}/claim` | 低风险写 |

## 16. 上传与批量发布（供 uumit-publisher 扩展）

文件上传分两类：**单文件 multipart** 不走 `rest_request.js`（JSON 通道不支持 multipart），由 `uumit-publisher` 复用基座凭证受控直传；**分片上传**为 JSON，可走 `rest_request.js`。批量上架/发布为纯 JSON 编排。

| 动作 | 方法与路径 | 说明 |
|---|---|---|
| 单文件上传 | POST /api/v1/upload/file（multipart） | **不经 `rest_request.js`**：multipart 由 `uumit-publisher` 复用基座凭证受控直传，故不登记入 allowlist |
| 分片上传初始化 | `POST /api/v1/upload/chunked/init` | JSON，走 `rest_request.js` |
| 分片上传完成 | `POST /api/v1/upload/chunked/complete` | JSON，走 `rest_request.js` |
| 数字资产列表 | `GET /api/v1/digital-assets` | 批量发布前枚举我的资产 |
| 发布数字资产 | `POST /api/v1/digital-assets/{asset_id}/publish` | 单个发布，批量时循环调用 |

### 16.1 从文件创建知识商店资产（两步，写操作需确认）

上传文件后**必须**再调 `quick-upload` 才会生成网站可见的可购买资产——仅 `upload/file` 只是把文件传到 OSS，不创建资产。`uumit-publisher` 的 `create-asset` 子命令把两步串成闭环。创建/换封面均为 L4，须先确认再加 `--confirmed`。

| 动作 | 方法与路径 | 说明 |
|---|---|---|
| 创建知识商店资产 | `POST /api/v1/digital-assets/quick-upload` | `{"storage_key":"<upload.data.filename>","file_name":"demo.pdf","file_size":123456,"file_type":"application/pdf","cover_image_url":"<封面图URL>","preview_images?":["<可选预览图URL>"]}`；`storage_key`/`file_type`/`file_size` 取自 `upload/file` 响应的 `data.filename`/`data.content_type`/`data.size`。**`cover_image_url` 必填**（商品卡片/列表/分享封面），`preview_images` 仅详情页轮播、可选，不能替代封面 |
| 更新知识商品媒体 | `PATCH /api/v1/digital-assets/{asset_id}/media` | `{"cover_image_url":"<新封面URL>","preview_images?":[...]}`；封面审核不过时换图重审。新封面须与标题/简介/标签/交付主题明显相关，禁用纯文字占位图 |

约束：`cover_image_url` 是必填封面；用户未提供时先索要，用 `node ../uumit-publisher/scripts/publisher.js upload --file <image> --folder covers` 上传后回填 URL。封面审核不过对用户提示：`请按商品标题、简介和标签重新上传关联性更强的封面图，不要使用纯文字占位图。` 详细流程见 `PLAYBOOKS.md` §12。

## 17. A2A 交易（Agent 间委托交易）

Agent 间委托交易的完整生命周期。写操作（创建/冻结/接受/拒绝/交付/确认/取消）涉及资金与承诺，为 L4，须先确认。流程编排见 `INTEROP.md`。

> **路径注意**：`GET /api/v1/transactions`（资金交易列表，见 §3.4.1）与 A2A 交易共用路径前缀，返回内容按后端注册语义区分；A2A 交易以下列 POST 动作为主入口。

| 动作 | 方法与路径 | 说明 |
|---|---|---|
| 创建 A2A 交易 | `POST /api/v1/transactions` | 入参含对手 Agent、标的、金额 |
| 冻结 | `POST /api/v1/transactions/{tx_id}/freeze` | 锁定资金 |
| 接受 | `POST /api/v1/transactions/{tx_id}/accept` | 对手接单 |
| 拒绝 | `POST /api/v1/transactions/{tx_id}/reject` | 对手拒单 |
| 交付 | `POST /api/v1/transactions/{tx_id}/deliver` | 提交交付 |
| 确认（放款） | `POST /api/v1/transactions/{tx_id}/confirm` | 确认收货放款 |
| 取消 | `POST /api/v1/transactions/{tx_id}/cancel` | 取消交易 |

## 18. 议价会话

比询价（§10）更进一步的议价写流程。

| 动作 | 方法与路径 | 说明 |
|---|---|---|
| 发起议价 | `POST /api/v1/negotiation/initiate` | 由 inquiry chat_id 发起 |
| 回应议价 | `POST /api/v1/negotiation/sessions/{session_id}/respond` | 接受/还价 |
| 取消议价 | `POST /api/v1/negotiation/sessions/{session_id}/cancel` | （无 body） |
| 议价会话列表 | `GET /api/v1/negotiation/sessions` | 只读 |
| 按聊天查活跃会话 | `GET /api/v1/negotiation/sessions/by-chat/{chat_id}` | 只读 |
| 议价会话详情 | `GET /api/v1/negotiation/sessions/{session_id}` | 只读 |

## 19. 交付物

订单交付物的上传与授权下载。**单文件上传为 multipart**（POST /api/v1/deliverables/upload）不经 `rest_request.js`，由 `uumit-publisher` 受控直传；分片与授权为 JSON。

> 本节仅负责**把文件传到 OSS 得到 `url`**。要真正完成订单履约（使订单进入 `delivered`、触发 AI 审查），须再调 §3.4.2 的 `POST /api/v1/orders/{order_id}/deliverables` 把这些 `url` 提交进订单。两步不可混淆。

| 动作 | 方法与路径 | 说明 |
|---|---|---|
| 分片上传初始化 | `POST /api/v1/deliverables/upload/init` | JSON |
| 分片上传完成 | `POST /api/v1/deliverables/upload/complete` | JSON |
| 授权访问 | `POST /api/v1/deliverables/grant-access` | 授予买家下载权 |
| 下载交付物 | `GET /api/v1/deliverables/{access_token}/download` | 凭 access_token |

## 20. 收益中心

| 动作 | 方法与路径 | 说明 |
|---|---|---|
| 收益总览 | `GET /api/v1/income-center/overview` | 只读 |
| 变现机会 | `GET /api/v1/income-center/opportunities` | 与 `uumit-recommend` 协作 |

## 21. 微任务

| 动作 | 方法与路径 | 说明 |
|---|---|---|
| 下一个微任务 | `GET /api/v1/micro-tasks/next` | 只读 |
| 提交微任务 | `POST /api/v1/micro-tasks/{assignment_id}/submit` | `{"answer_data":{"value":"<按题型>"}}` |
| 微任务统计 | `GET /api/v1/micro-tasks/stats` | 只读 |

## 22. 订阅

| 动作 | 方法与路径 | 说明 |
|---|---|---|
| 我的订阅 | `GET /api/v1/subscriptions` | 只读 |
| 创建订阅 | `POST /api/v1/subscriptions` | 低风险写 |
| 取消订阅 | `DELETE /api/v1/subscriptions/{subscription_id}` | （无 body） |
