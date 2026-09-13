#!/usr/bin/env node
/**
 * UUMit Skill v2.7.0 — 安装、初始化与更新脚本。
 *
 * 用法:
 *   node install.js                  # 首次安装：初始化 memory + 发起授权（顺带节流检查新版本）
 *   node install.js --check          # 检查基座与已安装扩展的文件漂移/版本
 *   node install.js --update         # 校验更新结果（验收 post-state）
 *   node install.js --fill-missing   # 列出缺失的 manifest 文件
 *   node install.js --upgrade        # 检查远程新版本（不改文件，转发给 update_check.js）
 *   node install.js --upgrade --apply --yes  # 确认后下载并覆盖（保留 memory/）
 *
 * 设计约束（见设计方案 4.4）:
 *   - 不在脚本运行期自行替换自身文件，拉取由宿主/分发流程完成。
 *   - 更新需要全局视角：基座 + 各扩展 manifest 一并比对。
 *
 * 输出: stdout=JSON；stderr=诊断。
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

// 用当前 Node 解释器的绝对路径拉起子脚本，避免宿主（如 Marvis 的 shell executor）
// 子进程 PATH 中没有 `node` 时报"找不到 node"。process.execPath 始终指向正在运行的 node。
const NODE_BIN = process.execPath;

const SKILL_DIR = path.resolve(__dirname, '..');
const MEMORY_DIR = path.join(SKILL_DIR, 'memory');
const CONFIG_FILE = path.join(MEMORY_DIR, 'uumit-config.json');
const AUTH_FILE = path.join(MEMORY_DIR, 'uumit-auth.json');
// 后台任务提醒的节流/选择状态：记录上次提醒时间、用户最近选择、各任务上次启动时间。
const BG_STATE_FILE = path.join(MEMORY_DIR, 'runtime', 'background-tasks-state.json');
// 提醒节流 TTL：24h 内最多提醒一次；用户"忽略/暂不启动"后冷却更久。
const BG_REMIND_TTL_SEC = 24 * 60 * 60;
const BG_DISMISS_COOLDOWN_SEC = 7 * 24 * 60 * 60;
// 扩展与基座同级并列。优先用 UUMIT_SKILL_DIR 定位基座，再取其父目录作为扩展根；
// 未设置时回退到本脚本所在基座的父目录。
const BASE_DIR = process.env.UUMIT_SKILL_DIR
  ? path.resolve(process.env.UUMIT_SKILL_DIR)
  : SKILL_DIR;
const SKILLS_ROOT = path.resolve(BASE_DIR, '..');

function emitJson(payload) {
  process.stdout.write(JSON.stringify(payload, null, 2) + '\n');
}

function checkNodeVersion() {
  const major = parseInt(process.versions.node.split('.')[0], 10);
  return major >= 18;
}

function ensureDirs() {
  fs.mkdirSync(path.join(MEMORY_DIR, 'runtime'), { recursive: true });
  fs.mkdirSync(path.join(MEMORY_DIR, 'sessions'), { recursive: true });
}

function ensureConfig() {
  if (fs.existsSync(CONFIG_FILE)) return;
  const cfg = {
    base_url: process.env.UUMIT_BASE_URL || 'https://api.uumit.com',
    web_url: process.env.UUMIT_WEB_URL || 'https://m.uumit.com',
  };
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(cfg, null, 2));
}

function hasCredentials() {
  try {
    const a = JSON.parse(fs.readFileSync(AUTH_FILE, 'utf8'));
    return Boolean(a.api_key && a.platform_user_id);
  } catch (_) {
    return false;
  }
}

function readManifest(manifestPath) {
  return JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
}

// 文本类扩展名：校验时按「无 BOM + LF」归一化后计算哈希，与发布侧 release/lib/pack.js 的
// readForPublish 完全一致。这样无论安装端文件是 CRLF 还是 LF、是否带 BOM，都能与
// manifest.files.sha256 匹配——跨平台容错，避免行尾差异导致 --check 全部失配。
const TEXT_EXT = new Set(['.js', '.md', '.json', '.txt', '.yml', '.yaml', '.toml', '.sh', '.bat', '.ps1', '.xml', '.html', '.css', '.csv']);

function isTextFile(rel) {
  return TEXT_EXT.has(path.extname(rel).toLowerCase());
}

function sha256(filePath, rel) {
  let buf = fs.readFileSync(filePath);
  if (isTextFile(rel)) {
    if (buf.length >= 3 && buf[0] === 0xef && buf[1] === 0xbb && buf[2] === 0xbf) buf = buf.subarray(3);
    buf = Buffer.from(buf.toString('utf8').replace(/\r\n/g, '\n').replace(/\r/g, '\n'), 'utf8');
  }
  return crypto.createHash('sha256').update(buf).digest('hex');
}

/**
 * 比对单个 Skill 的本地文件与其 manifest.files 声明。
 * 返回 { name, version, missing[], missing_optional[], mismatched[] }。
 *   missing：required:true 文件缺失——硬缺失，判定 drift、阻断安装完整性。
 *   missing_optional：required:false 文件缺失——软缺失（如宿主分发漏拉能力脚本），
 *     不算 drift 但必须显式告警，避免"声明了却拉不到"的缺口被静默放过。
 */
function inspectSkill(skillDir) {
  const manifestPath = path.join(skillDir, 'manifest.json');
  const manifest = readManifest(manifestPath);
  const files = manifest.files || {};
  const missing = [];
  const missing_optional = [];
  const mismatched = [];
  for (const [rel, meta] of Object.entries(files)) {
    const fp = path.join(skillDir, rel);
    if (!fs.existsSync(fp)) {
      if (meta && meta.required !== false) missing.push(rel);
      else missing_optional.push(rel);
      continue;
    }
    if (meta && meta.sha256) {
      if (sha256(fp, rel) !== meta.sha256) mismatched.push(rel);
    }
  }
  return { name: manifest.name, version: manifest.version, missing, missing_optional, mismatched };
}

/**
 * 发现并加载已安装扩展（与基座同级、声明 requires.base_skill=uumit-agent）。
 */
function discoverExtensions() {
  const exts = [];
  let entries = [];
  try {
    entries = fs.readdirSync(SKILLS_ROOT, { withFileTypes: true });
  } catch (_) {
    return exts;
  }
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const dir = path.join(SKILLS_ROOT, entry.name);
    if (path.resolve(dir) === path.resolve(BASE_DIR)) continue; // 跳过基座自身
    const mf = path.join(dir, 'manifest.json');
    if (!fs.existsSync(mf)) continue;
    let manifest;
    try {
      manifest = readManifest(mf);
    } catch (_) {
      continue;
    }
    const requires = manifest.requires || {};
    if (requires.base_skill !== 'uumit-agent') continue;
    exts.push({ dir, manifest });
  }
  return exts;
}

function collectTargets() {
  const targets = [{ role: 'base', dir: SKILL_DIR }];
  for (const ext of discoverExtensions()) {
    targets.push({ role: 'extension', dir: ext.dir });
  }
  return targets;
}

