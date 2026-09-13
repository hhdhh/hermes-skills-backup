#!/usr/bin/env node
'use strict';
/**
 * update_check.js — 宿主端自动检查 + 受确认的更新（v2.7.0）。
 *
 * 设计目标（见设计方案 4.4 + 本次需求）：
 *   - 「自动检查」：从 OSS 套件总清单 index.json 拉取各 skill 最新版本，与本地
 *     manifest.version 比对，判断是否有新版。多入口（cruise / install / discover /
 *     手动）调用，失败静默不阻断主流程。
 *   - 「受确认的更新」：默认只检查并提示，绝不擅自改文件；仅当显式 --apply 时才
 *     下载 zip、校验 sha256、解压覆盖，并始终保留 memory/（manifest.update.preserve）。
 *   - 无节流：每次调用都真实联网拉取 index.json 比对（版本检查开销可忽略；节流缓存已移除）。
 *
 * 不自带复杂依赖：仅用 Node 内置模块 + 系统解压（Windows: Expand-Archive；Unix: unzip）。
 *
 * 用法:
 *   node update_check.js                 # 主动检查一次，输出是否有新版（不改文件）
 *   node update_check.js --refresh       # 后台定时任务入口：检查一次；开启 auto_update 时到点自动应用
 *   node update_check.js --apply         # 检测到新版后下载并覆盖（保留 memory/），需用户/Agent 已确认
 *   node update_check.js --apply --yes   # 同上，跳过「需确认」提示（调用方已替用户确认）
 *   node update_check.js --index-url <u> # 覆盖 index.json 地址（默认据 manifest.base_url 推导）
 *
 * 输出: stdout=JSON（供 Agent 解析）；stderr=诊断；非 0 退出码=失败。
 *   { ok, stage:'update-check', current_version, latest_version, has_update,
 *     skills:[{name,role,local,remote,has_update}], applied, agent_hint }
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const https = require('https');
const http = require('http');
const crypto = require('crypto');
const { spawnSync } = require('child_process');

const SKILL_DIR = path.resolve(__dirname, '..');
const MANIFEST_PATH = path.join(SKILL_DIR, 'manifest.json');
// 基座与扩展并列；优先 UUMIT_SKILL_DIR 定位基座，其父目录为套件根。
const BASE_DIR = process.env.UUMIT_SKILL_DIR ? path.resolve(process.env.UUMIT_SKILL_DIR) : SKILL_DIR;
const SKILLS_ROOT = path.resolve(BASE_DIR, '..');
// auto_update 开关来源（opt-in，默认 false）：随 --refresh 从 cruise.js 迁入。
const AUTONOMY_FILE = path.join(BASE_DIR, 'memory', 'runtime', 'agent-autonomy-config.json');
// --refresh 的「最近一次执行摘要」结果文件（供 Agent 只读转述、禁编造）。
const LAST_RUN_UPDATE_FILE = path.join(BASE_DIR, 'memory', 'runtime', 'last-run-update.json');
const FETCH_TIMEOUT = 15000;
const BASE_NAME = 'uumit-agent';

function emit(payload) {
  process.stdout.write(JSON.stringify(payload, null, 2) + '\n');
}

function log(msg) {
  process.stderr.write(msg + '\n');
}

function parseArgs(argv) {
  const out = { apply: false, yes: false, refresh: false, indexUrl: null };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === '--apply') out.apply = true;
    else if (a === '--yes') out.yes = true;
    else if (a === '--refresh') out.refresh = true;
    else if (a === '--index-url') out.indexUrl = argv[++i];
  }
  return out;
}

function readJson(filePath, fallback) {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch (_) {
    return fallback;
  }
}

function sha256File(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

/** 读取 auto_update.enabled 开关（opt-in，默认 false）。文件缺失/解析失败一律视为关闭。 */
function isAutoUpdateEnabled() {
  const cfg = readJson(AUTONOMY_FILE, {});
  return Boolean(cfg && cfg.auto_update && cfg.auto_update.enabled === true);
}

