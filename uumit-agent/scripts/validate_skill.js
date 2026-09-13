#!/usr/bin/env node
/**
 * UUMit Skill v2.7.0 — 套件自检脚本。
 *
 * 校验:
 *   - manifest.files 中声明的文件都存在
 *   - manifest / SKILL.md frontmatter / metadata 三处 version 一致
 *   - smart-invoke 必须在 rest_request.js 的 allowlist 中（K1-3 硬要求）
 *   - 文档中登记的 REST 路由被 allowlist 覆盖（未覆盖目前为 warning，K1-6 将升为 error）
 *
 * 输出: stdout=JSON（成功）；stderr=JSON（失败）。errors 非空时退出码 1。
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SKILL_DIR = path.resolve(__dirname, '..');
const MANIFEST_PATH = path.join(SKILL_DIR, 'manifest.json');
const SKILL_PATH = path.join(SKILL_DIR, 'SKILL.md');
const REST_PATH = path.join(SKILL_DIR, 'scripts', 'rest_request.js');
// 扩展与基座同级并列。优先用 UUMIT_SKILL_DIR 定位基座，再取父目录作为扩展根。
const BASE_DIR = process.env.UUMIT_SKILL_DIR
  ? path.resolve(process.env.UUMIT_SKILL_DIR)
  : SKILL_DIR;
const SKILLS_ROOT = path.resolve(BASE_DIR, '..');
const BASE_NAME = 'uumit-agent';
// 扩展共享内存的约定路径（精确匹配）。
const EXPECTED_SHARED_MEMORY = '${UUMIT_SKILL_DIR}/memory/';

const DOC_FILES = [
  'SKILL.md', 'PLAYBOOKS.md', 'INTEROP.md', 'API_REFERENCE.md',
  'DEEP_LINKS.md', 'HOSTS.md', 'SAFETY.md', 'TROUBLESHOOTING.md',
];

const SMART_INVOKE_PATH = '/api/v1/capability-runtime/smart-invoke';
const DISCOVER_PATH = '/api/v1/capability-runtime/discover';

function extractFrontmatterVersion(text) {
  const m = text.match(/^version:\s*([^\n\r]+)/m);
  return m ? m[1].trim() : null;
}

function extractMetadataVersion(text) {
  const line = text.split(/\r?\n/).find((l) => l.startsWith('metadata: '));
  if (!line) return null;
  const metadata = JSON.parse(line.slice('metadata: '.length));
  return metadata.agent_skill && metadata.agent_skill.version;
}

function loadAllowlist() {
  const code = fs.readFileSync(REST_PATH, 'utf8');
  const start = code.indexOf('const ALLOWED_ROUTES = [');
  const end = code.indexOf('];', start);
  if (start === -1 || end === -1) throw new Error('ALLOWED_ROUTES block not found');
  const snippet = code.slice(start, end + 2) + '\nALLOWED_ROUTES;';
  return new vm.Script(snippet).runInNewContext({});
}

function normalizeEndpoint(raw) {
  let e = raw.trim();
  e = e.replace(/^https?:\/\/[^/]+/, '');
  e = e.replace(/\?[^`\s|)]*/g, '');
  e = e.replace(/\{[a-zA-Z0-9_]+\}/g, '00000000-0000-0000-0000-000000000000');
  e = e.replace(/<[^>]+>/g, '00000000-0000-0000-0000-000000000000');
  return e;
}

function collectDocumentedRoutes() {
  const routes = [];
  const seen = new Set();
  for (const file of DOC_FILES) {
    const fp = path.join(SKILL_DIR, file);
    if (!fs.existsSync(fp)) continue;
    const text = fs.readFileSync(fp, 'utf8');
    for (const line of text.split(/\r?\n/)) {
      const spans = [...line.matchAll(/`([^`]+)`/g)].map((m) => m[1].trim());
      for (let i = 0; i < spans.length - 1; i++) {
        if (/^(GET|POST|PUT|PATCH|DELETE)$/.test(spans[i])) {
          const endpoint = normalizeEndpoint(spans[i + 1].split(/\s+/)[0]);
          if (!endpoint.startsWith('/') || endpoint.includes('...')) continue;
          const key = `${file}:${spans[i]}:${endpoint}`;
          if (seen.has(key)) continue;
          seen.add(key);
          routes.push({ file, method: spans[i], endpoint });
        }
      }
      const inline = [...line.matchAll(/`(GET|POST|PUT|PATCH|DELETE)\s+([^`]+)`/g)];
      for (const m of inline) {
        const endpoint = normalizeEndpoint(m[2].split(/\s+/)[0]);
        if (!endpoint.startsWith('/') || endpoint.includes('...')) continue;
        const key = `${file}:${m[1]}:${endpoint}`;
        if (seen.has(key)) continue;
        seen.add(key);
        routes.push({ file, method: m[1], endpoint });
      }
    }
  }
  return routes;
}

