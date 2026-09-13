#!/usr/bin/env node
/**
 * uumit-publisher — 文件上传与批量发布薄编排脚本（v2.1.2）。
 *
 * 业务意图（源自 1.x upload_file.js / batch_publish.js / batch_upload.js，按 2.x 契约重写）：
 *   - upload：上传单个文件（multipart），返回可用于上架的文件 URL。
 *   - create-asset：上传文件 → quick-upload 创建知识商店资产（1.x 两步上架闭环）。
 *   - batch-publish：枚举我的数字资产并批量发布（草稿/已分析 → 已发布）。
 *
 * 设计约束（见设计方案 9.2 步骤 8）：
 *   - 纯 JSON 调用（批量发布）走基座 rest_request.js，自动过 allowlist + 安全闸门。
 *   - 单文件上传为 multipart，基座 rest_request.js 的 JSON 通道不支持，故受控直传，
 *     但凭证与 base_url 完全复用基座契约（auth.api_key / auth.platform_user_id、config.base_url）。
 *
 * 用法:
 *   node publisher.js upload --file <path> [--folder <name>]
 *   node publisher.js create-asset --file <path> --cover <cover_image_url> [--preview-images '["url"]'] [--confirmed]
 *   node publisher.js batch-publish [--limit <n>] [--dry-run]
 *
 * 输出: stdout=JSON；stderr=诊断；非 0 退出码=失败。
 */

const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');
// 用当前 Node 解释器绝对路径拉起子脚本，避免宿主子进程 PATH 无 `node` 时报"找不到 node"。
const NODE_BIN = process.execPath;

// 通过 UUMIT_SKILL_DIR 定位基座；未设置时回退到与本扩展并列的 uumit-agent。
const BASE_DIR = process.env.UUMIT_SKILL_DIR
  ? path.resolve(process.env.UUMIT_SKILL_DIR)
  : path.resolve(__dirname, '..', '..', 'uumit-agent');
const REST_SCRIPT = path.join(BASE_DIR, 'scripts', 'rest_request.js');
const SHARED_MEMORY = path.join(BASE_DIR, 'memory');
const AUTH_FILE = path.join(SHARED_MEMORY, 'uumit-auth.json');
const CONFIG_FILE = path.join(SHARED_MEMORY, 'uumit-config.json');

function log(msg) { console.error(`[publisher] ${msg}`); }
function emit(payload) { process.stdout.write(JSON.stringify(payload, null, 2) + '\n'); }
function failCli(message) { emit({ ok: false, error: message }); process.exit(2); }

// 复用基座凭证契约（剔除 1.x 的 cached_* 字段）。
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

function resolveBaseUrl() {
  if (process.env.UUMIT_BASE_URL) return process.env.UUMIT_BASE_URL;
  try {
    const cfg = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8'));
    if (cfg.base_url) return cfg.base_url;
  } catch (_) {}
  return 'https://api.uumit.com';
}

const BASE_URL = resolveBaseUrl();

/** 纯 JSON 调用走基座 rest_request.js。带 body 时写会话隔离临时文件用 --file 传入。 */
function baseRequest(method, apiPath, body, opts) {
  if (!fs.existsSync(REST_SCRIPT)) {
    throw new Error(`base rest_request.js not found at ${REST_SCRIPT}（设置 UUMIT_SKILL_DIR 指向基座目录）`);
  }
  const cliArgs = [REST_SCRIPT, method, apiPath];
  let tmpFile = null;
  if (body && typeof body === 'object') {
    const dir = path.join(SHARED_MEMORY, 'sessions', 'publisher');
    fs.mkdirSync(dir, { recursive: true });
    tmpFile = path.join(dir, `request-${crypto.randomBytes(6).toString('hex')}.json`);
    fs.writeFileSync(tmpFile, JSON.stringify(body), 'utf8');
    cliArgs.push('--file', tmpFile);
  }
  if (opts && opts.confirmed) cliArgs.push('--confirmed');
  try {
    const out = execFileSync(NODE_BIN, cliArgs, { encoding: 'utf8', timeout: 60000 });
    return out ? JSON.parse(out) : null;
  } finally {
    if (tmpFile) { try { fs.unlinkSync(tmpFile); } catch (_) {} }
  }
}