/**
 * 写 --refresh 的「最近一次执行摘要」结果文件（供 Agent 只读转述、禁编造）。
 * 写入失败静默（不阻断主流程），避免结果落盘异常影响检查本身。
 */
function writeLastRunUpdate(payload) {
  try {
    fs.mkdirSync(path.dirname(LAST_RUN_UPDATE_FILE), { recursive: true });
    fs.writeFileSync(
      LAST_RUN_UPDATE_FILE,
      JSON.stringify({ ran_at: new Date().toISOString(), ...payload }, null, 2) + '\n',
    );
  } catch (_) {
    /* 结果文件写入失败不阻断更新检查 */
  }
}

/** 解析语义版本为数字数组，缺位补 0。 */
function parseVersion(v) {
  return String(v || '0').split('.').map((n) => parseInt(n, 10) || 0);
}

/** a > b 返回 1，a < b 返回 -1，相等返回 0。 */
function compareVersion(a, b) {
  const va = parseVersion(a);
  const vb = parseVersion(b);
  for (let i = 0; i < Math.max(va.length, vb.length); i += 1) {
    const x = va[i] || 0;
    const y = vb[i] || 0;
    if (x > y) return 1;
    if (x < y) return -1;
  }
  return 0;
}

/**
 * 推导 index.json 地址：优先 --index-url / UUMIT_INDEX_URL；否则据基座 manifest.base_url
 * 拼出 <base_url>/v2/index.json（base_url 形如 https://oss.uumit.com/skills/）。
 */
function resolveIndexUrl(cliUrl) {
  if (cliUrl) return cliUrl;
  if (process.env.UUMIT_INDEX_URL) return process.env.UUMIT_INDEX_URL;
  const manifest = readJson(MANIFEST_PATH, {});
  const base = String(manifest.base_url || 'https://oss.uumit.com/skills/').replace(/\/+$/, '');
  return `${base}/v2/index.json`;
}

/** GET 一个 URL，跟随最多 3 次重定向，返回 Buffer。 */
function fetchUrl(url, redirects = 3) {
  return new Promise((resolve, reject) => {
    let u;
    try {
      u = new URL(url);
    } catch (e) {
      return reject(new Error(`无效 URL：${url}`));
    }
    const lib = u.protocol === 'http:' ? http : https;
    const req = lib.get(u, { timeout: FETCH_TIMEOUT }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location && redirects > 0) {
        res.resume();
        const next = new URL(res.headers.location, u).toString();
        return resolve(fetchUrl(next, redirects - 1));
      }
      if (res.statusCode !== 200) {
        res.resume();
        return reject(new Error(`HTTP ${res.statusCode} for ${url}`));
      }
      const chunks = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () => resolve(Buffer.concat(chunks)));
    });
    req.on('timeout', () => req.destroy(new Error(`请求超时：${url}`)));
    req.on('error', reject);
  });
}

/** 发现本地已安装 skill（基座 + 与基座同级、声明 requires.base_skill=uumit-agent 的扩展）。 */
function discoverLocalSkills() {
  const skills = [];
  const baseManifest = readJson(path.join(BASE_DIR, 'manifest.json'), null);
  if (baseManifest) {
    skills.push({ name: baseManifest.name, role: 'base', dir: BASE_DIR, manifest: baseManifest });
  }
  let entries = [];
  try {
    entries = fs.readdirSync(SKILLS_ROOT, { withFileTypes: true });
  } catch (_) {
    return skills;
  }
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const dir = path.join(SKILLS_ROOT, entry.name);
    if (path.resolve(dir) === path.resolve(BASE_DIR)) continue;
    const manifest = readJson(path.join(dir, 'manifest.json'), null);
    if (!manifest) continue;
    const requires = manifest.requires || {};
    if (requires.base_skill !== BASE_NAME) continue;
    skills.push({ name: manifest.name, role: 'extension', dir, manifest });
  }
  return skills;
}

