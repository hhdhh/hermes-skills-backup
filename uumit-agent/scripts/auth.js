#!/usr/bin/env node
/**
 * UUMit Skill v2.7.0 — 设备授权脚本。
 *
 * 用法:
 *   node auth.js --start [--platform <type>]   # 发起设备授权，尝试自动打开授权页；返回 verification_url / user_code / device_code
 *   node auth.js --wait <device_code>          # 单次短轮询（不阻塞），返回结构化 JSON
 *   node auth.js --check                        # 检查现有凭证
 *   node auth.js --reset                        # 清除凭证
 *
 * 设计: 命令短小、确定性、stdout 返回机器可读 JSON，适合 Agent 工具调用。
 * 输出: stdout=JSON；stderr=诊断。
 */

const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const SKILL_DIR = path.resolve(__dirname, '..');
const AUTH_FILE = path.join(SKILL_DIR, 'memory', 'uumit-auth.json');
const TIMEOUT = 15000;

const ALLOWED_PLATFORMS = new Set([
  'openclaw', 'claude_desktop', 'cursor', 'custom_mcp', 'hermes_agent',
]);

function loadConfig() {
  try {
    return JSON.parse(fs.readFileSync(path.join(SKILL_DIR, 'memory', 'uumit-config.json'), 'utf8'));
  } catch (_) {
    return {};
  }
}

function resolveBaseUrl() {
  return process.env.UUMIT_BASE_URL || loadConfig().base_url || 'https://api.uumit.com';
}

const BASE_URL = resolveBaseUrl();
const baseUrlObj = new URL(BASE_URL);
const isHttps = baseUrlObj.protocol === 'https:';

function emitJson(payload) {
  process.stdout.write(JSON.stringify(payload, null, 2) + '\n');
}

