---
name: openclaw-gateway-upgrade-recovery
description: 排查并修复 OpenClaw Gateway 升级后启动失败。覆盖版本错位、Node 版本下限、plist ProgramArguments 损坏、env 文件被裁、Secret 严格校验、migration gate、launchd 重启循环 breaker。触发词：openclaw 升级后起不来、gateway fail to start、SecretRefResolutionError、restart-loop breaker、迁移卡住、migration did not complete cleanly、Node 版本太低、plist 损坏、opencode-go、ANTHROPIC_PROXY_API_KEY missing。
---

# openclaw-gateway-upgrade-recovery

> Class-level skill：当 OpenClaw 升级（如 2026.6.x → 2026.7.x）后 gateway 起不来时触发。本 skill 是 gateway **启动阶段**的恢复路径；dashboard 渲染问题走 `openclaw-dashboard-troubleshooting`。

## 7 个高频陷阱（2026-07-14 / 2026-07-19 实战沉淀）

### 陷阱 1：版本错位 — CLI 旧 / 配置新

**症状**：`Your OpenClaw config was written by version 2026.7.1, but this command is running 2026.6.11.`

**根因**：`which openclaw` 命中 homebrew 装的 GUI 客户端（带 stub CLI），而不是真正安装在 `~/.openclaw/tools/node-v24.4.0/lib/node_modules/openclaw/` 下的新版。

**诊断**：
```bash
command -v openclaw
openclaw --version
# 再与 Gateway 实际 runtime 比较
/Users/kk/.openclaw/tools/node-v24.4.0/bin/openclaw --version
```

`/opt/homebrew/bin/openclaw` 是全局 npm shim，但**路径本身不等于故障**。只有默认 CLI 版本与 Gateway runtime 版本不一致才算版本错位；若二者同版，shim 可正常使用。

**修复**：先备份，再把全局 npm 包升级到与 runtime 相同的 `latest`；若暂时不能升级，诊断/启动命令使用 runtime 绝对路径绕开：
```bash
npm uninstall -g openclaw
npm install -g openclaw@latest --registry=https://registry.npmjs.org
cd /opt/homebrew/lib/node_modules/openclaw && npm run postinstall
openclaw --version
/Users/kk/.openclaw/tools/node-v24.4.0/bin/openclaw --version
```

### 陷阱 2：Node 版本下限

**症状**：`openclaw: Node.js >=22.22.3 <23, >=24.15.0 <25, or >=25.9.0 is required (current: v24.4.0).`

**根因**：OpenClaw 新版（7.1+）要求 Node ≥ 25.9.0，但 `~/.openclaw/tools/node-v24.4.0/` 是 v24.4.0 不满足。

**修复 plist（用 plutil，不用 sed）**：把 `ProgramArguments[3]` 改成 homebrew 的 `/opt/homebrew/opt/node/bin/node`（v26.3.0），同时更新 Comment 字段：
```bash
plutil -remove ProgramArguments ~/Library/LaunchAgents/ai.openclaw.gateway.plist
plutil -insert ProgramArguments -json '[
  "/bin/sh",
  "/Users/kk/.openclaw/service-env/ai.openclaw.gateway-env-wrapper.sh",
  "/Users/kk/.openclaw/service-env/ai.openclaw.gateway.env",
  "/opt/homebrew/opt/node/bin/node",
  "/Users/kk/.openclaw/tools/node-v24.4.0/lib/node_modules/openclaw/dist/index.js",
  "gateway",
  "--port",
  "18789"
]' ~/Library/LaunchAgents/ai.openclaw.gateway.plist
plutil -replace Comment -string "OpenClaw Gateway (v<actual>, node@26)" ~/Library/LaunchAgents/ai.openclaw.gateway.plist
plutil -lint ~/Library/LaunchAgents/ai.openclaw.gateway.plist  # 必须 OK
```

### 陷阱 3：plist ProgramArguments 数组脏状态

**症状**：gateway 启动时 env 没生效（ZHIPUAI/MINIMAX 缺失），但手动 `source env` 后 `printenv` 完全正常。

**根因**：之前用 `plutil -replace ProgramArguments.3 -string "..."` **不是替换而是插入**——`plutil -replace` 在数组索引处插入新值而非覆盖原值，导致前面 plutil 操作累积了 stale 元素。