/** 跨平台解压 zip 到目标目录（已存在则解压到临时目录后再覆盖式拷贝）。 */
function extractZip(zipPath, destDir) {
  fs.mkdirSync(destDir, { recursive: true });
  if (process.platform === 'win32') {
    const ps =
      `Expand-Archive -LiteralPath '${zipPath.replace(/'/g, "''")}' ` +
      `-DestinationPath '${destDir.replace(/'/g, "''")}' -Force`;
    const res = spawnSync('powershell', ['-NoProfile', '-NonInteractive', '-Command', ps], { encoding: 'utf8' });
    if (res.status !== 0) throw new Error(`Expand-Archive 失败：${(res.stderr || res.stdout || '').trim()}`);
  } else {
    const res = spawnSync('unzip', ['-o', '-q', zipPath, '-d', destDir], { encoding: 'utf8' });
    if (res.status !== 0) throw new Error(`unzip 失败：${(res.stderr || res.stdout || '').trim()}`);
  }
}

/** 递归覆盖式拷贝 src 到 dest，跳过 memory/（manifest.update.preserve）与 .zip。 */
function copyOverwrite(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    if (entry.name === 'memory' || entry.name.endsWith('.zip')) continue;
    const s = path.join(src, entry.name);
    const d = path.join(dest, entry.name);
    if (entry.isDirectory()) copyOverwrite(s, d);
    else fs.copyFileSync(s, d);
  }
}

/**
 * 下载并应用单个 skill 的更新：拉取 zip → 校验 sha256 → 解压到临时目录 → 覆盖到 skillDir
 * （保留 memory/）。返回 { name, ok, from, to, error? }。
 */
