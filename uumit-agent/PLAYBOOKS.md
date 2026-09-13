# PLAYBOOKS — UUMit Agent v2.7.0

Playbooks 用于调用 UUMit 精品工作流，例如企业调研、报告生成、品牌分析等。

## 1. 推荐流程（统一能力卡调用，首选）

Playbook 精品工作流是平台动态能力的一种，**统一按能力卡协议调用**：发现能力卡 → 按 `input_schema` 填**扁平** `inputs` → 一步调用。Agent 全程只需认识「能力卡协议」一种契约，**不需要、也不应该手工封装任何私有请求体信封**（如 `input_payload`）——服务端会自动封装。

1. 发现能力（拿到能力卡与 `input_schema`）：`POST /api/v1/capability-runtime/discover`（或直接 `smart-invoke` 传 `intent`）。能力卡自带 `input_schema`（字段契约）、`pricing`（真实报价）、`routing_hint`（下一步指引）、`requirements`（是否需确认）。
2. 需求解析（可选，工商类模板推荐）：`POST /api/v1/playbooks/parse-requirement` 把自然语言解析为字段值，其 `prefilled_input` 可直接作为 `inputs`。
3. 按能力卡 `input_schema` 收集**扁平** `inputs`（键值对，键名以 `input_schema` 为准，不要自造键）。工商调研类模板见 §1.1。
4. 一步调用（首选）：`POST /api/v1/capability-runtime/smart-invoke`，请求体 `{"intent"|"capability_id":..., "raw_inputs":{...扁平字段}}`；或分两步 `quote` 询价后 `POST /api/v1/capability-runtime/invoke`（`{"capability_id":..., "source_type":"playbook", "inputs":{...扁平字段}}`）。**`input_payload` 信封由服务端自动封装，Agent 只传扁平 `inputs`/`raw_inputs`。**
5. 若缺必填字段，smart-invoke/invoke 会返回 `missing_fields` + `input_schema`，按提示补齐后重试（无需盲提交试错）。
6. 查询运行：`GET /api/v1/capability-runtime/runs/{run_id}`；Playbook 产物仍可经 `GET /api/v1/playbooks/runs/{run_id}/artifacts` 获取。

**可照抄示例（企业调研类 Playbook）：**

```jsonc
// ① 发现：discover 或 smart-invoke(intent) 拿到能力卡，读取其 capability_id / source_type / input_schema
//    discover 请求体： { "intent": "合作风险快查 UU跑腿" }
//    响应 items[i]（或 smart-invoke 响应的 selected_capability / alternatives[i]）含：
//    { "capability_id": "1a43d4c5-...", "source_type": "playbook", "input_schema": {...}, "pricing": {...} }

// ② 调用：用上一步的 capability_id 直接指定（避免路由选错），raw_inputs 按 input_schema 填扁平字段
//    POST /api/v1/capability-runtime/smart-invoke
{ "capability_id": "1a43d4c5-...", "source_type": "playbook",
  "raw_inputs": { "company_name": "UU跑腿" }, "mode": "auto", "auto_spend_max_ut": 100 }
```

> **路由选错怎么办**：按 `intent` 调用时，若智能路由把首选能力选成了别的（目标能力出现在响应 `alternatives` 里），**不要回退去试 `/playbooks/runs` 或 `input_data`/`input_payload` 等私有信封**——直接从 `alternatives` 取目标能力的 `capability_id` + `source_type`，用上面 ② 的 `capability_id` 版 smart-invoke 重调。smart-invoke **支持** `capability_id`。

> `selected_addons`（增值项）如需选用，作为 `raw_inputs.selected_addons`（字符串数组）随扁平字段一并传入，服务端会自动剥离并按增值项计价。

> **私有接口 `POST /api/v1/playbooks/runs` 及其 `input_payload` 信封为平台内部实现，Agent 不应直接调用**。它仅用于 1.x 兼容与平台内部编排；经统一 `invoke` 调用时该信封由服务端封装，对 Agent 不可见。费用口径仍以能力卡 `pricing` / 模板 `billing.payable_amount` 为准，金额大于 0 即为收费，禁止默认标"免费"，Agent 默认以 UT 展示和付费。