// ---------------------------------------------------------------------------
// 子命令
// ---------------------------------------------------------------------------
function runCheck() {
  const report = [];
  let drift = false;
  let hasOptionalMissing = false;
  for (const t of collectTargets()) {
    const info = inspectSkill(t.dir);
    if (info.missing.length || info.mismatched.length) drift = true;
    if (info.missing_optional.length) hasOptionalMissing = true;
    report.push({ role: t.role, ...info });
  }
  // drift 只由硬缺失/漂移决定（保持"文件完整"语义）；但可选文件缺失（如宿主分发
  // 漏拉能力脚本）必须显式告警——否则 --check 会误报"完整"，缺口长期潜伏。
  let next;
  if (drift) {
    next = '存在文件缺失或漂移。运行 node install.js --fill-missing 查看缺失项，或由宿主分发流程重新拉取后再 node install.js --update。';
  } else if (hasOptionalMissing) {
    next = '必需文件完整，但存在可选文件缺失（见各 skill 的 missing_optional，通常是宿主分发/安装时漏拉了 required:false 的能力脚本）。相关功能会不可用，请由宿主分发流程按 manifest.distribution 重新拉取（fetch zip 或 manifest_files）补齐后再 node install.js --update。';
  } else {
    next = '所有已安装 Skill 文件完整且与 manifest 一致。';
  }
  emitJson({
    ok: !drift,
    stage: 'check',
    drift,
    optional_missing: hasOptionalMissing,
    skills: report,
    next,
  });
}

function runFillMissing() {
  const missingBySkill = [];
  for (const t of collectTargets()) {
    const info = inspectSkill(t.dir);
    // 同时列出硬缺失（required:true）与可选缺失（required:false）——后者常因宿主
    // 分发漏拉能力脚本产生，过去被静默忽略，导致缺口在此看不见。
    if (info.missing.length || info.missing_optional.length) {
      missingBySkill.push({
        role: t.role,
        name: info.name,
        missing: info.missing,
        missing_optional: info.missing_optional,
      });
    }
  }
  const ok = missingBySkill.length === 0;
  emitJson({
    ok,
    stage: 'fill-missing',
    missing: missingBySkill,
    next: ok
      ? '无缺失文件。'
      : '缺失文件（含可选的 missing_optional）需由宿主/分发流程按 manifest.distribution 重新拉取（fetch zip 或 manifest_files），脚本不自行替换自身文件。',
  });
  if (!ok) process.exitCode = 1;
}

function runUpdate() {
  // 不自行拉取文件；执行更新后用 validate_skill.js 验收 post-state。
  let verify;
  try {
    const out = execFileSync(NODE_BIN, [path.join(__dirname, 'validate_skill.js')], { encoding: 'utf8' });
    verify = JSON.parse(out);
  } catch (e) {
    let parsed = null;
    try { parsed = JSON.parse(String(e.stdout || e.stderr || '')); } catch (_) {}
    verify = parsed || { ok: false, errors: [String(e && e.message || e)] };
  }
  const ok = Boolean(verify && verify.ok);
  emitJson({
    ok,
    stage: 'update',
    verify,
    next: ok
      ? '更新已通过校验。基座与扩展共享 memory/ 已按 manifest.update.preserve 保留。'
      : '校验未通过，请按 verify.errors 修复后重试 node install.js --update。',
  });
  if (!ok) process.exitCode = 1;
}

/**
 * 静默检查远程新版本：转发给 update_check.js（每次真实联网，无节流缓存）。
 * 仅返回精简结论供 install 输出参考，失败返回 null，绝不阻断主流程。
 */
function checkUpdate() {
  try {
    const out = execFileSync(NODE_BIN, [path.join(__dirname, 'update_check.js')], {
      encoding: 'utf8',
      timeout: 20000,
    });
    const r = JSON.parse(out);
    if (r.check_failed) return null;
    return { has_update: Boolean(r.has_update), current_version: r.current_version, latest_version: r.latest_version };
  } catch (_) {
    return null;
  }
}

/** --upgrade：把更新检查/应用透传给 update_check.js（不改文件，除非 --apply --yes）。 */
function runUpgrade(args) {
  const passthrough = [];
  if (args.includes('--apply')) passthrough.push('--apply');
  if (args.includes('--yes')) passthrough.push('--yes');
  try {
    const out = execFileSync(NODE_BIN, [path.join(__dirname, 'update_check.js'), ...passthrough], {
      encoding: 'utf8',
      timeout: 120000,
    });
    process.stdout.write(out.endsWith('\n') ? out : out + '\n');
  } catch (e) {
    let parsed = null;
    try { parsed = JSON.parse(String(e.stdout || e.stderr || '')); } catch (_) {}
    emitJson(parsed || { ok: false, stage: 'update-check', error: String(e && e.message || e) });
    process.exitCode = 1;
  }
}

/**
 * 把 scheduled 任务的相对 command（如 "node ../uumit-cruise/scripts/cruise.js status"）
 * 解析为绝对路径命令，供 A/B 档宿主原样登记，跨平台可跑。Agent 禁止改写。
 * 相对路径以 skill 根目录（SKILL_DIR）为基准解析——command 约定在 skill 根目录下执行，
 * 故 "scripts/xxx" 与 "../uumit-xxx/..." 两种写法均以此为基准（与 __dirname/scripts 区分）。
 */
function resolveCommandAbs(relCommand) {
  if (!relCommand) return null;
  const m = relCommand.match(/^node\s+(.+)$/);
  if (!m) return relCommand;
  const scriptRel = m[1].trim();
  const scriptAbs = path.resolve(SKILL_DIR, scriptRel.split(/\s+/)[0]);
  const extraArgs = scriptRel.split(/\s+/).slice(1).join(' ');
  const cmd = `"${NODE_BIN}" "${scriptAbs}"`;
  return extraArgs ? `${cmd} ${extraArgs}` : cmd;
}

/**
 * 由官方推荐频率生成宿主可直接登记的标准 5 字段 cron 表达式（Agent 禁止再换算）。
 * 始终输出（不再按宿主档位预判拦截）——是否真能登记由 Agent 向宿主原生自动化系统实际尝试决定。
 * 仅支持"整除小时/分钟"的规整频率（14400s=4h、10800s=3h、3600s=1h、300s=5min 等），
 * 覆盖当前 cruise_status / capability_index_refresh / update_check_refresh / realtime_poll 等任务。
 */
function buildSchedule(intervalSec) {
  if (!intervalSec) return null;
  let cron;
  if (intervalSec % 3600 === 0) {
    const hours = intervalSec / 3600;
    // 每小时用规范表达式 `0 * * * *`（而非 `0 */1 * * *`）；每 N 小时用 `0 */N * * *`。
    cron = hours === 1 ? '0 * * * *' : `0 */${hours} * * *`;
  } else if (intervalSec % 60 === 0) {
    cron = `*/${intervalSec / 60} * * * *`;
  } else {
    cron = `*/${Math.max(1, Math.round(intervalSec / 60))} * * * *`;
  }
  const label = intervalSec % 3600 === 0
    ? (intervalSec / 3600 === 1 ? '每小时' : `每 ${intervalSec / 3600} 小时`)
    : `每 ${Math.round(intervalSec / 60)} 分钟`;
  return { cron, interval_seconds: intervalSec, label };
}

/**
 * 构建"安装后可启动的后台任务"清单，供宿主 Agent 提示用户并按其选择拉起。
 * 设计：脚本只描述任务、不自行 spawn 常驻进程（避免 install 退出后产生孤儿进程、避免越权）。
 * 仅列出"对应扩展已安装"的任务。
 */
