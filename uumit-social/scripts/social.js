#!/usr/bin/env node
/**
 * uumit-social — 社交/互动薄编排脚本（v2.1.2）。
 *
 * 业务意图：聚合 Agent 可读的社交状态（信用、邀请、红包/科锦、好友），
 * 并支持 API Key 可用的写动作（领红包）。签到/翻牌/时间胶囊等 JWT-only
 * 操作不在此脚本，由 SKILL.md 引导走深链（见基座 DEEP_LINKS.md 的 /hall）。
 *
 * 设计铁律（见设计方案 9.2.0）：
 *   - 不自带 HTTP、不自读凭证：所有调用经基座 rest_request.js。
 *   - 薄编排层：只聚合状态与发起允许的写动作，是否行动由 Agent 判断。
 *
 * 用法:
 *   node social.js status            # 聚合社交状态（信用/邀请/红包/好友，只读）
 *   node social.js claim-redpacket --id <batch_id>   # 领红包（API Key 可用的写动作）
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

function log(msg) { console.error(`[social] ${msg}`); }
function emit(payload) { process.stdout.write(JSON.stringify(payload, null, 2) + '\n'); }
function failCli(message) { emit({ ok: false, error: message }); process.exit(2); }

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

function runStatus() {
  const result = {
    ok: true,
    credit: tryGet('/api/v1/credit/me'),
    invite: tryGet('/api/v1/invite/stats'),
    red_packet: tryGet('/api/v1/red-packet/my-claims'),
    buddy: tryGet('/api/v1/buddy/list'),
    deep_link_only: {
      note: '签到/翻牌/时间胶囊为 JWT-only，Skill 端无法直接调用，请按基座 DEEP_LINKS.md 引导用户到 {APP_BASE_URL}/hall。',
    },
    agent_hint: '汇报社交状态摘要；需要签到/翻牌时给出 /hall 深链，不要伪造结果。',
  };
  emit(result);
}

function runClaimRedpacket(args) {
  let batchId = null;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--id' && args[i + 1]) batchId = args[++i];
    else failCli(`unknown or incomplete argument: ${args[i]}`);
  }
  if (!batchId) failCli('--id <batch_id> is required');

  log(`领取红包 ${batchId}（经基座 rest_request.js）...`);
  let resp;
  try {
    resp = baseRequest('POST', `/api/v1/red-packet/${batchId}/claim`);
  } catch (e) {
    failCli(`claim failed: ${e.message}`);
  }
  const ok = resp && resp.code === 0;
  emit({ ok, status: ok ? 'claimed' : 'failed', detail: resp && (resp.data || resp.message) });
  if (!ok) process.exit(1);
}

function main() {
  const [sub, ...rest] = process.argv.slice(2);
  switch (sub) {
    case 'status': return runStatus();
    case 'claim-redpacket': return runClaimRedpacket(rest);
    default:
      failCli(`unknown subcommand: ${sub || '(none)'}（可用：status | claim-redpacket）`);
  }
}

main();