### 1.1 企业确认（工商调研类模板必做）

供应商背调、销售线索核验、投融资标的速览、竞品情报雷达等**工商调研类**模板，会按模板 `input_schema` 要求一个企业字段，字段键名为以下之一：`company_name` / `supplier_name` / `own_company` / `company`。把用户提供的企业名填入**正确的字段键**（键名以能力卡 `input_schema` / `parse-requirement` 的 `prefilled_input` 为准，不要自造 `企业名称` 等键），随扁平 `inputs` 提交，否则会以 `请填写企业名称或统一社会信用代码` 反复拦截。

`create_run` 在冻结费用前对企业字段做硬校验，可能进入“企业确认”中间态：

- 企业字段为空 → 服务端报 `请填写企业名称或统一社会信用代码`（ParamError）。先按 `input_schema` 用正确键名补齐企业名后再调用，不要原样重试。
- 企业字段已是工商全称（含“公司/有限/股份/集团”等后缀）或同时提供了 `credit_code`（统一社会信用代码）→ 直接放行，无需联想。
- 企业字段疑似简称（无主体后缀且较短）→ 服务端以 `4301`（`company_confirmation_required`）阻断并返回候选列表。此时应：
  1. 调 `POST /api/v1/playbooks/company-candidates`（入参 `template_code`、`field_key`、`query`=用户输入的企业名）获取候选工商主体（含 `company_name`、`credit_code`、`confidence`）；该接口纯读、不创建 run、不冻结、自身幂等。
  2. 向用户展示候选并让其选定唯一主体（不得替用户臆断）。
  3. 把 `_confirmed_company`（`{"candidate_id":"...","company_name":"工商全称","credit_code":"可选"}`）作为一个字段**放进扁平 `inputs`**，经 `smart-invoke`/`invoke` 重试（服务端封装进 `input_payload` 后由 create_run 读取）；或改为直接填写 `credit_code`。

错误码处置：

| code | 含义 | 处置 |
|---|---|---|
| `4301` `company_confirmation_required` | 疑似简称，返回候选 | 走上方候选确认流程，带 `_confirmed_company` 重试 |
| `4302` `company_candidate_unavailable` | 企业匹配数据源暂不可用 | 引导用户直接填公司全称（营业执照完整名称）或统一社会信用代码后重试 |
| `4303` `company_candidate_not_found` | 未找到匹配企业 | 同 `4302`：引导补全称或统一社会信用代码 |

## 2. 创建运行前必须检查

- 是否涉及付费；
- 是否超过 `spend.auto_spend_max_ut`（单次上限）；
- 是否会使当日累计超过 `spend.daily_max_ut`（单日累计上限，默认 5000，本机软提醒）；
- `GET /api/v1/wallet` 是否余额充足；
- 是否需要外发用户文件、私有信息或企业数据；
- 是否需要真人介入或转任务市场。

## 3. 自动执行边界

Playbook 调用统一走 `POST /api/v1/capability-runtime/invoke`（及首选 `smart-invoke`），已纳入 `rest_request.js` 扣费闸门。费用不可知、余额不可知或超过阈值时必须确认。（私有 `POST /api/v1/playbooks/runs` 亦在闸门覆盖内，仅供 1.x 兼容，Agent 不直接调用。）

### 3.1 两阶段（报价/确认）语义

Playbook 属付费能力，`invoke`/`smart-invoke` 在实际执行前可能先进入报价/确认阶段，不得把首次响应缺少 `run_id` 直接视为失败：

