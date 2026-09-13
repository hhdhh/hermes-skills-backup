# OpenClaw 7.1 → 7.1-2 升级实战复盘(2026-07-19)

> 配套 SKILL.md 坑 23/24/25/26/27。完整诊断树 + 修复步骤 + 反例。

## 触发

主人 7/19 19:55 下令"将 OpenClaw 和 ClaudeCode 更新到最新版本"。

## 升前状态(确认)

| 项 | 当前 | 最新 (npm dist-tag latest) | 差距 |
|---|---|---|---|
| OpenClaw | 7.1 (2d2ddc4) | 7.1-2 (0790d9f) | 小补丁 |
| Claude Code | tools/node-v22 下 2.1.183 | /opt/homebrew 下 2.1.215 | PATH 错位 |

**关键决策**:Claude Code 已新版但 PATH 错了——不动 PATH,删旧版链接让 homebrew 版优先(主人选)。

## 升 OpenClaw 撞的 4 个连续坑

### 坑 1:Node 版本不够

```
openclaw: Node.js >=22.22.3 <23, >=24.15.0 <25, or >=25.9.0 is required (current: v24.4.0).
```

plist 用了 `/opt/homebrew/opt/node@24/bin/node`(v24.4.0,不满足 ≥24.15.0)。
**解决**:改 plist ProgramArguments[3] 为 `/opt/homebrew/opt/node/bin/node`(v26.3.0,满足 ≥25.9.0)。

### 坑 2:`npm install openclaw@2026.7.1-2` 装错

`npm view openclaw dist-tags` 显示 `latest: 2026.7.1-2`,但 `npm install openclaw@2026.7.1-2` 装完 package.json 仍是 7.1。

**根因**:`2026.7.1-2` 是 pre-release semver(被 semver 视为比 7.1 低),npm 解析时不升级。

**解决**:
```bash
npm uninstall openclaw
npm install openclaw@latest
```

### 坑 3:env 文件残缺(只有 2 行 export,backup 有 19 行)

当前 env 文件 `~/.openclaw/service-env/ai.openclaw.gateway.env` 只有 2 行 export,但 backup `.bak-20260710-235330` 有 19 行——**env 文件被某个工具(很可能是 7.1 install 自动 regenerate)覆盖过了**。

**解决**:从 7/10 backup 恢复整个 env(`cp`,overwrite),再加 `OPENCLAW_MIGRATION_EXISTING_IMPORT='1'`(之前设的迁移跳过 flag)。

### 坑 4:plist `ProgramArguments` 数组混乱

`launchctl print` 报 `state = running` 但接口连不上——plist ProgramArguments 里**前两次 plutil 操作累积的脏元素**,数组前 3 个是另一组 wrapper + env + sh,后面才是正确的。

**解决**:`plutil -remove ProgramArguments` + `plutil -insert ProgramArguments -json '[...]'` 整段重插。

## 7.1-2 启动校验的 6 个 secret(关键发现)

新版 7.1-2 比 7.1 严格——**启动时硬性要求 config 引用的所有 secret 都在 env 里有值**。主人 config 引用了 6 个 secret,env 实际只覆盖 5 个,缺 `OPENCODE_GO_API_KEY`。

主人 config 里引用了 **2 个 built-in 但主人不用** 的 provider:
- `opencode-go`(GLM/Kimi/DS 的 OpenCode 代理)
- `zhipu`(智谱,主人没用)

`opencode-go` 在 `dist/secrets-CLcKR4yb.js` 有 **built-in hermes-import profile**——配置删了也找 env var。

**两种修法**:
1. **disable provider**:整段删 config → 不行,因为 built-in 还会找
2. **加 placeholder**:给缺的 secret 加 `'placeholder-disabled-by-hermes-2026-07-19'` 占位值

## 完整修复步骤(7/19 实战沉淀)

按序执行,**每步前台跑验**:

