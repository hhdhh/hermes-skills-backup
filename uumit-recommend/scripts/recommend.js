#!/usr/bin/env node
/**
 * uumit-recommend — 推荐薄编排脚本（v2.1.2）。
 *
 * 业务意图（源自 1.x recommendation_tick.js，按 2.x 后端端点重写）：
 *   1.x 靠聚合多个只读端点 + 本地画像拼推荐；2.x 后端已提供专门推荐端点
 *   （/api/v1/recommendations 与 /feed），本扩展优先用之，并补充变现机会
 *   （income-center/opportunities），全部经基座 rest_request.js 调用。
 *
 * 设计铁律（见设计方案 9.2.0）：
 *   - 不自带 HTTP、不自读凭证：所有调用经基座 rest_request.js。
 *   - 薄编排层：只聚合与整理候选，是否行动由 Agent 判断。
 *
 * 用法:
 *   node recommend.js [--limit <n>] [--feed]
 *     默认输出推荐列表 + 变现机会；--feed 改用任务 feed 流。
 *
 * 输出: stdout=JSON；stderr=诊断。
 */

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
// 用当前 Node 解释器绝对路径拉起子脚本，避免宿主子进程 PATH 无 `node` 时报"找不到 node"。
const NODE_BIN = process.execPath;

const BASE_DIR = process.env.UUMIT_SKILL_DIR
  ? path.resolve(process.env.UUMIT_SKILL_DIR)
  : path.resolve(__dirname, '..', '..', 'uumit-agent');
const REST_SCRIPT = path.join(BASE_DIR, 'scripts', 'rest_request.js');

function log(msg) { console.error(`[recommend] ${msg}`); }
function emit(payload) { process.stdout.write(JSON.stringify(payload, null, 2) + '\n'); }

function baseRequest(method, apiPath) {
  if (!fs.existsSync(REST_SCRIPT)) {
    throw new Error(`base rest_request.js not found at ${REST_SCRIPT}（设置 UUMIT_SKILL_DIR 指向基座目录）`);
  }
  const out = execFileSync(NODE_BIN, [REST_SCRIPT, method, apiPath], { encoding: 'utf8', timeout: 60000 });
  return out ? JSON.parse(out) : null;
}

function safeData(resp) {
  return (resp && resp.code === 0 && resp.data) ? resp.data : null;
}

function tryGet(apiPath) {
  try {
    return safeData(baseRequest('GET', apiPath));
  } catch (e) {
    log(`${apiPath} 获取失败: ${e.message}`);
    return null;
  }
}

function main() {
  const args = process.argv.slice(2);
  let limit = 10;
  let useFeed = false;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--limit' && args[i + 1]) limit = Math.max(1, parseInt(args[++i], 10) || 10);
    else if (args[i] === '--feed') useFeed = true;
  }

  const result = {
    ok: true,
    recommendations: [],
    opportunities: [],
    source: useFeed ? 'recommendations/feed' : 'recommendations',
    agent_hint: '逐条评估推荐与变现机会；可安全自完成才提议并在写操作前确认，否则给出 UUMit 路由。',
  };

  // 主推荐：优先用后端专门端点。
  const recPath = useFeed
    ? `/api/v1/recommendations/feed?page_size=${limit}`
    : `/api/v1/recommendations?page_size=${limit}`;
  const recData = tryGet(recPath);
  if (recData) {
    result.recommendations = recData.items || recData.records || [];
  }

  // 变现机会：收益中心。
  const oppData = tryGet('/api/v1/income-center/opportunities');
  if (oppData) {
    result.opportunities = oppData.items || oppData.opportunities || oppData || [];
  }

  emit(result);
}

main();
