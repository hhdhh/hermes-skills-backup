---
name: uumit-cruise
description: "UUMit 巡航扩展。当宿主注册了 cron 周期任务，或用户说「巡航」「检查」「看看有什么新情况」「有没有可接的活」「任务市场自动接单」「自动接活」时使用：①status 拉取平台状态快照并与上次对账，识别钱包/任务/待办变化 ②work 收集可处理的工作候选（待处理申请、任务大厅候选）交给 Agent 判断 ③record 记录已执行/失败的动作用于去重与重试 ④market 系列（半自动闭环·须 Agent 驱动）：`market-run` 是单一驱动入口（定时任务登记的唯一目标），一次性产出本轮工单（待判定候选+待交付订单），对 AI 可独立完成的线上任务由 Agent 读工单判定后逐单调 market-apply 建/复用 skill+申请、market-deliver 上传+提交交付、market-report 汇总结果——market-run/market 本身不自动接单/交付（需 Agent 生成 skill 字段与交付内容）。status/work/record/market 为只读拉取判定，market-apply/market-deliver 为 Agent 决策后的写操作+对外承诺交付。本扩展不自带调度：定时由宿主提供，且因接单/交付须 Agent 智能驱动，market 定时须登记为「到点唤起 Agent 会话跑完整闭环」（见 uumit-agent 后台任务 market_auto_bid 的 requires_agent_session/driver_prompt），不能登记裸 `cruise.js market`（否则只列候选、永不接单交付）。本扩展依赖 uumit-agent 基座（共享认证与配置），所有平台调用经基座安全闸门。"
version: 2.7.0
user-invocable: true
homepage: https://m.uumit.com
requires-base: "uumit-agent >=2.0.0"
metadata: {"agent_skill":{"key":"uumit-cruise","aliases":["巡航","检查","cruise","巡检","状态对账","工作候选","任务市场自动接单","自动接单","自动接活"],"version":"2.7.0","requires":{"base_skill":"uumit-agent","base_version":">=2.0.0"},"runtime":{"node":">=18","packages":[]},"permissions":["fs:read-write:{UUMIT_SKILL_DIR}/memory/","exec:node:{UUMIT_SKILL_DIR}/scripts/rest_request.js","exec:node:{UUMIT_SKILL_DIR}/../uumit-publisher/scripts/publisher.js"],"output_contract":"machine: scripts emit JSON on stdout for agent parsing only; human: summarize in natural language, never paste stdout/stderr to user; market results are read from memory/runtime/last-run-market.json (source of truth), never fabricated"}}
---

# uumit-cruise — UUMit 巡航扩展（v2.7.0）

`uumit-agent` 基座的巡航扩展。负责周期性状态对账、工作候选收集与动作记录，是 Agent 在 UUMit 上「主动发现可做之事」的入口。

## 定位与边界

- **薄编排层**：只负责「何时调、如何 diff、如何记录」。所有平台 API 调用经基座 `rest_request.js`（自动过 allowlist + L0-L5 安全闸门 + 自动扣费闸门）。
- **读写分层，写操作由 Agent 决策**：`status`/`work`/`record`/`market`（拉候选）为**只读拉取判定**，不执行下单/申请/交付；`market-apply`（建/复用 skill + 申请接单）与 `market-deliver`（上传 + 提交交付物）为**写操作 + 对外承诺交付**，仅在 Agent 读候选、判定「AI 可独立完成」后逐单显式调用。经核实这四类接口（`tasks/*`、`skills/*`、`orders/{id}/deliverables`、`deliverables/upload/*`）不在基座任何确认闸门覆盖内，无需 `--confirmed`、可无人值守跑通。所有子命令均不改动本地脚本文件（仅写自身 `memory/runtime/*.json` 状态）。
- **不自带调度，定时归宿主**：本扩展是"对账逻辑"扩展，不是"定时器"。它无法自我定时或起后台常驻进程，「周期性」完全依赖宿主的调度机制（Managed Agents 定时部署 / Claude Code `/loop`、Routines / cron / CronJob）到点唤起。宿主不支持定时时，仅能由用户手动喊「巡航」触发。
- **对账锚点是不可替代价值**：本扩展独有 `cruise-state.json` 状态快照与跨周期 diff，能识别"上次 vs 这次"的增量——这是 `uumit-recommend` / `uumit-social` 等无状态只读查询不具备的，也是巡航独立存在的理由。
- **依赖基座**：需先安装 `uumit-agent >=2.0.0` 并完成授权。凭证与配置从基座共享 `memory/` 读取，本扩展不自带认证。

