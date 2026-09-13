#!/usr/bin/env node
/**
 * uumit-cruise — 巡航薄编排脚本（v2.7.0）。
 *
 * 业务意图（源自 1.x 巡航三脚本，按 2.x 安全模型重写）：
 *   - status：拉取巡航快照并与上次状态 diff，只读对账，不做写操作。
 *   - work：收集可处理的工作候选（待处理申请数、任务大厅候选），交给 Agent 判断。
 *   - record：记录 Agent 已执行/失败的动作，用于去重与重试提示。
 *
 * 设计铁律（见设计方案 9.2.0）：
 *   - 不自带 HTTP、不自读凭证：所有 API 调用经基座 rest_request.js（自动过 allowlist + 安全闸门）。
 *   - 薄编排层：只负责"何时调、如何 diff、如何记录"，请求/凭证/安全全部委托基座。
 *
 * 用法:
 *   node cruise.js status [--dry-run]
 *   node cruise.js work
 *   node cruise.js record --action <a> --target-id <id> --action-key <k> --idempotency-key <k> --status <done|failed|skipped|in_progress> [--retryable true|false] [--result-summary "..."]
 *
 * 输出: stdout=JSON；stderr=诊断；非 0 退出码=失败。
 */

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
// 用当前 Node 解释器绝对路径拉起子脚本，避免宿主子进程 PATH 无 `node` 时报"找不到 node"。
const NODE_BIN = process.execPath;

// 通过 UUMIT_SKILL_DIR 定位基座；未设置时回退到与本扩展并列的 uumit-agent。
const BASE_DIR = process.env.UUMIT_SKILL_DIR
  ? path.resolve(process.env.UUMIT_SKILL_DIR)
  : path.resolve(__dirname, '..', '..', 'uumit-agent');
const REST_SCRIPT = path.join(BASE_DIR, 'scripts', 'rest_request.js');
// 巡航状态存于基座共享 memory/，跨巡航周期保留。
const SHARED_MEMORY = path.join(BASE_DIR, 'memory');
const STATE_FILE = path.join(SHARED_MEMORY, 'runtime', 'cruise-state.json');
const ACTION_FILE = path.join(SHARED_MEMORY, 'runtime', 'cruise-actions.json');
// 最近一次巡航执行摘要：供 Agent 只读转述（禁编造）。定时任务无人值守跑完后，
// 结果以此文件为唯一事实来源；缺失或 env_error=true 时 Agent 须如实报"未取得结果"。
const LAST_RUN_FILE = path.join(SHARED_MEMORY, 'runtime', 'last-run-cruise.json');

// 任务市场自动接单（market 子命令）状态文件——与巡航对账严格隔离，market 是写操作 + 对外承诺交付，
// 不得写入/污染上方巡航的 cruise-state.json / last-run-cruise.json。
//   MARKET_STATE_FILE：接单历史 + 去重（已申请任务 id、已交付订单 id）+ 自建 skill 索引。
//   LAST_RUN_MARKET_FILE：最近一轮 market 执行摘要，作为 stdout 汇报的唯一事实来源。
const MARKET_STATE_FILE = path.join(SHARED_MEMORY, 'runtime', 'market-state.json');
const LAST_RUN_MARKET_FILE = path.join(SHARED_MEMORY, 'runtime', 'last-run-market.json');

function log(msg) { console.error(msg); }

function emit(payload) {
  process.stdout.write(JSON.stringify(payload, null, 2) + '\n');
}

function failCli(message) {
  emit({ ok: false, error: message });
  process.exit(2);
}

/**
 * 经基座 rest_request.js 发起调用，返回解析后的 JSON。失败抛错。
 * body 为可选项：传入对象时以 `--body` 透传给基座（market 子命令的 POST 建 skill / 申请 / 交付需要）；
 * 不传则为无 body 的 GET/DELETE。脚本自身不组 HTTP、不读凭证，一切委托基座过 allowlist + 安全闸门。
 */
function baseRequest(method, apiPath, body) {
  if (!fs.existsSync(REST_SCRIPT)) {
    throw new Error(`base rest_request.js not found at ${REST_SCRIPT}（设置 UUMIT_SKILL_DIR 指向基座目录）`);
  }
  const cliArgs = [REST_SCRIPT, method, apiPath];
  if (body !== undefined && body !== null) {
    cliArgs.push('--body', JSON.stringify(body));
  }
  const out = execFileSync(NODE_BIN, cliArgs, {
    encoding: 'utf8',
    timeout: 60000,
  });
  return out ? JSON.parse(out) : null;
}

function readJson(filePath, fallback) {
  try {
    if (!fs.existsSync(filePath)) return fallback;
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch (_) {
    return fallback;
  }
}

/**
 * 巡航时顺带、节流地检查是否该提醒用户"有后台任务可启动"（转发基座 install.js --background-status）。
 * 仅在"应提醒"时返回精简结论；其余返回 null，绝不阻断巡航主流程。
 */
function checkBackgroundReminder() {
  const installScript = path.join(BASE_DIR, 'scripts', 'install.js');
  if (!fs.existsSync(installScript)) return null;
  try {
    const out = execFileSync(NODE_BIN, [installScript, '--background-status'], { encoding: 'utf8', timeout: 20000 });
    const r = JSON.parse(out);
    if (!r.should_remind) return null;
    return { startable_not_launched: r.startable_not_launched, agent_hint: r.agent_hint };
  } catch (_) {
    return null;
  }
}

function writeJson(filePath, data) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf8');
}

/**
 * 写"最近一次巡航执行摘要"结果文件（供 Agent 只读转述、禁编造）。
 * 写入失败静默（不阻断主流程），避免结果落盘异常影响巡航本身。
 */
function writeLastRun(payload) {
  try {
    writeJson(LAST_RUN_FILE, { ran_at: new Date().toISOString(), ...payload });
  } catch (_) {
    /* 结果文件写入失败不阻断巡航 */
  }
}

/**
 * 写"最近一次 market 执行摘要"结果文件（供 Agent 只读转述、禁编造，stdout 汇报的唯一事实来源）。
 * 与 writeLastRun 隔离，写入独立的 last-run-market.json。写入失败静默、不阻断主流程。
 */
function writeLastRunMarket(payload) {
  try {
    writeJson(LAST_RUN_MARKET_FILE, { ran_at: new Date().toISOString(), ...payload });
  } catch (_) {
    /* 结果文件写入失败不阻断 market */
  }
}

/**
 * 向 last-run-market.json 追加本次子动作结果（承接 D8：唯一事实来源须含全轮 applied/delivered/failed）。
 * `market` 主入口写基线，`market-apply`/`market-deliver` 逐单调用时把各自结果 append 进对应数组，
 * 使 Agent 汇报时读到本轮完整全貌。读现有 → 合并数组 → 刷新 ran_at 写回；失败静默不阻断。
 * @param patch { applied?, delivered?, skipped?, failed? } 各为要追加的条目数组
 */
function appendLastRunMarket(patch) {
  try {
    const cur = readJson(LAST_RUN_MARKET_FILE, {});
    const merge = (key) => [
      ...(Array.isArray(cur[key]) ? cur[key] : []),
      ...(Array.isArray(patch[key]) ? patch[key] : []),
    ];
    writeJson(LAST_RUN_MARKET_FILE, {
      ...cur,
      ran_at: new Date().toISOString(),
      applied: merge('applied'),
      delivered: merge('delivered'),
      skipped: merge('skipped'),
      failed: merge('failed'),
    });
  } catch (_) {
    /* 结果文件写入失败不阻断 market */
  }
}