async function applySkillUpdate(localSkill, remoteSkill) {
  const result = { name: localSkill.name, from: localSkill.manifest.version, to: remoteSkill.version };
  if (!remoteSkill.zip || !remoteSkill.zip.url) {
    result.ok = false;
    result.error = '远程未提供 zip 下载地址';
    return result;
  }
  const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), `uumit-upd-${localSkill.name}-`));
  try {
    const zipPath = path.join(tmpRoot, remoteSkill.zip.name || `${localSkill.name}.zip`);
    const buf = await fetchUrl(remoteSkill.zip.url);
    fs.writeFileSync(zipPath, buf);
    if (remoteSkill.zip.sha256) {
      const actual = sha256File(zipPath);
      if (actual !== remoteSkill.zip.sha256) {
        result.ok = false;
        result.error = `zip sha256 不匹配（期望 ${remoteSkill.zip.sha256}，实际 ${actual}）`;
        return result;
      }
    }
    const extractDir = path.join(tmpRoot, 'extracted');
    extractZip(zipPath, extractDir);
    copyOverwrite(extractDir, localSkill.dir);
    result.ok = true;
    return result;
  } catch (e) {
    result.ok = false;
    result.error = String((e && e.message) || e);
    return result;
  } finally {
    try { fs.rmSync(tmpRoot, { recursive: true, force: true }); } catch (_) {}
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));

  const indexUrl = resolveIndexUrl(args.indexUrl);
  let index;
  try {
    const buf = await fetchUrl(indexUrl);
    index = JSON.parse(buf.toString('utf8'));
  } catch (e) {
    // 联网/解析失败：静默不阻断主流程，返回 ok:true 但标注 check_failed。
    const errMsg = String((e && e.message) || e);
    // --refresh 作为后台定时任务，须把"本次未取得结果/环境异常"落盘供 Agent 如实转述。
    if (args.refresh) {
      writeLastRunUpdate({
        status: 'error',
        env_error: true,
        current_version: null,
        latest_version: null,
        has_update: false,
        applied: false,
        error: errMsg,
      });
    }
    emit({
      ok: true,
      stage: 'update-check',
      check_failed: true,
      index_url: indexUrl,
      error: errMsg,
      has_update: false,
      applied: false,
      agent_hint: '版本检查失败（网络或地址问题），静默跳过，不影响本地流程。',
    });
    return;
  }

  const remoteByName = new Map((index.skills || []).map((s) => [s.name, s]));
  const localSkills = discoverLocalSkills();

  const skillsReport = [];
  let anyUpdate = false;
  for (const local of localSkills) {
    const remote = remoteByName.get(local.name);
    const localVer = local.manifest.version;
    const remoteVer = remote ? remote.version : null;
    const hasUpdate = Boolean(remoteVer && compareVersion(remoteVer, localVer) > 0);
    if (hasUpdate) anyUpdate = true;
    skillsReport.push({ name: local.name, role: local.role, local: localVer, remote: remoteVer, has_update: hasUpdate });
  }

  // 汇报口径：current/latest_version 默认反映基座；但当有更新的是某个扩展而非基座时，
  // 只报基座版本会让调用方（如 cruise）显示"版本号没变却说有更新"的失真结论。
  // 因此有更新时，优先把 current/latest 指向"有更新的那个 skill"，并在 hint 里列出具体 skill。
  const baseReport = skillsReport.find((s) => s.role === 'base') || {};
  const updatedReports = skillsReport.filter((s) => s.has_update);
  const primaryReport = updatedReports[0] || baseReport;
  const currentVersion = primaryReport.local || readJson(MANIFEST_PATH, {}).version || null;
  const latestVersion = primaryReport.remote || baseReport.remote || null;
  // 有更新的 skill 明细，形如 "uumit-cruise 2.1.2 → 2.1.3"，供 hint 直接转述。
  const updatedList = updatedReports.map((s) => `${s.name} ${s.local} → ${s.remote}`).join('、');

  // --refresh：面向后台定时任务的一次性入口。每次真实联网检查（上方已完成），
  // 再按 auto_update.enabled 决定是否自动应用更新（同进程内直接走内部 apply 路径，
  // 无需子进程调 --apply --yes）。last-run 结果文件见 U3。
  if (args.refresh) {
    const autoUpdate = isAutoUpdateEnabled();
    // 开关关闭、或本就无新版：仅检查，不改文件。
    if (!autoUpdate || !anyUpdate) {
      writeLastRunUpdate({
        status: anyUpdate ? 'update_available' : 'up_to_date',
        env_error: false,
        current_version: currentVersion,
        latest_version: latestVersion,
        has_update: anyUpdate,
        updated_skills: updatedList || null,
        applied: false,
        error: null,
      });
      emit({
        ok: true,
        stage: 'update-check',
        mode: 'refresh',
        auto_update: autoUpdate,
        current_version: currentVersion,
        latest_version: latestVersion,
        has_update: anyUpdate,
        updated_skills: updatedList || null,
        skills: skillsReport,
        applied: false,
        agent_hint: anyUpdate
          ? `检测到新版本（${updatedList}）。未开启自动更新；提示用户后可运行 node scripts/install.js --upgrade --apply --yes 更新（如需免确认，可在 agent-autonomy-config.json 开启 auto_update.enabled）。`
          : '已是最新版本，无需打扰用户。',
      });
      return;
    }

    // 开关开启且有新版：自动下载覆盖（保留 memory/），事后如实汇报。
    const applied = [];
    let allOk = true;
    for (const local of localSkills) {
      const remote = remoteByName.get(local.name);
      if (!remote || compareVersion(remote.version, local.manifest.version) <= 0) continue;
      log(`自动更新 ${local.name}：${local.manifest.version} → ${remote.version}`);
      const r = await applySkillUpdate(local, remote);
      if (!r.ok) allOk = false;
      applied.push(r);
    }
    // 更新后重读基座 manifest 取新版本，供结果汇报。
    const newBaseRefresh = readJson(path.join(BASE_DIR, 'manifest.json'), {});
    writeLastRunUpdate({
      status: allOk ? 'applied' : 'apply_failed',
      env_error: false,
      current_version: newBaseRefresh.version || currentVersion,
      latest_version: latestVersion,
      has_update: false,
      updated_skills: updatedList || null,
      applied: allOk,
      results: applied.map((r) => ({ name: r.name, ok: r.ok, from: r.from, to: r.to, error: r.error || null })),
      error: allOk ? null : 'partial_apply_failed',
    });
    emit({
      ok: allOk,
      stage: 'update-check',
      mode: 'refresh',
      auto_update: true,
      applied: allOk,
      results: applied,
      current_version: newBaseRefresh.version || currentVersion,
      latest_version: latestVersion,
      has_update: false,
      verify: 'node scripts/validate_skill.js',
      agent_hint: allOk
        ? `已自动更新 UUMit 套件（${updatedList}；auto_update 已开启，memory/ 已保留）。向用户简报已更新的内容即可。`
        : '自动更新部分失败，请查看 results[].error；可提示用户手动运行 node scripts/install.js --upgrade --apply --yes。',
    });
    if (!allOk) process.exitCode = 1;
    return;
  }

  // 仅检查：直接返回结论（不落缓存文件）。
  if (!args.apply) {
    emit({
      ok: true,
      stage: 'update-check',
      current_version: currentVersion,
      latest_version: latestVersion,
      has_update: anyUpdate,
      updated_skills: updatedList || null,
      skills: skillsReport,
      applied: false,
      agent_hint: anyUpdate
        ? `检测到新版本（${updatedList}）。先告知用户可更新内容，确认后运行 node scripts/update_check.js --apply 下载并覆盖（自动保留 memory/）。`
        : '已是最新版本，无需打扰用户。',
    });
    return;
  }

  // --apply：需用户/Agent 已确认。未加 --yes 时只给确认提示，不实际下载。
  if (!args.yes) {
    emit({
      ok: true,
      stage: 'update-check',
      requires_confirmation: true,
      current_version: currentVersion,
      latest_version: latestVersion,
      has_update: anyUpdate,
      skills: skillsReport,
      applied: false,
      agent_hint: anyUpdate
        ? '更新会覆盖本地 skill 文件（保留 memory/）。请向用户确认后，追加 --yes 重跑以执行：node scripts/update_check.js --apply --yes。'
        : '当前已是最新版本，无需更新。',
    });
    return;
  }

  if (!anyUpdate) {
    emit({
      ok: true,
      stage: 'update-check',
      applied: false,
      has_update: false,
      skills: skillsReport,
      agent_hint: '当前已是最新版本，无需更新。',
    });
    return;
  }

  const applied = [];
  let allOk = true;
  for (const local of localSkills) {
    const remote = remoteByName.get(local.name);
    if (!remote || compareVersion(remote.version, local.manifest.version) <= 0) continue;
    log(`更新 ${local.name}：${local.manifest.version} → ${remote.version}`);
    const r = await applySkillUpdate(local, remote);
    if (!r.ok) allOk = false;
    applied.push(r);
  }

  // 更新后重读基座 manifest 取新版本，供结果汇报。
  const newBase = readJson(path.join(BASE_DIR, 'manifest.json'), {});

  emit({
    ok: allOk,
    stage: 'update-check',
    applied: true,
    results: applied,
    current_version: newBase.version || currentVersion,
    latest_version: latestVersion,
    verify: 'node scripts/validate_skill.js',
    agent_hint: allOk
      ? '更新已下载并覆盖完成（memory/ 已保留）。建议运行 node scripts/validate_skill.js 验收。'
      : '部分 skill 更新失败，请查看 results[].error 后重试。',
  });
  if (!allOk) process.exitCode = 1;
}

main().catch((e) => {
  log(`update_check 失败：${(e && e.stack) || e}`);
  emit({ ok: true, stage: 'update-check', check_failed: true, error: String((e && e.message) || e), applied: false });
});
