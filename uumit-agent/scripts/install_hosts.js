#!/usr/bin/env node
'use strict';
/**
 * install_hosts.js — 多宿主一键安装（批次 4）。
 *
 * 作用：探测本机常见 Agent 宿主的 skills 目录，并把 UUMit 套件（基座 + 扩展）
 * 安装/更新到这些目录，免去逐个宿主手动拷贝。
 *
 * 安全默认：默认仅**探测并预览**（dry-run），不写任何文件；加 `--apply` 才实际复制。
 *
 * 用法:
 *   node install_hosts.js                 # 探测各宿主 skills 目录并预览将安装的套件（不写盘）
 *   node install_hosts.js --apply         # 实际复制套件到探测到的宿主目录
 *   node install_hosts.js --host claude   # 只针对指定宿主（claude/codex/cursor/openclaw）
 *
 * 输出(stdout, JSON)：{ hosts:[{host,dir,exists,action}], applied }
 *
 * 退出码：0=成功；1=出错。
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

const HOME = os.homedir();
const SKILLS_ROOT = path.resolve(__dirname, '..', '..'); // 套件根（基座与扩展并列）
const SKILL_PACKAGES = ['uumit-agent', 'uumit-cruise', 'uumit-publisher', 'uumit-realtime', 'uumit-recommend', 'uumit-social', 'uumit-compute'];

// 各宿主 skills 目录约定（相对 HOME）。不同平台路径可能不同，未命中即跳过。
const HOST_DIRS = {
  claude: path.join(HOME, '.claude', 'skills'),
  codex: path.join(HOME, '.codex', 'skills'),
  cursor: path.join(HOME, '.cursor', 'skills'),
  openclaw: path.join(HOME, '.openclaw', 'skills'),
};

function parseArgs(argv) {
  const out = { apply: false, host: null };
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === '--apply') out.apply = true;
    else if (argv[i] === '--host') out.host = argv[++i];
  }
  return out;
}

function copyDir(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    // 跳过本地态：memory 运行时数据、压缩包。
    if (entry.name === 'memory' || entry.name.endsWith('.zip')) continue;
    const s = path.join(src, entry.name);
    const d = path.join(dest, entry.name);
    if (entry.isDirectory()) copyDir(s, d);
    else fs.copyFileSync(s, d);
  }
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const targets = args.host ? { [args.host]: HOST_DIRS[args.host] } : HOST_DIRS;
  if (args.host && !HOST_DIRS[args.host]) {
    console.error(JSON.stringify({ ok: false, error: `未知宿主: ${args.host}，可选 ${Object.keys(HOST_DIRS).join('/')}` }));
    process.exit(1);
  }

  const hosts = [];
  for (const [host, baseDir] of Object.entries(targets)) {
    if (!baseDir) continue;
    const parentExists = fs.existsSync(path.dirname(baseDir)); // 宿主主目录是否存在 → 推断是否装了该宿主
    let action = 'skip';
    if (parentExists) {
      action = args.apply ? 'installed' : 'would-install';
      if (args.apply) {
        for (const pkg of SKILL_PACKAGES) {
          const src = path.join(SKILLS_ROOT, pkg);
          if (fs.existsSync(src)) copyDir(src, path.join(baseDir, pkg));
        }
      }
    }
    hosts.push({ host, dir: baseDir, host_detected: parentExists, action });
  }

  process.stdout.write(JSON.stringify({ ok: true, applied: args.apply, hosts }) + '\n');
}

main();