function buildBackgroundTasks() {
  const installedExtNames = new Set(discoverExtensions().map((e) => e.manifest && e.manifest.name));
  const hasRealtime = installedExtNames.has('uumit-realtime');
  const hasCruise = installedExtNames.has('uumit-cruise');

  const resident = [];
  const on_demand_features = [];
  if (hasRealtime) {
    on_demand_features.push({
      id: 'runtime_connect',
      display_name: '实时任务接单',
      user_summary: '套件支持在线实时接收平台派发的智能体任务、Agent 消息与状态变化。需要时请明确说“启动实时任务接单”；它只在当前客户端会话存续期间运行，退出后停止。',
      activation: 'explicit_user_request_only',
      included_in_onboarding_offer: false,
      included_in_start_all: false,
      command: 'node ../uumit-realtime/scripts/runtime_connect.js',
      success_signal: 'connection.open',
      note: '这是按需会话功能，不是首装后台任务。首装不得展示或提及，也不参与“全开”；只有用户明确要求启动时才运行。必须收到 connection.open 后才可说已启动；进程无法拉起、认证失败或未收到 connection.open 时，按实际结果说明，不能仅凭宿主能力预判为开启失败。',
    });
  }

  // B 类：需周期调度（脚本自身一次性，由宿主定时器周期触发）。
  // scheduled：参与首装征询的周期任务（仅 Agent 据 suggested_plan 向用户征询这些）；
  // scheduled_lazy：不参与首装征询/日常兜底提醒的周期任务（prompt_on_install=false），
  // 首装及常规对话不得展示、不得提及，仅用户主动明确要求开启时才据其登记（见 agent_hint）。
  const scheduled = [];
  const scheduled_lazy = [];
  if (hasCruise) {
    scheduled_lazy.push({
      id: 'cruise_status',
      display_name: '账户巡航对账',
      desc: '巡航对账：账户 / 钱包 / 任务快照 diff',
      command: 'node ../uumit-cruise/scripts/cruise.js status',
      kind: 'scheduled',
      writes: false,
      side_effects: [],
      // 不参与首装征询与日常兜底提醒：仅在用户主动要求时开启（见 agent_hint 首装征询范围）。
      prompt_on_install: false,
      recommended_interval: { seconds: 14400, label: '每 4 小时' },
      user_summary: '每 4 小时核对账户余额/钱包/任务有无异常。纯只读对账，不改动任何文件。',
      note: '只读对账（仅写本地状态）；周期触发须向宿主原生自动化系统实际登记（频率用 schedule.cron、命令用 command_abs，照抄勿改），宿主确无自动化能力才告知手动',
    });
    scheduled.push({
      id: 'market_auto_bid',
      display_name: '任务市场自动接单',
      desc: '每小时拉任务市场，对 AI 能独立完成的线上任务自动申请接单并交付完成',
      // 【单一调度目标】command 指向 market-run（统一驱动入口），而非分立的 market/apply/deliver——
      // 消除「command 误导调度器直调裸 market、requires_agent_session 又要求别这么调」的结构性歧义：
      // market-run 是唯一可登记/可复用/可审计的入口，一次性产出本轮待 Agent 决策工单（候选+待交付订单）。
      command: 'node ../uumit-cruise/scripts/cruise.js market-run',
      kind: 'scheduled',
      // 写操作 + 对外承诺交付（建 skill / 申请 / 提交交付物），但均不在基座确认闸门覆盖内、无需 --confirmed。
      writes: true,
      side_effects: [],
      recommended_interval: { seconds: 3600, label: '每小时' },
      // 自动替用户接单/交付属"须让用户知情"的结果，成功也放开回显（同 capability_index_refresh / update_check_refresh）。
      present_on_success: true,
      // 【半自动闭环·须 Agent 驱动】与其它 scheduled 任务不同：market-run 只产出工单（候选+待交付订单），
      // 真正的接单（market-apply）/交付（market-deliver）须 Agent 读工单、逐单判定并生成 skill 字段/交付内容后调用。
      // 因此定时入口须能「到点唤起 Agent 会话并投喂 driver_prompt 让其驱动 market-run→逐单回调 的整轮闭环」；
      // 宿主不支持定时唤起 Agent 会话时，不得只登记 command_abs 裸跑冒充自动接单，须如实降级告知（见 note / agent_hint）。
      requires_agent_session: true,
      driver_prompt: '执行一轮任务市场自动接单闭环：①运行 `node ../uumit-cruise/scripts/cruise.js market-run` 产出本轮工单（候选+待交付订单）；'
        + '②逐条读 candidates 保守判定「本 Agent 能否独立完成」，拿不准就跳过（宁可漏接不错接）；'
        + '③对可做任务生成对口 skill 语义字段，运行 `cruise.js market-apply` 建/复用 skill 并申请接单；'
        + '④对 market-run 已产出的 pending_orders 每个订单：initial 按任务要求生成交付内容；rework 必须读取 rework_reason 并针对发布人的返工意见修正后重新交付；'
        + '运行 `cruise.js market-deliver --order-id <id> --files <json>` 上传+提交（触内容安全被拦则重生成 --retry 重交一次）；'
        + '⑤运行 `cruise.js market-report` 汇总本轮结果并如实向用户汇报（只读 last-run-market.json，禁编造）。',
      user_summary: '每小时自动查询任务市场，对 AI 能独立完成的任务自动申请接单并交付完成；接单/交付结果会在任务窗口向你汇报。仅接无需人工介入的线上任务。',
      note: '【半自动闭环·须 Agent 驱动，登记 market-run 单一入口、不能登记裸 market】cruise.js market-run 是唯一可登记/可审计的驱动入口，一次性产出本轮工单（候选+待交付订单）；真正的接单/交付须 Agent 读工单逐单判定后调 market-apply / market-deliver 完成——若把 command_abs（market-run）当普通裸命令直接登记进 cron 而无 Agent 在场消费其工单，每轮只会产出工单、永不接单交付（承诺全自动即失真、假上线）。因此定时任务须登记为「到点唤起 Agent 会话并投喂本任务 driver_prompt，由 Agent 驱动 market-run→逐单回调 的整轮闭环」：宿主原生支持定时唤起 Agent 会话/带 prompt 定时任务的（如 Scheduled/Managed Agent），把 driver_prompt 作为任务内容、频率用 schedule.cron；宿主仅有裸命令定时器的，登记「非交互/headless 模式拉起本 Agent 并传入 driver_prompt」的入口；宿主完全不支持定时唤起 Agent 的，不登记裸命令冒充，须如实告知「本客户端无法无人值守自动接单，需要时可发指令由我手动跑一轮」。经基座 rest_request.js 调 tasks/skills/orders/deliverables 均无需 --confirmed；须放开成功回显——每轮把接单/交付结果输出 stdout 呈现给用户；结果以 memory/runtime/last-run-market.json 为唯一事实来源（可用 cruise.js market-report 汇总），Agent 只读转述禁编造。',
    });
  }
  scheduled_lazy.push({
    id: 'realtime_poll',
    display_name: '智能体任务自动接单',
    desc: '定时轮询补拉：到点拉取平台派给你的智能体任务 / Agent 消息 / 状态变更（一次性 GET，服务端记账续拉）',
    command: 'node scripts/rest_request.js GET /api/v1/agent-runtime/pending',
    kind: 'scheduled',
    writes: false,
    side_effects: [],
    // 不参与首装征询与日常兜底提醒：仅在用户主动要求时开启（见 agent_hint 首装征询范围）。
    prompt_on_install: false,
    recommended_interval: { seconds: 3600, label: '每小时' },
    // 拉到的新智能体任务属"需让用户看到"的结果，即便任务成功也须放开回显。
    present_on_success: true,
    user_summary: '每小时接收一次平台定向派给你的任务和消息，不浏览公开任务市场，也不会主动申请任务。与「平台派单实时接收」互补：本项每小时查看一次，实时接收则需你主动启动并保持客户端在线。',
    note: '一次性脚本（走基座 rest_request.js GET /api/v1/agent-runtime/pending，服务端读写游标 agent_poll_cursor 一次拉全、客户端零编排）；默认每小时运行，周期触发须向宿主原生自动化系统实际登记（频率用 schedule.cron、命令用 command_abs，照抄勿改）；登记失败则不启用、不空登记并如实告知可手动触发；拉到新智能体任务时放开成功回显呈现给用户。',
  });

  scheduled_lazy.push({
    id: 'capability_index_refresh',
    display_name: '能力目录刷新',
    desc: '本地能力索引刷新：均衡拉取平台各来源代表能力，保持本地粗筛名录新鲜',
    command: 'node scripts/capability_index.js --refresh',
    kind: 'scheduled',
    writes: false,
    side_effects: [],
    // 不参与首装征询与日常兜底提醒：仅在用户主动要求时开启（见 agent_hint 首装征询范围）。
    prompt_on_install: false,
    recommended_interval: { seconds: 3600, label: '每小时' },
    user_summary: '每小时刷新一份“平台大概有哪些能力”的本地目录，用于更快判断需求是否有对应能力，并顺带告诉你平台能力有没有上新/下架；它只是粗筛名录、不是可直接调用的能力卡片，关掉不影响临时发现最新能力，只是发现效率略降。每次刷新会在任务窗口给你一份平台能力摘要（有哪些品类、各多少、列举平台上的部分能力、共多少条），并附本地缓存名录的文件位置（仅每类部分代表条目、非平台全部能力）；若本轮有能力上新/下架，还会额外告诉你新增/下架了哪些。',
    note: '仅写本地索引文件；承接原能力变更通知职责——每次 --refresh 覆写索引前先与旧索引对比算出本轮 added/removed，仅当有上新/下架才按打扰克制提示用户（无变更不打扰）；每次 --refresh 在 stdout 附平台能力摘要（品类分布/能力示例（默认 10 条、每次随机不同）/总数/本地缓存目录地址 catalog_hint，须澄清仅每类部分代表条目、非全部能力），有变更时附变更段 change_note，供任务窗口即时展示、不落额外文件、成功时照常呈现给用户；呈现示例时用“平台上的部分能力，例如：”自然措辞，勿用“随机代表能力/随机抽取/样本”字样；周期触发须向宿主原生自动化系统实际登记（频率用 schedule.cron、命令用 command_abs，照抄勿改），宿主确无自动化能力才告知手动',
  });

  scheduled.push({
    id: 'update_check_refresh',
    display_name: '套件更新检查',
    desc: '检查 UUMit 套件是否有新版本；开启自动更新时到点自动应用（保留本地数据）',
    command: 'node scripts/update_check.js --refresh',
    kind: 'scheduled',
    writes: false,
    // 自动更新开启时会下载并覆盖本地脚本，属安全敏感副作用，须向用户点明。
    side_effects: ['auto_update'],
    recommended_interval: { seconds: 10800, label: '每 3 小时' },
    // 有新版/已自动更新属"需让用户看到"的结果，即便任务成功也须放开回显（同 capability_index_refresh）。
    present_on_success: true,
    user_summary: '每 3 小时检查一次 UUMit 套件有没有新版本；若你开启了自动更新，有新版会自动下载更新（自动执行发布源脚本，不信任可关闭自动更新），本地数据始终保留。默认只提示、不自动改文件。',
    note: '一次性脚本，周期触发须向宿主原生自动化系统实际登记（频率用 schedule.cron、命令用 command_abs，照抄勿改）；每次真实联网查远程版本（已移除 TTL 节流缓存）；auto_update.enabled=true 时自动应用更新，否则仅检查提示；结果以 memory/runtime/last-run-update.json 为唯一事实来源，Agent 只读转述禁编造；成功即静默会漏掉“有新版/已更新”提示，故须为本任务放开成功回显（登记时开启宿主“成功也回显 stdout”）',
  });

  // 为每个 scheduled 任务补齐登记所需字段（D02 第五轮修正：移除 host_tier 预判门禁）：
  //   schedule：官方给定、Agent 照抄的标准 cron 表达式（始终输出）；
  //   command_abs：绝对路径命令，跨平台可跑、Agent 禁止改写。
  // 不再由 install.js 预判宿主档位并把 schedule/command_abs 置空——是否真能登记，
  // 由 Agent 向宿主原生自动化系统实际尝试后决定：登记成功才说"已开启"，
  // 宿主确实无自动化能力（登记接口不存在/失败）才如实告知改手动。
  //
  // 【任务分型·结构级防误用（2026-07-10 次选方案落地）】把 scheduled 任务分两型：
  //   command_task      ：可直接登记的普通脚本任务 —— 补 command_abs，宿主定时器裸调即完整生效。
  //   agent_session_task：必须由「宿主唤起的 Agent 会话」执行的任务（如 market_auto_bid：脚本只产工单，
  //                       接单/交付须 Agent 判定+生成后逐单回调）—— 【故意不输出 command_abs】，改输出 launch_spec，
  //                       从结构上杜绝「只认 command_abs 的宿主/桥接层/维护者」把它当普通脚本裸登记进 cron
  //                       （裸调只会空转产工单、永不接单交付，即假上线）。是否 agent_session_task 由 task.requires_agent_session 决定。
  // scheduled 与 scheduled_lazy 均补齐登记字段：用户同意开启（或主动要求开启）时 Agent 才能据此登记。
  const allScheduled = [...scheduled, ...scheduled_lazy];
  for (const task of allScheduled) {
    const intervalSec = task.recommended_interval && task.recommended_interval.seconds;
    task.schedule = buildSchedule(intervalSec);

    if (task.requires_agent_session) {
      task.task_type = 'agent_session_task';
      // 故意不给可裸登记的 command_abs：改用 launch_spec 描述「须唤起 Agent 会话并投喂 driver_prompt」的登记形态。
      // inner_command_abs 仅供 Agent 会话内部驱动时使用（是闭环第一步），不是可交给定时器裸跑的登记命令。
      task.launch_spec = {
        exec: 'agent_session',
        driver_prompt: task.driver_prompt || null,
        inner_command_abs: resolveCommandAbs(task.command),
        note: '本任务必须由宿主唤起的 Agent 会话执行：登记时不要把任何命令当普通定时脚本裸登记；'
          + '应登记「到点唤起带 driver_prompt 的 Agent 会话」（宿主原生支持则用其 Scheduled/Managed Agent；'
          + '仅有裸命令定时器且提供 headless 唤起入口则登记该入口传入 driver_prompt；两者皆无则不登记、如实告知可手动触发）。',
      };
    } else {
      task.task_type = 'command_task';
      task.command_abs = resolveCommandAbs(task.command);
    }
  }

  // 推荐开启组合：首装（bg-state 无任何 launched/disabled 记录）时 Agent 据此**征询用户是否开启**
  // （不再自动开启）。仅收录当前实际存在的任务 id。
  const presentIds = new Set([...resident, ...scheduled].map((t) => t.id));
  const suggested_plan = ['market_auto_bid', 'update_check_refresh'].filter((id) =>
    presentIds.has(id),
  );

  // 互斥组：每个子数组内的任务「只能同时启用一个」，供 Agent/宿主校验避免重复拉取。当前无互斥项。
  const mutually_exclusive = [];

  const onboarding_offer = {
    title: '后台能力：请确认是否开启',
    display_before_question: [
      '可选择开启以下 2 项后台能力，默认都不会开启：',
      '1. 套件更新检查（每 3 小时）：检查 UUMit 套件是否有新版本；默认只提示、不修改文件。只有你另行开启自动更新后，才会自动下载更新，本地数据始终保留。',
      '2. 任务市场自动接单（每小时）：自动查询任务市场，只对 AI 能独立完成的线上任务申请接单并交付，接单与交付结果会向你汇报。这项会产生实际接单和交付操作。',
      '这些能力需要当前客户端支持定时运行才能真正无人值守；我会在你确认后尝试登记，登记失败会如实告诉你。',
    ].join('\n'),
    question: '请先阅读完整说明，再选择是否开启：\n\n1. 套件更新检查（每 3 小时）：检查 UUMit 套件是否有新版本；默认只提示、不修改文件。只有你另行开启自动更新后，才会自动下载更新，本地数据始终保留。\n\n2. 任务市场自动接单（每小时）：自动查询任务市场，只对 AI 能独立完成的线上任务申请接单并交付，接单与交付结果会向你汇报。这项会产生实际接单与交付操作。\n\n这些能力需要当前客户端支持定时运行才能真正无人值守；我会在你确认后尝试登记，登记失败会如实告诉你。\n\n你希望开启哪些？',
    choices: [
      { label: '全部开启：更新检查 + 任务市场自动接单（推荐）', task_ids: ['update_check_refresh', 'market_auto_bid'] },
      { label: '只开套件更新检查（每 3 小时检查新版，默认只提示）', task_ids: ['update_check_refresh'] },
      { label: '只开任务市场自动接单（每小时申请并交付任务）', task_ids: ['market_auto_bid'] },
      { label: '暂不开启', task_ids: [] },
    ],
    presentation_order: ['display_before_question', 'question', 'choices'],
  };

  return {
    suggested_plan,
    onboarding_offer,
    mutually_exclusive,
    resident,
    scheduled,
    // 不参与首装征询/兜底提醒的周期任务：首装及常规对话不得展示、不得提及、不得主动介绍；
    // 仅用户主动明确要求开启时才据其介绍并尝试登记（agent_hint 首装征询范围段已约束）。
    scheduled_lazy,
    builtin: [],
    on_demand_features,
    agent_hint:
      '【首装·征询式开启（不自动开启）】首次安装（bg-state 无任何 launched/disabled 记录）授权完成后：不要自动开启任何后台能力；on_demand_features 中的实时任务接单为静默按需功能，首装及任何常规对话都不得展示、不得提及、不得主动介绍（含“关于实时接单”这类说明），仅当用户明确说“启动实时任务接单”时才据 on_demand_features 处理。' +
      '【首装征询展示顺序·硬性要求】发起选择前，必须先把 onboarding_offer.display_before_question 完整展示给用户，让用户明确看到每项的中文名称、频率、作用与风险；然后逐字使用 onboarding_offer.question 发起选择，并逐字使用 onboarding_offer.choices 的 label 提供选项。不得自行改写、删减、折叠、重排、替换推荐项，也不得根据用户画像或历史偏好代替用户做判断；不得只显示“是否开启后台能力”及按钮，不得用“官方建议了若干项”代替任务说明。即使宿主只能显示一个选择控件，也必须把 onboarding_offer.question 的完整内容逐字放进问题正文。' +
      '【首装征询范围·只谈 suggested_plan 中列出的任务】征询只针对 suggested_plan 数组里列出的任务（用其 display_name 与 user_summary 一次性介绍其作用，不逐项分开问）；scheduled_lazy 中的任务（prompt_on_install=false 者：账户巡航对账、智能体任务自动接单、能力目录刷新）【不得展示、不得提及、不得主动介绍】——不得把它们列进征询清单、不得用 user_summary 描述它们、不得说“还有以下可开启”之类引出它们，仅当用户主动明确要求开启时才据 scheduled_lazy 数据介绍并尝试开启。' +
      '直接用大白话向用户【整体征询一次】“是否为你开启这套定时后台能力”（推荐组合见 suggested_plan，用各项 user_summary 一次性介绍其作用，不逐项分开问）；' +
      '【征询时必须先做预期澄清】明确告诉用户“这些后台能力需要本客户端支持到点自动运行才能真正无人值守；我会尝试为你开启，若本客户端支持则开启成功、若不支持则可能开启失败，届时我会如实告诉你并改为可手动触发”，给用户一个心理预期，不要把成功当作必然。' +
      '【征得同意后由你自行尝试开启】用户同意后，由你【向本客户端的原生自动化/定时系统实际尝试登记】各任务（登记方式见下“周期任务落地”）；' +
      '尝试登记成功（宿主确认已建任务）才用 install.js --background-launched <id...> 记状态，并如实告知“已为你开启”；' +
      '【尝试失败如实告知+可手动】若本客户端没有可用的自动化/定时系统、或登记未成功，不得谎称“已开启”，须如实告知用户“当前客户端无法自动运行，未能为你开启无人值守，需要时可发指令由我手动触发一次”。' +
      '其中 side_effects 含 auto_update 的项（如 update_check_refresh）介绍时必须明确点明“会自动更新套件、如不信任发布源可关闭”，不得当作纯只读一笔带过。' +
      '若用户不同意开启，用 install.js --background-dismissed 记录进入冷却，之后需要时再提醒。' +
      '【呈现纪律·适用于全部对话回合（含首装、排障、追问）】面向用户展示时：条目名用各任务的 display_name（中文名）、说明用 user_summary；' +
      '任何回合都禁止向用户暴露内部 id（如 cruise_status / market_auto_bid）、命令行 / command_abs、cron / RRULE 表达式、文件路径、--background-* 与 market-run / market / market-apply / market-deliver / market-report 等子命令、--confirmed、suggested_plan / schedule / side_effects 等字段名，以及 SSE / 轮询 / 索引 / 技能 skill / 订单 order / 交付物 deliverable 等技术术语；排障答疑也一律用中文名 + 自然语言。' +
      '关闭引导用自然语言（如“告诉我关闭「账户巡航对账」即可”），由你把用户说的中文名映射回对应 id 再执行 --background-disabled。' +
      '【周期任务落地·先按 task_type 分流，再登记】scheduled 与 scheduled_lazy 中的任务分两型，登记方式不同，务必先看每个任务的 task_type：' +
      '① task_type=command_task（如 cruise_status / realtime_poll / capability_index_refresh / update_check_refresh）：普通一次性脚本，带 command_abs（绝对路径命令），把 command_abs 当定时命令原样登记即可。' +
      '② task_type=agent_session_task（如 market_auto_bid）：【故意没有 command_abs】——因为它必须由「宿主唤起的 Agent 会话」执行（脚本只产工单、接单/交付须 Agent 判定+生成后逐单回调），绝不能把它当普通脚本裸登记进 cron/plans.json/crontab/schtasks（裸跑只会空转产工单、永不接单交付＝假上线）。它带的是 launch_spec（含 driver_prompt 与登记形态说明，其中 inner_command_abs 只是 Agent 会话内部驱动的第一步、不是可交给定时器裸跑的登记命令）：须按 launch_spec.note 登记「到点唤起带 driver_prompt 的 Agent 会话」——宿主原生支持定时唤起 Agent 会话/带 prompt 定时任务的用其原生入口、把 driver_prompt 作为任务内容、频率用 schedule.cron；仅有裸命令定时器但提供 headless/非交互唤起入口的登记该入口并传入 driver_prompt；两者皆无则不登记、如实告知「本客户端无法无人值守自动接单，需要时可发指令由我手动跑一轮」。' +
      '各 command_task 已带 schedule（官方 cron 表达式）、command_abs（绝对路径命令）——' +
      '【铁律】登记 command_task 时频率必须原样用 schedule.cron、命令必须原样用 command_abs，严禁自行把秒数/间隔翻译成 cron/RRULE，严禁改写或拼接路径。' +
      '【铁律·登记后逐字回读校对】每登记完一个任务，必须回读宿主实建的定时表达式（cron/RRULE/间隔），与本任务的 schedule.cron 逐字比对；' +
      '常见误译务必自查：`0 */6 * * *`（每 6 小时）不得写成 `0 0 * * *`（每天 0 点）、`0 * * * *`（每小时）不得写成每天某点——凡宿主把“每 N 小时”落成“每天某点”或改了周期，一律判为错误并就地改正到与 schedule.cron 完全一致；改不动则删除该任务并如实告知未能按官方频率登记，不得将就。' +
      '【铁律·所述即所建】向用户口述的频率（如“每 6 小时”）必须与宿主实建任务的真实频率完全一致；不得出现“对话说每 6 小时、面板却是每天 0 点”这类自相矛盾——以 schedule 的 label 为准，且必须先完成上述回读校对确保实建值与之相符，再据此向用户表述。' +
      '【关键·必须真实落到宿主】不要只用 --background-launched 记个本地状态就说“已开启”——那只是 UUMit 本地标记、不会让任务真正跑起来。必须先探明本客户端有没有原生自动化/定时系统并向其实际建任务：' +
      '如 Claude Code 用 CronCreate、Cline 用 cline schedule create、WorkBuddy 写其 plans.json（cron + command）、OpenClaw/LobsterAI 写 jobs.json；若本客户端本身无内置调度但有可被系统定时拉起的非交互模式，则登记系统级定时——Linux/macOS 写 crontab 条目、Windows 用 schtasks /Create，频率用 schedule.cron、命令用 command_abs，引导用户确认后登记。' +
      '只有在宿主原生系统里确认建成任务后，才用 --background-launched 记状态并告知“已开启”。' +
      '【能力目录刷新·成功也要展示摘要，勿套用“成功即静默”】capability_index_refresh 每次运行会在脚本输出（stdout）里附一份“平台能力摘要”（有哪些品类、各多少、平台上有哪些能力示例、共多少条，并附本地缓存目录文件位置 catalog_hint/catalog_path——须每次原样附给用户作为“查看本地已缓存能力”的指引，且须澄清这只是每类部分代表条目的缓存名录、非平台全部能力）。登记该任务时，若宿主默认对成功任务保持静默/不回显输出，须为这一任务放开：让其到点运行成功后把该摘要呈现到任务窗口给用户看（如宿主支持“成功也汇报/回显 stdout”的选项则开启；写 plans.json / jobs.json / crontab 等时，命令仍原样用 command_abs，仅调整“成功是否呈现输出”的策略）。若宿主无法配置成功回显，如实告知用户“本客户端周期任务成功时不展示输出，可发指令由我手动触发一次刷新来查看平台能力摘要”。此项针对能力目录刷新、套件更新检查、任务市场自动接单三类任务（其余周期任务沿用宿主默认呈现策略）。' +
      '【任务市场自动接单·agent_session_task，须登记 Agent 会话驱动、无 command_abs 可裸登记】market_auto_bid 的 task_type=agent_session_task 且【故意不带 command_abs】——它与 command_task 不同：脚本只产工单（候选+待交付订单），真正的接单/交付须 Agent 读工单、逐单判定并生成 skill 字段/交付内容后调 market-apply / market-deliver 完成。' +
      '【铁律】它没有可交给定时器裸跑的登记命令；launch_spec.inner_command_abs 只是 Agent 会话内部驱动的第一步，绝不能把它当普通命令登记进 cron/plans.json/crontab/schtasks（裸跑只会空转产工单、永不接单交付＝假上线）。必须按 launch_spec 登记为“到点唤起一个 Agent 会话并投喂 driver_prompt 跑完整闭环”：' +
      '①宿主原生支持定时唤起 Agent 会话/带 prompt 的定时任务（如 Scheduled Agent / Managed Agent 定时部署 / 定时对话任务）→ 登记该原生入口，把 launch_spec.driver_prompt 作为任务内容、频率用 schedule.cron；' +
      '②宿主仅有裸命令定时器但提供“非交互/headless 模式拉起本 Agent 并传入 prompt”的入口 → 登记该入口并传入 driver_prompt；' +
      '③宿主完全不支持定时唤起 Agent 会话 → 不登记冒充自动接单，须如实告知用户“本客户端无法无人值守自动接单，需要时可发指令由我手动跑一轮任务市场自动接单”，并可用 install.js --background-dismissed 记录，不空登记、不谎称已开启。' +
      '登记后回读校对时，除频率外还须确认“到点唤起的是 Agent 会话而非某条被误当命令的脚本”；只能提示、无法真自动时如实降级表述为“仅每小时提示有哪些可接候选、需你确认后我再逐单接”，不得说成“已开启自动接单并交付”。' +
      '【任务市场自动接单·成功也要汇报接单/交付，勿套用“成功即静默”】market_auto_bid 每轮会把本轮接单/交付结果输出 stdout，登记时须放开成功回显把结果呈现给用户（同能力目录刷新处置）；宿主无法配置成功回显时，如实告知“本客户端周期任务成功时不展示输出，可发指令由我手动触发一次来查看接单/交付结果”。' +
      '【套件更新检查·成功也要提示新版，勿套用“成功即静默”】update_check_refresh 到点检查成功后，若结果为有新版/已自动更新/更新失败，须放开成功回显把提示呈现给用户（无新版则可安静不打扰）；同 capability_index_refresh 一样，登记时开启宿主“成功也回显 stdout”的策略，命令仍原样用 command_abs。宿主无法配置成功回显时，如实告知用户“本客户端周期任务成功时不展示输出，可发指令由我手动触发一次检查来查看是否有新版”。' +
      '【摘要呈现措辞】呈现 summary.samples 时，用“平台上的部分能力，例如：”这类自然引导语列出这些能力名，让用户直观感到“平台能干这些事”；不要用“随机代表能力”“随机抽取”“样本/samples”等字样作标题或描述（这些能力每次展示的是不同侧写、并非全部，措辞上避免让用户觉得随意或不完整），也不要暴露内部字段名与英文 source_type。' +
      '【能力目录·必附本地缓存文件位置（呈现纪律的例外）】每次呈现能力目录刷新摘要时，都必须在结尾附上本地缓存目录文件位置——直接原样使用 summary.catalog_hint（内含 catalog_path 完整路径）即可。措辞须澄清“这只是平台能力的本地缓存名录、每类仅取部分代表条目、并非平台全部能力”，不得说成“完整/全部能力目录”，以免误导用户以为本地文件就是平台能力的全集；需检索平台全部能力时仍走远程 discover（让用户直接说需求）。此为「不暴露文件路径」呈现纪律的明确例外：仅能力目录刷新这一处允许展示该本地文件路径，其余场景仍不暴露路径。' +
      '【确无自动化能力才降级手动】若本客户端既无原生自动化/定时系统、也无法配合系统定时（或尝试登记失败），不得空登记、不得谎称“已定时/已开启”；如实告知用户“当前客户端无法自动运行无人值守巡航”，并提示需要时可发指令由你手动触发一次巡航/能力刷新。' +
      '【结果纪律·禁编造】用户询问周期任务（巡航对账 / 能力目录刷新 / 套件更新检查 / 任务市场自动接单）的结果时，只读脚本实际输出并原样转述，不得凭记忆或想象补全余额、货币单位、版本号、能力条数、接单/交付单数等任何数字：' +
      '巡航结果读 memory/runtime/last-run-cruise.json（以文件中 summary/changes/status 等字段为唯一事实来源，如余额单位为 UT、版本号以实际字段为准）；能力目录刷新的结果以该任务本次运行的脚本输出（stdout 里的 summary：by_source/samples/count/updated_at/catalog_path）为唯一事实来源——它不落结果文件，若用户在两次运行之间追问且无本次输出可依，可临时手动触发一次刷新取最新摘要，或改用 capability_index.js --stats 读本地目录规模，绝不编造；套件更新检查的结果读 memory/runtime/last-run-update.json（以 status/current_version/latest_version/has_update/applied/error 等字段为唯一事实来源，版本号以实际字段为准）；任务市场自动接单的结果读 memory/runtime/last-run-market.json（可用 cruise.js market-report 汇总，以 applied/delivered/skipped/failed 及各 count、status、ran_at 等字段为唯一事实来源，接单/交付/失败单数与失败原因以实际字段为准）。' +
      '若巡航 / 更新 / 任务市场结果文件缺失、或其 env_error 为 true、或 status 为失败，须如实告知用户“最近一次未取得结果 / 运行环境异常”，绝不伪造成功、不编造具体数值。（呈现时仍遵循呈现纪律，用中文名与自然语言，不暴露文件路径/字段名/source_type 英文 id。）' +
      '非首装 / 补充提醒场景不擅自拉起常驻进程。' +
      '【接单通道】平台派给你的智能体任务由「智能体任务自动接单」（realtime_poll，scheduled 类）承接——客户端每小时自动接一次；离线期间不接、只在客户端被到点拉起时补接。首装不主动提示、不征询开启这一项。' +
      '「实时任务接单」（on_demand_features 中的 runtime_connect）是静默按需功能：首装及任何常规对话都不得提及、不得主动介绍，仅当用户明确说“启动实时任务接单”时才拉起；不参与“全开”，客户端退出即停，重启需用户再次启动。未启动是正常状态，不得归入“开启失败”。' +
      '【智能体任务自动接单·登记失败则降级】realtime_poll 默认每小时运行；若宿主定时任务登记失败，不启用该项、不空登记、不谎称已开启，如实告知“当前客户端未能开启智能体任务自动接单，需要时可发指令由我手动拉一次待接的智能体任务”，降级为手动触发（其余登记纪律同上“周期任务落地”）。' +
      '【实时接单·启动结果判定】用户明确要求启动后才尝试运行 on_demand_features 中的 command。只有进程实际启动且输出 success_signal 对应的 connection.open 事件，才可说“实时任务接单已启动”；认证失败、进程退出或未收到成功信号时，按实际错误说明。不得因为它不支持定时登记就断言实时连接也无法运行。' +
      '【实时接单·主动告知能力如实说明】启动后能否在新任务到达时主动提示，取决于本客户端是否把该进程输出回显到对话/任务窗口：支持则新任务自动提示、不支持则用户下次跟你说话时再告知；不得暗示“必然主动弹提醒”。' +
      '【任务市场自动接单·与上述两通道是不同的事】market_auto_bid（「任务市场自动接单」）不属于上面的智能体任务接单通道：它每小时自动去任务市场找 AI 能独立完成的线上任务、自动申请并交付完成，是主动接活；而「智能体任务自动接单」「实时任务接单」是被动接收平台派给你的智能体任务。介绍时讲清区别、不要与这两项混为一谈，仍只用其 display_name 与 user_summary 呈现。' +
      '实时任务接单不使用 --background-launched / --background-disabled 记录；用户要求停止时终止当前连接进程即可。',
  };
}