function routeAllowed(allowlist, method, endpoint) {
  const clean = endpoint.split('?')[0];
  return allowlist.some(([m, re]) => m === method && re.test(clean));
}

function parseVersion(v) {
  return String(v || '').split('.').map((n) => parseInt(n, 10) || 0);
}

/** 判断 baseVersion 是否满足 `>=x.y.z` 形式的约束（仅支持 >= 与精确版本）。 */
function satisfiesBaseVersion(baseVersion, constraint) {
  if (!constraint) return true;
  const m = String(constraint).trim().match(/^(>=|=)?\s*([0-9.]+)$/);
  if (!m) return true; // 不识别的约束不阻断，交由人工判断
  const op = m[1] || '=';
  const want = parseVersion(m[2]);
  const have = parseVersion(baseVersion);
  for (let i = 0; i < Math.max(want.length, have.length); i++) {
    const a = have[i] || 0;
    const b = want[i] || 0;
    if (a > b) return true;
    if (a < b) return false;
  }
  return op === '>=' || op === '=';
}

/**
 * 扫描已安装扩展（基座同级、声明 requires.base_skill=uumit-agent），
 * 校验 base_version 兼容性与 shared_memory 指向基座 memory/。
 * 返回 { extensions: [...], errors: [...] }。
 */
function scanExtensions(baseVersion) {
  const extensions = [];
  const errors = [];
  let entries = [];
  try {
    entries = fs.readdirSync(SKILLS_ROOT, { withFileTypes: true });
  } catch (_) {
    return { extensions, errors };
  }
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const dir = path.join(SKILLS_ROOT, entry.name);
    if (path.resolve(dir) === path.resolve(BASE_DIR)) continue; // 跳过基座自身
    const mf = path.join(dir, 'manifest.json');
    if (!fs.existsSync(mf)) continue;
    let manifest;
    try {
      manifest = JSON.parse(fs.readFileSync(mf, 'utf8'));
    } catch (e) {
      errors.push(`extension ${entry.name}: manifest parse failed: ${e.message}`);
      continue;
    }
    const requires = manifest.requires || {};
    if (requires.base_skill !== BASE_NAME) continue; // 非本基座扩展，忽略

    if (!satisfiesBaseVersion(baseVersion, requires.base_version)) {
      errors.push(
        `extension ${manifest.name}: requires base ${requires.base_version}, but base is ${baseVersion}`
      );
    }

    if (manifest.shared_memory !== EXPECTED_SHARED_MEMORY) {
      errors.push(
        `extension ${manifest.name}: shared_memory 必须精确为 "${EXPECTED_SHARED_MEMORY}"，实际 "${manifest.shared_memory || 'missing'}"`
      );
    }

    extensions.push({
      name: manifest.name,
      version: manifest.version,
      base_version: requires.base_version || null,
      shared_memory: manifest.shared_memory || null,
    });
  }
  return { extensions, errors };
}