// ---------------------------------------------------------------------------
// market 状态：接单历史去重 + 自建 skill 索引（与巡航状态隔离）
// state 结构：
//   applied_task_ids   已申请任务 id（防重复接单）
//   delivered_order_ids 已交付订单 id（防重复交付）
//   delivered_rework_counts    已交付时记录的买方返工计数（orderId -> rework_count），用于识别新一轮买方返工
//   delivered_ai_rework_counts 已交付时记录的 AI 自动返工计数（orderId -> ai_rework_count），用于识别新一轮 AI 审查打回
//   pending_rework_counts      当前待处理买方返工计数快照（orderId -> rework_count）
//   pending_ai_rework_counts   当前待处理 AI 返工计数快照（orderId -> ai_rework_count），供 market-deliver 交付后回写基线
//   content_retry      订单内容安全被拦重试计数（orderId -> 次数），承接 D10「最多重试一次」
//   self_skills        本脚本建过的 skill 索引：{ skill_id, keywords[], summary, price, created_at }
//   updated_at         最后写入时间
// ---------------------------------------------------------------------------

/** 读取 market state 并规整为标准结构（缺字段补默认，容忍旧文件/手改）。 */
function readMarketState() {
  const raw = readJson(MARKET_STATE_FILE, {});
  return {
    applied_task_ids: Array.isArray(raw.applied_task_ids) ? raw.applied_task_ids : [],
    delivered_order_ids: Array.isArray(raw.delivered_order_ids) ? raw.delivered_order_ids : [],
    delivered_rework_counts: (raw.delivered_rework_counts && typeof raw.delivered_rework_counts === 'object')
      ? raw.delivered_rework_counts : {},
    delivered_ai_rework_counts: (raw.delivered_ai_rework_counts && typeof raw.delivered_ai_rework_counts === 'object')
      ? raw.delivered_ai_rework_counts : {},
    pending_rework_counts: (raw.pending_rework_counts && typeof raw.pending_rework_counts === 'object')
      ? raw.pending_rework_counts : {},
    pending_ai_rework_counts: (raw.pending_ai_rework_counts && typeof raw.pending_ai_rework_counts === 'object')
      ? raw.pending_ai_rework_counts : {},
    self_skills: Array.isArray(raw.self_skills) ? raw.self_skills : [],
    // 订单内容安全被拦重试计数（orderId -> 已重试次数），承接 D10「最多重试一次」。
    content_retry: (raw.content_retry && typeof raw.content_retry === 'object') ? raw.content_retry : {},
    updated_at: raw.updated_at || null,
  };
}

/** 写回 market state（打时间戳）。绝不触碰巡航的 cruise-state.json。 */
function writeMarketState(state) {
  writeJson(MARKET_STATE_FILE, {
    applied_task_ids: state.applied_task_ids,
    delivered_order_ids: state.delivered_order_ids,
    delivered_rework_counts: state.delivered_rework_counts || {},
    delivered_ai_rework_counts: state.delivered_ai_rework_counts || {},
    pending_rework_counts: state.pending_rework_counts || {},
    pending_ai_rework_counts: state.pending_ai_rework_counts || {},
    self_skills: state.self_skills,
    content_retry: state.content_retry || {},
    updated_at: new Date().toISOString(),
  });
}

/** 任务是否已申请过（去重，供步骤 3 过滤候选 / 步骤 5 二次保险）。 */
function isTaskApplied(state, taskId) {
  return state.applied_task_ids.includes(taskId);
}

/** 订单是否已交付过（去重，供步骤 6 跳过重复交付）。 */
function isOrderDelivered(state, orderId) {
  return state.delivered_order_ids.includes(orderId);
}

/** 记录一次成功申请（幂等入集）。 */
function recordApplied(state, taskId) {
  if (taskId && !state.applied_task_ids.includes(taskId)) {
    state.applied_task_ids.push(taskId);
  }
}

/** 记录一次成功交付（幂等入集）。 */
function recordDelivered(state, orderId) {
  if (orderId && !state.delivered_order_ids.includes(orderId)) {
    state.delivered_order_ids.push(orderId);
  }
}

/** 该订单是否已用掉唯一一次内容安全重试机会（承接 D10「最多重试一次」）。 */
function contentRetryExhausted(state, orderId) {
  return Number((state.content_retry || {})[orderId] || 0) >= 1;
}

/** 记录该订单一次内容安全被拦重试（计数 +1）。 */
function recordContentRetry(state, orderId) {
  if (!state.content_retry) state.content_retry = {};
  state.content_retry[orderId] = Number(state.content_retry[orderId] || 0) + 1;
}

/**
 * 从任务标题/描述提取关键词（用于自建 skill 索引匹配）。
 * 简易分词：按非字母数字中文切分、去空、去重、截断长度，供后续步骤复用判定用。
 * 已知局限：中英文直接相连（如「写Python脚本」）不在中英边界切分，会漏出独立英文词；
 * 该局限仅降低 skill 复用命中率（未命中则新建，结果仍安全），不影响接单正确性。
 */
function extractKeywords(text) {
  if (!text || typeof text !== 'string') return [];
  const tokens = text
    .toLowerCase()
    .split(/[^0-9a-z\u4e00-\u9fa5]+/)
    .filter((t) => t.length >= 2);
  return Array.from(new Set(tokens)).slice(0, 20);
}

/**
 * 在自建 skill 索引中查找与给定关键词对口的 skill（承接 D7 本地复用判定，不依赖 skills/mine）。
 * 命中标准：关键词交集 >= 2 或交集占任务关键词比例 >= 0.5；返回命中项或 null。
 */
function findReusableSkill(state, keywords) {
  if (!keywords.length) return null;
  const wanted = new Set(keywords);
  let best = null;
  let bestScore = 0;
  for (const skill of state.self_skills) {
    const have = new Set(skill.keywords || []);
    let overlap = 0;
    for (const k of wanted) if (have.has(k)) overlap++;
    const ratio = overlap / wanted.size;
    if ((overlap >= 2 || ratio >= 0.5) && overlap > bestScore) {
      best = skill;
      bestScore = overlap;
    }
  }
  return best;
}

/** 把新建的自建 skill 写入索引（供后续任务复用）。 */
function recordSelfSkill(state, { skillId, keywords, summary, price }) {
  if (!skillId) return;
  if (state.self_skills.some((s) => s.skill_id === skillId)) return;
  state.self_skills.push({
    skill_id: skillId,
    keywords: keywords || [],
    summary: summary || '',
    price: price != null ? price : null,
    created_at: new Date().toISOString(),
  });
}

/** market 硬过滤准入门槛（机器判定，承接 D1）：仅 status=open 且 mode=online 的任务可进入候选。 */
function passesMarketGate(task) {
  return task && task.status === 'open' && task.mode === 'online';
}

/**
 * 拉任务市场并做「硬过滤 + 去重」，产出交给 Agent 做「AI 可完成」判定的候选（承接 D1/步骤 3）。
 * 脚本只做机器可判定的部分（字段准入、已申请去重），不自行判断任务能否由 AI 完成——
 * 该判定由 Agent 读候选的 title/description/deliverables 保守自评（拿不准跳过）。
 *
 * 返回 { candidates, skipped, error }：
 *   candidates 过滤后待 Agent 判定的候选（含判定所需的描述字段）；
 *   skipped    被硬过滤/去重剔除的任务及原因（计入本轮摘要）；
 *   error      拉取失败信息（null 表示成功）。
 */