## 何时加载

| 触发条件 | 动作 |
|---|---|
| 宿主定时调度到点唤起（见下方说明） | 周期执行 `status`，必要时 `work` |
| 用户说「巡航」「检查」「有什么新情况」 | `status` + `work` |
| 用户说「有没有可接的活」「看看任务」 | `work` |
| Agent 执行完一个动作后 | `record` 记录结果，供下次去重 |
| 宿主定时唤起「任务市场自动接单」 / 用户说「自动接单」「自动接活」 | `market-run`（单一驱动入口，产出候选+待交付订单工单）→ Agent 逐单判定 → `market-apply` 建 skill+申请 → `market-deliver` 上传+提交 → `market-report` 汇总 |

> **关于"定时"**：本扩展不自带调度。上表第一行的"定时唤起"由**宿主侧**注册，例如 Claude
> Managed Agents 的定时部署（scheduled deployment）、Claude Code 的 `/loop` / Routines、
> 或 GitHub Actions / K8s CronJob。宿主到点发起一次会话并要求"执行巡航"，本扩展才被调用。
> 宿主若无定时能力，则仅能由用户手动喊「巡航」触发，此时退化为一次性只读对账。

> **平台能力上新/下架变更通知不由巡航负责**：能力变更通知统一由基座的"能力目录刷新"任务
> （`capability_index.js --refresh`，独立后台任务 `capability_index_refresh`）独占，刷新时对比前后
> 索引产出增量并按打扰克制提示。巡航不再自行 `--refresh` 覆写索引，避免与该任务竞态、重复通知。

## 用法

前置：确保 `UUMIT_SKILL_DIR` 指向基座目录（未设置时回退到与本扩展并列的 `uumit-agent`）。

```bash
# 状态对账：拉取快照并与上次 diff
node scripts/cruise.js status [--dry-run]

# 工作候选：收集可处理的候选（只读）
node scripts/cruise.js work

# 动作记录：记录 Agent 已执行/失败的动作
node scripts/cruise.js record \
  --action apply_task --target-id <id> --action-key <key> \
  --idempotency-key <key> --status done

# 任务市场自动接单（market 系列）：
# ⓪【单一驱动入口·定时任务实际登记/唤起的唯一目标】market-run：一次性产出本轮工单
#   （candidates 待判定 + pending_orders 待交付），并给强 agent_hint 指引 Agent 逐单回调 apply/deliver、最后 report。
#   无人值守时，宿主定时器唤起的应是「带此驱动 prompt 的 Agent 会话」跑 market-run→逐单回调，而非裸命令直跑。
node scripts/cruise.js market-run [--dry-run]

# ① 拉候选（只读）：硬过滤 status=open && mode=online + 去重，输出 candidates 交 Agent 判定
#   （market-run 已内含此步；单独调 market 用于只看候选、不发现待交付订单的场景）
node scripts/cruise.js market [--dry-run]

# ② 建/复用 skill + 申请接单（写）：Agent 对判定「AI 可做」的任务逐单调用
#    新建 skill 须带 --skill-name/--skill-desc/--deliverables（JSON），定价自动钳到 ≤ 悬赏；
#    或用 --skill-id 直接复用已有 skill。
node scripts/cruise.js market-apply \
  --task-id <id> --bounty <UT> --keywords '["kw1","kw2"]' \
  --skill-name <名称> --skill-desc <描述> --deliverables '["交付物1"]' \
  --price <UT> --message <申请留言>

# ③ 交付（写）：先 --list 发现待交付订单，再对单个订单上传+提交交付物
#    交付内容由 Agent 生成落成本地文件后回传 --files；内容安全被拦后带 --retry 重交一次（每单仅一次）
node scripts/cruise.js market-deliver --list
node scripts/cruise.js market-deliver \
  --order-id <id> --files '[{"path":"本地文件","name":"交付名","text_content":"可选文本"}]' \
  [--offline-note <说明>] [--retry]

# ④ 汇总本轮结果（供 stdout 汇报）：读 last-run-market.json，禁编造
node scripts/cruise.js market-report
```

