#!/usr/bin/env node
/**
 * UUMit Skill v2.7.0 — REST 请求脚本。
 *
 * 用法:
 *   node rest_request.js <METHOD> <PATH> [--file JSON_FILE] [--param KEY VALUE] [--idempotency-key KEY] [--dry-run] [--confirmed]
 *
 * 鉴权（优先级）: 环境变量 > 本地 auth 文件
 *   UUMIT_API_KEY / UUMIT_USER_ID 或 memory/uumit-auth.json
 *
 * 特性:
 *   - 路由白名单（仅放行已登记接口）
 *   - 5xx/超时/网络错误重试
 *   - 写操作幂等键自动生成
 *   - 自动扣费闸门（超阈值/议价/价格不可知时要求确认）
 *
 * 输出: stdout=JSON（供 Agent 内部解析）；stderr=诊断；非 0 退出码=失败。
 */

const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const os = require('os');

const SKILL_DIR = path.resolve(__dirname, '..');
const AUTH_FILE = path.join(SKILL_DIR, 'memory', 'uumit-auth.json');
const TIMEOUT = 15000;
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000;
const AUTO_SPEND_GATE_ENABLED = process.env.UUMIT_AUTO_SPEND_GATE !== '0';

// 读取并解析 JSON 文件，容忍 UTF-8 BOM（\uFEFF）。
// Node 的 JSON.parse 不会自动跳过 BOM，若 auth/config 等文件被编辑器写入 BOM
// 会直接抛错，导致鉴权文件读取失败、请求匿名发出，服务端回 Not Found。
function readJsonFile(filePath) {
  let text = fs.readFileSync(filePath, 'utf8');
  if (text.charCodeAt(0) === 0xfeff) text = text.slice(1);
  return JSON.parse(text);
}

// 解析 JSON 字符串，同样容忍前导 BOM。
function parseJson(text) {
  if (typeof text === 'string' && text.charCodeAt(0) === 0xfeff) text = text.slice(1);
  return JSON.parse(text);
}

function loadConfig() {
  try {
    return readJsonFile(path.join(SKILL_DIR, 'memory', 'uumit-config.json'));
  } catch (_) {
    return {};
  }
}

const RUNTIME_CONFIG = loadConfig();

function resolveBaseUrl() {
  return process.env.UUMIT_BASE_URL || RUNTIME_CONFIG.base_url || 'https://api.uumit.com';
}

const BASE_URL = resolveBaseUrl();
const baseUrlObj = new URL(BASE_URL);
const isHttps = baseUrlObj.protocol === 'https:';