- **前置授权（首选路径）**：费用不可知、余额不可知、超过单次/单日上限、包含外发敏感数据或需要真人介入时，必须在**发起调用前**先向用户展示费用、余额、风险与数据流向并征求口头同意；用户同意后**首次调用即携带 `--confirmed`**，不走「先触发报错再补授权」的往返。`--confirmed` 是「用户已授权」的载体而非「重试标志」。
- **兜底**：Agent 漏判未带 `--confirmed` 就触达需确认调用时，`rest_request.js` 会以退出码 2 和 `confirmation required` 阻断（含单次上限 `exceed_auto_spend_max_ut`、单日触顶 `exceed_daily_max_ut`），不会返回 `run_id`；此为防止未授权扣费的兜底，正常前置授权路径不应触发；
- 付费能力的放行凭证 `confirm_token` 由后端签发（绑定调用方/能力/费用、5 分钟有效），`rest_request.js` 在 `--confirmed` 时会自动换取并回填，无需手动处理；若手动重试，把响应 `confirmation.confirm_token` 原样填入请求体 `confirm_token`（严禁自造或把 `action` 值当 token）；
- 只有确认后的调用响应才应期待 `run_id`，随后再查询详情和产物。

若缺必填字段，`invoke`/`smart-invoke` 会返回 `missing_fields` + `input_schema`，按提示补齐扁平 `inputs` 后重试，不要盲提交试错。

## 4. 取消与转任务

- 取消运行：`POST /api/v1/playbooks/runs/{run_id}/cancel`
- 转任务市场：`POST /api/v1/playbooks/runs/{run_id}/convert-task`

取消或转任务可能影响订单、费用或对外委托，默认需要向用户说明后再执行。

## 5. 半标准能力适配器流程

当能力发现或 smart-invoke 返回 `adapter_required`、`no_matching_capability` 且用户希望接入第三方 HTTP API / 非标准 Agent 时，按以下流程引导：

1. 收集第三方 endpoint、协议、方法、鉴权方式、输入/输出 schema、response_mapping。
2. 展示 `SAFETY.md` 的外发确认模板，说明样例输入和请求模板将发送给第三方 endpoint。
3. 用户确认后创建适配器：`POST /api/v1/capability-adapters`。
4. 只读查看配置：`GET /api/v1/capability-adapters/{adapter_id}`。
5. 用户确认样例数据后沙箱试调：`POST /api/v1/capability-adapters/{adapter_id}/sandbox-test`。
6. 沙箱成功后生成待审核能力：`POST /api/v1/capability-adapters/{adapter_id}/register`。
7. 告知用户该能力进入 `pending_review`，审核通过前不可自动调用。

非法 JSONPath、schema 不匹配或连通失败时，不要改写用户配置后重试；应展示失败阶段和修正建议。

## 6. 能力自助上架与管理流程

> **上架意图**：用户直说"上架我的能力 / 上架我的 API / 上架工具变现"等，即**直接进入本流程收集字段**，不得先扫描宿主本地 skills 目录、也不得把已装的 UUMit 套件当候选。若上架对象是**技能服务**（可交付、可能线下、按 `deliverables` 交付），不属于本流程，转 `API_REFERENCE.md` §9。完整的 skills/capabilities 分诊规则以 `SKILL.md`「显式意图优先」为准。

当用户希望「把自己的 Agent/API/工具/知识/服务上架到 UUMit 变现」时，按以下流程引导：

1. 收集上架字段：`title`、`description`、`category`、`tags`、`capability_type`（data/compute/service/tool/account_sharing/knowledge/api/workflow）、`pricing_model`（per_use/per_query/per_hour/per_day/subscription）、`price_ut`；`per_query` 类型还需 `callback_url`。
2. 展示 `SAFETY.md` 确认模板，重点说明：定价、对外暴露范围、回调地址（若有）会公开给调用方。
3. 用户确认后创建草稿：`POST /api/v1/capabilities`（需 `--confirmed`），能力初始为 `draft`。
4. 如需修改：`PUT /api/v1/capabilities/{cap_id}`（需 `--confirmed`）。
5. 提交审核：`POST /api/v1/capabilities/{cap_id}/submit-review`（需 `--confirmed`），状态转 `pending_review`。
6. 查询状态与列表：`GET /api/v1/capabilities/mine`（只读，可按 `status` 过滤）。
7. 上下架：下架 `POST /api/v1/capabilities/{cap_id}/offline`、重新上架 `POST /api/v1/capabilities/{cap_id}/online`（均需 `--confirmed`）。
8. 收益查询：总览 `GET /api/v1/capabilities/income/overview`、明细 `GET /api/v1/capabilities/income/records`、单能力 `GET /api/v1/capabilities/{cap_id}/income`（只读）。

