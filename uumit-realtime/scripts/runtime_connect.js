#!/usr/bin/env node
/**
 * uumit-realtime — Agent Runtime SSE 长连接脚本（v2.1.2）。
 *
 * 业务意图（源自 1.x runtime_connect.js，按 2.x 凭证契约重写）：
 *   建立并维持与平台 GET /api/v1/agent-runtime/connect 的 SSE 长连接，
 *   接收智能体任务（job_dispatch）、Agent 间消息（agent_msg）与状态变更。
 *   与巡航独立并存：SSE 负责实时推送，uumit-cruise 负责定期对账。
 *
 * 设计约束（见设计方案 9.2 步骤 7，SSE 为受控例外）：
 *   - rest_request.js 为一次性请求模型，无法承载 SSE 长连接，故本扩展自建连接。
 *   - 但凭证与 base_url 必须复用基座契约（auth.api_key / auth.platform_user_id、
 *     memory/uumit-config.json.base_url），不得另起一套（剔除 1.x 的 cached_* 字段）。
 *
 * 用法:
 *   node runtime_connect.js                          # stdout 每事件一行 JSON
 *   node runtime_connect.js --last-event-id <id>     # 断线续传
 *   node runtime_connect.js --max-reconnect-delay 30 # 最大重连间隔（秒）
 *
 * stdout: 每个 SSE 事件一行 JSON（heartbeat 静默）；stderr: 连接状态日志。
 * 退出码: 0=正常退出（SIGINT/SIGTERM）；2=认证失败不重连。
 */

const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');

// 通过 UUMIT_SKILL_DIR 定位基座；未设置时回退到与本扩展并列的 uumit-agent。
const BASE_DIR = process.env.UUMIT_SKILL_DIR
  ? path.resolve(process.env.UUMIT_SKILL_DIR)
  : path.resolve(__dirname, '..', '..', 'uumit-agent');
const SHARED_MEMORY = path.join(BASE_DIR, 'memory');
const AUTH_FILE = path.join(SHARED_MEMORY, 'uumit-auth.json');
const CONFIG_FILE = path.join(SHARED_MEMORY, 'uumit-config.json');

const DEFAULT_MAX_RECONNECT_DELAY = 30;
const INITIAL_RECONNECT_DELAY = 1;

function log(msg) { console.error(`[realtime] ${msg}`); }
function emitStdout(obj) { process.stdout.write(JSON.stringify(obj) + '\n'); }

// 复用基座凭证契约：环境变量优先，否则读基座共享 memory/uumit-auth.json。
function loadCredentials() {
  let apiKey = process.env.UUMIT_API_KEY || '';
  let userId = process.env.UUMIT_USER_ID || '';
  if (apiKey && userId) return { apiKey, userId };
  try {
    const auth = JSON.parse(fs.readFileSync(AUTH_FILE, 'utf8'));
    apiKey = apiKey || auth.api_key || '';
    userId = userId || auth.platform_user_id || auth.user_id || '';
  } catch (_) {}
  return { apiKey, userId };
}

// 复用基座 base_url 契约：环境变量 > 共享 config > 默认。
function resolveBaseUrl() {
  if (process.env.UUMIT_BASE_URL) return process.env.UUMIT_BASE_URL;
  try {
    const cfg = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8'));
    if (cfg.base_url) return cfg.base_url;
  } catch (_) {}
  return 'https://api.uumit.com';
}

const BASE_URL = resolveBaseUrl();
const baseUrlObj = new URL(BASE_URL);
const isHttps = baseUrlObj.protocol === 'https:';

function parseArgs() {
  const args = process.argv.slice(2);
  const opts = { lastEventId: null, maxReconnectDelay: DEFAULT_MAX_RECONNECT_DELAY };
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--last-event-id' && args[i + 1]) {
      opts.lastEventId = args[++i];
    } else if (args[i] === '--max-reconnect-delay' && args[i + 1]) {
      opts.maxReconnectDelay = Math.max(1, parseInt(args[++i], 10) || DEFAULT_MAX_RECONNECT_DELAY);
    }
  }
  return opts;
}

class AuthError extends Error { constructor(m) { super(m); this.name = 'AuthError'; } }
class RetryError extends Error { constructor(m, r) { super(m); this.name = 'RetryError'; this.retryAfter = r; } }

// 最小 SSE 解析器：按 SSE 规范切分 event/data/id。
class SSEParser {
  constructor(onEvent) {
    this.onEvent = onEvent;
    this._buffer = '';
    this._eventType = '';
    this._data = '';
    this._id = '';
  }
  feed(chunk) {
    this._buffer += chunk;
    const lines = this._buffer.split('\n');
    this._buffer = lines.pop() || '';
    for (const line of lines) {
      if (line === '' || line === '\r') {
        this._dispatch();
      } else if (line.startsWith('event:')) {
        this._eventType = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        this._data += (this._data ? '\n' : '') + line.slice(5).trim();
      } else if (line.startsWith('id:')) {
        this._id = line.slice(3).trim();
      }
    }
  }
  _dispatch() {
    if (this._data || this._eventType) {
      this.onEvent({ event: this._eventType || 'message', data: this._data, id: this._id });
    }
    this._eventType = '';
    this._data = '';
  }
}