function fetchMarketCandidates(state, pageSize) {
  const size = pageSize || 20;
  let resp;
  try {
    // mode=online 交服务端预过滤；status 与去重在客户端兜底，避免服务端语义差异漏挡。
    resp = baseRequest('GET', `/api/v1/tasks/hall?mode=online&page_size=${size}`);
  } catch (e) {
    return { candidates: [], skipped: [], error: String((e && e.message) || e) };
  }
  const data = safeData(resp);
  if (!data) {
    return { candidates: [], skipped: [], error: (resp && resp.message) || 'unexpected tasks/hall response' };
  }

  const items = Array.isArray(data.items) ? data.items : [];
  const candidates = [];
  const skipped = [];
  for (const task of items) {
    if (!passesMarketGate(task)) {
      skipped.push({ task_id: task && task.id, title: task && task.title, reason: 'gate_filtered' });
      continue;
    }
    if (isTaskApplied(state, task.id)) {
      skipped.push({ task_id: task.id, title: task.title, reason: 'already_applied' });
      continue;
    }
    candidates.push({
      task_id: task.id,
      title: task.title,
      description: task.description,
      deliverables: task.deliverables || null,
      mode: task.mode,
      status: task.status,
      owner_type: task.owner_type,
      bounty_amount: task.bounty_amount,
      bounty_currency: task.bounty_currency,
      approval_mode: task.approval_mode,
      completion_mode: task.completion_mode,
      // 供 Agent 复用判定与后续建 skill 使用的关键词（本地提取）。
      keywords: extractKeywords(`${task.title || ''} ${task.description || ''}`),
    });
  }
  return { candidates, skipped, error: null };
}

/**
 * 把定价钳制到「≤ 任务悬赏」（承接 D9）：读任务 bounty_amount，若 Agent 给的 price 超过悬赏则压到悬赏值；
 * 悬赏缺失/非法时保留 Agent 定价（由后续审批兜底）。返回规范化的数值字符串或 null。
 */
function clampPriceToBounty(price, bountyAmount) {
  const p = Number(price);
  const b = Number(bountyAmount);
  if (!Number.isFinite(p) || p < 0) return null;
  if (!Number.isFinite(b) || b <= 0) return String(p);
  return String(Math.min(p, b));
}

/**
 * 建/复用对口 skill（承接 D1/D7/D9，步骤 4）。脚本只编排，不自造 skill 语义字段——
 * name/description/deliverables/tags 等由 Agent 按任务描述生成后经 skillFields 回传。
 *
 * 流程：先 findReusableSkill 本地匹配命中则复用其 skill_id（不重复建）；
 * 未命中则 POST /api/v1/skills 新建（定价 clampPriceToBounty 钳到 ≤ 悬赏），成功后 recordSelfSkill 回写索引。
 *
 * @param state       market 状态（含自建 skill 索引）
 * @param task        候选任务（需 task_id/bounty_amount/keywords）
 * @param skillFields Agent 生成的 skill 字段：{ name, description, deliverables[], tags?, category?, price?, input_schema? }
 * @returns { skillId, reused, created, error }
 */
function ensureSkillForTask(state, task, skillFields) {
  const keywords = (task && task.keywords) || [];

  // 1) 本地复用判定：命中对口自建 skill 直接复用，不重复建（D7）。
  const reusable = findReusableSkill(state, keywords);
  if (reusable) {
    return { skillId: reusable.skill_id, reused: true, created: false, error: null };
  }

  // 2) 未命中 → 新建。skill 语义字段必须由 Agent 提供（薄编排层，脚本不自造）。
  if (!skillFields || !skillFields.name || !skillFields.description
    || !Array.isArray(skillFields.deliverables) || skillFields.deliverables.length === 0) {
    return {
      skillId: null, reused: false, created: false,
      error: 'skill_fields_required：新建 skill 需 Agent 提供 name/description/deliverables（不使用通用泛化 skill）',
    };
  }

  const price = clampPriceToBounty(skillFields.price, task && task.bounty_amount);
  const body = {
    name: skillFields.name,
    description: skillFields.description,
    deliverables: skillFields.deliverables,
    mode: 'online',                    // 本方案只接线上任务（D1），无需 city
    tags: skillFields.tags || [],
    category: skillFields.category || null,
    ut_price: price,
    pricing_model: skillFields.pricing_model || 'fixed',
    input_schema: skillFields.input_schema || [],
  };

  let resp;
  try {
    resp = baseRequest('POST', '/api/v1/skills', body);
  } catch (e) {
    return { skillId: null, reused: false, created: false, error: String((e && e.message) || e) };
  }
  const data = safeData(resp);
  const skillId = data && (data.id || data.skill_id);
  if (!skillId) {
    return {
      skillId: null, reused: false, created: false,
      error: (resp && resp.message) || 'create skill failed: missing skill id',
    };
  }

  // 3) 回写自建 skill 索引，供后续任务复用（D7）。
  recordSelfSkill(state, {
    skillId,
    keywords,
    summary: skillFields.name,
    price,
  });
  return { skillId, reused: false, created: true, error: null };
}

/**
 * 申请接单（步骤 5）：POST /tasks/{id}/applications 带 skill_id。成功后 recordApplied 入去重集。
 * 经确认闸门核实无需 --confirmed（详见方案确认闸门核实结论）。
 * @returns { ok, applicationId, error }
 */
function applyToTask(state, taskId, skillId, { message, proposedPrice } = {}) {
  if (isTaskApplied(state, taskId)) {
    // 二次保险：已申请过则视为幂等成功，不重复发起。
    return { ok: true, applicationId: null, alreadyApplied: true, error: null };
  }
  const body = { skill_id: skillId };
  if (message) body.message = message;
  if (proposedPrice != null) body.proposed_price = String(proposedPrice);

  let resp;
  try {
    resp = baseRequest('POST', `/api/v1/tasks/${taskId}/applications`, body);
  } catch (e) {
    return { ok: false, applicationId: null, error: String((e && e.message) || e) };
  }
  const data = safeData(resp);
  if (!data) {
    return { ok: false, applicationId: null, error: (resp && resp.message) || 'apply failed' };
  }
  recordApplied(state, taskId);
  return { ok: true, applicationId: data.id || data.application_id || null, error: null };
}

/**
 * 发现待交付订单（步骤 6）：GET /orders?status=pending_delivery，剔除已交付（去重）。
 * @returns { orders, error }  orders 为 [{ order_id, task_id, ... }]
 */
function fetchPendingDeliveryOrders(state) {
  let resp;
  try {
    resp = baseRequest('GET', '/api/v1/orders?role=seller&page_size=100');
  } catch (e) {
    return { orders: [], error: String((e && e.message) || e) };
  }
  const data = safeData(resp);
  if (!data) return { orders: [], error: (resp && resp.message) || 'unexpected orders response' };
  const items = Array.isArray(data.items) ? data.items : [];
  const orders = [];
  const activeReworkIds = new Set();
  for (const o of items) {
    if (o.status === 'rework') {
      const reworkCount = Number(o.rework_count || 0);
      // AI 审查自动打回只自增 ai_rework_count、不动买方 rework_count（后端计数器分离），
      // 故去重必须同时对账两个计数，否则 AI 打回的返工会因 rework_count 未变而被误判为「已处理」漏掉。
      const aiReworkCount = Number(o.ai_rework_count || 0);
      const previousPendingReworkCount = Number(state.pending_rework_counts[o.id] || 0);
      const deliveredReworkCount = Number(state.delivered_rework_counts[o.id] || 0);
      const deliveredAiReworkCount = Number(state.delivered_ai_rework_counts[o.id] || 0);
      activeReworkIds.add(o.id);
      state.pending_rework_counts[o.id] = reworkCount;
      state.pending_ai_rework_counts[o.id] = aiReworkCount;
      // 仅当买方与 AI 两个返工计数都未超过「上次已交付时记录的值」，才视为已处理并跳过。
      const hasNewBuyerRework = reworkCount > deliveredReworkCount;
      const hasNewAiRework = aiReworkCount > deliveredAiReworkCount;
      if (!hasNewBuyerRework && !hasNewAiRework) continue;
      // 任一计数出现新一轮返工，重置该单的内容安全重试机会。
      if (previousPendingReworkCount !== reworkCount || hasNewAiRework) state.content_retry[o.id] = 0;
      orders.push({
        order_id: o.id,
        task_id: o.task_id,
        task_title: o.task_title || null,
        order_no: o.order_no,
        skill_id: o.skill_id,
        status: o.status,
        delivery_kind: 'rework',
        rework_count: reworkCount,
        rework_reason: o.last_rework_reason || null,
        rework_deadline: o.rework_deadline || null,
        // 结构化整改指令（优先于自由文本 rework_reason）与 AI 自动打回信号，供 Agent 精确修正。
        rework_guidance: o.rework_guidance || null,
        ai_precheck_passed: typeof o.ai_precheck_passed === 'boolean' ? o.ai_precheck_passed : null,
        ai_rework_count: Number(o.ai_rework_count || 0),
      });
      continue;
    }
    if (o.status !== 'pending_delivery') continue;
    if (isOrderDelivered(state, o.id)) continue;
    orders.push({
      order_id: o.id,
      task_id: o.task_id,
      task_title: o.task_title || null,
      order_no: o.order_no,
      skill_id: o.skill_id,
      status: o.status,
      delivery_kind: 'initial',
      rework_count: Number(o.rework_count || 0),
      rework_reason: null,
      rework_deadline: null,
    });
  }
  for (const orderId of Object.keys(state.pending_rework_counts)) {
    if (!activeReworkIds.has(orderId)) delete state.pending_rework_counts[orderId];
  }
  for (const orderId of Object.keys(state.pending_ai_rework_counts)) {
    if (!activeReworkIds.has(orderId)) delete state.pending_ai_rework_counts[orderId];
  }
  return { orders, error: null };
}