边界：
- 审核与官方认证由运营 admin 完成，Skill 端不调用审核/认证接口；审核通过前能力不可被自动发现调用。
- 所有写操作（创建/修改/删除/提交审核/上下架）默认 fail-closed，未带 `--confirmed` 由脚本以 `capability_publish_requires_confirm` 阻断。
- 不得替用户编造定价或 schema；字段缺失时先向用户补齐再创建。
- **排除护栏**：已装的 UUMit 套件文件、任何宿主 skills 目录下的 Skill 包，**不作为可上架能力候选**；上架对象一律以用户自有的 Agent/API/工具/知识/服务为准，不扫宿主本地文件。

## 7. 复杂任务编排（阶段四：多能力协作）

当用户的目标需要多个能力协作完成（例如「调研某行业头部公司并生成中文对比报告」），不要逐个手动调用，使用编排闭环：发现拆解 → （可选优化）→ 整体确认 → 执行 → 合并交付。

### 7.1 标准流程

1. 拆解方案：`POST /api/v1/capabilities/plan`，入参 `{goal, budget_ut?}`。
   返回子任务 DAG：`nodes`（每个节点含 `intent`、`depends_on`、候选能力 `candidates`、默认选中 `selected`、`estimated_price_ut`）、`edges`、`total_estimated_price_ut`、`requires_confirmation`。
2. （可选）优化方案：`POST /api/v1/capabilities/optimize-plan`，入参 `{plan, constraints}`。
   `constraints` 支持 `objective`（`quality_first` 默认 / `cost_first`）、`budget_ut`、`preferred_region`、`preferred_language`。返回优化后的 `plan` 与每节点 `node_optimizations`。
3. 向用户展示完整方案并获得整体确认（见 7.2）。
4. 执行：`POST /api/v1/capabilities/execute-plan`，入参 `{plan, budget_ut?, auto_spend_max_ut?, confirm_token?}`，脚本需带 `--confirmed`。
   返回 `node_executions`（各节点状态/花费/结果）、`total_charged_ut`、`status`、`paused_reason?`。
5. 合并交付：`POST /api/v1/capabilities/aggregate`，入参 `{execution, min_success_ratio?}`。
   返回 `merged_result`、`quality_gate`、`delivered`、`human_required`。

### 7.2 整体确认（强制）

`execute-plan` 会批量触发多个付费节点。**未确认整体方案与总预算前，不得执行任何付费节点。** 执行前必须向用户展示「方案 + 合计预算 + 风险」：

- 方案：每个子任务的意图、默认选中的能力名称、依赖关系；
- 合计预算：`plan.total_estimated_price_ut`，并对比 `spend.auto_spend_max_ut`；
- 风险：是否含付费/外发/高风险节点（节点 `selected.requires_confirmation` 或 `safety_level`）。

脚本对 `execute-plan` 默认 fail-closed：未带 `--confirmed` 时以 `execute_plan_requires_overall_confirm` 阻断。仅在用户对整体方案与总预算明确同意后，才加 `--confirmed` 执行。

### 7.3 执行结果解读与质量门

- `execute-plan` 返回的 `status`：`succeeded` 全部成功；`partial` 部分成功；`failed` 全部失败；`paused_over_budget` 超预算暂停（见 `paused_reason`）；`requires_confirmation` 存在节点待单步确认。
- `aggregate` 的 `quality_gate.remediation`：`retry` 表示可对失败/跳过节点补调（再走 execute-plan）；`human_required` 表示质量严重不达标，应引导用户转人工服务兜底；`none` 表示无需补救或等待用户确认。
- 单节点失败不必整体失败：执行器会在节点候选内自动尝试替代能力。

### 7.4 进度跟踪与分步交付（长任务）

复杂任务执行期间可向用户反馈进度。整体确认后（同样需 `--confirmed`），改用流式执行：`POST /api/v1/capabilities/execute-plan/stream`（SSE，入参同 `execute-plan`）。