// ---------------------------------------------------------------------------
// 路由白名单（正则）。仅放行 SKILL.md / 子文档登记的接口。
// ---------------------------------------------------------------------------
const ALLOWED_ROUTES = [
  // 鉴权与互通
  ['GET', /^\/\.well-known\/agent\.json$/],
  ['POST', /^\/a2a$/],
  ['POST', /^\/api\/v1\/auth\/device-auth(\/poll)?$/],
  ['GET', /^\/api\/v1\/agents\/[a-f0-9-]+\/(card|\.well-known\/agent\.json)$/],
  ['GET', /^\/api\/v1\/interop\/debug$/],
  ['GET', /^\/api\/v1\/skill-pack$/],
  ['GET', /^\/api\/v1\/external-agents(\/[a-f0-9-]+)?$/],
  ['POST', /^\/api\/v1\/external-agents$/],
  ['PATCH', /^\/api\/v1\/external-agents\/[a-f0-9-]+\/webhook$/],

  // 用户与账户（只读 + 资料更新）
  ['GET', /^\/api\/v1\/users\/me(\/(profile-completeness|agent))?$/],
  ['PUT', /^\/api\/v1\/users\/me\/profile$/],
  ['GET', /^\/api\/v1\/users\/[a-f0-9-]+\/public-profile$/],

  // 钱包 / 信用 / 订单 / 交易（K3-3：钱包/充值/提现/账单/收益意图）
  ['GET', /^\/api\/v1\/wallet(\/transactions|\/stats|\/rates|\/withdraw-config|\/withdrawals|\/payment-accounts)?$/],
  ['GET', /^\/api\/v1\/wallet\/withdrawals\/[a-f0-9-]+$/],
  ['POST', /^\/api\/v1\/wallet\/(withdraw|withdraw-cash|payment-accounts)$/],
  ['POST', /^\/api\/v1\/wallet\/withdraw\/[a-f0-9-]+\/cancel$/],
  ['GET', /^\/api\/v1\/wallet\/recharge$/],
  ['GET', /^\/api\/v1\/wallet\/recharge\/[a-f0-9-]+(\/status)?$/],
  ['POST', /^\/api\/v1\/wallet\/recharge$/],
  ['GET', /^\/api\/v1\/capabilities\/income\/(overview|records)$/],
  ['GET', /^\/api\/v1\/credit\/me(\/events)?$/],
  // 订单与售后（K3-2：订单查询/退款/投诉/评价/沟通）
  ['GET', /^\/api\/v1\/orders(\/[a-f0-9-]+)?$/],
  ['GET', /^\/api\/v1\/orders\/seller-pending-count$/],
  ['GET', /^\/api\/v1\/orders\/[a-f0-9-]+\/(renewals|disputes)$/],
  ['POST', /^\/api\/v1\/orders\/[a-f0-9-]+\/(deliverables|confirm|cancel|rating|rework|disputes)$/],
  ['GET', /^\/api\/v1\/orders\/[a-f0-9-]+\/chat(\/messages)?$/],
  ['POST', /^\/api\/v1\/orders\/[a-f0-9-]+\/chat\/messages$/],
  ['PUT', /^\/api\/v1\/orders\/[a-f0-9-]+\/chat\/read$/],
  ['GET', /^\/api\/v1\/order-chats(\/unread-count)?$/],
  ['GET', /^\/api\/v1\/disputes\/active$/],
  ['POST', /^\/api\/v1\/disputes\/[a-f0-9-]+\/evidence$/],
  ['GET', /^\/api\/v1\/transactions(\/[a-f0-9-]+)?$/],

  // 知识商店 / 数字资产
  ['GET', /^\/api\/v1\/marketplace\/search$/],
  ['GET', /^\/api\/v1\/digital-assets\/purchased$/],
  ['GET', /^\/api\/v1\/digital-assets\/[a-f0-9-]+\/purchased-secret$/],
  ['GET', /^\/api\/v1\/digital-assets\/market\/[a-f0-9-]+$/],
  ['POST', /^\/api\/v1\/digital-assets\/[a-f0-9-]+\/purchase$/],

  // 知识商店 — 账号类商品上架（会员账号/卡密/兑换码/共享账号）
  ['POST', /^\/api\/v1\/digital-assets\/account-inventory$/],
  ['POST', /^\/api\/v1\/digital-assets\/account-shared$/],
  ['POST', /^\/api\/v1\/digital-assets\/[a-f0-9-]+\/account-publish$/],
  ['POST', /^\/api\/v1\/digital-assets\/[a-f0-9-]+\/inventory-items\/bulk$/],
  ['GET', /^\/api\/v1\/digital-assets\/[a-f0-9-]+\/inventory-items$/],
  ['PATCH', /^\/api\/v1\/digital-assets\/inventory-items\/[a-f0-9-]+$/],
  ['POST', /^\/api\/v1\/digital-assets\/inventory-items\/[a-f0-9-]+\/toggle-disable$/],
  ['GET', /^\/api\/v1\/digital-assets\/[a-f0-9-]+\/shared-secret\/stats$/],

  // 数据广场
  ['GET', /^\/api\/v1\/data-marketplace\/[a-f0-9-]+$/],
  ['POST', /^\/api\/v1\/data-marketplace\/[a-f0-9-]+\/call(\/stream)?$/],

  // 市场行情建议价 / 价格偏离检查（只读，上架/发布前定价依据）
  ['GET', /^\/api\/v1\/pricing\/(suggestion|anomaly-check)$/],

  // 能力上架与管理（K3-1：供给侧自助上架）
  ['POST', /^\/api\/v1\/capabilities$/],
  ['GET', /^\/api\/v1\/capabilities\/mine$/],
  ['GET', /^\/api\/v1\/capabilities\/[a-f0-9-]+$/],
  ['PUT', /^\/api\/v1\/capabilities\/[a-f0-9-]+$/],
  ['DELETE', /^\/api\/v1\/capabilities\/[a-f0-9-]+$/],
  ['POST', /^\/api\/v1\/capabilities\/[a-f0-9-]+\/(submit-review|offline|online)$/],
  ['GET', /^\/api\/v1\/capabilities\/[a-f0-9-]+\/income$/],

  // 能力运行时（K1-3：放行 smart-invoke）
  ['POST', /^\/api\/v1\/capability-runtime\/smart-invoke$/],
  ['POST', /^\/api\/v1\/capability-runtime\/(discover|quote|invoke)$/],
  ['GET', /^\/api\/v1\/capability-runtime\/catalog$/],
  ['GET', /^\/api\/v1\/capability-runtime\/runs\/[a-f0-9-]+$/],

  // 复杂任务编排（K4-1：阶段四 plan→optimize→execute→aggregate）
  ['POST', /^\/api\/v1\/capabilities\/(plan|optimize-plan|execute-plan|aggregate)$/],
  // 复杂任务编排流式执行（K4-2：SSE 分步进度）
  ['POST', /^\/api\/v1\/capabilities\/execute-plan\/stream$/],

  // 半标准能力适配器（K2-1/K2-2）
  ['GET', /^\/api\/v1\/capability-adapters(\/[A-Za-z0-9_-]+)?$/],
  ['POST', /^\/api\/v1\/capability-adapters$/],
  ['PATCH', /^\/api\/v1\/capability-adapters\/[A-Za-z0-9_-]+$/],
  ['POST', /^\/api\/v1\/capability-adapters\/[A-Za-z0-9_-]+\/(sandbox-test|register)$/],

  // Playbooks 精品工作流
  ['GET', /^\/api\/v1\/playbooks\/templates$/],
  ['POST', /^\/api\/v1\/playbooks\/parse-requirement$/],
  ['POST', /^\/api\/v1\/playbooks\/company-candidates$/],
  ['POST', /^\/api\/v1\/playbooks\/runs(\/estimate)?$/],
  ['GET', /^\/api\/v1\/playbooks\/runs(\/[a-f0-9-]+(\/artifacts|\/events)?)?$/],
  ['POST', /^\/api\/v1\/playbooks\/runs\/[a-f0-9-]+\/(cancel|convert-task)$/],

  // 巡航 / Agent 设置（只读）
  ['GET', /^\/api\/v1\/agent\/(cruise|bootstrap)$/],
  ['GET', /^\/api\/v1\/agent\/agent-settings$/],

  // 算力共享
  ['GET', /^\/api\/v1\/compute-share(\/[a-f0-9-]+)?$/],

  // 任务市场
  ['POST', /^\/api\/v1\/tasks$/],
  ['POST', /^\/api\/v1\/tasks\/ai-create$/],
  ['GET', /^\/api\/v1\/tasks(\/hall|\/market\/stats)?$/],
  ['GET', /^\/api\/v1\/tasks\/applications\/mine$/],
  ['GET', /^\/api\/v1\/tasks\/[a-f0-9-]+$/],
  ['PUT', /^\/api\/v1\/tasks\/[a-f0-9-]+$/],
  ['POST', /^\/api\/v1\/tasks\/[a-f0-9-]+\/(close|publish-draft|applications)$/],
  ['GET', /^\/api\/v1\/tasks\/[a-f0-9-]+\/applications$/],
  ['DELETE', /^\/api\/v1\/tasks\/[a-f0-9-]+\/applications\/[a-f0-9-]+$/],
  ['POST', /^\/api\/v1\/tasks\/[a-f0-9-]+\/applications\/[a-f0-9-]+\/(accept|reject)$/],
  ['POST', /^\/api\/v1\/tasks\/from-skill$/],

  // 技能市场
  ['POST', /^\/api\/v1\/skills$/],
  ['POST', /^\/api\/v1\/skills\/ai-create$/],
  ['POST', /^\/api\/v1\/skills\/input-schema\/generate$/],
  ['GET', /^\/api\/v1\/skills(\/hall)?$/],
  ['GET', /^\/api\/v1\/skills\/[a-f0-9-]+(\/ratings)?$/],
  ['PUT', /^\/api\/v1\/skills\/[a-f0-9-]+$/],
  ['DELETE', /^\/api\/v1\/skills\/[a-f0-9-]+$/],

  // 询价 / 议价
  ['POST', /^\/api\/v1\/inquiry\/chats$/],
  ['GET', /^\/api\/v1\/inquiry\/chats$/],
  ['GET', /^\/api\/v1\/inquiry\/chats\/[a-f0-9-]+\/messages$/],
  ['POST', /^\/api\/v1\/inquiry\/chats\/[a-f0-9-]+\/messages$/],

  // 时间市场
  ['GET', /^\/api\/v1\/time-market\/available$/],
  ['POST', /^\/api\/v1\/time-market\/book$/],
  ['POST', /^\/api\/v1\/time-market\/[a-f0-9-]+\/(accept|decline)$/],

  // 星火计划 / AI 额度
  ['POST', /^\/api\/v1\/llm\/cyber-egg\/claim$/],
  ['GET', /^\/api\/v1\/llm\/cyber-egg\/(today|history)$/],
  ['GET', /^\/api\/v1\/llm\/models$/],
  ['GET', /^\/api\/v1\/llm\/my-credits\/summary$/],

  // 优惠券
  ['GET', /^\/api\/v1\/coupons(\/claimable)?$/],
  ['POST', /^\/api\/v1\/coupons\/claim$/],

  // 帮解锁
  ['GET', /^\/api\/v1\/help-unlock\/config$/],
  ['GET', /^\/api\/v1\/help-unlock\/instances\/mine$/],
  ['POST', /^\/api\/v1\/help-unlock\/instances$/],
  ['GET', /^\/api\/v1\/help-unlock\/instances\/[a-f0-9-]+$/],
  ['POST', /^\/api\/v1\/help-unlock\/instances\/[a-f0-9-]+\/(help|claim)$/],

  // 上传（分片为 JSON；单文件 multipart 由 uumit-publisher 受控直传，不走本脚本）
  ['POST', /^\/api\/v1\/upload\/chunked\/(init|complete)$/],

  // 数字资产批量发布（供 uumit-publisher 编排）
  ['GET', /^\/api\/v1\/digital-assets$/],
  ['POST', /^\/api\/v1\/digital-assets\/[a-f0-9-]+\/publish$/],

  // 知识商店 — 文件型资产创建与封面媒体（upload_file → quick-upload 两步）
  ['POST', /^\/api\/v1\/digital-assets\/quick-upload$/],
  ['PATCH', /^\/api\/v1\/digital-assets\/[a-f0-9-]+\/media$/],

  // ---- 阶段三：覆盖度复审增补域（7.3）----

  // A2A 交易（Agent 间委托交易；GET /transactions 与资金交易同路径，按后端语义区分）
  ['POST', /^\/api\/v1\/transactions$/],
  ['POST', /^\/api\/v1\/transactions\/[a-f0-9-]+\/(freeze|accept|reject|deliver|confirm|cancel)$/],

  // 智能体任务轮询补拉（智能体任务自动接单：一次性拉全上次运行以来的未处理事件）
  ['GET', /^\/api\/v1\/agent-runtime\/pending$/],

  // 议价会话
  ['POST', /^\/api\/v1\/negotiation\/initiate$/],
  ['POST', /^\/api\/v1\/negotiation\/sessions\/[a-f0-9-]+\/(respond|cancel)$/],
  ['GET', /^\/api\/v1\/negotiation\/sessions$/],
  ['GET', /^\/api\/v1\/negotiation\/sessions\/by-chat\/[a-f0-9-]+$/],
  ['GET', /^\/api\/v1\/negotiation\/sessions\/[a-f0-9-]+$/],

  // 交付物（JSON 端点；multipart upload 由 uumit-publisher 受控直传，不入此处）
  ['POST', /^\/api\/v1\/deliverables\/upload\/(init|complete)$/],
  ['POST', /^\/api\/v1\/deliverables\/grant-access$/],
  ['GET', /^\/api\/v1\/deliverables\/[A-Za-z0-9_-]+\/download$/],

  // 收益中心
  ['GET', /^\/api\/v1\/income-center\/(overview|opportunities)$/],

  // 微任务（1.x 已有，补回）
  ['GET', /^\/api\/v1\/micro-tasks\/(next|stats)$/],
  ['POST', /^\/api\/v1\/micro-tasks\/[a-f0-9-]+\/submit$/],

  // 订阅
  ['GET', /^\/api\/v1\/subscriptions$/],
  ['POST', /^\/api\/v1\/subscriptions$/],
  ['DELETE', /^\/api\/v1\/subscriptions\/[a-f0-9-]+$/],

  // ---- 阶段三：扩展所需 ----

  // 推荐（供 uumit-recommend 编排）
  ['GET', /^\/api\/v1\/recommendations(\/feed)?$/],
  ['POST', /^\/api\/v1\/recommendations\/feedback(\/batch)?$/],
  // 动态能力上下文推荐（批次 2：activation 预计算的高价值能力）
  ['GET', /^\/api\/v1\/capability-runtime\/recommended-capabilities$/],
  ['GET', /^\/api\/v1\/digital-assets\/market\/list$/],
  ['GET', /^\/api\/v1\/data-marketplace\/?$/],

  // 算力共享（供 uumit-compute 引导；JSON 端点经基座调用，归基座覆盖）
  ['GET', /^\/api\/v1\/compute-share\/(status|my\/summary|calls)$/],
  ['GET', /^\/api\/v1\/compute-share\/credentials(\/[a-f0-9-]+)?$/],
  ['POST', /^\/api\/v1\/compute-share\/credentials$/],

  // 社交（供 uumit-social；仅 API Key 可用端点，JWT-only 走深链）
  ['GET', /^\/api\/v1\/credit\/me\/(penalty|verification|appeals)$/],
  ['GET', /^\/api\/v1\/invite\/(stats|chain|records|rewards|milestones)$/],
  ['GET', /^\/api\/v1\/red-packet\/(koi-counter|koi-activity-feed|my-batches|my-claims)$/],
  ['POST', /^\/api\/v1\/red-packet\/[a-f0-9-]+\/claim$/],
  ['GET', /^\/api\/v1\/buddy\/(list|feed)$/],
];