/**
 * 上传单个交付文件拿 OSS URL（委托 uumit-publisher 的受控 multipart 直传，cruise 不自造 HTTP）。
 * publisher `upload` 复用基座凭证/base_url，返回 { data: { url, ... } }。
 * @returns { url, error }
 */
function uploadDeliverableFile(filePath) {
  const publisherScript = path.join(BASE_DIR, '..', 'uumit-publisher', 'scripts', 'publisher.js');
  if (!fs.existsSync(publisherScript)) {
    return { url: null, error: `uumit-publisher 不可达（${publisherScript}）；交付物上传需要 uumit-publisher。` };
  }
  if (!fs.existsSync(filePath)) {
    return { url: null, error: `交付文件不存在：${filePath}` };
  }
  try {
    const out = execFileSync(NODE_BIN, [publisherScript, 'upload', '--file', filePath], {
      encoding: 'utf8',
      timeout: 180000,
      env: { ...process.env, UUMIT_SKILL_DIR: BASE_DIR },
    });
    const parsed = out ? JSON.parse(out) : null;
    const file = parsed && parsed.ok && parsed.file;
    const url = file && (file.url || file.file_url);
    if (!url) return { url: null, error: (parsed && parsed.error) || 'upload 未返回文件 URL' };
    return { url, error: null };
  } catch (e) {
    return { url: null, error: String((e && e.message) || e) };
  }
}

// L1 前置过滤拦截码（服务端 deliverable_precheck）：提交交付物时同步 400 返回，body 带 data.guidance。
const L1_PRECHECK_ERROR_CODES = new Set(['DELIVERABLE_FORMAT_MISMATCH', 'DELIVERABLE_UNCHANGED_RESUBMIT']);

/**
 * 提交订单交付物（步骤 6）：POST /orders/{id}/deliverables。
 * 每项 deliverables 必带 url+name（服务端硬约束，url 须为平台 OSS 对象）。
 * deliverables 为自治履约写，不在 enforceOrderAftersaleConfirmation 覆盖内，无需 --confirmed。
 * 服务端非 0 响应（含 400）由基座 rest_request.js 打到 stdout 后 exit 1 → execFileSync 抛错、body 落在 e.stdout。
 * @param deliverables [{ url, name, text_content? }]
 * @returns { ok, error, contentUnsafe?, precheckError?, guidance? }
 */
function submitOrderDeliverables(state, orderId, deliverables, offlineNote) {
  const body = { deliverables };
  if (offlineNote) body.offline_note = offlineNote;
  let resp;
  try {
    resp = baseRequest('POST', `/api/v1/orders/${orderId}/deliverables`, body);
  } catch (e) {
    // 服务端错误 body 在 e.stdout（基座 400 时原样输出后端信封再 exit 1）：解析出 L1 拦截码与整改指令。
    const parsed = parseErrorStdout(e);
    if (parsed) return classifyDeliverableFailure(parsed);
    return { ok: false, error: String((e && e.message) || e) };
  }
  if (!resp || resp.code !== 0) return classifyDeliverableFailure(resp);
  recordDelivered(state, orderId);
  return { ok: true, error: null };
}

// 从 execFileSync 抛出的错误对象里解析基座打到 stdout 的后端 JSON 信封（失败返回 null）。
function parseErrorStdout(e) {
  const out = e && e.stdout;
  if (!out) return null;
  try {
    return JSON.parse(typeof out === 'string' ? out : out.toString('utf8'));
  } catch (_) {
    return null;
  }
}

// 归类交付失败：L1 前置过滤（可整改）> 内容安全（可重试一次）> 通用失败。
function classifyDeliverableFailure(resp) {
  const errorCode = resp && resp.error_code;
  if (errorCode && L1_PRECHECK_ERROR_CODES.has(errorCode)) {
    const guidance = (resp && resp.data && resp.data.guidance) || null;
    return {
      ok: false,
      precheckError: errorCode,
      guidance,
      error: (resp && resp.message) || errorCode,
    };
  }
  // 内容安全审核被拦：服务端 ContentUnsafeError → code=4801（承接 D10，供 market-deliver 决定是否重试一次）。
  const contentUnsafe = resp && (resp.code === 4801 || /审核未通过/.test(resp.message || ''));
  return { ok: false, contentUnsafe: Boolean(contentUnsafe), error: (resp && resp.message) || 'submit deliverable failed' };
}

// ---------------------------------------------------------------------------
// status：状态对账
// ---------------------------------------------------------------------------
function summarizeSnapshot(data) {
  const profile = (data.profile && data.profile.profile) || {};
  const wallet = data.wallet || {};
  const todos = data.todos || {};
  const tasks = data.tasks || {};
  return {
    profile: {
      nickname: profile.nickname || null,
      completeness: profile.completeness || 0,
    },
    wallet: {
      ut_available: wallet.ut && wallet.ut.available,
      ut_frozen: wallet.ut && wallet.ut.frozen,
    },
    counts: {
      todos: Array.isArray(todos.items) ? todos.items.length : null,
      active_tasks: Array.isArray(tasks.active) ? tasks.active.length : null,
      pending_transactions: Array.isArray(data.pending_transactions) ? data.pending_transactions.length : null,
    },
  };
}

function diffSummaries(previous, current) {
  const changes = [];
  const keys = [
    ['profile', 'nickname'], ['profile', 'completeness'],
    ['wallet', 'ut_available'], ['wallet', 'ut_frozen'],
    ['counts', 'todos'], ['counts', 'active_tasks'], ['counts', 'pending_transactions'],
  ];
  for (const [group, key] of keys) {
    const before = previous[group] && previous[group][key];
    const after = current[group] && current[group][key];
    if (before !== after) changes.push({ field: `${group}.${key}`, before, after });
  }
  return changes;
}

