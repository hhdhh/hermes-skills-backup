# TROUBLESHOOTING — UUMit Agent v2.7.0

## 1. missing credentials

现象：`rest_request.js` 返回 `missing credentials`。

处理：

```bash
node scripts/auth.js --start
node scripts/auth.js --wait <device_code>
```

也可通过环境变量注入：`UUMIT_API_KEY` 与 `UUMIT_USER_ID`。

## 2. route not in allowlist

说明：请求路径未登记，脚本默认拒绝。

处理：确认该接口是否属于公开 Skill 能力；如需要新增，必须同步更新：

- `scripts/rest_request.js` allowlist；
- `API_REFERENCE.md`；
- `scripts/validate_skill.js` 校验；
- `manifest.json` 哈希。

## 3. confirmation required

说明：触发安全闸门。常见原因：

- 超过 `spend.auto_spend_max_ut`；
- 钱包余额不足；
- 无法读取价格或余额；
- 议价购买；
- 付费 Playbook / 能力调用 / 数据 API 调用；
- 配置第三方 endpoint、鉴权或适配器沙箱试调；
- 上架/发布类写操作：账号商品（`account_asset_publish_requires_confirm`）、知识资产创建/换封面（`knowledge_asset_publish_requires_confirm`）、能力上架、订单售后。

处理：按 `SAFETY.md` 的确认模板向用户确认，用户同意后加 `--confirmed` 重试即可——smart-invoke 场景下 `rest_request.js` 会**自动**向后端换取签名 `confirm_token` 并回填放行，无需手动处理 token。

若响应体返回 `requires_confirmation: true` + `confirmation.confirm_token`（后端签发、绑定 caller/能力/费用、5 分钟有效）：说明用户尚未确认或 token 已失效。向用户确认后，把该 `confirm_token` **原样**放进下次 smart-invoke 请求体的 `confirm_token` 字段重调即可放行。**不要**把 `confirmation.action` 的值（`"confirm_invoke"`）当作 token，也不要回退去试 `/playbooks/runs`。

## 4. smart-invoke preview 成功但 auto 被拦截

说明：preview 不扣费；auto 是真实调用，必须经过阈值与余额检查。

处理：展示报价和风险，让用户确认后执行。

## 5. validate_skill.js 失败

处理顺序：

1. 检查 `manifest.json` 文件列表；
2. 检查三处 version 是否一致（当前应为 `2.1.0`）；
3. 检查 `POST /api/v1/capability-runtime/smart-invoke` 是否在 allowlist；
4. 检查文档中的 API 是否都被 allowlist 覆盖；
5. 重新计算 manifest 哈希。

## 6. 企业确认相关（工商调研类 Playbook）

现象与处理：

- 服务端反复返回 `请填写企业名称或统一社会信用代码`（ParamError）：企业字段未填或键名不对。工商调研类模板的企业字段键为 `company_name`/`supplier_name`/`own_company`/`company`，须按模板 `input_schema` 用正确键名填入企业名，不要自造键名后原样重试。详见 `PLAYBOOKS.md` §1.1。
- `4301` `company_confirmation_required`：输入疑似企业简称。调 `POST /api/v1/playbooks/company-candidates` 联想候选，展示给用户选定主体后，把 `_confirmed_company`（或 `credit_code`）放进扁平 `raw_inputs`，经 `smart-invoke`/`invoke` 重试。
- `4302` `company_candidate_unavailable` / `4303` `company_candidate_not_found`：企业匹配数据源不可用或无候选。引导用户直接填写公司全称（营业执照完整名称）或统一社会信用代码后重试。

## 7. Playbook 调用绕圈 / 反复试错请求体

**现象**：调用精品工作流时在 `input_data` / `input_payload` / `/playbooks/runs` / `smart-invoke` 之间反复切换、迟迟调不成功。

**根因与处理**：Playbook 一律作为能力卡统一调用，Agent 只传扁平 `raw_inputs`/`inputs`，**不要手工封装 `input_payload` 信封、不要直连 `/playbooks/runs`**（该接口为平台内部实现）。正确闭环见 `PLAYBOOKS.md` §1 的可照抄示例：

- **误判「capability_id 在 smart-invoke 里不可用」**：错误。smart-invoke **支持** `capability_id`（与 `intent` 二选一）。已知能力就传 `{ "capability_id": "<id>", "source_type": "playbook", "raw_inputs": {...} }`，不要因此回退私有接口。
- **智能路由选错能力**（目标在响应 `alternatives` 里）：从 `alternatives` 取目标能力的 `capability_id` + `source_type`，用 `capability_id` 版 smart-invoke 重调，不要改用 `/playbooks/runs`。
- **缺必填字段**：`smart-invoke`/`invoke` 返回 `missing_fields` + `input_schema` 时，按 `input_schema` 补齐扁平字段后重试，不要盲提交试错。
- **企业字段确认**：见上方 §6，`_confirmed_company` 放进扁平 `raw_inputs` 即可，服务端自动封装。
- **扣费确认卡住 / 反复试 `confirm_token` 与各种 flag**：付费能力需签名 `confirm_token` 放行。用户确认后加 `--confirmed`，`rest_request.js` 会自动换取并回填 token；若手动处理，则把响应 `confirmation.confirm_token` 原样回填 smart-invoke 的 `confirm_token`。**不要**自造 token、不要把 `action` 值当 token、不要回退 `/playbooks/runs`（详见 §3）。