function routeAllowed(method, urlPath) {
  const clean = urlPath.split('?')[0];
  return ALLOWED_ROUTES.some(([m, re]) => m === method && re.test(clean));
}

// 公开只读端点：服务端无需认证即可访问（如算力共享功能开关状态检查，
// uumit-compute 引导流程要求未授权用户先确认功能是否开启）。
// 无凭据时仅放行此类路由，且请求不带认证头；写操作与含用户数据的端点绝不豁免。
// 仍受 ALLOWED_ROUTES 白名单约束（PUBLIC_ROUTES 必须是已登记路由）。
const PUBLIC_ROUTES = [
  ['GET', '/api/v1/compute-share/status'],
];

function isPublicRoute(method, cleanPath) {
  return PUBLIC_ROUTES.some(([m, p]) => m === method && p === cleanPath);
}

// ---------------------------------------------------------------------------
// 鉴权
// ---------------------------------------------------------------------------
function loadCredentials() {
  let apiKey = process.env.UUMIT_API_KEY;
  let userId = process.env.UUMIT_USER_ID;
  if (!apiKey || !userId) {
    try {
      const auth = readJsonFile(AUTH_FILE);
      apiKey = apiKey || auth.api_key;
      userId = userId || auth.platform_user_id || auth.user_id;
    } catch (e) {
      // 鉴权文件不存在是未授权环境的正常状态（公开端点匿名请求也会走到这里），不打印噪音。
      if (e.code !== 'ENOENT') console.error('[rest_request] 读取鉴权文件失败:', e.message);
    }
  }
  return { apiKey, userId };
}

// ---------------------------------------------------------------------------
// HTTP
// ---------------------------------------------------------------------------
function makeRequest(method, urlPath, headers, body) {
  return new Promise((resolve, reject) => {
    const lib = isHttps ? https : http;
    const data = body ? JSON.stringify(body) : null;
    const options = {
      method,
      hostname: baseUrlObj.hostname,
      port: baseUrlObj.port || (isHttps ? 443 : 80),
      path: urlPath,
      headers: {
        'Content-Type': 'application/json',
        ...headers,
        ...(data ? { 'Content-Length': Buffer.byteLength(data) } : {}),
      },
      timeout: TIMEOUT,
    };
    const req = lib.request(options, (res) => {
      let chunks = '';
      res.on('data', (c) => { chunks += c; });
      res.on('end', () => {
        let parsed = null;
        try { parsed = chunks ? JSON.parse(chunks) : null; } catch (_) { parsed = chunks; }
        resolve({ statusCode: res.statusCode, data: parsed });
      });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(new Error('request timeout')); });
    if (data) req.write(data);
    req.end();
  });
}