// ---------------------------------------------------------------------------
// 后台任务提醒（老用户兜底）：在高频入口顺带、节流地提醒"有后台任务可启动"。
// 状态文件记录：last_reminded_at（上次提醒）、last_choice（用户最近选择）、
// launched{taskId:isoTime}（各任务上次被记录启动的时间）。脚本不探测进程存活。
// ---------------------------------------------------------------------------
function readBgState() {
  try {
    return JSON.parse(fs.readFileSync(BG_STATE_FILE, 'utf8'));
  } catch (_) {
    return {};
  }
}

function writeBgState(state) {
  fs.mkdirSync(path.dirname(BG_STATE_FILE), { recursive: true });
  fs.writeFileSync(BG_STATE_FILE, JSON.stringify(state, null, 2));
}

function ageSec(isoTime) {
  if (!isoTime) return Infinity;
  const t = new Date(isoTime).getTime();
  if (Number.isNaN(t)) return Infinity;
  return (Date.now() - t) / 1000;
}

/**
 * 计算"现在是否应提醒用户后台任务"，并给出节流结论。供 install/cruise/discover 复用。
 * 不写状态（只读）；调用方据 should_remind 决定是否展示，展示后由 --background-launched/
 * --background-dismissed 落状态。
 */
function computeBackgroundReminder() {
  const tasks = buildBackgroundTasks();
  const state = readBgState();
  const launched = state.launched || {};
  const disabled = state.disabled || {};

  // 不再默认提示开启的任务：prompt_on_install=false 的任务不进入首装征询，也不进入老用户
  // 兜底提醒候选（账户巡航对账 / 智能体任务自动接单 / 能力目录刷新），仅在用户主动要求时开启。
  const startable = [...tasks.resident, ...tasks.scheduled].filter((t) => t.prompt_on_install !== false);
  const neverLaunched = startable.filter((t) => !launched[t.id] && !disabled[t.id]);

  // 节流：用户最近"暂不启动"→长冷却；否则按 24h TTL。
  const since = ageSec(state.last_reminded_at);
  const cooldown = state.last_choice === 'dismissed' ? BG_DISMISS_COOLDOWN_SEC : BG_REMIND_TTL_SEC;
  const throttled = since < cooldown;

  const shouldRemind = neverLaunched.length > 0 && !throttled;

  return {
    should_remind: shouldRemind,
    throttled,
    last_reminded_at: state.last_reminded_at || null,
    last_choice: state.last_choice || null,
    disabled_ids: Object.keys(disabled),
    startable_not_launched: neverLaunched.map((t) => ({
      id: t.id,
      display_name: t.display_name,
      desc: t.desc,
      // agent_session_task 故意不回显可裸登记的 command，避免被误当普通定时脚本登记；仅暴露 task_type 供调用方分流。
      command: t.task_type === 'agent_session_task' ? null : t.command,
      task_type: t.task_type || 'command_task',
      kind: t.kind,
      user_summary: t.user_summary,
      side_effects: t.side_effects || [],
    })),
    tasks,
    agent_hint: shouldRemind
      ? '检测到有后台任务从未被启动过。请温和地提醒用户“可启动这些后台能力”，展示时用各任务的 display_name（中文名）作条目名、user_summary 说明作用；' +
        '禁止向用户暴露内部 id、命令行、字段名与 SSE/轮询/索引等术语。含 auto_update 副作用的项须点明会自动更新套件、可关闭。' +
        '用户选择后，自动启动用 install.js --background-launched <id...>，关闭某项用 install.js --background-disabled <id...>（用户说中文名，你映射回 id），整体暂不启动用 install.js --background-dismissed 记录以进入冷却，避免反复打扰。'
      : '后台任务提醒处于冷却期或任务均已记录启动，本次无需打扰用户。',
  };
}