// ---------------------------------------------------------------------------
// upload：单文件 multipart 受控直传（基座 JSON 通道不支持 multipart）
// ---------------------------------------------------------------------------
function uploadFile(filePath, folder, credentials) {
  return new Promise((resolve, reject) => {
    const fileName = path.basename(filePath);
    const fileBuf = fs.readFileSync(filePath);
    const boundary = `----uumit${crypto.randomBytes(12).toString('hex')}`;

    const parts = [];
    if (folder) {
      parts.push(Buffer.from(
        `--${boundary}\r\nContent-Disposition: form-data; name="folder"\r\n\r\n${folder}\r\n`
      ));
    }
    parts.push(Buffer.from(
      `--${boundary}\r\n` +
      `Content-Disposition: form-data; name="file"; filename="${fileName}"\r\n` +
      `Content-Type: application/octet-stream\r\n\r\n`
    ));
    parts.push(fileBuf);
    parts.push(Buffer.from(`\r\n--${boundary}--\r\n`));
    const body = Buffer.concat(parts);

    const urlObj = new URL(BASE_URL + '/api/v1/upload/file');
    const isHttps = urlObj.protocol === 'https:';
    const mod = isHttps ? https : http;
    const req = mod.request({
      hostname: urlObj.hostname,
      port: urlObj.port || (isHttps ? 443 : 80),
      path: urlObj.pathname,
      method: 'POST',
      headers: {
        'Content-Type': `multipart/form-data; boundary=${boundary}`,
        'Content-Length': body.length,
        'X-Api-Key': credentials.apiKey,
        'X-Platform-User-Id': credentials.userId,
      },
      timeout: 120000,
    }, (res) => {
      const chunks = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () => {
        const raw = Buffer.concat(chunks).toString('utf8');
        let parsed = null;
        try { parsed = JSON.parse(raw); } catch (_) { parsed = raw; }
        resolve({ statusCode: res.statusCode, data: parsed });
      });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(new Error('upload timeout')); });
    req.write(body);
    req.end();
  });
}

async function runUpload(args) {
  let filePath = null;
  let folder = null;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--file' && args[i + 1]) filePath = args[++i];
    else if (args[i] === '--folder' && args[i + 1]) folder = args[++i];
    else failCli(`unknown or incomplete argument: ${args[i]}`);
  }
  if (!filePath) failCli('--file is required');
  if (!fs.existsSync(filePath)) failCli(`file not found: ${filePath}`);

  const credentials = loadCredentials();
  if (!credentials.apiKey || !credentials.userId) {
    failCli('未找到凭证。请先在基座完成授权（node scripts/auth.js）。');
  }

  log(`上传文件 ${filePath}（multipart 受控直传）...`);
  const res = await uploadFile(filePath, folder, credentials);
  if (res.statusCode !== 200 || !res.data || res.data.code !== 0) {
    emit({ ok: false, status: 'upload_failed', http: res.statusCode, detail: res.data });
    process.exit(1);
  }
  emit({ ok: true, status: 'uploaded', file: res.data.data });
}

// ---------------------------------------------------------------------------
// batch-publish：纯 JSON 编排，走基座 rest_request.js
// ---------------------------------------------------------------------------
function runBatchPublish(args) {
  let limit = 20;
  let dryRun = false;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--limit' && args[i + 1]) limit = Math.max(1, parseInt(args[++i], 10) || 20);
    else if (args[i] === '--dry-run') dryRun = true;
    else failCli(`unknown or incomplete argument: ${args[i]}`);
  }

  log('枚举我的数字资产（经基座 rest_request.js）...');
  let listResp;
  try {
    listResp = baseRequest('GET', `/api/v1/digital-assets?page=1&page_size=${limit}`);
  } catch (e) {
    failCli(`list failed: ${e.message}`);
  }
  const items = (listResp && listResp.code === 0 && listResp.data && listResp.data.items) || [];

  // 仅发布尚未发布的资产（草稿/已分析）。
  const pending = items.filter((a) => a.status && a.status !== 'published');
  const results = [];

  for (const asset of pending) {
    if (dryRun) {
      results.push({ asset_id: asset.id, title: asset.title, action: 'would_publish' });
      continue;
    }
    // publish 为"发布时可携带封面/价格/标题等覆盖字段"的合一接口，服务端对
    // cover_image_url 有必填校验（空 body 会 422）。列表接口已返回 cover_image_url，
    // 直接回填；无封面（如 draft 未填）的资产无法发布，跳过并提示补封面。
    if (!asset.cover_image_url) {
      results.push({
        asset_id: asset.id, title: asset.title, skipped: 'missing cover_image_url',
        hint: '请先为资产补充封面（create-asset 带 cover_image_url 或 updateAssetMedia）后重试',
      });
      continue;
    }
    try {
      const body = { cover_image_url: asset.cover_image_url };
      if (Array.isArray(asset.preview_images) && asset.preview_images.length) body.preview_images = asset.preview_images;
      const pub = baseRequest('POST', `/api/v1/digital-assets/${asset.id}/publish`, body);
      results.push({ asset_id: asset.id, title: asset.title, ok: pub && pub.code === 0, detail: pub && pub.message });
    } catch (e) {
      results.push({ asset_id: asset.id, title: asset.title, ok: false, error: e.message });
    }
  }

  emit({
    ok: true,
    dry_run: dryRun,
    total_assets: items.length,
    pending_count: pending.length,
    results,
    agent_hint: '批量发布为写操作，已逐个经基座安全闸门。向用户汇报结果摘要，不要粘贴原始输出。',
  });
}