function makeRequest(method, urlPath, body) {
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

function ensureMemoryDir() {
  fs.mkdirSync(path.dirname(AUTH_FILE), { recursive: true });
}

function saveCredentials(apiKey, userId) {
  ensureMemoryDir();
  fs.writeFileSync(AUTH_FILE, JSON.stringify({ api_key: apiKey, platform_user_id: userId }, null, 2));
}

function readCredentials() {
  try {
    return JSON.parse(fs.readFileSync(AUTH_FILE, 'utf8'));
  } catch (_) {
    return null;
  }
}

/**
 * 尝试用系统默认浏览器自动打开授权页。
 * 返回 { opened: boolean, method: string|null, error: string|null }——如实上报，
 * 不谎称已打开；无桌面环境（headless/远程）等场景应如实降级为展示链接。
 */
function tryOpenBrowser(url) {
  return new Promise((resolve) => {
    let cmd;
    let args;
    if (process.platform === 'win32') {
      // Windows: start 是 cmd 内建命令，须经 cmd /c 调用。
      cmd = 'cmd';
      args = ['/c', 'start', '', url];
    } else if (process.platform === 'darwin') {
      cmd = 'open';
      args = [url];
    } else {
      cmd = 'xdg-open';
      args = [url];
    }
    let child;
    try {
      child = spawn(cmd, args, { detached: true, stdio: 'ignore' });
    } catch (e) {
      resolve({ opened: false, method: cmd, error: String(e && e.message || e) });
      return;
    }
    // spawn 成功即认为已拉起打开动作；不等其退出（detached），避免阻塞轮询。
    child.on('error', (err) => {
      resolve({ opened: false, method: cmd, error: String(err && err.message || err) });
    });
    child.on('spawn', () => {
      child.unref();
      resolve({ opened: true, method: cmd, error: null });
    });
  });
}

async function start(platform) {
  const p = ALLOWED_PLATFORMS.has(platform) ? platform : 'openclaw';
  const res = await makeRequest('POST', '/api/v1/auth/device-auth', { agent_platform_type: p });
  if (res.statusCode >= 400 || !res.data || res.data.code !== 0) {
    emitJson({ ok: false, stage: 'start', error: '发起设备授权失败', detail: res.data });
    process.exit(1);
  }
  const d = res.data.data || {};
  // 优先用带 user_code 的完整链接：用户点击即可打开授权页并自动带入授权码，
  // 登录后自动确认，无需手动输入。老服务端无此字段时回退本地拼接。
  const verificationUrlComplete = d.verification_url_complete
    || (d.verification_url && d.user_code
        ? `${d.verification_url}${d.verification_url.includes('?') ? '&' : '?'}user_code=${encodeURIComponent(d.user_code)}`
        : d.verification_url);
  // 尝试自动打开授权页；失败不谎称，如实上报后回退为展示链接。
  const opened = await tryOpenBrowser(verificationUrlComplete);
  emitJson({
    ok: true,
    stage: 'start',
    verification_url: d.verification_url,
    verification_url_complete: verificationUrlComplete,
    user_code: d.user_code,
    device_code: d.device_code,
    retry_after_seconds: d.interval || 5,
    browser_opened: opened.opened,
    browser_open_method: opened.method,
    browser_open_error: opened.error,
    required_next_command: `node scripts/auth.js --wait ${d.device_code}`,
    hint: opened.opened
      ? '已尝试自动打开授权页（浏览器若未弹出，请手动打开 verification_url_complete 链接）。登录后即自动完成授权，无需手动输入 user_code。然后按 retry_after_seconds 重复 --wait 轮询结果。'
      : '未能自动打开浏览器，请把 verification_url_complete 作为可点击链接展示给用户，用户点击后登录即自动完成授权，无需手动输入 user_code。然后按 retry_after_seconds 重复 --wait 轮询结果。',
  });
}

async function wait(deviceCode) {
  if (!deviceCode) {
    emitJson({ ok: false, stage: 'wait', error: '缺少 device_code' });
    process.exit(1);
  }
  const res = await makeRequest('POST', '/api/v1/auth/device-auth/poll', { device_code: deviceCode });
  const data = res.data || {};
  // 授权完成
  if (data.code === 0 && data.data && data.data.api_key) {
    saveCredentials(data.data.api_key, data.data.platform_user_id || data.data.user_id);
    emitJson({ ok: true, stage: 'wait', status: 'authorized', message: '授权成功，凭证已保存。' });
    return;
  }
  // 待授权（继续轮询）
  emitJson({
    ok: true,
    stage: 'wait',
    status: 'pending',
    retry_after_seconds: (data.data && data.data.interval) || 5,
    required_next_command: `node scripts/auth.js --wait ${deviceCode}`,
    detail: data.message || 'authorization_pending',
  });
}

function check() {
  const cred = readCredentials();
  if (cred && cred.api_key && cred.platform_user_id) {
    emitJson({ ok: true, stage: 'check', authorized: true });
  } else {
    emitJson({ ok: true, stage: 'check', authorized: false, hint: '运行 node scripts/auth.js --start 开始授权。' });
  }
}

function reset() {
  try { fs.unlinkSync(AUTH_FILE); } catch (_) {}
  emitJson({ ok: true, stage: 'reset', message: '凭证已清除。' });
}

async function main() {
  const argv = process.argv.slice(2);
  const cmd = argv[0];
  try {
    if (cmd === '--start') {
      const pIdx = argv.indexOf('--platform');
      await start(pIdx !== -1 ? argv[pIdx + 1] : 'openclaw');
    } else if (cmd === '--wait') {
      await wait(argv[1]);
    } else if (cmd === '--check') {
      check();
    } else if (cmd === '--reset') {
      reset();
    } else {
      emitJson({ ok: false, error: 'usage: auth.js --start|--wait <device_code>|--check|--reset' });
      process.exit(1);
    }
  } catch (e) {
    emitJson({ ok: false, error: String(e && e.message || e) });
    process.exit(1);
  }
}

main();