function main() {
  const errors = [];
  const warnings = [];

  let manifest;
  try {
    manifest = JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf8'));
  } catch (e) {
    errors.push(`manifest parse failed: ${e.message}`);
    manifest = { files: {} };
  }

  const requiredFiles = [
    ...DOC_FILES,
    'manifest.json',
    'scripts/install.js',
    'scripts/auth.js',
    'scripts/rest_request.js',
    'scripts/validate_skill.js',
    'memory/runtime/agent-autonomy-config.json',
  ];

  for (const file of requiredFiles) {
    if (!fs.existsSync(path.join(SKILL_DIR, file))) {
      errors.push(`required file missing: ${file}`);
    }
  }

  for (const file of Object.keys(manifest.files || {})) {
    if (!fs.existsSync(path.join(SKILL_DIR, file))) {
      errors.push(`manifest file missing: ${file}`);
    }
  }

  for (const file of requiredFiles) {
    if (!manifest.files || !manifest.files[file]) {
      errors.push(`manifest missing required file entry: ${file}`);
    }
  }

  const skillText = fs.existsSync(SKILL_PATH) ? fs.readFileSync(SKILL_PATH, 'utf8') : '';
  const frontmatterVersion = extractFrontmatterVersion(skillText);
  let metadataVersion = null;
  try {
    metadataVersion = extractMetadataVersion(skillText);
  } catch (e) {
    errors.push(`metadata version parse failed: ${e.message}`);
  }

  const versions = [
    ['manifest', manifest.version],
    ['frontmatter', frontmatterVersion],
    ['metadata', metadataVersion],
  ];
  const distinct = new Set(versions.map(([, v]) => v).filter(Boolean));
  if (distinct.size !== 1) {
    errors.push(`version mismatch: ${versions.map(([k, v]) => `${k}=${v || 'missing'}`).join(', ')}`);
  }

  let allowlist = [];
  try {
    allowlist = loadAllowlist();
  } catch (e) {
    errors.push(`allowlist load failed: ${e.message}`);
  }

  // K1-3 硬要求：smart-invoke 必须放行
  if (!routeAllowed(allowlist, 'POST', SMART_INVOKE_PATH)) {
    errors.push('smart-invoke not in allowlist (K1-3 required)');
  }

  // 动态能力发现（批次 0 / 防线 1）：discover 是发现命门端点，必须放行。
  if (!routeAllowed(allowlist, 'POST', DISCOVER_PATH)) {
    errors.push('capability-runtime/discover not in allowlist (dynamic capability discovery required)');
  }
  // 若提供了 discover 薄封装脚本，SKILL.md 应含"动态能力发现"段，保证触发文档同源。
  const discoverScript = path.join(SKILL_DIR, 'scripts', 'capability_discover.js');
  if (fs.existsSync(discoverScript)) {
    const skillText = fs.existsSync(SKILL_PATH) ? fs.readFileSync(SKILL_PATH, 'utf8') : '';
    if (!skillText.includes('动态能力发现')) {
      warnings.push('capability_discover.js exists but SKILL.md lacks "动态能力发现" section (weak-intent trigger doc)');
    }
  }

  const documentedRoutes = collectDocumentedRoutes();
  for (const route of documentedRoutes) {
    if (!routeAllowed(allowlist, route.method, route.endpoint)) {
      errors.push(`documented route not in allowlist: ${route.method} ${route.endpoint} (${route.file})`);
    }
  }

  const restText = fs.existsSync(REST_PATH) ? fs.readFileSync(REST_PATH, 'utf8') : '';
  if (!restText.includes('loadAutoSpendMaxUt') || !restText.includes('spend') || !restText.includes('auto_spend_max_ut')) {
    errors.push('rest_request.js does not use unified spend.auto_spend_max_ut config');
  }
  if (!restText.includes('loadDailyMaxUt') || !restText.includes('daily_max_ut') || !restText.includes('daily_ledger_path')) {
    errors.push('rest_request.js does not use unified spend.daily_max_ut config');
  }

  try {
    const autonomy = JSON.parse(fs.readFileSync(path.join(SKILL_DIR, 'memory', 'runtime', 'agent-autonomy-config.json'), 'utf8'));
    const threshold = autonomy.spend && autonomy.spend.auto_spend_max_ut;
    if (typeof threshold !== 'number' || !Number.isFinite(threshold) || threshold < 0) {
      errors.push('invalid spend.auto_spend_max_ut in agent-autonomy-config.json');
    }
    const dailyMax = autonomy.spend && autonomy.spend.daily_max_ut;
    if (typeof dailyMax !== 'number' || !Number.isFinite(dailyMax) || dailyMax <= 0) {
      errors.push('invalid spend.daily_max_ut in agent-autonomy-config.json');
    }
  } catch (e) {
    errors.push(`agent-autonomy-config parse failed: ${e.message}`);
  }

  // 扫描已安装扩展并校验与基座的兼容性。
  const { extensions, errors: extErrors } = scanExtensions(manifest.version);
  for (const e of extErrors) errors.push(e);

  const result = {
    ok: errors.length === 0,
    errors,
    warnings,
    checked: {
      manifest_files: Object.keys(manifest.files || {}).length,
      documented_routes: documentedRoutes.length,
      extensions: extensions.length,
    },
    extensions,
  };

  const output = JSON.stringify(result, null, 2);
  if (errors.length > 0) {
    console.error(output);
    process.exit(1);
  }
  console.log(output);
}

main();
