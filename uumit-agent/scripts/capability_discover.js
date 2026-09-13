#!/usr/bin/env node
'use strict';
/**
 * capability_discover.js — 动态能力发现薄封装（批次 0 / 防线 1）。
 *
 * 作用：把用户的自然语言意图包装为 `POST /api/v1/capability-runtime/discover`，
 * 复用 rest_request.js（白名单 + 凭证 + 安全闸门），返回精简后的候选能力卡，
 * 便于 Agent 解释与决定下一步（quote / smart-invoke）。
 *
 * 不自起 HTTP：所有网络与安全闸门都委托 rest_request.js。
 *
 * 用法:
 *   node capability_discover.js --query "<用户意图>" [--limit 5] [--raw]
 *
 * 输出(stdout, JSON)：
 *   { query, total, best, items:[{capability_id,title,source_type,capability_type,
 *     match_score,match_reason,pricing,safety_level,routing_hint,examples}] }
 *   --raw 时透传 rest_request 原始响应。
 *
 * 退出码：0=成功；1=参数缺失或调用失败。
 */

const path = require('path');
const { spawnSync } = require('child_process');

// 用当前 Node 解释器绝对路径拉起子脚本，避免宿主子进程 PATH 无 `node` 时报"找不到 node"。
const NODE_BIN = process.execPath;

function parseArgs(argv) {
  const out = { limit: 5, raw: false };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === '--query') out.query = argv[++i];
    else if (a === '--limit') out.limit = parseInt(argv[++i], 10) || 5;
    else if (a === '--raw') out.raw = true;
  }
  return out;
}

function fail(obj) {
  console.error(JSON.stringify(obj));
  process.exit(1);
}

/**
 * 节流检查后台任务提醒（转发 install.js --background-status）。高频入口顺带，节流由其内部 TTL 控制。
 * 仅在"应提醒"时返回精简结论供 Agent 提示老用户；其余返回 null，绝不阻断 discover 主流程。
 */
function checkBackgroundReminder() {
  try {
    const res = spawnSync(NODE_BIN, [path.join(__dirname, 'install.js'), '--background-status'], {
      encoding: 'utf8',
      timeout: 20000,
    });
    if (res.status !== 0) return null;
    const r = JSON.parse(res.stdout);
    if (!r.should_remind) return null;
    return { startable_not_launched: r.startable_not_launched, agent_hint: r.agent_hint };
  } catch (_) {
    return null;
  }
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.query) {
    fail({ error: 'usage: capability_discover.js --query "<用户意图>" [--limit N] [--raw]' });
  }

  const body = JSON.stringify({ query: args.query, limit: args.limit });
  const restPath = path.join(__dirname, 'rest_request.js');
  const res = spawnSync(
    NODE_BIN,
    [restPath, 'POST', '/api/v1/capability-runtime/discover', '--body', body],
    { encoding: 'utf8', timeout: 30000 },
  );

  if (res.status !== 0) {
    fail({ error: 'discover failed', detail: (res.stderr || res.stdout || '').trim() });
  }

  let parsed;
  try {
    parsed = JSON.parse(res.stdout);
  } catch (e) {
    fail({ error: 'invalid discover response', raw: (res.stdout || '').slice(0, 500) });
  }

  const background_reminder = checkBackgroundReminder();

  if (args.raw) {
    process.stdout.write(JSON.stringify({ ...parsed, background_reminder }) + '\n');
    return;
  }

  const data = parsed.data || parsed;
  const items = Array.isArray(data.items) ? data.items : [];
  const slim = (c) => ({
    capability_id: c.capability_id,
    title: c.title,
    source_type: c.source_type,
    capability_type: c.capability_type,
    match_score: c.match_score,
    match_reason: c.match_reason,
    pricing: c.pricing,
    safety_level: c.safety_level,
    routing_hint: c.routing_hint,
    examples: c.examples || [],
  });

  process.stdout.write(JSON.stringify({
    query: args.query,
    total: data.total != null ? data.total : items.length,
    best: data.best ? slim(data.best) : (items[0] ? slim(items[0]) : null),
    items: items.map(slim),
    background_reminder,
  }) + '\n');
}

main();
