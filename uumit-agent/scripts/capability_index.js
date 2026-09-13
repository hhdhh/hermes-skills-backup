#!/usr/bin/env node
'use strict';
/**
 * capability_index.js — 本地轻量能力索引（批次 2 / 防线 3）。
 *
 * 定位：本地目录是"唤醒信号"，不是"能力匹配的前置过滤器"。它让 Agent 大致知道
 *   "平台大概能干哪些品类的事"，从而在用户提相关需求时更倾向于唤醒 uumit-agent；
 *   一旦唤醒，就拿用户完整意图去远程 discover 精确搜索——具体能力匹配发生在远程，
 *   而非本地。因此本地目录只需大致覆盖平台能力的样貌/品类，不追求全、不追求准：
 *   漏收的条目会在唤醒后由远程 discover 补齐，本地不承担"判无则拦截远程"的职责。
 *
 * 索引只存判断所需的最轻字段（source_type/type/tags/title/category/关键词），
 * 不含 input_schema 等重字段。数据来源为 catalog 端点（覆盖全部来源、每类代表条目、
 * 由服务端均衡列出，不按关键词过滤）；存储于 memory/runtime/capability-index.json。
 *
 * 不自起 HTTP：刷新通过 rest_request.js 调 catalog 端点。
 *
 * 用法:
 *   node capability_index.js --refresh [--limit 100]   # 拉取并重建本地索引（--limit 透传 per_type_limit）
 *   node capability_index.js --match "<意图关键词>"      # 本地粗筛，返回是否可能有相关能力
 *   node capability_index.js --stats                    # 查看本地索引规模、时间与来源分布
 *
 * --refresh 每次跑完在 stdout 附一份"平台能力摘要"（品类分布 by_source / 随机代表能力 samples /
 * 总数时间 / 本地缓存目录地址 catalog_path / 面向用户的现成引导语 catalog_hint），供周期任务窗口即时展示；
 * catalog_hint 供 Agent 每次原样附给用户，指引"查看本地已缓存的这部分能力可打开该文件"，并澄清本地仅缓存每类部分代表条目、非平台全部能力；样本每次随机 → 即使本轮无变更
 * 摘要也不同。摘要仅走 stdout，不落文件（本轮缓存的能力条目已在 capability-index.json，仅每类部分代表条目、非平台全部能力）。
 *
 * --refresh 覆写索引前先与旧索引对比，算出本轮 added / removed 增量，随 stdout 与 last-run 结果文件
 * 一并产出，供 Agent 按"打扰克制"只在有上新/下架时提示用户；首刷（无旧索引）不误报打扰
 *（first_run:true、added/removed 均空）。
 *
 * 退出码：0=成功；1=参数缺失/调用失败。
 */

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const SKILL_DIR = path.resolve(__dirname, '..');
const INDEX_DIR = path.join(SKILL_DIR, 'memory', 'runtime');
const INDEX_PATH = path.join(INDEX_DIR, 'capability-index.json');
// 用当前 Node 解释器绝对路径拉起子脚本，避免宿主子进程 PATH 无 `node`。
const NODE_BIN = process.execPath;
const REST_SCRIPT = path.join(__dirname, 'rest_request.js');
// 最近一次索引刷新执行摘要：供 Agent 只读转述（禁编造）；缺失或 env_error=true 时如实报未取得。
const LAST_RUN_INDEX_PATH = path.join(INDEX_DIR, 'last-run-index.json');

function parseArgs(argv) {
  // limit 透传为 catalog 端点的 per_type_limit（每来源类型上限），默认 100。
  const out = { limit: 100 };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === '--refresh') out.refresh = true;
    else if (a === '--match') out.match = argv[++i];
    else if (a === '--stats') out.stats = true;
    else if (a === '--limit') out.limit = parseInt(argv[++i], 10) || 100;
  }
  out.limit = Math.max(out.limit, 1);
  return out;
}

function fail(obj) {
  console.error(JSON.stringify(obj));
  process.exit(1);
}

function slimEntry(c) {
  return {
    capability_id: c.capability_id,
    title: c.title || '',
    source_type: c.source_type || '',
    capability_type: c.capability_type || '',
    category: c.category || '',
    tags: Array.isArray(c.tags) ? c.tags : [],
    examples: Array.isArray(c.examples) ? c.examples : [],
  };
}

function loadIndex() {
  if (!fs.existsSync(INDEX_PATH)) return null;
  try {
    return JSON.parse(fs.readFileSync(INDEX_PATH, 'utf8'));
  } catch (e) {
    return null;
  }
}

/**
 * 对比"旧索引"与"新条目"，以 capability_id 为键算出 added / removed 增量。
 * 首刷（prevIndex 为 null）时约定不误报打扰：added 为空、removed 为空、first_run:true。
 */