**诊断**：
```bash
plutil -p ~/Library/LaunchAgents/ai.openclaw.gateway.plist | grep -A 10 ProgramArguments
# 应该看到 8 行（/bin/sh / wrapper / env / node / dist/.../js / gateway / --port / 18789）
# 如果看到 6 行说明脏了
```

**修复**：见陷阱 2 的 remove + insert。

### 陷阱 4：npm install 静默跳过 prerelease

**症状**：`npm install openclaw@2026.7.1-2` 看似成功（"added 310 packages"），但 `cat package.json | jq .version` 还是 `2026.7.1`。

**根因**：`2026.7.1-2` 含 `-` 后缀，npm 当作 prerelease。按 semver 评估 `2026.7.1-2 < 2026.7.1` stable，所以 npm install 即使显式 `@<version>` 也会拒绝升。

**诊断**：
```bash
npm view openclaw dist-tags
# latest: '2026.7.1-2' → 确实最新
cat node_modules/openclaw/package.json | jq .version
# 2026.7.1 → 但装的是旧的
```

**修复**：
```bash
cd lib/node_modules
npm uninstall openclaw           # 卸 stable
npm install openclaw@latest      # @latest 强制解析 latest dist-tag（含 prerelease）
# 或：npm install openclaw@2026.7.1-2 --force-prefix
```

### 陷阱 5：Secret 严格校验（7.1-2 引入）

**症状**：`SecretRefResolutionError: Environment variable "X_API_KEY" is missing or empty.`，gateway 在 `state_leases` 写 lease，连续 21+ 次 unclean boot 触发 `restart-loop breaker`。

**根因**：7.1-2 引入"启动时必须解析所有引用 secret"的检查，且 hermes 自动注册内置 provider（`opencode-go`）→ **config 里删了 provider 还不够**，secret 必须存在。

**诊断**：
```bash
# 1. 找 config 引用了哪些 secret
grep -oE '"id": "[A-Z_]+_API_KEY"' ~/.openclaw/openclaw.json | sort -u

# 2. 验证每个 secret 在 env 里都有
set -a && source ~/.openclaw/service-env/ai.openclaw.gateway.env && set +a
for k in ANTHROPIC_PROXY_API_KEY MINIMAX_API_KEY ...; do
  v=$(eval echo \$$k)
  [ -z "$v" ] && echo "❌ $k: MISSING" || echo "✅ $k: ${v:0:5}...${#v}"
done

# 3. 找隐式 hermes-import 注册
grep -rl "OPENCODE_GO_API_KEY" ~/.openclaw/tools/node-*/lib/node_modules/openclaw/dist/secrets-CLcKR4yb.js
```

**修复**：
- 对主人不用的 provider：删 `config.providers[name]` 整段 + `aliases[model]` 引用
- 对 hermes-import 隐式注册的 provider（如 opencode-go）：加 dummy env var 占位让它不阻塞启动
  ```bash
  echo "export OPENCODE_GO_API_KEY='placeholder-disabled-by-hermes-<date>'" >> \
    ~/.openclaw/service-env/ai.openclaw.gateway.env
  ```
- **⚠️ schema 陷阱（7.1-2 验证）**：`apiKey` 字段不能用 `enabled: false` / `_disabled: true` 这种字段禁用——7.1-2 zod-schema 不接这俩 key。**禁用只有两种合法写法**：(a) 删整个 provider 节点 (b) 删 provider 内部的 `apiKey` 节点。其他字段加 `"enabled": false` 会报 `Invalid input`，而且 zod 校验过的失败错稳定 bundle 写 `/Users/kk/.openclaw/logs/stability/openclaw-stability-*.json`
- **典型 6 个必查 provider/secret**：ANTHROPIC_PROXY_API_KEY / MINIMAX_API_KEY / ZHIPUAI_API_KEY / OPENCODE_GO_API_KEY / XIAOMI_CODING_API_KEY / XIAOMI_TTS_API_KEY（**每次升级都要重新核一遍，可能新增**；本次升级 7.1 → 7.1-2 新增了对 zhipu 的强制检查，主人过去一直没配）