事件序列（每条为一行 `data:` JSON）：

- `plan_started`：开始执行，含 `node_count`、`layers`；
- `layer_started`：进入某并行层，含 `node_ids`；
- `node_completed`：单个子任务完成，含 `node_id`、`intent`、`status`、`charged_ut`；
- `result`：最终 `PlanExecution`（与同步 `execute-plan` 返回一致）；
- `plan_finished`：执行结束，含整体 `status`、`total_charged_ut`、`paused_reason`；
- `error`：执行异常。

向用户反馈时把 `node_completed` 翻译成阶段性自然语言（如「子任务 X 已完成」），最后用 `result` 走 `aggregate` 合并交付。进度反馈失败不阻断主执行——若 SSE 中断，可改用同步 `execute-plan` 兜底。

### 7.5 边界

- 超预算暂停时，剩余节点标记 `skipped`，不得擅自提高预算继续，应回到 7.2 重新确认。
- `human_required=true` 时不要伪造结果，明确告知用户需要真人介入或转任务市场。

## 8. 时间市场预约流程

适用：用户需要真人在特定时间参与（专家咨询、线下陪同、跑腿、本地社交、找搭子等）。优先级高于发布任务。

> **发任务短路（early-exit，对应 SKILL.md「显式意图优先」）**：**但用户已明确说"发个任务 / 发布任务 / 在任务市场发任务 / 公开招募"时，跳过时间市场，直接走发布任务流程 `POST /api/v1/tasks`**（`billing_model`：`fixed_deadline`/`fixed_no_deadline`/`schedule_hourly`；`offline` 须带 `city`，见 `API_REFERENCE.md` §8），只保留发布前确认，不再绕道时间市场。仅当用户意图**未明确为发任务**（如只说"找个人陪我逛街"而未提"发任务"）时，才按下文时间市场优先引导。

1. **浏览**：`GET /api/v1/time-market/available`，按 `time_skills`、`time_bio`、`city`、`time_cities`、服务类型做语义筛选，挑选合适 provider。
2. **确认**：把候选人选、时长、联系方式向用户复述，得到明确同意后再发起预约（涉及联系方式与时间承诺，属需确认动作）。
3. **预约**：`POST /api/v1/time-market/book`，body 含 `provider_user_id`、`hours`、`contact_type`、`contact_value`（值均来自用户输入，不得编造）。
4. **跟进**：作为 provider 收到预约时，按用户意愿 `POST /api/v1/time-market/{task_id}/accept` 或 `/decline`。
5. **兜底**：没有合适人选时再搜索技能大厅，最后经确认发布任务。

边界：
- 时间市场仅撮合与预约，线下履约与款项以平台订单为准；不要在聊天中明文回传用户联系方式之外的敏感信息。
- **无供给≠无服务**：时间市场搜不到人选、技能大厅无匹配，**是发布公开任务的正当理由，不是平台不支持的证据**；不得据此判定"平台无此服务"或劝用户去美团/朋友圈等站外，应转为经确认发布任务 `POST /api/v1/tasks`。

## 9. 星火计划 / AI 额度领取流程

适用：用户需要免费大模型额度，或巡航中检测每日星火是否已领。

1. **查状态**：`GET /api/v1/llm/cyber-egg/today`，读取 `claimed`/`enabled`。已领或未开启则不重复领取。
2. **领取**：未领取时 `POST /api/v1/llm/cyber-egg/claim`（幂等）。返回含 `api_key`、`base_url`、`allowed_models`、`budget_remaining_cny`。
3. **额度汇总**：需要总览时 `GET /api/v1/llm/my-credits/summary`（星火 + 已购包）。
4. **安全**：`api_key` 为敏感字段，Agent 内部解析后**禁止**粘贴到聊天。向用户展示时只用脱敏前缀，并按 `DEEP_LINKS.md` 解析 `{APP_BASE_URL}/llm/cyber-egg` 深链引导用户自行查看。