function diffEntries(prevIndex, newEntries) {
  const prevEntries = prevIndex && Array.isArray(prevIndex.entries) ? prevIndex.entries : [];
  const firstRun = !prevIndex;
  const prevIds = new Map(prevEntries.map((e) => [e.capability_id, e.title || '']));
  const curIds = new Map(newEntries.map((e) => [e.capability_id, e.title || '']));

  const added = [];
  const removed = [];
  // 首刷无对比基准：不把全量计入 added，避免首次刷新即误报"平台新增了全部能力"打扰用户。
  if (!firstRun) {
    for (const [id, title] of curIds) {
      if (!prevIds.has(id)) added.push({ capability_id: id, title });
    }
    for (const [id, title] of prevIds) {
      if (!curIds.has(id)) removed.push({ capability_id: id, title });
    }
  }
  return {
    first_run: firstRun,
    since: prevIndex ? prevIndex.updated_at : null,
    added,
    removed,
    added_count: added.length,
    removed_count: removed.length,
  };
}

/** 写"最近一次索引刷新执行摘要"结果文件（供 Agent 只读转述、禁编造）；写入失败静默不阻断。 */
function writeLastRunIndex(payload) {
  try {
    fs.mkdirSync(INDEX_DIR, { recursive: true });
    fs.writeFileSync(
      LAST_RUN_INDEX_PATH,
      JSON.stringify({ ran_at: new Date().toISOString(), ...payload }, null, 2),
      'utf8',
    );
  } catch (_) {
    /* 结果文件写入失败不阻断刷新 */
  }
}

/**
 * 基于本地索引构建"平台能力摘要"（供周期任务窗口即时展示，仅走 stdout、不落文件）。
 * 要素：品类分布 by_source、能力示例 samples（默认 10 条、每次随机→摘要每次不同）、总数/时间、全量目录地址。
 * 构建异常时返回 null，由调用方静默降级（不影响刷新主流程与退出码）。
 */