**配置删除的步骤顺序**（避免 7.1-2 重启循环不让启动）：
1. config 删 provider 节点 + aliases 同前缀引用 → `openclaw config validate` 必须 "Config valid"
2. **仍报 secret missing** → 那是 hermes 隐式注册，加 dummy env var（上面那段）
3. 都 OK 前台跑后，再回到 launchd + 清 startup-migrations lease（陷阱 6）

### 陷阱 6：Migration gate 卡住

**症状**：`OpenClaw startup migrations did not complete cleanly; refusing to report the gateway ready.` 在 `state_leases` 反复写 lease。

**根因**：7.x 引入 `schema_meta.startup-migrations = app_version` 标记。升级后该标记与当前 VERSION 不等 → 走 migration → migration 卡住（通常是 legacy data 已迁移过但 migration 检查器仍报 warning）。

**修复**（直接 bypass migration gate）：
```python
python3 << 'EOF'
import sqlite3, time
conn = sqlite3.connect('/Users/kk/.openclaw/state/openclaw.sqlite')
cur = conn.cursor()
cur.execute("DELETE FROM state_leases WHERE scope='startup-migrations'")
now = int(time.time()*1000)
cur.execute("""INSERT OR REPLACE INTO schema_meta
   (meta_key, role, schema_version, agent_id, app_version, created_at, updated_at)
   VALUES (?, ?, ?, ?, ?, ?, ?)""",
   ('startup-migrations', 'global', 1, None, '<实际 VERSION, 如 2026.7.1-2>', now, now))
conn.commit()
EOF
```

**也可设 env var**：`OPENCLAW_MIGRATION_EXISTING_IMPORT=1`（但只能跳过 `setup.migration-import-mgeyEjXF.js` 的检查，不能跳过 startup checkpoint）。

### 陷阱 8：npm 主进程是新 Node，但安装脚本误命中旧 Node

**症状**：明确用 Node 26 启动 `npm-cli.js`，OpenClaw 的 preinstall 仍报告：
`detected Node 24.4.0 (exec: ~/.openclaw/tools/node-v24.4.0/bin/node)`。

**根因**：npm 的包内 lifecycle script 通过 `sh -c node ...` 再次按 `PATH` 查找 Node；Hermes/launchd 的持久化 shell环境可能把 OpenClaw 自带旧 Node 放在 Homebrew Node 前面。只固定 npm 主进程解释器不够。

**修复**：同时固定父进程与 lifecycle script 的 PATH：
```bash
env PATH=/opt/homebrew/opt/node/bin:/opt/homebrew/bin:/usr/bin:/bin \
  /opt/homebrew/opt/node/bin/node \
  /opt/homebrew/lib/node_modules/npm/bin/npm-cli.js \
  install -g openclaw@latest \
  --registry=https://registry.npmmirror.com
```
安装后若 npm 的 allow-scripts 策略跳过 postinstall，显式执行：
```bash
GLOBAL=/opt/homebrew/lib/node_modules/openclaw
env PATH=/opt/homebrew/opt/node/bin:/opt/homebrew/bin:/usr/bin:/bin \
  /opt/homebrew/opt/node/bin/node \
  /opt/homebrew/lib/node_modules/npm/bin/npm-cli.js \
  run postinstall --prefix "$GLOBAL"
```
最后必须同时验证 global/managed 两处 `package.json.version` 和两个 CLI 入口。

### 陷阱 7：env 文件被裁

**症状**：所有 secret 检查都失败，但 backup env 文件里都是好的。

**诊断**：
```bash
grep -c "^export" ~/.openclaw/service-env/ai.openclaw.gateway.env
# 期望 19-21 行（包含 PATH/HOME 等 + 所有 secret）
# 如果只有 2-3 行 → 被工具（installer？）覆盖了

# 对比 backup
grep -c "^export" ~/.openclaw/service-env/ai.openclaw.gateway.env.bak-*
```

**修复**：从最新已知良好 backup 恢复 + 不要覆盖 env 行注释：
```bash
BACKUP=$(ls -t ~/.openclaw/service-env/ai.openclaw.gateway.env.bak-* | head -1)
cp "$BACKUP" ~/.openclaw/service-env/ai.openclaw.gateway.env
# 再加本次 session 需要的 flag（如 OPENCLAW_MIGRATION_EXISTING_IMPORT）
echo "export OPENCLAW_MIGRATION_EXISTING_IMPORT='1'" >> ~/.openclaw/service-env/ai.openclaw.gateway.env
```