// probe（估价/换取确认凭证）必须用独立的幂等键，不能与主请求共用同一 Idempotency-Key：
// 主流程为写请求设了固定的 headers['Idempotency-Key']，若 probe 复用同一头，后端头级幂等会把
// 随后的正式请求当作 probe 的重复而回放 probe 的 requires_confirmation，导致两段式确认永远失效。
// 这里返回一份带全新 Idempotency-Key 的 headers 副本，隔离每次 probe。
function probeHeaders(headers) {
  const copy = { ...(headers || {}) };
  if ('Idempotency-Key' in copy) copy['Idempotency-Key'] = crypto.randomUUID();
  return copy;
}

async function requestWithRetry(method, urlPath, headers, body) {
  let lastErr = null;
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const res = await makeRequest(method, urlPath, headers, body);
      if (res.statusCode >= 500 && attempt < MAX_RETRIES) {
        await sleep(RETRY_DELAY * (attempt + 1));
        continue;
      }
      return res;
    } catch (e) {
      lastErr = e;
      if (attempt < MAX_RETRIES) {
        await sleep(RETRY_DELAY * (attempt + 1));
        continue;
      }
    }
  }
  throw lastErr || new Error('request failed');
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

// ---------------------------------------------------------------------------
// 参数解析
// ---------------------------------------------------------------------------
function resolveSkillRelativePath(filePath) {
  if (path.isAbsolute(filePath)) return filePath;
  return path.join(SKILL_DIR, filePath);
}

function parseArgs(argv) {
  const args = { method: argv[0], urlPath: argv[1], params: {}, body: null, idempotencyKey: null, outputFile: null, dryRun: false, confirmed: false };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--file') {
      const fp = resolveSkillRelativePath(argv[++i]);
      args.body = readJsonFile(fp);
    } else if (a === '--body') {
      // 内联 JSON 请求体（供 capability_* 等薄封装直接传 body，不必落临时文件）。
      args.body = parseJson(argv[++i]);
    } else if (a === '--param') {
      args.params[argv[++i]] = argv[++i];
    } else if (a === '--idempotency-key') {
      args.idempotencyKey = argv[++i];
    } else if (a === '--output-file') {
      args.outputFile = argv[++i];
    } else if (a === '--dry-run') {
      args.dryRun = true;
    } else if (a === '--confirmed') {
      args.confirmed = true;
    }
  }
  return args;
}