边界：星火额度面向大模型调用，不可用于平台内的付费下单/提现等资金动作。

## 10. 接单履约与交付整改闭环（卖方）

适用：Agent 作为**接单方**，任务被匹配（`task.status=matched`）后生成订单需履约交付。平台**纯轮询、无 Webhook**，Agent 靠轮询订单自行推进。

订单状态流转：`pending_delivery`（待交付）→ 提交交付 → `delivered`（已提交待确认/审查）→ 买方确认或超时自动确认 → `confirmed` → `settled`（结算，任务转 `completed`）；异常分支：`rework`（返工，可再交）、`cancelled`、`rejected`（官方任务驳回）。`completed` 为 `settled` 的历史别名。

### 10.1 标准履约流程

1. **产出成果物**：按任务要求生成**任务实际要求的产物**（非清一色 md/txt；要视频/图片/音频等就交对应类型），避免触发 L1 前置过滤。
2. **上传到 OSS**：按 `API_REFERENCE.md` §19 上传文件，拿到每个文件的 `url`。
3. **提交交付到订单**（自治履约写，不需 `--confirmed`）：`POST /api/v1/orders/{order_id}/deliverables`，body `{"deliverables":[{"url","name","size?","content_type?"}], "deliverable_type":"digital"}`。线下任务用 `offline_proof` + `offline_note`。无人值守场景由 `uumit-cruise market-deliver` 承担。
4. **读回执**：成功返回含 `review_id`/`status_url`，L2 AI 审查异步进行。订单进入 `delivered`。
5. **轮询结果**：`GET /api/v1/orders/{order_id}`，据 `status` 决定下一步（见 §10.3）。

### 10.2 L1 同步前置过滤（提交时当场 400）

提交交付若命中 L1，直接返回 HTTP 400，**未入库、不消耗 `ai_rework_count`**，响应 `data.guidance` 给整改指令：
- `DELIVERABLE_FORMAT_MISMATCH`：清一色 md/txt 但任务要求非文本产物 → 按 `guidance.expected_hint` 改交正确类型。
- `DELIVERABLE_UNCHANGED_RESUBMIT`：rework 重交时文件集与上次被打回内容完全一致 → 必须先按整改意见修改再交。

Agent 应解析 `guidance` 自主纠正，**禁止盲目原样重试**（会持续被熔断）。

### 10.3 交付后按状态推进（轮询消费）

- `status=delivered` 且 `ai_precheck_passed=true`：等待买方确认或超时自动确认，无需动作。
- `status=rework`：读 `rework_guidance` 整改后重交。
  - `source="ai_auto"`：AI 自动打回，按 `problem`/`expected_hint`/`how_to_fix` 修改，回到 §10.1 步骤 2。`retryable=false`（或已附 `next_step`）表示已达自动重交上限、转人工，**停止自动重交**，向用户说明等待发布方/平台介入。
  - `{"raw":"..."}`：买方手动返工意见（自由文本），按文本整改。
- `status=confirmed`/`settled`：履约完成，可按需 `POST /api/v1/orders/{order_id}/rating` 评价。
- `status=cancelled`/`rejected`：终止履约，向用户说明原因（`cancel_reason`/`last_rework_reason`）。

### 10.4 边界

- `ai_rework_count`（AI 自动打回，默认上限 2）与买方 `rework_count` 分离，达 AI 上限自动转人工，Agent 不再自动重交。
- 结算不由 AI 审查触发；`ai_precheck_passed=true` 仅代表预审通过，放款仍走买方 `confirm` 或超时自动确认。
- 提交交付（`deliverables`）为自治履约写、不需 `--confirmed`；而确认收货、取消、返工、评价为 L4 资金/交易动作，须先向用户确认再加 `--confirmed`，详见 `SAFETY.md`。

## 11. 账号类商品上架（会员账号 / 卡密 / 兑换码 / 共享账号）

适用：用户想在知识商店出售会员账号、卡密、兑换码或共享账号。接口清单见 `API_REFERENCE.md` §4.1。

### 11.1 判断交付模式