function runStatus(args) {
  const dryRun = args.includes('--dry-run');

  // 环境异常显式暴露（无人值守时不静默/不挂起）：基座 rest_request.js 不可达即视为运行环境异常。
  // 写 env_error 结果文件并 emit env_error，供 Agent 如实报"未取得结果"，杜绝伪造成功。
  if (!fs.existsSync(REST_SCRIPT)) {
    const msg = `基座 rest_request.js 不可达（${REST_SCRIPT}）；请确认在 skill 目录下运行或设置 UUMIT_SKILL_DIR。`;
    if (!dryRun) writeLastRun({ status: 'env_error', env_error: true, error: msg });
    emit({ ok: false, status: 'env_error', env_error: true, error: msg });
    process.exit(2);
  }

  log('获取巡航快照（经基座 rest_request.js）...');
  let resp;
  try {
    resp = baseRequest('GET', '/api/v1/agent/cruise?include=all');
  } catch (e) {
    const err = String(e && e.message || e);
    if (!dryRun) writeLastRun({ status: 'snapshot_failed', env_error: false, error: err });
    emit({ ok: false, status: 'snapshot_failed', error: err, retryable: true });
    process.exit(1);
  }

  if (!resp || resp.code !== 0) {
    const err = (resp && resp.message) || 'unexpected response';
    if (!dryRun) writeLastRun({ status: 'snapshot_failed', env_error: false, error: err });
    emit({ ok: false, status: 'snapshot_failed', error: err });
    process.exit(1);
  }

  const previousState = readJson(STATE_FILE, {});
  const currentSummary = summarizeSnapshot(resp.data || {});
  const hasBaseline = Object.prototype.hasOwnProperty.call(previousState, 'summary');
  const changes = hasBaseline ? diffSummaries(previousState.summary || {}, currentSummary) : [];
  const status = hasBaseline ? (changes.length ? 'changed' : 'unchanged') : 'initialized';

  if (!dryRun) {
    writeJson(STATE_FILE, { summary: currentSummary, updated_at: new Date().toISOString() });
  }

  const background_reminder = checkBackgroundReminder();

  // 写"最近一次执行摘要"结果文件：Agent 只读此文件转述真实结果（余额单位 UT、真实版本号等），
  // 禁凭记忆编造。dry-run 不落盘，避免污染无人值守的事实来源。
  if (!dryRun) {
    writeLastRun({
      status,
      env_error: false,
      summary: currentSummary,
      changes,
    });
  }

  emit({
    ok: true,
    status,
    dry_run: dryRun,
    changes,
    summary: currentSummary,
    background_reminder,
    agent_hint: status === 'changed'
      ? '内部审阅变化字段；仅在需要行动或与用户相关时通知。写/购买/提交/交付前须确认。'
      : '无变化，除非已有待办流程否则无需打扰用户。',
  });
}

// ---------------------------------------------------------------------------
// work：工作候选收集（只读，不判断是否可做）
// ---------------------------------------------------------------------------
function safeData(resp) {
  return (resp && resp.code === 0 && resp.data) ? resp.data : null;
}

function runWork() {
  const actionState = readJson(ACTION_FILE, { actions: {} });
  const recorded = Object.keys(actionState.actions || {}).length;

  const result = {
    ok: true,
    account: { pending_application_count: 0 },
    task_market: { candidates: [] },
    action_state: {
      file: ACTION_FILE,
      total_recorded_actions: recorded,
      note: '脚本只读取动作记录做去重/重试提示；是否执行动作仍由 Agent 判断。',
    },
    agent_hint: '逐条评估候选；可安全自完成才提议并在写操作前确认，否则给出 UUMit 路由（发任务/约时间/买资产等）。',
  };

  try {
    const data = safeData(baseRequest('GET', '/api/v1/tasks/applications/mine?status=pending&page_size=1'));
    if (data) result.account.pending_application_count = data.total || 0;
  } catch (e) {
    log(`pending applications 获取失败: ${e.message}`);
  }

  try {
    const data = safeData(baseRequest('GET', '/api/v1/tasks/hall?page_size=20'));
    const tasks = (data && data.items) || [];
    for (const task of tasks) {
      const actionKey = `apply-task-${task.id}`;
      const prev = actionState.actions[actionKey];
      result.task_market.candidates.push({
        task_id: task.id,
        title: task.title,
        bounty_amount: task.bounty_amount,
        action_key: actionKey,
        already_done: prev ? prev.status === 'done' : false,
        action_status: prev ? prev.status : 'new',
      });
    }
  } catch (e) {
    log(`task hall 获取失败: ${e.message}`);
  }

  emit(result);
}

// ---------------------------------------------------------------------------
// record：动作记录（去重 / 重试提示）
// ---------------------------------------------------------------------------
function parseRecordArgs(argv) {
  const out = { status: 'done', retryable: null, resultSummary: '' };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    const val = () => {
      if (i + 1 >= argv.length || argv[i + 1].startsWith('--')) failCli(`missing value for ${arg}`);
      return argv[++i];
    };
    switch (arg) {
      case '--action': out.action = val(); break;
      case '--target-id': out.targetId = val(); break;
      case '--action-key': out.actionKey = val(); break;
      case '--idempotency-key': out.idempotencyKey = val(); break;
      case '--status': out.status = val(); break;
      case '--retryable': out.retryable = val() === 'true'; break;
      case '--result-summary': out.resultSummary = val(); break;
      default: failCli(`unknown argument: ${arg}`);
    }
  }
  if (!out.action) failCli('--action is required');
  if (!out.targetId) failCli('--target-id is required');
  if (!out.actionKey) failCli('--action-key is required');
  if (!out.idempotencyKey) failCli('--idempotency-key is required');
  if (!['done', 'failed', 'skipped', 'in_progress'].includes(out.status)) {
    failCli('--status must be one of done, failed, skipped, in_progress');
  }
  return out;
}

function runRecord(args) {
  const a = parseRecordArgs(args);
  const state = readJson(ACTION_FILE, { actions: {} });
  if (!state.actions) state.actions = {};
  const now = new Date().toISOString();
  const prev = state.actions[a.actionKey] || {};

  state.actions[a.actionKey] = {
    action: a.action,
    target_id: a.targetId,
    action_key: a.actionKey,
    idempotency_key: a.idempotencyKey,
    status: a.status,
    retryable: a.retryable,
    attempt_count: Number(prev.attempt_count || 0) + 1,
    first_attempt_at: prev.first_attempt_at || now,
    last_attempt_at: now,
    result_summary: (a.status === 'done' || a.status === 'skipped') ? a.resultSummary : (prev.result_summary || ''),
    last_error: a.status === 'failed' ? a.resultSummary : '',
  };
  state.updated_at = now;
  writeJson(ACTION_FILE, state);

  emit({ ok: true, action_key: a.actionKey, status: a.status, attempt_count: state.actions[a.actionKey].attempt_count });
}

// ---------------------------------------------------------------------------
// market：任务市场自动接单全闭环（一次性执行，由宿主每小时 cron 拉起）
// 拉市场 → 硬过滤 + AI 判定 → 建/复用 skill → 申请接单 → 撮合后补交付。
// 本步骤（步骤 1）先打通入口、环境兜底与结果落盘；各闭环环节留待后续步骤实现。
// ---------------------------------------------------------------------------
function runMarket(args) {
  const dryRun = args.includes('--dry-run');

  // 环境异常显式暴露（无人值守时不静默/不挂起）：基座 rest_request.js 不可达即视为运行环境异常。
  // 写 env_error 结果文件并 emit env_error，供 Agent 如实报"未取得结果"，杜绝伪造成功。
  if (!fs.existsSync(REST_SCRIPT)) {
    const msg = `基座 rest_request.js 不可达（${REST_SCRIPT}）；请确认在 skill 目录下运行或设置 UUMIT_SKILL_DIR。`;
    if (!dryRun) writeLastRunMarket({ status: 'env_error', env_error: true, error: msg });
    emit({ ok: false, status: 'env_error', env_error: true, error: msg });
    process.exit(2);
  }

  // 接单历史 + 去重集 + 自建 skill 索引（与巡航状态隔离，缺字段自动补默认）。
  const marketState = readMarketState();

  // 本轮执行摘要（作为 stdout 汇报唯一事实来源）。
  const summary = { applied: [], delivered: [], skipped: [], failed: [] };

  // 步骤 3：拉市场 → 硬过滤（status=open && mode=online）→ 去重（剔除已申请）→ 输出候选待 Agent 判定。
  const { candidates, skipped, error } = fetchMarketCandidates(marketState, 20);
  if (error) {
    // 拉市场失败：如实记入摘要与结果文件，不静默、不伪造成功。
    summary.failed.push({ stage: 'fetch_market', error });
    if (!dryRun) {
      writeMarketState(marketState);
      writeLastRunMarket({ status: 'fetch_failed', env_error: false, ...summary, error });
    }
    emit({ ok: false, status: 'fetch_failed', dry_run: dryRun, ...summary, error, retryable: true });
    process.exit(1);
  }
  summary.skipped.push(...skipped);

  // 步骤 4+5：建/复用 skill + 申请接单 → 由 Agent 读候选判定后，对可做任务调 `market-apply` 子命令完成
  //           （见 runMarketApply）；`market` 主入口只负责产出候选，不在同进程内替 Agent 决策。
  // 步骤 6：撮合后交付 → Agent 用 `market-deliver --list` 发现 pending_delivery 订单，按任务要求生成交付
  //           内容后用 `market-deliver --order-id <id> --files <json>` 上传+提交（见 runMarketDeliver）。
  // 步骤 7：交付触内容安全审核被拦（code=4801）→ market-deliver 返回 content_unsafe，Agent 重生成后带
  //           --retry 重交一次；二次仍拦即 content_retry_exhausted 放弃该单（D10：每单最多一次）。

  if (!dryRun) {
    writeMarketState(marketState);
    writeLastRunMarket({ status: 'ok', env_error: false, candidate_count: candidates.length, ...summary });
  }

  emit({
    ok: true,
    status: 'ok',
    dry_run: dryRun,
    // candidates 交 Agent 逐条读 title/description/deliverables 做「AI 可完成」保守自评（拿不准跳过）。
    candidates,
    ...summary,
    agent_hint: '逐条评估 candidates：仅对 AI 能独立完成的线上任务继续接单流程（拿不准就跳过，宁可漏接不错接）；'
      + '对判定可做的任务用 `market-apply` 子命令带 skill 字段完成建/复用 skill + 申请接单；'
      + '结果最终以 last-run-market.json 为准，如实向用户汇报本轮接单/交付，禁编造。',
  });
}