## 升级 Gateway 标准流程

```
1. 备份当前版本 + env + plist + config
   cp -R lib/node_modules/openclaw lib/node_modules/openclaw.bak-<date>
   cp openclaw.json openclaw.json.bak-<date>
   cp ai.openclaw.gateway.plist ai.openclaw.gateway.plist.bak-<date>
   cp ai.openclaw.gateway.env ai.openclaw.gateway.env.bak-<date>

2. 停服务（launchctl bootout）+ 等 ThrottleInterval (10s) + lease 过期

3. 升级
   npm uninstall openclaw
   npm install openclaw@latest
   npm run postinstall  # 在新装目录里跑一次

4. 检查 Node 版本下限（陷阱 2）
   node --version
   调整 plist ProgramArguments[3] 用满足要求的 node

5. 检查并清理 config（陷阱 5）
   grep '"id":' openclaw.json | grep API_KEY → 找引用 secret
   如果有不用的 provider → 删整段

6. 验证 config schema
   openclaw config validate
   # 必须 "Config valid"

7. 清理 startup-migrations 标记（陷阱 6）
   写入 schema_meta.startup-migrations = 实际 VERSION
   清 state_leases WHERE scope='startup-migrations'

8. 恢复 env 如果被裁（陷阱 7）
   cp env.bak env

9. 启动
   launchctl bootstrap gui/$UID ~/Library/LaunchAgents/ai.openclaw.gateway.plist
   sleep 15
   curl -sS http://127.0.0.1:18789/healthz  # 期望 {"ok":true,"status":"live"}
```

## Doctor 输出解读

`openclaw doctor` 报"Plugin version drift: N active official plugins not on gateway X.Y.Z"——这是 doctor 的缓存跟最新 dist-tag 不匹配，**不是 blocker**。

判断是否 blocker：
```bash
# 1. health 必须活
curl http://127.0.0.1:18789/healthz

# 2. dashboard 必须 HTTP 200
curl -o /dev/null -w "%{http_code}" http://127.0.0.1:18789/dashboard/

# 3. WebSocket 必须能连
# (主人用一个会话发消息确认)

# 全 OK → 可以更新 plugin 但不是必须
openclaw plugins update feishu discord slack
```

## 反例（不该做的事）

❌ **不要用 `sed` 改 plist**——会把 KeepAlive dict 改成单 true，plist 仍 OK 但 launchd 拒收
❌ **不要 trim env 文件到最少项**——OpenClaw 升级可能引入新的 secret 检查，env 宁可多留几行
❌ **不要在没有 backup 的情况下 `npm install openclaw@latest`**——会触发陷阱 4
❌ **不要相信 `npm view openclaw version` 等于 `latest`**——`2026.7.1-2` 是 latest dist-tag，但 npm semver 把它当 prerelease
❌ **不要手动编辑 state.sqlite**——除非已确认上面所有陷阱排除，且**写在 sqlite 前先 `cp openclaw.sqlite openclaw.sqlite.<date>` 备份**
❌ **不要用 `node-v24.4.0` 跑 7.1+**——要么升级 node 要么换 node 路径
❌ **不要信任 doctor 报的所有 warning**——"Plugin version drift" 是 cosmetic，"Secrets reloader degraded" 是 blocker

## 多 Agent ownership gate（配置/插件/Heartbeat）

升级或迁移后若出现 `AgentSelectionRequiredError: Multiple agents are configured...`，先不要按 Gateway 崩溃处理。这通常表示 fleet 已启用显式所有权，但 unscoped CLI、插件发现或 ambient heartbeat 没有 owner。

处理原则：

1. 先 `openclaw agents list --json` 确认目标 owner。
2. 用 schema 验证后设置 `agents.defaults.systemAgent.agentId`；默认 heartbeat 另设 `agents.defaults.heartbeat.agentId`。
3. 检查非 owner agent 没有显式 heartbeat override，避免重复运行。
4. 多项配置用一个 `config patch` 原子提交：backup → dry-run → apply → validate → 必要重启。
5. 重启后既逐路径 `config get`，也做运行态验收；配置正确与 heartbeat 实际成功必须分开报告。
6. Embedding provider 必须以真实向量 probe 为准，不能只凭“存在凭证”或“schema 支持”；没有可用 provider 时保持搜索开启并验证 FTS 回退。