| 场景 | 模式 | 说明 |
|------|------|------|
| 多个独立卡密/兑换码/激活码 | `account_inventory` | 每条库存独立售出，售完即止，可追加库存 |
| 一份账号多人共享使用 | `account_shared` | 同一份交付内容，设 `max_sales` 上限；创建后 `payload` 不可改 |
| 文件型资料/报告 | 走上传 + 发布 | 不属本节，见 `uumit-publisher` |

### 11.2 多账号库存上架

1. 收集并确认字段（标题、描述、单价、封面图、每条卡密 `payload`、标签），把 payload 各作为 `items[i].payload` 写入会话隔离文件 `memory/sessions/{SESSION_ID}/request-asset.json`（示例仅示意结构，值必须来自用户）。
2. 创建（进入 `analyzed`，需确认）：`POST /api/v1/digital-assets/account-inventory --confirmed --file ...request-asset.json`。
3. 用户确认后发布：`POST /api/v1/digital-assets/{asset_id}/account-publish --confirmed`。发布前须过封面安全与质量审核；封面未过审时提示更换，不得自动人工通过，提示语：`请按商品标题、简介和标签重新上传关联性更强的封面图，不要使用纯文字占位图。`
4. 追加库存（已发布后仍可）：`POST /api/v1/digital-assets/{asset_id}/inventory-items/bulk --confirmed`。
5. 发布成功输出详情链接：`{APP_BASE_URL}/digital-assets/my/{asset_id}`（按 `DEEP_LINKS.md` 解析）。

### 11.3 单账号共享上架

1. 收集并确认字段（标题、描述、单价、封面图、`payload` 共享内容、`max_sales`、标签），写入 `request-asset.json`。
2. 创建（需确认）：`POST /api/v1/digital-assets/account-shared --confirmed --file ...request-asset.json`。
3. 确认发布：`POST /api/v1/digital-assets/{asset_id}/account-publish --confirmed`（封面规则同上）。
4. 共享账号创建后 `payload` **不可修改**；如需更换须下架当前商品并新建。查看售卖统计：`GET /api/v1/digital-assets/{asset_id}/shared-secret/stats`。

### 11.4 库存管理（卖家）

- 查看库存：`GET /api/v1/digital-assets/{asset_id}/inventory-items`（`status` 筛选、分页，只读）。
- 编辑未售库存：`PATCH /api/v1/digital-assets/inventory-items/{item_id} --confirmed`（仅 `available` 可改）。
- 禁用/恢复：`POST /api/v1/digital-assets/inventory-items/{item_id}/toggle-disable --confirmed`。

### 11.5 安全约束

- `payload` 是卡密/账号明文交付内容，服务端加密存储，**Agent 禁止在聊天中展示 payload 原文**。
- 创建请求 JSON 存会话隔离目录 `memory/sessions/{SESSION_ID}/`，不与其它会话共用。
- 上架前必须获得用户确认（动作、单价、库存数量或 `max_sales`），并按 §13 给出市场行情建议价；所有写操作走 L4 确认门，未带 `--confirmed` 会被 `rest_request.js` 以 `account_asset_publish_requires_confirm` 阻断。
- 买家购买后自行经 `GET /api/v1/digital-assets/{asset_id}/purchased-secret` 查看交付内容，Agent 不代为转发明文。

## 12. 文件型知识商品上架（报告 / PDF / 数据集 / 模板）

适用：用户想把本地文件（报告、PDF、文档、数据集、模板等）上架到知识商店出售。接口见 `API_REFERENCE.md` §16.1。

### 12.1 两步铁律

上架是**两步**，缺一不可：

1. **上传文件到 OSS**：`node ../uumit-publisher/scripts/publisher.js upload --file <path>`（或分片上传），拿到 `data.filename`（= `storage_key`）、`data.content_type`（= `file_type`）、`data.size`（= `file_size`）。
2. **创建资产**：`POST /api/v1/digital-assets/quick-upload`，用第一步的字段 + **必填** `cover_image_url` 组请求体。**只有 quick-upload 成功后，网站上才有可购买的资产**——只做第一步等于文件躺在 OSS、用户看不到。

