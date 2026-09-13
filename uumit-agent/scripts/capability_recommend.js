#!/usr/bin/env node
'use strict';
/**
 * capability_recommend.js — 上下文能力推荐（批次 2 / 防线 4）。
 *
 * 作用：在 Agent 工作流的自然节点（任务开始 / 子任务完成 / 用户问"还能做什么"）主动巡查
 * 一次平台能力，绕开"用户恰好说对触发词"。复用服务端 activation 预计算的高价值能力
 * （`recommended-capabilities`），并在 Skill 侧落地**推送克制约束**：相关性阈值 / 频次上限。
 *
 * 不自起 HTTP：通过 rest_request.js 调用。
 *
 * 用法:
 *   node capability_recommend.js [--min-relevance 0.75] [--limit 3]
 *
 * 输出(stdout, JSON)：
 *   { recommendable, count, items:[{capability_id,title,relevance,...}], constraint:{...} }
 *   recommendable=false 表示按克制约束本轮不应推送。
 *
 * 注意：本脚本只产出"可推荐的候选"，是否真正打断用户由 Agent 按 constraint 决定——
 *       SKILL.md 规定：无相关性不推、用户输入中不打断、被拒后冷却。
 *
 * 退出码：0=成功；1=调用失败。
 */

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const SKILL_DIR = path.resolve(__dirname, '..');
const CONFIG_PATH = path.join(SKILL_DIR, 'memory', 'runtime', 'agent-autonomy-config.json');

function loadRecommendConfig() {
  const fallback = { min_relevance: 0.75, cooldown_minutes: 30, max_per_session: 3 };
  try {
    const cfg = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
    return { ...fallback, ...(cfg.recommend || {}) };
  } catch (e) {
    return fallback;
  }
}

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === '--min-relevance') out.minRelevance = parseFloat(argv[++i]);
    else if (a === '--limit') out.limit = parseInt(argv[++i], 10);
  }
  return out;
}

function fail(obj) {
  console.error(JSON.stringify(obj));
  process.exit(1);
}

function relevanceOf(c) {
  // 优先 match_score / relevance；退回 quality.score。
  if (typeof c.match_score === 'number') return c.match_score;
  if (typeof c.relevance === 'number') return c.relevance;
  if (c.quality && typeof c.quality.score === 'number') return c.quality.score;
  return 0;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const cfg = loadRecommendConfig();
  const minRelevance = args.minRelevance != null ? args.minRelevance : cfg.min_relevance;
  const limit = args.limit != null ? args.limit : cfg.max_per_session;

  const res = spawnSync(
    'node',
    [path.join(__dirname, 'rest_request.js'), 'GET', '/api/v1/capability-runtime/recommended-capabilities'],
    { encoding: 'utf8', timeout: 30000 },
  );
  if (res.status !== 0) {
    fail({ error: 'recommend failed', detail: (res.stderr || res.stdout || '').trim() });
  }
  let parsed;
  try {
    parsed = JSON.parse(res.stdout);
  } catch (e) {
    fail({ error: 'invalid recommend response', raw: (res.stdout || '').slice(0, 500) });
  }

  const data = parsed.data || parsed;
  const raw = Array.isArray(data.recommendations) ? data.recommendations : [];

  // 应用克制约束：相关性阈值过滤 + 频次上限。
  const filtered = raw
    .map((c) => ({ ...c, _relevance: relevanceOf(c) }))
    .filter((c) => c._relevance >= minRelevance)
    .sort((a, b) => b._relevance - a._relevance)
    .slice(0, limit)
    .map((c) => ({
      capability_id: c.capability_id,
      title: c.title,
      relevance: Number(c._relevance.toFixed(3)),
      capability_type: c.capability_type,
      pricing: c.pricing,
      match_reason: c.match_reason || '',
    }));

  process.stdout.write(JSON.stringify({
    recommendable: filtered.length > 0,
    count: filtered.length,
    items: filtered,
    constraint: {
      min_relevance: minRelevance,
      max_per_session: limit,
      cooldown_minutes: cfg.cooldown_minutes,
      note: '无相关性不推；用户输入中不打断；被拒后进入冷却。最终是否打断由 Agent 按 SKILL.md 决定。',
    },
  }) + '\n');
}

main();