完整命令、Memory Wiki 验收标准与 provider readiness 流程见 `references/multi-agent-owner-memory-wiki-heartbeat.md`。

## 联动

- `openclaw-dashboard-troubleshooting`：Gateway 启动成功后浏览器侧 dashboard 问题
- `workspace-hygiene` 坑 18/19/20：磁盘清理与 hermes self-cleanup；本 skill 是 gateway 进程级
- `node-version-upgrade`：Node 本体升级的流程（陷阱 2 的修复可参考）
- `hermes-launchd` / `macos-launchd`：plist 写法和 launchd bootout/bootstrap 操作

## 支持文件

- `scripts/diagnose-gateway.sh` — 一键诊断脚本，跑所有 7 个陷阱的诊断路径并标出命中项。`--deep` 加 sqlite / launchd 深检。
- `references/symptom-decision-tree.md` — 症状 → 陷阱 → 修复的快速查询表（pending，未来 session 收到新症状时维护）。
- `references/openclaw-launchagent-autostart.md` — "将 OpenClaw 设为开机自启" / "现在是不是自启了" 验证清单 + 最小可接受 plist 模板 + 反例
- `references/approval-aware-upgrade.md` — invoking/global root 与 managed Gateway runtime 分离时的备份、升级、审批和验收流程

## 双安装根与审批感知升级

升级前优先运行 `openclaw update --tag latest --dry-run --json --no-restart --yes`，读取它报告的 **managed service root**。全局 CLI root 与 Gateway runtime root 可能不同；两处都要检查版本和备份，最终以 managed root 是否升级成功为准。

### 旧 CLI 阻断 dry-run 的引导悖论

若全局 CLI 落后于 managed runtime，它可能把新版配置误判为 invalid，导致官方 dry-run 在报告 managed root 之前就退出。此时不要运行旧 CLI 的 `doctor --fix`，否则可能用旧 schema 改坏新版配置。按以下顺序只读确认：

1. 从 LaunchAgent `ProgramArguments` 定位 Gateway 实际 `dist/index.js`，由此反推出 managed package root；不要只凭 `command -v openclaw` 猜。
2. 比较 global 与 managed 两处 `package.json.version`。
3. 用 managed root 对应的 CLI 执行 `config validate --json`；若新版 CLI 返回 `valid: true`，旧 CLI 的 invalid 结论视为版本错位症状。
4. managed CLI 的 `update --dry-run` 若报 `package manager owner is unknown`，只说明该复制式 runtime 不是包管理器拥有的安装，不能据此判断安装损坏；升级 global root 时改走其实际 npm/pnpm/Bun shim。
5. 先备份两处根，再把 global CLI 升到 latest，使默认 CLI 与 managed runtime 对齐。

备份与升级要小步**串行**执行：创建备份目录、复制敏感配置、归档 managed runtime、归档 global runtime 分别进行。不要并行触发两个大型安装根归档：审批 UI 可能同时超时，导致两步都中断且难以判断完成边界。若工具审批超时，聊天中的“继续”不能代替审批 UI；必须停下等待显式工具批准，不能重复或改写命令绕过。完整流程见 `references/approval-aware-upgrade.md`。

## 验证清单（升级前 + 升级后必跑）

```bash
# 升级前
openclaw --version                                       # 当前
npm view openclaw dist-tags                              # latest
node --version                                           # 当前 node
plutil -lint ~/Library/LaunchAgents/ai.openclaw.gateway.plist
wc -l ~/.openclaw/service-env/ai.openclaw.gateway.env   # 行数 ≥ 19

# 升级后
openclaw --version                                       # 期望等于 latest
openclaw config validate                                 # 必须 "Config valid"
curl -sS http://127.0.0.1:18789/healthz                # {"ok":true}
curl -o /dev/null -w "%{http_code}\n" http://127.0.0.1:18789/dashboard/  # 200
launchctl print gui/$UID/ai.openclaw.gateway | grep -E "active count|state"  # running
```