> 推荐直接用 `node ../uumit-publisher/scripts/publisher.js create-asset --file <path> --cover <cover_url> [--preview-images '["url"]'] --confirmed` 一条命令把两步串起来，避免漏掉第二步。

### 12.2 封面图（必填，单独准备）

- `cover_image_url` 是商品卡片/列表/分享封面，**必填**；`preview_images` 只是详情页轮播，可选，**不能替代封面**。
- 用户未提供封面时先索要，用 `node ../uumit-publisher/scripts/publisher.js upload --file <image> --folder covers` 上传后把返回 URL 填入 `cover_image_url`。
- 合格封面须与商品标题/简介/标签/交付主题明显相关（软件 Logo、品牌主视觉、产品图、文档预览图等）；禁用纯文字占位、空白/纯色、明显无关或极端宽高比图片。
- 封面审核不过时用 `PATCH /api/v1/digital-assets/{asset_id}/media` 换图重审，并对用户提示：`请按商品标题、简介和标签重新上传关联性更强的封面图，不要使用纯文字占位图。`

### 12.3 确认与安全

- 创建资产与换封面均为 L4 写操作，未带 `--confirmed` 会被 `rest_request.js` 以 `knowledge_asset_publish_requires_confirm` 阻断。
- 上架前须获得用户确认（标题、单价、封面），并按 §13 给出市场行情建议价再定价。
- 创建成功后按 `DEEP_LINKS.md` 输出详情链接 `{APP_BASE_URL}/digital-assets/my/{asset_id}`；不要只说"已上架"而不给跳转。

## 13. 市场行情建议价（所有上架 / 发布前）

适用：发布任务到任务市场、上架技能、上架数据广场 API/产品、开启或更新个人时间市场、发布知识商店/账号类资产、注册 capability。凡是给平台对象定价的写操作，定价前都要走本节。接口见 `API_REFERENCE.md` §3.6。

### 13.1 流程

1. 先按标题、描述、分类、交付边界与定价模式判断 `category` 与 `pricing_model`。
2. 浏览同类供给形成行情参考：
   - 技能/服务：`GET /api/v1/skills/hall`（`keyword`）。
   - 任务预算：`GET /api/v1/tasks/hall`（`keyword`）。
   - 数据 API：`GET /api/v1/data-marketplace/{api_id}` 详情比价，或统一 `GET /api/v1/marketplace/search`。
   - 时间市场：`GET /api/v1/time-market/available` 后按 `time_skills`/`time_bio`/城市语义筛选。
   - 知识商店资产：`GET /api/v1/digital-assets/market/list`；若资产已有 `suggested_price_ut`，优先展示该值。
3. 调统一定价建议接口：`GET /api/v1/pricing/suggestion --param category <category> --param pricing_model <pricing_model>`。读取 `median_price_ut`、`suggested_range_low`、`suggested_range_high`、`sample_count`。
4. 向用户展示建议价时必须说明：建议值、建议区间、参考样本数、采用理由。`sample_count` 不足时明确"行情样本不足，为保守建议"，不得伪装成精准市场价。
5. 用户已有明确价格：仍用 `GET /api/v1/pricing/anomaly-check --param category <c> --param pricing_model <m> --param price_ut <价>` 或建议区间判断是否偏离；偏离明显时提醒风险，用户确认后可继续。
6. 若无法获取行情或建议价：基于同类列表和交付成本给出保守建议，并说明缺少自动行情数据；**不得静默用固定默认价**。

### 13.2 写入字段映射

| 对象 | 建议价写入字段 |
|---|---|
| 任务市场发布 | `bounty_amount`；`schedule_hourly` 用 `unit_price`（再由 `unit_price × 数量` 得预算） |
| 技能 | `ut_price` + `pricing_model` |
| 数据广场 API/产品 | `price_ut` |
| 时间市场 | `hourly_rate_ut`；如需人民币价，用 `GET /api/v1/wallet/rates` 换算 |
| 知识商店 / 账号类资产 | `price_ut` |
| capability | `price_ut` + `pricing_model` |