function buildQuery(params) {
  const keys = Object.keys(params);
  if (!keys.length) return '';
  return '?' + keys.map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(params[k])}`).join('&');
}

function resolveOutputFile(filePath) {
  if (!filePath || !path.isAbsolute(filePath)) {
    throw new Error('--output-file 必须是操作系统临时目录内的绝对路径');
  }
  const resolved = path.resolve(filePath);
  const tempRoot = path.resolve(os.tmpdir());
  const relative = path.relative(tempRoot, resolved);
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative)) {
    throw new Error('--output-file 仅允许写入操作系统临时目录的子路径');
  }
  const parent = path.dirname(resolved);
  if (!fs.existsSync(parent) || !fs.statSync(parent).isDirectory()) {
    throw new Error('--output-file 的父目录必须已存在');
  }
  if (fs.existsSync(resolved)) {
    throw new Error('--output-file 目标文件已存在，拒绝覆盖');
  }
  return resolved;
}

function writeOutputFile(filePath, payload) {
  const outputPath = resolveOutputFile(filePath);
  const content = JSON.stringify(payload, null, 2);
  fs.writeFileSync(outputPath, content, { encoding: 'utf8', flag: 'wx', mode: 0o600 });
  return { output_file: outputPath, bytes: Buffer.byteLength(content) };
}

// ---------------------------------------------------------------------------
// 自动扣费闸门（基础版；余额校验扩展见 K1-4）
// ---------------------------------------------------------------------------
function loadAutoSpendMaxUt() {
  const cfgPath = path.join(SKILL_DIR, 'memory', 'runtime', 'agent-autonomy-config.json');
  try {
    const raw = readJsonFile(cfgPath);
    const t = Number(raw.spend && raw.spend.auto_spend_max_ut);
    return Number.isFinite(t) ? t : 100;
  } catch (_) {
    return 100;
  }
}

// 单日累计上限：本机花费软提醒（非权威风控）。缺失/异常回退 5000。
function loadDailyMaxUt() {
  const cfgPath = path.join(SKILL_DIR, 'memory', 'runtime', 'agent-autonomy-config.json');
  try {
    const raw = readJsonFile(cfgPath);
    const t = Number(raw.spend && raw.spend.daily_max_ut);
    return Number.isFinite(t) ? t : 5000;
  } catch (_) {
    return 5000;
  }
}

// 单日 ledger 路径：相对 SKILL_DIR（不支持绝对路径），缺失时回退默认路径。
function dailyLedgerPath() {
  const cfgPath = path.join(SKILL_DIR, 'memory', 'runtime', 'agent-autonomy-config.json');
  let rel = 'memory/runtime/spend-daily-ledger.json';
  try {
    const raw = readJsonFile(cfgPath);
    const p = raw.spend && raw.spend.daily_ledger_path;
    if (typeof p === 'string' && p.length > 0) rel = p;
  } catch (_) { /* 回退默认路径 */ }
  return path.join(SKILL_DIR, rel);
}

// 当前本地自然日（Asia/Shanghai），格式 YYYY-MM-DD。
function todayLocalDate() {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Shanghai' });
}

// 读取当日累计：文件不存在或跨日（date≠今日）均归零；任何读/解析异常回退当日零累计。
function readDailyLedger() {
  const today = todayLocalDate();
  try {
    const ledger = readJsonFile(dailyLedgerPath());
    if (ledger && ledger.date === today && Number.isFinite(Number(ledger.spent_ut))) {
      return { date: today, spent_ut: Number(ledger.spent_ut) };
    }
  } catch (_) { /* 不存在/损坏：回退当日零累计 */ }
  return { date: today, spent_ut: 0 };
}

// 写回当日累计：记账为旁路，写失败仅提示不抛出，不得中断付费主流程。
function writeDailyLedger(spentUt) {
  const record = {
    date: todayLocalDate(),
    spent_ut: spentUt,
    updated_at: new Date().toISOString(),
  };
  try {
    fs.writeFileSync(dailyLedgerPath(), JSON.stringify(record, null, 2), { mode: 0o600 });
  } catch (e) {
    console.error(JSON.stringify({ warn: 'write_daily_ledger_failed', message: String(e && e.message || e) }));
  }
}

function failNeedConfirmation(payload) {
  console.error(JSON.stringify({ error: 'confirmation required', ...payload }));
  process.exit(2);
}

function parsePrice(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

async function fetchPriceUt(cleanPath, headers) {
  // 数据广场调用
  let m = cleanPath.match(/^\/api\/v1\/data-marketplace\/([a-f0-9-]+)\/call/);
  if (m) {
    const { statusCode, data } = await requestWithRetry('GET', `/api/v1/data-marketplace/${m[1]}`, headers, null);
    if (statusCode < 400 && data && data.code === 0 && data.data) return parsePrice(data.data.price_ut);
    return null;
  }
  // 数字资产购买
  m = cleanPath.match(/^\/api\/v1\/digital-assets\/([a-f0-9-]+)\/purchase$/);
  if (m) {
    const { statusCode, data } = await requestWithRetry('GET', `/api/v1/digital-assets/market/${m[1]}`, headers, null);
    if (statusCode < 400 && data && data.code === 0 && data.data) {
      return parsePrice(data.data.actual_price_ut) ?? parsePrice(data.data.price_ut);
    }
    return null;
  }
  return null;
}

function extractEstimatedCostUt(data) {
  if (!data) return null;
  const payload = data.data || data;
  return (
    parsePrice(payload.estimated_cost_ut)
    ?? parsePrice(payload.price_ut)
    ?? parsePrice(payload.cost_ut)
    ?? parsePrice(payload.estimated_price_ut)
  );
}

function isCapabilityAdapterWrite(cleanPath) {
  return cleanPath === '/api/v1/capability-adapters'
    || /^\/api\/v1\/capability-adapters\/[A-Za-z0-9_-]+$/.test(cleanPath)
    || /^\/api\/v1\/capability-adapters\/[A-Za-z0-9_-]+\/(sandbox-test|register)$/.test(cleanPath);
}

function enforceExternalDataConfirmation(method, cleanPath, body, confirmed) {
  if (method !== 'POST' && method !== 'PATCH') return;
  if (!isCapabilityAdapterWrite(cleanPath)) return;
  if (confirmed) return;

  const payload = body && typeof body === 'object' ? body : {};
  const hasEndpoint = typeof payload.endpoint === 'string' && payload.endpoint.length > 0;
  const hasAuth = payload.auth_config && Object.keys(payload.auth_config).length > 0;
  const hasHeaders = payload.headers && Object.keys(payload.headers).length > 0;
  const isSandbox = /\/sandbox-test$/.test(cleanPath);
  const isRegister = /\/register$/.test(cleanPath);

  failNeedConfirmation({
    reason: 'external_adapter_requires_confirm',
    path: cleanPath,
    risk_level: 'L4',
    data_flow: hasEndpoint
      ? `请求样例、schema 映射与沙箱数据将发送给第三方 endpoint: ${payload.endpoint}`
      : '适配器配置、样例输入或能力元数据将发送到外部 endpoint 或写入 UUMit 适配器配置',
    has_auth_config: Boolean(hasAuth),
    has_custom_headers: Boolean(hasHeaders),
    operation: isSandbox ? 'sandbox-test' : (isRegister ? 'register-adapter-capability' : 'configure-adapter'),
    hint: '配置第三方 endpoint、鉴权、沙箱试调或生成适配器能力前，必须向用户展示外发范围并获得确认，然后加 --confirmed 重试。',
  });
}

function isWalletFundsWrite(cleanPath) {
  return cleanPath === '/api/v1/wallet/withdraw'
    || cleanPath === '/api/v1/wallet/withdraw-cash'
    || cleanPath === '/api/v1/wallet/payment-accounts'
    || /^\/api\/v1\/wallet\/withdraw\/[a-f0-9-]+\/cancel$/.test(cleanPath)
    || cleanPath === '/api/v1/wallet/recharge';
}

function enforceWalletWriteConfirmation(method, cleanPath, confirmed) {
  if (method !== 'POST') return;
  if (!isWalletFundsWrite(cleanPath)) return;
  if (confirmed) return;

  const isRecharge = cleanPath === '/api/v1/wallet/recharge';
  const isCancel = /\/cancel$/.test(cleanPath);
  const isPaymentAccount = cleanPath === '/api/v1/wallet/payment-accounts';
  let operation = 'withdraw';
  if (isRecharge) operation = 'create-recharge-order';
  else if (isCancel) operation = 'cancel-withdrawal';
  else if (isPaymentAccount) operation = 'bind-payment-account';

  failNeedConfirmation({
    reason: 'wallet_funds_change_requires_confirm',
    path: cleanPath,
    risk_level: 'L4',
    operation,
    hint: '资金变动类操作（提现/创建充值订单/绑定收款账户/取消提现）必须先向用户展示金额与账户信息并获得确认，然后加 --confirmed 重试。',
  });
}

function isOrderAftersaleWrite(method, cleanPath) {
  if (method !== 'POST') return false;
  return /^\/api\/v1\/orders\/[a-f0-9-]+\/(confirm|cancel|rework|rating|disputes)$/.test(cleanPath)
    || /^\/api\/v1\/disputes\/[a-f0-9-]+\/evidence$/.test(cleanPath);
}

function enforceOrderAftersaleConfirmation(method, cleanPath, confirmed) {
  if (!isOrderAftersaleWrite(method, cleanPath)) return;
  if (confirmed) return;

  let operation = 'order-action';
  if (/\/confirm$/.test(cleanPath)) operation = 'confirm-receipt-and-release-funds';
  else if (/\/cancel$/.test(cleanPath)) operation = 'cancel-order';
  else if (/\/rework$/.test(cleanPath)) operation = 'request-rework';
  else if (/\/rating$/.test(cleanPath)) operation = 'submit-rating';
  else if (/\/orders\/[a-f0-9-]+\/disputes$/.test(cleanPath)) operation = 'raise-dispute';
  else if (/\/evidence$/.test(cleanPath)) operation = 'submit-dispute-evidence';

  failNeedConfirmation({
    reason: 'order_aftersale_requires_confirm',
    path: cleanPath,
    risk_level: 'L4',
    operation,
    hint: '订单售后写操作（确认收货放款/取消/返工/评价/发起投诉/提交证据）不可逆或涉及资金，必须先向用户展示订单与影响并获得确认，然后加 --confirmed 重试。',
  });
}

function isCapabilityPublishWrite(method, cleanPath) {
  if (method === 'POST' && cleanPath === '/api/v1/capabilities') return true;
  if (method === 'PUT' && /^\/api\/v1\/capabilities\/[a-f0-9-]+$/.test(cleanPath)) return true;
  if (method === 'DELETE' && /^\/api\/v1\/capabilities\/[a-f0-9-]+$/.test(cleanPath)) return true;
  if (method === 'POST' && /^\/api\/v1\/capabilities\/[a-f0-9-]+\/(submit-review|offline|online)$/.test(cleanPath)) return true;
  return false;
}

function enforcePublishWriteConfirmation(method, cleanPath, confirmed) {
  if (!isCapabilityPublishWrite(method, cleanPath)) return;
  if (confirmed) return;

  let operation = 'create-capability';
  if (method === 'PUT') operation = 'update-capability';
  else if (method === 'DELETE') operation = 'delete-capability';
  else if (/\/submit-review$/.test(cleanPath)) operation = 'submit-review';
  else if (/\/offline$/.test(cleanPath)) operation = 'offline-capability';
  else if (/\/online$/.test(cleanPath)) operation = 'online-capability';

  failNeedConfirmation({
    reason: 'capability_publish_requires_confirm',
    path: cleanPath,
    risk_level: 'L4',
    operation,
    hint: '上架/修改/删除/提交审核/上下架自有能力前，必须先向用户展示能力标题、定价、对外暴露范围与回调地址并获得确认，然后加 --confirmed 重试。',
  });
}

function isAccountAssetPublishWrite(method, cleanPath) {
  if (method !== 'POST' && method !== 'PATCH') return false;
  if (method === 'POST' && (cleanPath === '/api/v1/digital-assets/account-inventory'
    || cleanPath === '/api/v1/digital-assets/account-shared')) return true;
  if (method === 'POST' && /^\/api\/v1\/digital-assets\/[a-f0-9-]+\/account-publish$/.test(cleanPath)) return true;
  if (method === 'POST' && /^\/api\/v1\/digital-assets\/[a-f0-9-]+\/inventory-items\/bulk$/.test(cleanPath)) return true;
  if (method === 'PATCH' && /^\/api\/v1\/digital-assets\/inventory-items\/[a-f0-9-]+$/.test(cleanPath)) return true;
  if (method === 'POST' && /^\/api\/v1\/digital-assets\/inventory-items\/[a-f0-9-]+\/toggle-disable$/.test(cleanPath)) return true;
  return false;
}

function enforceAccountAssetPublishConfirmation(method, cleanPath, confirmed) {
  if (!isAccountAssetPublishWrite(method, cleanPath)) return;
  if (confirmed) return;

  let operation = 'create-account-asset';
  if (/\/account-publish$/.test(cleanPath)) operation = 'account-publish';
  else if (/\/inventory-items\/bulk$/.test(cleanPath)) operation = 'append-inventory';
  else if (/\/toggle-disable$/.test(cleanPath)) operation = 'toggle-inventory';
  else if (method === 'PATCH') operation = 'edit-inventory';
  else if (cleanPath.endsWith('/account-shared')) operation = 'create-account-shared';

  failNeedConfirmation({
    reason: 'account_asset_publish_requires_confirm',
    path: cleanPath,
    risk_level: 'L4',
    operation,
    hint: '上架/发布账号类商品（会员账号/卡密/兑换码/共享账号）、追加库存或编辑库存前，必须先向用户展示商品标题、单价、库存数量或最大售卖次数并给出建议价，获得确认后加 --confirmed 重试。payload 明文交付内容禁止粘贴到聊天。',
  });
}

function isKnowledgeAssetWrite(method, cleanPath) {
  if (method === 'POST' && cleanPath === '/api/v1/digital-assets/quick-upload') return true;
  if (method === 'PATCH' && /^\/api\/v1\/digital-assets\/[a-f0-9-]+\/media$/.test(cleanPath)) return true;
  return false;
}

function enforceKnowledgeAssetWriteConfirmation(method, cleanPath, confirmed) {
  if (!isKnowledgeAssetWrite(method, cleanPath)) return;
  if (confirmed) return;

  const operation = /\/media$/.test(cleanPath) ? 'update-asset-media' : 'create-knowledge-asset';
  failNeedConfirmation({
    reason: 'knowledge_asset_publish_requires_confirm',
    path: cleanPath,
    risk_level: 'L4',
    operation,
    hint: '创建知识商店资产（quick-upload）或更换封面媒体前，必须先向用户展示商品标题、单价、封面图并按建议价确认定价，获得确认后加 --confirmed 重试。封面 cover_image_url 必填，不得用纯文字占位图。',
  });
}

async function fetchWalletAvailableUt(headers) {
  const { statusCode, data } = await requestWithRetry('GET', '/api/v1/wallet', headers, null);
  if (statusCode >= 400 || !data || data.code !== 0 || !data.data) return null;
  const wallet = data.data;
  const ut = wallet.ut || wallet.UT || wallet;
  return (
    parsePrice(ut.available)
    ?? parsePrice(ut.balance)
    ?? parsePrice(ut.effective_withdrawable_ut)
    ?? null
  );
}

async function ensureWalletBalance(priceUt, headers, cleanPath) {
  if (priceUt === null || priceUt <= 0) return;
  const balanceUt = await fetchWalletAvailableUt(headers);
  if (balanceUt === null) {
    failNeedConfirmation({
      reason: 'wallet_balance_unavailable_requires_confirm',
      path: cleanPath,
      price_ut: priceUt,
      hint: '无法读取钱包余额，默认按高风险处理。请先确认后加 --confirmed 重试。',
    });
  }
  if (balanceUt < priceUt) {
    failNeedConfirmation({
      reason: 'wallet_balance_insufficient',
      path: cleanPath,
      price_ut: priceUt,
      balance_ut: balanceUt,
      hint: '余额不足，请先引导用户充值或降低调用预算。',
    });
  }
}

async function estimateSmartInvokeUt(body, headers) {
  if (!body || typeof body !== 'object') return null;
  const previewBody = { ...body, mode: 'preview' };
  delete previewBody.confirm_token;
  const { statusCode, data } = await requestWithRetry(
    'POST',
    '/api/v1/capability-runtime/smart-invoke',
    probeHeaders(headers),
    previewBody,
  );
  if (statusCode >= 400) return null;
  return extractEstimatedCostUt(data);
}

// 用户已确认（--confirmed）但 body 未携带 confirm_token 时，向后端换取签名确认凭证：
// 以 mode=auto 且不带 confirm_token 调一次，后端会返回 requires_confirmation + confirmation.confirm_token。
// 该 token 由后端绑定 caller/能力/费用、短时效，回填后再次调用即可放行扣费（方案 B 两段式确认）。
async function fetchSmartInvokeConfirmToken(body, headers) {
  if (!body || typeof body !== 'object') return null;
  const probeBody = { ...body, mode: 'auto' };
  delete probeBody.confirm_token;
  delete probeBody.idempotency_key;
  const { statusCode, data } = await requestWithRetry(
    'POST',
    '/api/v1/capability-runtime/smart-invoke',
    probeHeaders(headers),
    probeBody,
  );
  if (statusCode >= 400 || !data || typeof data !== 'object') return null;
  const payload = data.data || {};
  const confirmation = payload.confirmation;
  if (!confirmation || !confirmation.confirm_token) return null;
  // 一并回带后端本次选中的能力：intent 调用时二次请求若重新排序可能选到不同能力，
  // 导致确认凭证三绑定失配。回填 capability_id/source_type 锁定同一能力，走稳定路径。
  const selected = payload.selected_capability || {};
  return {
    token: confirmation.confirm_token,
    capabilityId: selected.capability_id || null,
    sourceType: selected.source_type || null,
  };
}

// invoke 端点换取签名确认凭证：不带 confirm_token 调一次，后端在扣费/创建 run 之前
// 若需确认会直接返回 requires_confirmation + confirmation.confirm_token（不产生副作用）。
async function fetchInvokeConfirmToken(body, headers) {
  if (!body || typeof body !== 'object') return null;
  const probeBody = { ...body };
  delete probeBody.confirm_token;
  delete probeBody.idempotency_key;
  const { statusCode, data } = await requestWithRetry(
    'POST',
    '/api/v1/capability-runtime/invoke',
    probeHeaders(headers),
    probeBody,
  );
  if (statusCode >= 400 || !data || typeof data !== 'object') return null;
  const confirmation = data.data && data.data.confirmation;
  return confirmation && confirmation.confirm_token ? confirmation.confirm_token : null;
}

async function estimatePlaybookRunUt(body, headers) {
  const { statusCode, data } = await requestWithRetry(
    'POST',
    '/api/v1/playbooks/runs/estimate',
    probeHeaders(headers),
    body || {},
  );
  if (statusCode >= 400) return null;
  return extractEstimatedCostUt(data);
}

async function enforceAutoSpendGate(method, urlPath, body, headers, confirmed) {
  if (!AUTO_SPEND_GATE_ENABLED || method !== 'POST') return { isPaidPath: false, priceUt: null };
  const cleanPath = urlPath.split('?')[0];

  const isMarketplaceCall = /^\/api\/v1\/data-marketplace\/[a-f0-9-]+\/call(\/stream)?$/.test(cleanPath);
  const isAssetPurchase = /^\/api\/v1\/digital-assets\/[a-f0-9-]+\/purchase$/.test(cleanPath);
  const isSmartInvokeAuto = cleanPath === '/api/v1/capability-runtime/smart-invoke'
    && body && typeof body === 'object' && body.mode === 'auto';
  const isCapabilityInvoke = cleanPath === '/api/v1/capability-runtime/invoke';
  const isPlaybookRun = cleanPath === '/api/v1/playbooks/runs';
  const isExecutePlan = cleanPath === '/api/v1/capabilities/execute-plan'
    || cleanPath === '/api/v1/capabilities/execute-plan/stream';

  if (!isMarketplaceCall && !isAssetPurchase && !isSmartInvokeAuto && !isCapabilityInvoke && !isPlaybookRun && !isExecutePlan) return { isPaidPath: false, priceUt: null };

  const autoSpendMaxUt = loadAutoSpendMaxUt();

  // 复杂任务编排（K4-1）：execute-plan 会批量触发多个付费节点，
  // 未确认整体方案与总预算前，不得执行任何付费节点 —— 强制整体确认。
  if (isExecutePlan && !confirmed) {
    const plan = body && typeof body === 'object' ? body.plan : null;
    const totalUt = plan ? Number(plan.total_estimated_price_ut) : null;
    failNeedConfirmation({
      reason: 'execute_plan_requires_overall_confirm',
      path: cleanPath,
      total_estimated_price_ut: Number.isFinite(totalUt) ? totalUt : null,
      auto_spend_max_ut: autoSpendMaxUt,
      hint: '复杂任务编排执行前必须向用户展示完整方案、合计预算与风险并获得整体确认，确认后加 --confirmed 重试。',
    });
  }

  // 议价购买必须确认
  if (isAssetPurchase && body && body.negotiation_session_id && !confirmed) {
    failNeedConfirmation({
      reason: 'negotiated_purchase_requires_confirm',
      path: cleanPath,
      auto_spend_max_ut: autoSpendMaxUt,
      hint: '该购买包含 negotiation_session_id，必须先获得用户确认后再加 --confirmed 重试。',
    });
  }

  let priceUt = null;

  if (isSmartInvokeAuto) {
    priceUt = await estimateSmartInvokeUt(body, headers);
    const declared = Number(body.auto_spend_max_ut);
    const effective = Number.isFinite(declared) ? Math.min(declared, autoSpendMaxUt) : autoSpendMaxUt;
    if (!body.confirm_token && !confirmed) {
      body.auto_spend_max_ut = effective;
    }
    // 用户已确认但未带 confirm_token：后端付费能力需签名凭证放行，主动换取并回填，
    // 免去 Agent 手动两段式往返（方案 B）。换取失败则原样发出，由后端返回 requires_confirmation 兜底。
    if (confirmed && !body.confirm_token) {
      const fetched = await fetchSmartInvokeConfirmToken(body, headers);
      if (fetched && fetched.token) {
        body.confirm_token = fetched.token;
        // 锁定后端首次选中的能力，避免二次调用重新排序选到不同能力导致凭证失配。
        if (!body.capability_id && fetched.capabilityId) {
          body.capability_id = fetched.capabilityId;
          if (fetched.sourceType) body.source_type = fetched.sourceType;
        }
      }
    }
  } else if (isPlaybookRun) {
    priceUt = await estimatePlaybookRunUt(body, headers);
  } else if (isCapabilityInvoke && body && typeof body === 'object') {
    // capability-runtime/invoke 没有独立 quote 时，尝试调用 quote 估价。
    const quoteBody = {
      capability_id: body.capability_id,
      source_type: body.source_type,
      inputs: body.inputs || {},
    };
    const { statusCode, data } = await requestWithRetry(
      'POST',
      '/api/v1/capability-runtime/quote',
      probeHeaders(headers),
      quoteBody,
    );
    if (statusCode < 400) priceUt = extractEstimatedCostUt(data);
    // 用户已确认但未带 confirm_token：与 smart-invoke 一致，主动换取签名凭证回填放行。
    // 仅对付费能力（priceUt>0）换取——只读能力不触发后端确认，probe 会误执行，故跳过。
    if (confirmed && !body.confirm_token && Number(priceUt) > 0) {
      const token = await fetchInvokeConfirmToken(body, headers);
      if (token) body.confirm_token = token;
    }
  } else {
    priceUt = await fetchPriceUt(cleanPath, headers);
  }

  if (priceUt === null && !confirmed) {
    failNeedConfirmation({
      reason: 'price_unavailable_requires_confirm',
      path: cleanPath,
      auto_spend_max_ut: autoSpendMaxUt,
      hint: '无法读取价格，默认按高风险处理。请先确认后加 --confirmed 重试。',
    });
  }

  if (priceUt !== null) {
    await ensureWalletBalance(priceUt, headers, cleanPath);
  }

  if (priceUt !== null && priceUt > autoSpendMaxUt && !confirmed) {
    failNeedConfirmation({
      reason: 'exceed_auto_spend_max_ut',
      path: cleanPath,
      price_ut: priceUt,
      auto_spend_max_ut: autoSpendMaxUt,
      hint: '当前操作超出自动扣费阈值，请先向用户确认后再加 --confirmed 重试。',
    });
  }

  // 单日累计预判（本机软提醒）：仅对已取得单节点估价的付费路径生效；
  // execute-plan 等取不到 priceUt 的路径跳过，其花费保护由整体确认闸门与 Agent 前置呈现兜底。
  if (priceUt !== null && priceUt > 0) {
    const dailyMax = loadDailyMaxUt();
    const { spent_ut } = readDailyLedger();
    if (spent_ut + priceUt >= dailyMax && !confirmed) {
      failNeedConfirmation({
        reason: 'exceed_daily_max_ut',
        path: cleanPath,
        spent_ut,
        price_ut: priceUt,
        daily_max_ut: dailyMax,
        remaining_ut: Math.max(0, dailyMax - spent_ut),
        hint: '本次调用将使当日累计花费触顶，请先向用户说明并获得口头授权后再加 --confirmed 重试。',
      });
    }
  }

  // isPaidPath：是否参与本地记账的付费路径（命中付费路径且 priceUt > 0）；
  // priceUt=null（含 execute-plan、price_unavailable 经确认放行）恒为 false，不纳入本地记账。
  return { isPaidPath: priceUt !== null && priceUt > 0, priceUt };
}

// 请求成功后回写单日累计（本机软提醒记账）。
// 排除待确认响应（未成交）；仅付费路径（gate.isPaidPath）且本次实际扣费 > 0 才回写。
// 当前响应无可靠「实际扣费」字段（extractEstimatedCostUt 提取的均为预估价），故回退本次估价 gate.priceUt。
function recordDailySpendOnSuccess(gate, payload) {
  if (!gate || !gate.isPaidPath) return;
  const data = payload && payload.data;
  // 待确认响应（2xx）视为未成交，不计入。
  if (data && (data.requires_confirmation === true || data.confirmation)) return;
  // 优先取响应内明确的实际扣费字段，无则回退本次估价。
  const actual = data
    ? (parsePrice(data.actual_charged_ut) ?? parsePrice(data.charged_ut))
    : null;
  const charged = actual !== null ? actual : gate.priceUt;
  if (!(Number.isFinite(charged) && charged > 0)) return;
  writeDailyLedger(readDailyLedger().spent_ut + charged);
}

// 人话摘要兜底：确认响应缺 human_summary 时，用「费用 + 能力名」拼一句注入 confirmation.human_summary。
// 后端已给 human_summary 则原样透传优先。能力名取确认响应内字段，取不到只拼费用、不编造；不写风险/售后文案。
function ensureHumanSummary(payload) {
  const confirmation = payload && payload.data && payload.data.confirmation;
  if (!confirmation || typeof confirmation !== 'object') return;
  if (typeof confirmation.human_summary === 'string' && confirmation.human_summary.length > 0) return;

  const cost = parsePrice(confirmation.estimated_cost_ut);
  if (cost === null) return; // 无费用数据则拼不出可信摘要，不编造。

  // 付后余额：优先响应字段，否则由余额减费用算出。
  const balanceBefore = parsePrice(confirmation.balance_ut);
  const balanceAfter = balanceBefore !== null ? balanceBefore - cost : null;

  // 能力名仅取确认响应内真实字段，取不到则只拼费用部分，不编造。
  const capName = [confirmation.capability_title, confirmation.title, confirmation.capability_name]
    .find((v) => typeof v === 'string' && v.length > 0) || null;

  let summary = capName
    ? `你将支付 ${cost} UT 购买《${capName}》`
    : `你将支付 ${cost} UT`;
  if (balanceAfter !== null) summary += `，余额将变为 ${balanceAfter} UT`;

  confirmation.human_summary = summary;
}

// ---------------------------------------------------------------------------
// 主流程
// ---------------------------------------------------------------------------
async function main() {
  const args = parseArgs(process.argv.slice(2));
  const { method, urlPath } = args;

  if (!method || !urlPath) {
    console.error(JSON.stringify({ error: 'usage: rest_request.js <METHOD> <PATH> [options]' }));
    process.exit(1);
  }

  if (!routeAllowed(method, urlPath)) {
    console.error(JSON.stringify({ error: 'route not in allowlist', method, path: urlPath.split('?')[0] }));
    process.exit(1);
  }

  if (args.outputFile) resolveOutputFile(args.outputFile);

  const { apiKey, userId } = loadCredentials();
  // 公开只读端点（PUBLIC_ROUTES）在无凭据时仍可匿名访问；其余路由必须带凭据。
  if ((!apiKey || !userId) && !isPublicRoute(method, urlPath.split('?')[0])) {
    console.error(JSON.stringify({ error: 'missing credentials', hint: '先运行 node scripts/install.js 或 auth.js 完成授权' }));
    process.exit(1);
  }

  // 匿名请求（公开端点无凭据）不带认证头；有凭据时按原行为携带。
  const headers = {};
  if (apiKey) headers['X-Api-Key'] = apiKey;
  if (userId) headers['X-Platform-User-Id'] = userId;

  const isWrite = method !== 'GET';
  if (isWrite) {
    headers['Idempotency-Key'] = args.idempotencyKey || crypto.randomUUID();
  }

  if (args.dryRun) {
    console.log(JSON.stringify({ dry_run: true, method, path: urlPath, body: args.body }, null, 2));
    return;
  }

  const cleanPath = urlPath.split('?')[0];
  enforceExternalDataConfirmation(method, cleanPath, args.body, args.confirmed);
  enforceWalletWriteConfirmation(method, cleanPath, args.confirmed);
  enforcePublishWriteConfirmation(method, cleanPath, args.confirmed);
  enforceAccountAssetPublishConfirmation(method, cleanPath, args.confirmed);
  enforceKnowledgeAssetWriteConfirmation(method, cleanPath, args.confirmed);
  enforceOrderAftersaleConfirmation(method, cleanPath, args.confirmed);
  const gate = await enforceAutoSpendGate(method, urlPath, args.body, headers, args.confirmed);

  const fullPath = urlPath + buildQuery(args.params);
  const res = await requestWithRetry(method, fullPath, headers, args.body);
  const payload = res.data ?? { statusCode: res.statusCode };
  if (res.statusCode >= 400) {
    console.log(JSON.stringify(payload, null, 2));
    process.exit(1);
  }

  // 请求成功（非 4xx）后回写单日累计：两个成功出口（--output-file 落盘 / 默认 stdout）的公共前置位置。
  recordDailySpendOnSuccess(gate, payload);
  // 确认响应缺 human_summary 时由 skill 兜底拼「费用 + 能力名」，注入后随两个出口一并输出。
  ensureHumanSummary(payload);

  if (args.outputFile) {
    console.log(JSON.stringify(writeOutputFile(args.outputFile, payload)));
    return;
  }
  console.log(JSON.stringify(payload, null, 2));
}

main().catch((e) => {
  console.error(JSON.stringify({ error: String(e && e.message || e) }));
  process.exit(1);
});