function connect(opts, credentials) {
  return new Promise((resolve, reject) => {
    const { apiKey, userId } = credentials;
    let urlPath = '/api/v1/agent-runtime/connect';
    if (opts.lastEventId) urlPath += `?last_event_id=${encodeURIComponent(opts.lastEventId)}`;

    const urlObj = new URL(BASE_URL + urlPath);
    const requestOpts = {
      hostname: urlObj.hostname,
      port: urlObj.port || (isHttps ? 443 : 80),
      path: urlObj.pathname + urlObj.search,
      method: 'GET',
      headers: {
        Accept: 'text/event-stream',
        'X-Api-Key': apiKey,
        'X-Platform-User-Id': userId,
        'Cache-Control': 'no-cache',
      },
    };

    const mod = isHttps ? https : http;
    const req = mod.request(requestOpts, (res) => {
      if (res.statusCode === 401 || res.statusCode === 403) {
        const chunks = [];
        res.on('data', (c) => chunks.push(c));
        res.on('end', () => reject(new AuthError(`认证失败 (${res.statusCode})`)));
        return;
      }
      if (res.statusCode === 503) {
        const retryAfter = parseInt(res.headers['retry-after'] || '30', 10);
        reject(new RetryError('服务暂不可用 (503)', retryAfter));
        return;
      }
      if (res.statusCode !== 200) {
        reject(new Error(`意外状态码: ${res.statusCode}`));
        return;
      }
      resolve(res);
    });
    req.on('error', (e) => reject(e));
    req.setTimeout(0); // SSE 长连接不设超时
    req.end();
  });
}

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

// 父进程死亡自杀守卫：宿主被强杀/崩溃且未向本子进程发信号时，主循环是无限重连、
// 会形成「Agent 已退但 SSE 仍假执行」的僵尸进程。故补一道守卫，父进程一旦消失即
// 自杀退出（退出码 0，与 SIGTERM 同路径），不依赖宿主一定发信号。
function installParentDeathGuard() {
  let dying = false;
  const suicide = (reason) => {
    if (dying) return;
    dying = true;
    log(`父进程已消失（${reason}），自杀退出以避免僵尸重连。`);
    process.exit(0);
  };

  // 主判据 · stdout 管道断裂：宿主以子进程方式拉起时 stdout 连到宿主管道，
  // 父进程消失后写 stdout 触发 EPIPE；监听 error(EPIPE) 与 close 即判定父亡。
  process.stdout.on('error', (e) => {
    if (e && (e.code === 'EPIPE' || e.code === 'ERR_STREAM_DESTROYED')) suicide('stdout EPIPE');
  });
  process.stdout.on('close', () => suicide('stdout close'));

  // 辅助判据 · ppid 变化轮询：某些宿主不接管 stdout（如重定向到文件）时管道判据失效，
  // 低频比对 process.ppid 与启动时记录值，原父消失（被 init 收养/ppid 改变）即自杀。
  // Windows 上 process.ppid 恒定、变化判据可能不触发，此时仍由 stdout 主判据兜底。
  const initialPpid = process.ppid;
  const timer = setInterval(() => {
    if (process.ppid !== initialPpid) suicide(`ppid ${initialPpid}→${process.ppid}`);
  }, 30000);
  timer.unref(); // 不阻碍进程在其他路径下的自然退出
}

async function run() {
  const opts = parseArgs();
  const credentials = loadCredentials();
  if (!credentials.apiKey || !credentials.userId) {
    emitStdout({ ok: false, error: '未找到凭证。请先在基座完成授权（node scripts/auth.js）。' });
    process.exit(2);
  }

  let lastEventId = opts.lastEventId;
  let reconnectDelay = INITIAL_RECONNECT_DELAY;
  let stopping = false;

  const onSignal = () => { stopping = true; log('收到退出信号，关闭连接。'); process.exit(0); };
  process.on('SIGINT', onSignal);
  process.on('SIGTERM', onSignal);
  installParentDeathGuard(); // 父进程死亡自杀守卫（宿主未发信号时兜底，防僵尸重连）

  while (!stopping) {
    try {
      log(`连接 ${BASE_URL}/api/v1/agent-runtime/connect${lastEventId ? `（续传 ${lastEventId}）` : ''}`);
      const res = await connect({ ...opts, lastEventId }, credentials);
      reconnectDelay = INITIAL_RECONNECT_DELAY; // 连接成功后重置退避
      log('连接已建立。');
      // 向 stdout 发一条连接状态事件，供上游可靠感知“SSE 已连上”。
      // 非 capability.* / 非 ok:false，现有消费者会忽略，不破坏输出契约。
      emitStdout({ event: 'connection.open' });

      const parser = new SSEParser((evt) => {
        if (evt.id) lastEventId = evt.id;
        if (evt.event === 'heartbeat' || evt.event === 'ping') return; // 心跳静默
        let payload = evt.data;
        try { payload = JSON.parse(evt.data); } catch (_) {}
        emitStdout({ event: evt.event, id: evt.id || null, data: payload });
      });

      await new Promise((resolve, reject) => {
        res.setEncoding('utf8');
        res.on('data', (chunk) => parser.feed(chunk));
        res.on('end', () => resolve());
        res.on('error', (e) => reject(e));
      });

      log('连接结束，准备重连。');
    } catch (e) {
      if (e instanceof AuthError) {
        emitStdout({ ok: false, error: e.message, retryable: false });
        process.exit(2);
      }
      const wait = e instanceof RetryError ? e.retryAfter : reconnectDelay;
      log(`连接失败：${e.message}，${wait}s 后重连。`);
      // 向 stdout 发一条连接失败事件，供上游自回退监督累计失败次数（普通失败仍会重连，不退出）。
      emitStdout({ event: 'connection.failed', retryable: true });
      await sleep(wait * 1000);
      reconnectDelay = Math.min(opts.maxReconnectDelay, reconnectDelay * 2); // 指数退避
    }
  }
}

run();