/** --background-status：只读输出后台任务状态与节流结论（供其他脚本 spawn 调用）。 */
function runBackgroundStatus() {
  emitJson({ ok: true, stage: 'background-status', ...computeBackgroundReminder() });
}

/** --background-launched <id...>：记录指定任务已被启动（消除其待提醒状态），并更新提醒时间。 */
function runBackgroundLaunched(ids) {
  const state = readBgState();
  state.launched = state.launched || {};
  const now = new Date().toISOString();
  const recorded = [];
  for (const id of ids) {
    state.launched[id] = now;
    // 重新启动即解除之前的禁用，保持 launched 与 disabled 互斥。
    if (state.disabled && state.disabled[id]) delete state.disabled[id];
    recorded.push(id);
  }
  state.last_reminded_at = now;
  state.last_choice = 'launched';
  writeBgState(state);
  emitJson({ ok: true, stage: 'background-launched', recorded });
}

/** --background-dismissed：记录用户"暂不启动"，进入更长冷却期。 */
function runBackgroundDismissed() {
  const state = readBgState();
  const now = new Date().toISOString();
  state.last_reminded_at = now;
  state.last_choice = 'dismissed';
  writeBgState(state);
  emitJson({ ok: true, stage: 'background-dismissed', cooldown_seconds: BG_DISMISS_COOLDOWN_SEC });
}