function buildSummary(index, sampleSize = 10) {
  try {
    const entries = Array.isArray(index.entries) ? index.entries : [];
    const bySource = {};
    for (const e of entries) {
      const st = e.source_type || 'unknown';
      bySource[st] = (bySource[st] || 0) + 1;
    }
    // 随机抽取代表能力：Fisher–Yates 洗牌取前 N，保证即使无变更每次样本也不同。
    const shuffled = entries.slice();
    for (let i = shuffled.length - 1; i > 0; i -= 1) {
      const j = Math.floor(Math.random() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    const samples = shuffled
      .slice(0, Math.min(sampleSize, shuffled.length))
      .map((e) => ({ title: e.title || '', source_type: e.source_type || '' }));
    return {
      count: index.count,
      updated_at: index.updated_at,
      by_source: bySource,
      samples,
      catalog_path: INDEX_PATH,
      // 面向用户的现成引导语：本地缓存目录文件位置，供 Agent 每次刷新后原样附给用户。
      // 措辞须澄清"这只是平台能力的本地缓存名录、每类仅取代表条目、并非平台全部能力"，
      // 不得说成"完整/全部能力"。此为能力目录刷新的特例，允许展示该路径。
      catalog_hint: `平台能力的本地缓存名录（每类仅取部分代表条目、非平台全部能力）已保存在文件：${INDEX_PATH}，想查看已缓存的这部分能力时可打开该文件；如需检索平台全部能力，直接告诉我你的需求即可。`,
    };
  } catch (_) {
    return null;
  }
}

/**
 * 基于本轮 changes 构建"变更段"（供 Agent 原样转述、禁编造，S2）。
 * 打扰克制：仅当 added 或 removed 非空才返回该段；无变更（或首刷）返回 null，摘要不含变更段、不打扰。
 * 只做结构化 → 展示字段的整理，标题原样取自 changes，不臆造能力名/数量。
 */
function buildChangeNote(changes) {
  if (!changes || changes.first_run) return null;
  const added = Array.isArray(changes.added) ? changes.added : [];
  const removed = Array.isArray(changes.removed) ? changes.removed : [];
  if (added.length === 0 && removed.length === 0) return null;
  return {
    added_count: added.length,
    removed_count: removed.length,
    // 标题原样取自结构化 changes，供 Agent 转述时直接引用，禁再加工/补全。
    added_titles: added.map((e) => e.title || '').filter(Boolean),
    removed_titles: removed.map((e) => e.title || '').filter(Boolean),
  };
}

function refresh(limit) {
  // 环境异常显式暴露：基座 rest_request.js 不可达即视为运行环境异常，写 env_error 结果文件后报错退出。
  if (!fs.existsSync(REST_SCRIPT)) {
    const msg = `rest_request.js 不可达（${REST_SCRIPT}）；请确认在 skill 目录下运行。`;
    writeLastRunIndex({ status: 'env_error', env_error: true, error: msg });
    fail({ error: 'index refresh env_error', env_error: true, detail: msg });
  }

  // 拉取 catalog 端点：覆盖全部来源、每类代表条目，由服务端均衡列出。
  // 不传 query、不传 source_types、不做任何来源筛选；limit 透传为 per_type_limit。
  const apiPath = `/api/v1/capability-runtime/catalog?per_type_limit=${encodeURIComponent(limit)}`;
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'uumit-catalog-'));
  const responsePath = path.join(tempDir, 'response.json');
  let parsed;
  let refreshError = null;
  try {
    const res = spawnSync(
      NODE_BIN,
      [REST_SCRIPT, 'GET', apiPath, '--output-file', responsePath],
      { encoding: 'utf8', timeout: 30000 },
    );
    if (res.status !== 0) {
      throw new Error((res.stderr || res.stdout || (res.error && res.error.message) || 'catalog request failed').trim());
    }
    parsed = JSON.parse(fs.readFileSync(responsePath, 'utf8'));
  } catch (e) {
    refreshError = String(e && e.message || e).slice(0, 500);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
  if (refreshError) {
    writeLastRunIndex({ status: 'refresh_failed', env_error: false, error: refreshError });
    fail({ error: 'index refresh failed', detail: refreshError });
  }
  const data = parsed.data || parsed;
  const items = Array.isArray(data.items) ? data.items : [];
  const newEntries = items.map(slimEntry);
  // 变更对比须在覆写前完成：先加载旧索引与本次结果 diff，再覆写，否则 diff 基准会被本次结果覆盖。
  const prevIndex = loadIndex();
  const changes = diffEntries(prevIndex, newEntries);
  const index = {
    updated_at: new Date().toISOString(),
    count: items.length,
    entries: newEntries,
  };
  fs.mkdirSync(INDEX_DIR, { recursive: true });
  fs.writeFileSync(INDEX_PATH, JSON.stringify(index), 'utf8');
  writeLastRunIndex({
    status: 'refreshed',
    env_error: false,
    refreshed_count: index.count,
    changes,
  });
  // 平台能力摘要仅走 stdout 供周期任务窗口即时展示（不落文件）；构建失败静默降级为无 summary。
  const summary = buildSummary(index);
  const changeNote = buildChangeNote(changes);
  if (summary) {
    summary.changes = changes;
    // 打扰克制：仅有上新/下架才增列变更段；无变更则不含该段，其余摘要照旧。
    if (changeNote) summary.change_note = changeNote;
  }
  const out = { refreshed: true, count: index.count, updated_at: index.updated_at, changes };
  if (summary) out.summary = summary;
  process.stdout.write(JSON.stringify(out) + '\n');
}

function match(keyword) {
  const index = loadIndex();
  if (!index) {
    // 无本地索引时不阻断：返回 unknown，让上层决定是否直接走 discover。
    process.stdout.write(JSON.stringify({ has_local_index: false, likely: 'unknown', hint: '先运行 --refresh 建立本地索引' }) + '\n');
    return;
  }
  const kw = keyword.toLowerCase();
  const tokens = kw.split(/\s+/).filter(Boolean);
  const hits = index.entries.filter((e) => {
    const hay = [e.title, e.category, e.capability_type, e.source_type, ...(e.tags || []), ...(e.examples || [])]
      .join(' ')
      .toLowerCase();
    return tokens.some((t) => hay.includes(t));
  });
  process.stdout.write(JSON.stringify({
    has_local_index: true,
    likely: hits.length > 0 ? 'yes' : 'no',
    match_count: hits.length,
    top: hits.slice(0, 5).map((e) => ({ capability_id: e.capability_id, title: e.title })),
    index_updated_at: index.updated_at,
  }) + '\n');
}

function stats() {
  const index = loadIndex();
  if (!index) {
    process.stdout.write(JSON.stringify({ has_local_index: false }) + '\n');
    return;
  }
  // 按 source_type 统计来源分布，直观呈现"覆盖了哪些品类的能力"。
  const bySource = {};
  for (const e of index.entries || []) {
    const st = e.source_type || 'unknown';
    bySource[st] = (bySource[st] || 0) + 1;
  }
  process.stdout.write(JSON.stringify({
    has_local_index: true,
    count: index.count,
    updated_at: index.updated_at,
    by_source: bySource,
  }) + '\n');
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.refresh) return refresh(args.limit);
  if (args.match) return match(args.match);
  if (args.stats) return stats();
  fail({ error: 'usage: capability_index.js --refresh [--limit N] | --match "<keyword>" | --stats' });
}

main();