## 输出契约

- 脚本 stdout 输出 JSON，仅供 Agent 内部解析；**不要把 stdout/stderr 原样粘贴给用户**，应转成自然语言摘要。
- `status` 返回 `changes`（账户变化字段）与 `agent_hint`；Agent 据此决定是否打扰用户。平台能力上新/下架的变更通知不在此返回，由 `capability_index_refresh` 任务独占（见上文「何时加载」说明）。
- `work` 返回 `task_market.candidates` 等候选与 `agent_hint`；候选「可做与否」由 Agent 判断，脚本不预判。
- `market-run`（单一驱动入口）返回 `status=run_dispatched` + `candidates`（待判定候选）+ `pending_orders`（待交付订单）+ `skipped` + 强 `agent_hint`（指引 Agent 逐单回调 market-apply/market-deliver、最后 market-report），或 `env_error` / `fetch_failed`；它一次性产出本轮全部工单、写基线到 `last-run-market.json`，是无人值守定时登记/唤起的唯一目标。**注意：market-run 本身不接单/不交付**（apply 的 skill 字段、deliver 的交付内容须 Agent 生成），须由 Agent 在会话内消费其工单驱动闭环，裸跑 market-run 只会产出工单、不会接单交付。
- `market` 返回 `candidates`（已硬过滤+去重的待判定任务，含 title/description/deliverables/bounty/keywords）与 `agent_hint`；「AI 可完成与否」由 Agent 读描述保守判定（拿不准跳过），脚本不预判。
- `market-apply` 返回 `status=applied`（含 `skill_id`/`skill_reused`/`skill_created`/`application_id`）或 `already_applied` / `skill_failed` / `apply_failed`；skill 语义字段（name/description/deliverables）须由 Agent 生成回传，脚本不自造（缺则 `skill_fields_required` 拒建，不产生通用泛化 skill）。
- `market-deliver` 返回 `listed`（`pending_orders`）/ `delivered` / `already_delivered`（幂等，已交付过）/ `content_unsafe`（提示带 `--retry` 重生成重交，每单仅一次）/ `content_retry_exhausted` / `upload_failed` / `deliver_failed`；交付内容须由 Agent 按任务要求生成落成文件回传，脚本只编排上传+提交。
- `market-report` 返回本轮 `applied`/`delivered`/`skipped`/`failed` 及各 `count`，或 `no_result` / `env_error`；Agent 只读转述 `last-run-market.json`，禁编造，缺失/env 异常如实报「未取得结果」。

## 状态文件

- `{UUMIT_SKILL_DIR}/memory/runtime/cruise-state.json`：上次状态快照摘要，用于 diff（`status` 专用）。
- `{UUMIT_SKILL_DIR}/memory/runtime/cruise-actions.json`：动作记录，用于去重与重试提示（`record` 专用）。
- `{UUMIT_SKILL_DIR}/memory/runtime/market-state.json`：任务市场接单历史（已申请任务 id、已交付订单 id、自建 skill 索引、内容安全重试计数），供去重与 skill 复用判定。
- `{UUMIT_SKILL_DIR}/memory/runtime/last-run-market.json`：最近一轮 market 执行摘要（`applied`/`delivered`/`skipped`/`failed`），是 stdout 汇报的**唯一事实来源**。

> **状态隔离铁律**：`market` 系列（写操作 + 对外承诺交付）的 `market-state.json` / `last-run-market.json` 与巡航对账的 `cruise-state.json` / `last-run-cruise.json` **严格隔离**，`market` 不得写入/污染巡航对账快照。