// ---------------------------------------------------------------------------
// create-asset：上传文件 → quick-upload 创建知识商店资产（1.x 两步流程闭环）
// ---------------------------------------------------------------------------
async function runCreateAsset(args) {
  let filePath = null;
  let coverUrl = null;
  let previewImages = null;
  let confirmed = false;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--file' && args[i + 1]) filePath = args[++i];
    else if (args[i] === '--cover' && args[i + 1]) coverUrl = args[++i];
    else if (args[i] === '--preview-images' && args[i + 1]) previewImages = args[++i];
    else if (args[i] === '--confirmed') confirmed = true;
    else failCli(`unknown or incomplete argument: ${args[i]}`);
  }
  if (!filePath) failCli('--file is required');
  if (!fs.existsSync(filePath)) failCli(`file not found: ${filePath}`);
  if (!coverUrl) failCli('--cover is required（cover_image_url 为知识商品封面，必填，不得用纯文字占位图）');

  const credentials = loadCredentials();
  if (!credentials.apiKey || !credentials.userId) {
    failCli('未找到凭证。请先在基座完成授权（node scripts/auth.js）。');
  }

  // 第一步：上传文件到 OSS（multipart 受控直传）。
  log(`第一步：上传文件 ${filePath} 到 OSS...`);
  const up = await uploadFile(filePath, 'attachments', credentials);
  if (up.statusCode !== 200 || !up.data || up.data.code !== 0 || !up.data.data) {
    emit({ ok: false, status: 'upload_failed', http: up.statusCode, detail: up.data });
    process.exit(1);
  }
  const f = up.data.data;
  const body = {
    storage_key: f.filename,
    file_name: path.basename(filePath),
    file_size: f.size,
    file_type: f.content_type,
    cover_image_url: coverUrl,
  };
  if (previewImages) {
    try { body.preview_images = JSON.parse(previewImages); }
    catch (_) { failCli('--preview-images 必须是 JSON 数组字符串，如 \'["url1","url2"]\''); }
  }

  // 第二步：quick-upload 创建资产（L4 写操作，基座闸门要求 --confirmed）。
  log('第二步：quick-upload 创建知识商店资产（经基座安全闸门）...');
  let created;
  try {
    created = baseRequest('POST', '/api/v1/digital-assets/quick-upload', body, { confirmed });
  } catch (e) {
    failCli(`quick-upload failed: ${e.message}`);
  }
  const ok = created && created.code === 0;
  emit({
    ok,
    status: ok ? 'asset_created' : 'quick_upload_failed',
    file: f,
    asset: ok ? created.data : undefined,
    detail: ok ? undefined : (created && created.message),
    agent_hint: ok
      ? '资产已创建。向用户汇报标题/状态与详情链接，不要粘贴原始输出。'
      : '仅完成 OSS 上传，资产未创建。未带 --confirmed 会被基座以 knowledge_asset_publish_requires_confirm 阻断；确认价格与封面后重试。',
  });
  if (!ok) process.exit(1);
}

// ---------------------------------------------------------------------------
function main() {
  const [sub, ...rest] = process.argv.slice(2);
  switch (sub) {
    case 'upload': return runUpload(rest);
    case 'create-asset': return runCreateAsset(rest);
    case 'batch-publish': return runBatchPublish(rest);
    default:
      failCli(`unknown subcommand: ${sub || '(none)'}（可用：upload | create-asset | batch-publish）`);
  }
}

main();