/**
 * --background-disabled <id...>：记录用户"关闭某项后台任务"（按 id，可只关一项、留其他）。
 * 语义区别于全局 --background-dismissed（本次全不启+冷却）：disabled 是永久关闭指定项，
 * 使其从后续可启动候选与提醒中剔除，直到被重新启动（--background-launched 会清除禁用）。
 */
function runBackgroundDisabled(ids) {
  const state = readBgState();
  state.disabled = state.disabled || {};
  const now = new Date().toISOString();
  const recorded = [];
  for (const id of ids) {
    state.disabled[id] = now;
    // 关闭即撤销其"已启动"记录，避免 launched 与 disabled 同时存在造成状态矛盾。
    if (state.launched && state.launched[id]) delete state.launched[id];
    recorded.push(id);
  }
  writeBgState(state);
  emitJson({ ok: true, stage: 'background-disabled', recorded });
}


function runInstall() {
  ensureDirs();
  ensureConfig();
  const update = checkUpdate();

  if (hasCredentials()) {
    emitJson({
      ok: true,
      stage: 'install',
      authorized: true,
      update,
      message: '已安装且已授权。可直接调用 rest_request.js。',
      onboarding: 'UUMit 平台上有大量用户与官方提供的动态能力（工作流、数据、知识、工具、子 Agent 等），可随时按需发现与调用。遇到本地无法直接满足的需求时，记得用 capability_discover.js 搜一下平台能力。首装授权完成后：用大白话告诉用户已就绪，并用 capabilities_overview 简述可用能力（用中文名、别暴露技术术语）。',
      capabilities_overview: [
        '数据广场', '知识商店', 'Playbooks', '任务与时间市场', '钱包', 'A2A 互通',
        '算力共享', '巡航', '实时接单', '推荐变现', '批量发布', '社交互动',
      ],
      background_tasks: buildBackgroundTasks(),
      update_hint: update && update.has_update
        ? '检测到新版本，提示用户后可运行 node scripts/install.js --upgrade --apply --yes 更新。'
        : undefined,
    });
    return;
  }

  try {
    const out = execFileSync(NODE_BIN, [path.join(__dirname, 'auth.js'), '--start'], { encoding: 'utf8' });
    const auth = JSON.parse(out);
    emitJson({
      ok: true,
      stage: 'install',
      authorized: false,
      auth,
      next: auth.browser_opened
        ? '已尝试自动打开授权页，引导用户在弹出的浏览器中登录完成授权（若未弹出则展示 auth.verification_url_complete 链接）；然后按 auth.retry_after_seconds 执行 auth.required_next_command。'
        : '未能自动打开浏览器，把 auth.verification_url_complete 作为可点击链接展示给用户，用户点击后登录即自动完成授权；然后按 auth.retry_after_seconds 执行 auth.required_next_command。',
    });
  } catch (e) {
    emitJson({
      ok: true,
      stage: 'install',
      authorized: false,
      hint: '安装完成，但发起授权失败。请手动运行 node scripts/auth.js --start。',
      detail: String(e && e.message || e),
    });
  }
}

function main() {
  if (!checkNodeVersion()) {
    emitJson({ ok: false, stage: 'install', error: `需要 Node >= 18，当前 ${process.versions.node}` });
    process.exit(1);
  }

  const args = process.argv.slice(2);
  if (args.includes('--upgrade')) return runUpgrade(args);
  if (args.includes('--check')) return runCheck();
  if (args.includes('--fill-missing')) return runFillMissing();
  if (args.includes('--update')) return runUpdate();
  if (args.includes('--background-status')) return runBackgroundStatus();
  if (args.includes('--background-launched')) {
    const idx = args.indexOf('--background-launched');
    const ids = args.slice(idx + 1).filter((a) => !a.startsWith('--'));
    return runBackgroundLaunched(ids);
  }
  if (args.includes('--background-disabled')) {
    const idx = args.indexOf('--background-disabled');
    const ids = args.slice(idx + 1).filter((a) => !a.startsWith('--'));
    return runBackgroundDisabled(ids);
  }
  if (args.includes('--background-dismissed')) return runBackgroundDismissed();
  return runInstall();
}

if (require.main === module) main();

module.exports = { buildBackgroundTasks };