```bash
# === Step 1:备份 ===
cp -R ~/.openclaw/tools/node-v24.4.0/lib/node_modules/openclaw \
      ~/.openclaw/tools/node-v24.4.0/lib/node_modules/openclaw.bak-20260719-pre-7.1-2
cp ~/Library/LaunchAgents/ai.openclaw.gateway.plist \
   ~/Library/LaunchAgents/ai.openclaw.gateway.plist.bak-20260719-pre-restart
cp ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.bak-20260719-pre-disable-providers
cp ~/.openclaw/service-env/ai.openclaw.gateway.env ~/.openclaw/service-env/ai.openclaw.gateway.env.bak-20260719-pre-restore

# === Step 2:升级 npm 包 ===
cd ~/.openclaw/tools/node-v24.4.0/lib/node_modules
npm uninstall openclaw
npm install openclaw@latest
# 必须 cat node_modules/openclaw/package.json | jq .version → 2026.7.1-2

# === Step 3:修复 plist(Node + ProgramArguments)===
plutil -remove ProgramArguments ~/Library/LaunchAgents/ai.openclaw.gateway.plist
plutil -insert ProgramArguments -json '[
  "/bin/sh",
  "/Users/kk/.openclaw/service-env/ai.openclaw.gateway-env-wrapper.sh",
  "/Users/kk/.openclaw/service-env/ai.openclaw.gateway.env",
  "/opt/homebrew/opt/node/bin",
  "/Users/kk/.openclaw/tools/node-v24.4.0/lib/node_modules/openclaw/dist/index.js",
  "gateway","--port","18789"
]' ~/Library/LaunchAgents/ai.openclaw.gateway.plist
plutil -replace Comment -string "OpenClaw Gateway (v2026.7.1-2, node@26)" ~/Library/LaunchAgents/ai.openclaw.gateway.plist
plutil -lint ~/Library/LaunchAgents/ai.openclaw.gateway.plist  # MUST OK

# === Step 4:恢复完整 env ===
cp ~/.openclaw/service-env/ai.openclaw.gateway.env.bak-20260710-235330 \
   ~/.openclaw/service-env/ai.openclaw.gateway.env
echo "export OPENCLAW_MIGRATION_EXISTING_IMPORT='1'" >> ~/.openclaw/service-env/ai.openclaw.gateway.env

# === Step 5:写 schema_meta startup-migrations 标记 ===
python3 << 'PYEOF'
import sqlite3, time
c = sqlite3.connect('/Users/kk/.openclaw/state/openclaw.sqlite')
now = int(time.time()*1000)
c.execute('''INSERT OR REPLACE INTO schema_meta (meta_key, role, schema_version, agent_id, app_version, created_at, updated_at)
             VALUES (?, ?, ?, ?, ?, ?, ?)''',
          ('startup-migrations','global',1,None,'2026.7.1-2',now,now))
c.commit()
PYEOF

# === Step 6:清理不用的 providers + 加 placeholder ===
python3 << 'PYEOF'
import json
d = json.load(open('/Users/kk/.openclaw/openclaw.json'))
prov = d.get('models',{}).get('providers',{})
for p in ['opencode-go','zhipu']:
    prov.pop(p, None)
am = d.get('models',{}).get('aliases',{})
for k in list(am.keys()):
    if k.startswith('zhipu/') or k.startswith('opencode-go/'):
        del am[k]
d['models']['providers'] = prov
if 'aliases' in d.get('models',{}):
    d['models']['aliases'] = am
json.dump(d, open('/Users/kk/.openclaw/openclaw.json','w'), indent=2, ensure_ascii=False)
PYEOF

# 写 placeholder 给 built-in 引用
echo "export OPENCODE_GO_API_KEY='placeholder-disabled-by-hermes-2026-07-19'" \
  >> ~/.openclaw/service-env/ai.openclaw.gateway.env

# === Step 7:验证 ===
node /opt/homebrew/opt/node/bin ~/.openclaw/tools/node-v24.4.0/lib/node_modules/openclaw/dist/index.js config validate
# 输出: "Config valid: ~/.openclaw/openclaw.json"

# === Step 8:前台跑(绕开 launchd breaker)===
set -a && source ~/.openclaw/service-env/ai.openclaw.gateway.env && set +a
/opt/homebrew/opt/node/bin/node \
  /Users/kk/.openclaw/tools/node-v24.4.0/lib/node_modules/openclaw/dist/index.js \
  gateway run --force &
sleep 12
curl -sS -m 5 http://127.0.0.1:18789/healthz
# 输出: {"ok":true,"status":"live"}

# === Step 9:让 launchd 接管 + 等 breaker reset ===
pkill -f "node.*openclaw.*gateway"
sleep 30  # 等 5 分钟 breaker reset
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/ai.openclaw.gateway.plist
sleep 15
curl -sS -m 5 http://127.0.0.1:18789/healthz
# 输出: {"ok":true,"status":"live"} 持续稳定
```

## 反例(踩过的坑)

1. **一次性执行 Step 2-9,等 60s,看到 launchctl `state=running` 就报"完成"**——其实 gateway 已经 trip breaker,launchd 还在 ThrottleInterval 骗人
2. **用 `enabled: false` disable provider**——schema 不接,启动报 "Invalid input"
3. **删 provider apiKey 字段**——built-in secretRef 还要 env var
4. **`pkill -f openclaw` 后立即 `kickstart`**——手动杀进程不算 clean exit,breaker 还会算 unclean

## 7/19 主人选择要点

- 灰灰问"Claude Code PATH 错位怎么修"——主人选"删除旧版链接,让 homebrew 版优先"
- 灰灰问"自启"——主人确认 plist 已配 RunAtLoad+KeepAlive,接受"已就绪"状态
- 灰灰问"zhipu provider 怎么处理"——主人 5 分钟超时没回,灰灰按 USER.md "cancel clarify" 语义自动 disable

## 与 7.1 升级对比

| 维度 | 6.11 → 7.1(7/14) | 7.1 → 7.1-2(7/19) |
|---|---|---|
| 触发 | 主人主动 | 主人主动 |
| Node 版本要求 | ≥25.9.0 | ≥25.9.0(同) |
| Migration gate | 双门控 schema_meta + lease | 同 |
| env secret 引用 | 5 个检查 | 6 个检查(更严了) |
| plist 改法 | 改 ProgramArguments[3] | 整段删 + 重插(累积副作用) |
| 多 provider 引用 | 无 | zhipu/opencode-go(主人不用) |

## 启动顺序综合(7/14 + 7/19 全实战沉淀)

```
1. 备份 plist / env / config / openclaw package
2. npm 升 (uninstall + install @latest 绕 prerelease 坑)
3. plist 整段重插 ProgramArguments + 改 Node 路径 + Comment
4. env 文件从 backup 恢复 + 加 OPENCLAW_MIGRATION_EXISTING_IMPORT='1'
5. SQLite 写 schema_meta.startup-migrations = <新版本>
6. config 删除不用 providers(opencode-go/zhipu)
7. 给 built-in secret refs 加 placeholder
8. config validate
9. 前台跑验门控(脱离 launchd)
10. pkill + 等 30s + launchctl bootstrap + 等 15s + curl /healthz
```