/**
 * market-apply 参数解析（步骤 5 的 Agent 决策入口）。
 * Agent 在 `market` 输出候选并判定「AI 可做」后，对每个可做任务调用本子命令，
 * 带上 skill 字段（新建时必填）或直接指定复用的 skill_id，完成建/复用 skill + 申请接单。
 */
function parseMarketApplyArgs(argv) {
  const out = { keywords: [], deliverables: [] };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--dry-run') { out.dryRun = true; continue; }
    const val = () => {
      if (i + 1 >= argv.length || argv[i + 1].startsWith('--')) failCli(`missing value for ${arg}`);
      return argv[++i];
    };
    switch (arg) {
      case '--task-id': out.taskId = val(); break;
      case '--bounty': out.bounty = val(); break;
      case '--skill-id': out.skillId = val(); break;         // 直接复用某 skill（可选）
      case '--skill-name': out.skillName = val(); break;
      case '--skill-desc': out.skillDesc = val(); break;
      case '--deliverables': out.deliverables = JSON.parse(val()); break;  // JSON 数组
      case '--keywords': out.keywords = JSON.parse(val()); break;          // JSON 数组
      case '--price': out.price = val(); break;
      case '--message': out.message = val(); break;
      case '--category': out.category = val(); break;
      case '--tags': out.tags = JSON.parse(val()); break;                  // JSON 数组
      default: failCli(`unknown argument: ${arg}`);
    }
  }
  if (!out.taskId) failCli('--task-id is required');
  return out;
}

// ---------------------------------------------------------------------------
// market-apply：对单个「Agent 判定可做」的任务，建/复用 skill（步骤 4）+ 申请接单（步骤 5）。
// ---------------------------------------------------------------------------
function runMarketApply(args) {
  const a = parseMarketApplyArgs(args);
  const dryRun = Boolean(a.dryRun);

  if (!fs.existsSync(REST_SCRIPT)) {
    const msg = `基座 rest_request.js 不可达（${REST_SCRIPT}）；请确认在 skill 目录下运行或设置 UUMIT_SKILL_DIR。`;
    emit({ ok: false, status: 'env_error', env_error: true, error: msg });
    process.exit(2);
  }

  const state = readMarketState();

  // 已申请去重（幂等）：直接返回，不重复建 skill / 不重复申请。
  if (isTaskApplied(state, a.taskId)) {
    emit({ ok: true, status: 'already_applied', task_id: a.taskId });
    return;
  }

  if (dryRun) {
    emit({ ok: true, status: 'dry_run', task_id: a.taskId, note: '仅校验参数，未建 skill / 未申请。' });
    return;
  }

  const task = { task_id: a.taskId, bounty_amount: a.bounty, keywords: a.keywords };

  // 步骤 4：建/复用 skill。若 Agent 直接给了 --skill-id 则跳过判定直接用；否则走 ensureSkillForTask。
  let skillId = a.skillId;
  let skillResult = { reused: false, created: false };
  if (!skillId) {
    skillResult = ensureSkillForTask(state, task, {
      name: a.skillName,
      description: a.skillDesc,
      deliverables: a.deliverables,
      tags: a.tags,
      category: a.category,
      price: a.price,
    });
    if (skillResult.error) {
      writeMarketState(state);
      appendLastRunMarket({ failed: [{ stage: 'ensure_skill', task_id: a.taskId, error: skillResult.error }] });
      emit({ ok: false, status: 'skill_failed', task_id: a.taskId, error: skillResult.error });
      process.exit(1);
    }
    skillId = skillResult.skillId;
  }

  // 步骤 5：申请接单。
  const applyResult = applyToTask(state, a.taskId, skillId, { message: a.message, proposedPrice: a.price });
  writeMarketState(state);

  if (!applyResult.ok) {
    // 失败如实直写事实来源（D8）：不伪造成功、不静默。
    appendLastRunMarket({ failed: [{ stage: 'apply', task_id: a.taskId, skill_id: skillId, error: applyResult.error }] });
    emit({ ok: false, status: 'apply_failed', task_id: a.taskId, skill_id: skillId, error: applyResult.error });
    process.exit(1);
  }

  // 成功接单直写事实来源（D8）：供本轮 stdout 汇报如实转述。
  appendLastRunMarket({
    applied: [{
      task_id: a.taskId,
      skill_id: skillId,
      skill_reused: Boolean(skillResult.reused),
      skill_created: Boolean(skillResult.created),
      application_id: applyResult.applicationId,
    }],
  });

  emit({
    ok: true,
    status: 'applied',
    task_id: a.taskId,
    skill_id: skillId,
    skill_reused: Boolean(skillResult.reused),
    skill_created: Boolean(skillResult.created),
    application_id: applyResult.applicationId,
    already_applied: Boolean(applyResult.alreadyApplied),
  });
}

/**
 * market-deliver 参数解析（步骤 6 的 Agent 交付入口）。
 * Agent 按任务要求生成交付内容并落成本地文件后，调本子命令完成上传拿 URL + 提交交付物。
 *   --list       先发现待交付订单（不交付），供 Agent 逐单按任务要求生成交付内容
 *   --order-id   提交交付时指定的订单（提交模式必填）
 *   --files      JSON 数组 [{ "path": "本地文件", "name": "交付文件名", "text_content": "可选文本" }]
 *   --offline-note 可选交付说明
 *   --retry      标识本次是「内容安全被拦后 Agent 重生成内容的重交」（D10：每单最多一次）
 */
