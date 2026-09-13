#!/usr/bin/env node
'use strict';
/**
 * capability_explain.js — 能力解释（批次 2）。
 *
 * 作用：取一个能力的详情，结构化为"能做什么 / 需要什么 / 花多少 / 有何风险 / 备选"，
 * 便于 Agent 在调用前向用户清楚解释，而不是把原始字段直接抛给用户。
 *
 * 数据来源复用 `GET /api/v1/capabilities/{id}`（已在白名单），不新建端点。
 * 不自起 HTTP：通过 rest_request.js 调用。
 *
 * 用法:
 *   node capability_explain.js --id <capability_id>
 *
 * 输出(stdout, JSON)：
 *   { capability_id, title, what_it_does, what_it_needs, what_it_costs, what_it_risks, alternatives }
 *
 * 退出码：0=成功；1=参数缺失/调用失败。
 */

const path = require('path');
const { spawnSync } = require('child_process');

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === '--id') out.id = argv[++i];
  }
  return out;
}

function fail(obj) {
  console.error(JSON.stringify(obj));
  process.exit(1);
}

function describeCost(pricing) {
  if (!pricing) return '价格未知';
  const model = pricing.model || pricing.type;
  if (model === 'free') return '免费';
  const price = pricing.price_ut != null ? `${pricing.price_ut} UT` : (pricing.price || '价格待报价');
  return `${price}（计费方式：${model || '未知'}）`;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.id) fail({ error: 'usage: capability_explain.js --id <capability_id>' });

  const res = spawnSync(
    'node',
    [path.join(__dirname, 'rest_request.js'), 'GET', `/api/v1/capabilities/${args.id}`],
    { encoding: 'utf8', timeout: 30000 },
  );
  if (res.status !== 0) {
    fail({ error: 'explain failed', detail: (res.stderr || res.stdout || '').trim() });
  }
  let parsed;
  try {
    parsed = JSON.parse(res.stdout);
  } catch (e) {
    fail({ error: 'invalid capability response', raw: (res.stdout || '').slice(0, 500) });
  }

  const c = parsed.data || parsed;
  const needs = [];
  if (c.input_schema && c.input_schema.required) needs.push(...c.input_schema.required);
  if (Array.isArray(c.missing_inputs)) needs.push(...c.missing_inputs);

  const risks = [];
  if (c.safety_level) risks.push(`安全等级：${c.safety_level}`);
  if (c.risk_level) risks.push(`风险：${c.risk_level}`);
  if (c.requirements && c.requirements.user_confirm_required) risks.push('调用前需用户确认');

  process.stdout.write(JSON.stringify({
    capability_id: c.capability_id || args.id,
    title: c.title || '',
    what_it_does: c.description || '',
    what_it_needs: [...new Set(needs)],
    what_it_costs: describeCost(c.pricing),
    what_it_risks: risks.join('；') || '低风险',
    alternatives: Array.isArray(c.alternatives) ? c.alternatives : [],
  }) + '\n');
}

main();