function parseMarketDeliverArgs(argv) {
  const out = { files: [] };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--dry-run') { out.dryRun = true; continue; }
    if (arg === '--list') { out.list = true; continue; }
    if (arg === '--retry') { out.retry = true; continue; }
    const val = () => {
      if (i + 1 >= argv.length || argv[i + 1].startsWith('--')) failCli(`missing value for ${arg}`);
      return argv[++i];
    };
    switch (arg) {
      case '--order-id': out.orderId = val(); break;
      case '--files': out.files = JSON.parse(val()); break;      // JSON 数组
      case '--offline-note': out.offlineNote = val(); break;
      default: failCli(`unknown argument: ${arg}`);
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// market-deliver：发现待交付订单 / 对指定订单上传交付物 + 提交（步骤 6）。
// ---------------------------------------------------------------------------
function runMarketDeliver(args) {
  const a = parseMarketDeliverArgs(args);

  if (!fs.existsSync(REST_SCRIPT)) {
    const msg = `基座 rest_request.js 不可达（${REST_SCRIPT}）；请确认在 skill 目录下运行或设置 UUMIT_SKILL_DIR。`;
    emit({ ok: false, status: 'env_error', env_error: true, error: msg });
    process.exit(2);
  }

  const state = readMarketState();

  // --list：仅发现待交付订单交给 Agent 逐单生成交付内容，不交付。
  if (a.list) {
    const { orders, error } = fetchPendingDeliveryOrders(state);
    if (error) {
      emit({ ok: false, status: 'fetch_failed', error, retryable: true });
      process.exit(1);
    }
    writeMarketState(state);
    emit({
      ok: true, status: 'listed', pending_orders: orders,
      agent_hint: '对每个待交付订单：初次交付按任务要求生成内容；返工订单优先读 rework_guidance（problem/expected_hint/how_to_fix，含 AI 自动打回 source=ai_auto）、无则读 rework_reason 针对性修正，然后用 market-deliver --order-id <id> --files <json> 重新提交。',
    });
    return;
  }

  if (!a.orderId) failCli('--order-id is required（或用 --list 先发现待交付订单）');
  const pendingReworkCount = Number(state.pending_rework_counts[a.orderId] || 0);
  const pendingAiReworkCount = Number(state.pending_ai_rework_counts[a.orderId] || 0);
  // 「已交付」仅当此前交付过、且买方与 AI 返工计数均未超过上次交付基线（否则是新一轮返工，需重交）。
  const hasNewRework = pendingReworkCount > Number(state.delivered_rework_counts[a.orderId] || 0)
    || pendingAiReworkCount > Number(state.delivered_ai_rework_counts[a.orderId] || 0);
  if (isOrderDelivered(state, a.orderId) && !hasNewRework) {
    emit({ ok: true, status: 'already_delivered', order_id: a.orderId });
    return;
  }
  // D10：内容安全重试机会已用尽（该单此前重交过一次仍被拦）→ 放弃，不再重交。
  if (contentRetryExhausted(state, a.orderId)) {
    const err = '该订单交付物内容安全审核二次仍被拦，已放弃（D10：每单最多重试一次）。';
    appendLastRunMarket({ failed: [{ stage: 'deliver', order_id: a.orderId, content_unsafe: true, error: err }] });
    emit({ ok: false, status: 'content_retry_exhausted', order_id: a.orderId, error: err });
    process.exit(1);
  }
  if (!Array.isArray(a.files) || a.files.length === 0) {
    failCli('--files is required：交付物需 Agent 生成文件后回传 [{path,name}]');
  }

  if (a.dryRun) {
    emit({ ok: true, status: 'dry_run', order_id: a.orderId, file_count: a.files.length, note: '仅校验参数，未上传/未提交。' });
    return;
  }

  // 逐文件上传拿 OSS URL（委托 publisher 受控直传）。任一失败即整单失败、如实暴露、不伪造。
  const deliverables = [];
  for (const f of a.files) {
    const name = f.name || (f.path ? path.basename(f.path) : null);
    if (!f.path || !name) {
      const err = `文件项缺 path/name：${JSON.stringify(f)}`;
      appendLastRunMarket({ failed: [{ stage: 'deliver', order_id: a.orderId, error: err }] });
      emit({ ok: false, status: 'deliver_failed', order_id: a.orderId, error: err });
      process.exit(1);
    }
    const { url, error } = uploadDeliverableFile(f.path);
    if (error) {
      appendLastRunMarket({ failed: [{ stage: 'upload', order_id: a.orderId, file: name, error }] });
      emit({ ok: false, status: 'upload_failed', order_id: a.orderId, error, file: name });
      process.exit(1);
    }
    const item = { url, name };
    if (f.text_content) item.text_content = String(f.text_content);
    deliverables.push(item);
  }

  // 提交交付物。
  const res = submitOrderDeliverables(state, a.orderId, deliverables, a.offlineNote);

  if (!res.ok) {
    // L1 前置过滤被拦（格式不符 / 原样重传）：服务端未入库、不消耗返工次数，附结构化 guidance 供 Agent 自主整改后重交。
    if (res.precheckError) {
      writeMarketState(state);
      appendLastRunMarket({ failed: [{ stage: 'deliver', order_id: a.orderId, precheck_error: res.precheckError, retryable: true, error: res.error }] });
      emit({
        ok: false,
        status: 'precheck_rejected',
        order_id: a.orderId,
        precheck_error: res.precheckError,
        guidance: res.guidance || null,
        error: res.error,
        agent_hint: '交付物被前置过滤拦截（未入库、不计返工）：请读 guidance（problem/expected_hint/how_to_fix）改交任务实际要求的成果物，再用 market-deliver --order-id <id> --files <json> 重交，禁止原样重试。',
      });
      process.exit(1);
    }
    // 内容安全被拦（D10）：分「首次」与「重交(--retry)」两种处置。
    if (res.contentUnsafe) {
      if (a.retry) {
        // 重交仍被拦 → 记一次重试并放弃该单，失败如实记入事实来源（D8/D10）。
        recordContentRetry(state, a.orderId);
        writeMarketState(state);
        const err = `重生成交付内容后仍被内容安全审核拦截，已放弃：${res.error}`;
        appendLastRunMarket({ failed: [{ stage: 'deliver', order_id: a.orderId, content_unsafe: true, error: err }] });
        emit({ ok: false, status: 'content_retry_exhausted', order_id: a.orderId, content_unsafe: true, error: err });
        process.exit(1);
      }
      // 首次被拦 → 提示 Agent 重生成内容后带 --retry 重交一次（此时尚未消耗重试次数）。
      writeMarketState(state);
      appendLastRunMarket({ failed: [{ stage: 'deliver', order_id: a.orderId, content_unsafe: true, retryable: true, error: res.error }] });
      emit({
        ok: false, status: 'content_unsafe', order_id: a.orderId, content_unsafe: true, error: res.error,
        agent_hint: '交付物内容安全审核被拦：请调整/重生成交付内容后，用 market-deliver --order-id <id> --files <json> --retry 重交一次（仅一次机会）。',
      });
      process.exit(1);
    }
    // 其他失败（非内容安全）：如实暴露，不伪造。
    writeMarketState(state);
    appendLastRunMarket({ failed: [{ stage: 'deliver', order_id: a.orderId, error: res.error }] });
    emit({ ok: false, status: 'deliver_failed', order_id: a.orderId, error: res.error });
    process.exit(1);
  }

  writeMarketState(state);
  const deliveryKind = hasNewRework ? 'rework' : 'initial';
  if (hasNewRework) {
    // 记录本次交付对应的买方与 AI 返工基线，避免下一轮重复识别为新返工造成重交死循环。
    state.delivered_rework_counts[a.orderId] = pendingReworkCount;
    state.delivered_ai_rework_counts[a.orderId] = pendingAiReworkCount;
    delete state.pending_rework_counts[a.orderId];
    delete state.pending_ai_rework_counts[a.orderId];
    state.content_retry[a.orderId] = 0;
    writeMarketState(state);
  }
  appendLastRunMarket({
    delivered: [{
      order_id: a.orderId,
      deliverable_count: deliverables.length,
      delivery_kind: deliveryKind,
      rework_count: pendingReworkCount || 0,
      ai_rework_count: pendingAiReworkCount || 0,
    }],
  });
  emit({
    ok: true,
    status: deliveryKind === 'rework' ? 'rework_delivered' : 'delivered',
    order_id: a.orderId,
    deliverable_count: deliverables.length,
    delivery_kind: deliveryKind,
    rework_count: pendingReworkCount || 0,
  });
}

// ---------------------------------------------------------------------------
// market-report：读 last-run-market.json 汇总本轮接单/交付结果输出 stdout（D8 唯一事实来源）。
// 定时任务收尾或 Agent 汇报时调用；结果缺失/env_error 时如实报"未取得结果"，禁编造。
// ---------------------------------------------------------------------------
function runMarketReport() {
  const cur = readJson(LAST_RUN_MARKET_FILE, null);
  if (!cur) {
    emit({
      ok: true, status: 'no_result',
      message: '未取得本轮任务市场自动接单结果（结果文件缺失）；如需可手动触发一次 market。',
    });
    return;
  }
  if (cur.env_error) {
    emit({
      ok: false, status: 'env_error', env_error: true, ran_at: cur.ran_at || null,
      error: cur.error || '运行环境异常，未取得结果。',
      message: '本轮任务市场自动接单未取得结果（运行环境异常），请检查后手动触发一次。',
    });
    return;
  }
  const applied = Array.isArray(cur.applied) ? cur.applied : [];
  const delivered = Array.isArray(cur.delivered) ? cur.delivered : [];
  const skipped = Array.isArray(cur.skipped) ? cur.skipped : [];
  const failed = Array.isArray(cur.failed) ? cur.failed : [];
  emit({
    ok: true,
    status: 'reported',
    ran_at: cur.ran_at || null,
    summary: {
      applied_count: applied.length,
      delivered_count: delivered.length,
      skipped_count: skipped.length,
      failed_count: failed.length,
    },
    applied, delivered, skipped, failed,
    agent_hint: '以本文件为唯一事实来源如实向用户汇报本轮接单/交付：成功几单、交付几单、失败原因；禁编造，无结果如实说明。',
  });
}

// ---------------------------------------------------------------------------
// market-run：任务市场自动接单的【单一调度目标 / Agent 驱动壳入口】。
//
// 定位（承接 §4.6）：无人值守系统需要「单一可登记、可复用、可审计的入口」，而非让宿主/维护者
// 自行理解 market / market-apply / market-deliver / market-report 之间的业务关系再手工串联。
// 因此本子命令是定时任务实际登记/唤起的唯一目标：它一次性把「本轮需 Agent 决策的全部工单」
// （待判定候选 + 待交付订单）结构化产出，并给出强 agent_hint 指引 Agent 逐单回调 market-apply /
// market-deliver 完成闭环，最后由 Agent 调 market-report 汇报。
//
// 边界（不越界替 Agent 决策）：apply 的 skill 语义字段、deliver 的交付内容本质需 Agent 智能生成，
// 脚本不自造。故 market-run 只做「机器可做的编排」（拉候选、硬过滤去重、发现待交付订单、写基线、
// 产出工单），把「判定 + 生成 + 回调」交给 Agent —— 这是明确的「脚本↔Agent 回调协议」，
// 而非脚本内自动跑完全链（那会越权替 Agent 决策，且脚本无法生成 skill 字段/交付内容）。
// ---------------------------------------------------------------------------
function runMarketRun(args) {
  const dryRun = args.includes('--dry-run');

  // 环境异常显式暴露（无人值守不静默/不挂起）：基座不可达即写 env_error 事实来源并退非 0。
  if (!fs.existsSync(REST_SCRIPT)) {
    const msg = `基座 rest_request.js 不可达（${REST_SCRIPT}）；请确认在 skill 目录下运行或设置 UUMIT_SKILL_DIR。`;
    if (!dryRun) writeLastRunMarket({ status: 'env_error', env_error: true, error: msg });
    emit({ ok: false, status: 'env_error', env_error: true, error: msg });
    process.exit(2);
  }

  const state = readMarketState();

  // ① 拉候选（硬过滤 + 去重）。拉取失败：如实写事实来源、退非 0，不静默、不伪造。
  const { candidates, skipped, error: fetchErr } = fetchMarketCandidates(state, 20);
  if (fetchErr) {
    if (!dryRun) writeLastRunMarket({ status: 'fetch_failed', env_error: false, skipped, error: fetchErr });
    emit({ ok: false, status: 'fetch_failed', dry_run: dryRun, candidates: [], skipped, error: fetchErr, retryable: true });
    process.exit(1);
  }

  // ② 发现待交付订单（撮合已成、待本方交付）。失败不阻断本轮候选产出，仅在工单里标注发现失败。
  const { orders: pendingOrders, error: ordersErr } = fetchPendingDeliveryOrders(state);
  if (!dryRun && !ordersErr) writeMarketState(state);

  // ③ 写基线事实来源（本轮已发现多少候选/待交付，供审计与 report 兜底；不含 applied/delivered——那须 Agent 回调后由子命令追加）。
  if (!dryRun) {
    writeLastRunMarket({
      status: 'run_dispatched',
      env_error: false,
      candidate_count: candidates.length,
      pending_delivery_count: pendingOrders.length,
      skipped,
      pending_orders_error: ordersErr || null,
    });
  }

  // ④ 产出「单一入口工单」+ 强 agent_hint：Agent 据此逐单回调 apply/deliver，最后 report。
  emit({
    ok: true,
    status: 'run_dispatched',
    dry_run: dryRun,
    // 待 Agent 逐条判定「AI 可完成」的候选（拿不准跳过）。
    candidates,
    // 已硬过滤/去重剔除的项（计入审计）。
    skipped,
    // 已撮合、待本方交付的订单（Agent 按各订单任务要求生成交付内容后回调 market-deliver）。
    pending_orders: pendingOrders,
    pending_orders_error: ordersErr || null,
    agent_hint:
      '这是任务市场自动接单的单一驱动入口，请在本次会话内按序完成整轮闭环，不要中途停在“只列候选”：\n'
      + '① 逐条评估 candidates：仅对本 Agent 能独立完成的线上任务继续，拿不准就跳过（宁可漏接不错接）；'
      + '评估时务必判断交付物形态——若任务需要生成图片/视频/音频等你当前模型不具备的产物，则不要接（或提醒用户切换到多模态模型后再接），优先接你当前能直接完成的文本类任务；\n'
      + '② 对判定可做的任务，生成对口 skill 语义字段后调 `cruise.js market-apply --task-id <id> ...` 建/复用 skill 并申请接单；\n'
      + '③ 对 pending_orders 每个订单：initial 按任务要求生成交付内容；rework 优先读结构化 rework_guidance（problem/expected_hint/how_to_fix；source=ai_auto 为 AI 自动打回、retryable=false 表示已达上限转人工则勿再自动重交），无则读 rework_reason/rework_count/rework_deadline，针对返工原因修正原交付内容；完成后落成本地文件并调 `cruise.js market-deliver --order-id <id> --files <json>` 上传+提交（触内容安全被拦则重生成内容后带 --retry 重交一次；触前置过滤 precheck_rejected 则按 guidance 改交正确成果物、禁止原样重试）；\n'
      + '④ 最后调 `cruise.js market-report` 汇总本轮接单/交付结果并如实向用户汇报（只读 last-run-market.json，禁编造）；\n'
      + '若 candidates 与 pending_orders 均为空，则本轮无可接/可交付事项，直接调 market-report 如实汇报即可。',
  });
}

// ---------------------------------------------------------------------------
function main() {
  const [sub, ...rest] = process.argv.slice(2);
  switch (sub) {
    case 'status': return runStatus(rest);
    case 'work': return runWork();
    case 'record': return runRecord(rest);
    case 'market-run': return runMarketRun(rest);
    case 'market': return runMarket(rest);
    case 'market-apply': return runMarketApply(rest);
    case 'market-deliver': return runMarketDeliver(rest);
    case 'market-report': return runMarketReport();
    default:
      failCli(`unknown subcommand: ${sub || '(none)'}（可用：status | work | record | market-run | market | market-apply | market-deliver | market-report）`);
  }
}

main();
