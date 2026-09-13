# OpenClaw 6.11 → 7.1 升级实战(2026-07-14)

> 配套 workspace-hygiene SKILL.md 的坑 18/19/20,记录完整诊断 → 修复 → 验证流程。
> 主人升级到任何 OpenClaw 7.x 版本都可以参考。

## 症状全景

| 现象 | 报告 |
|------|------|
| `openclaw --version` | `OpenClaw 2026.7.1 (2d2ddc4)` ✅ |
| `openclaw gateway status --deep` | `Service config issue: Gateway service was installed by OpenClaw 2026.6.11; current CLI is 2026.7.1` |
| `openclaw gateway run --force` 前台 | `[openclaw] Reason: OpenClaw startup migrations did not complete cleanly; refusing to report the gateway ready.` |
| `openclaw gateway run --force`(SQLite 写标记后) | `[openclaw] Reason: OpenClaw startup migrations are already running for this state directory; retry after the other gateway finishes or after 2026-07-14T15:30:21.449Z.` |
| 端口 18789 | 一直 LISTEN 失败 / `Failed to connect` |
| launchd `last exit code` | 1 → 反复 spawn → ThrottleInterval=10s 节流 |

## 根因树

```
gateway 启动失败
├─ 直查 1: Node 版本不对
│  ├─ openclaw 7.1 要求 ≥25.9.0 / 22.22.3+ / 24.15.0+
│  ├─ plist 用的是 v24.4.0(node@24 keg,不满足)
│  └─ 修复:plist 改用 /opt/homebrew/opt/node/bin/node(v26.3.0)
│
├─ 直查 2: Migration gate 拒绝
│  ├─ 启动时报 "Memory Core migration skipped because SQLite rows already exist"
│  └─ 这其实是**警告**被升级成**错误**——SQLite 已迁过 + legacy JSON 还在 → 卡
│
└─ 直查 3: launchd 反复 spawn 留 lease
   ├─ KeepAlive=true + ThrottleInterval=10s
   ├─ 每次 spawn 都 acquire lease,release 没等就跑下一次
   ├─ 5 分钟 TTL 过期后,新启动又 acquire 失败
   └─ 修复:SQLite 直接清 lease + 写 startup-migrations 标记
```

## 修复步骤(已验证可重复)

### Step 0: 备份 + 全查

```bash
# plist 备份
cp ~/Library/LaunchAgents/ai.openclaw.gateway.plist \
   ~/Library/LaunchAgents/ai.openclaw.gateway.plist.bak-$(date +%Y%m%d-pre-restart)

# 看 schema_meta + state_leases
python3 << 'EOF'
import sqlite3
c = sqlite3.connect('/Users/kk/.openclaw/state/openclaw.sqlite')
cur = c.cursor()
cur.execute("SELECT * FROM schema_meta WHERE meta_key='startup-migrations'")
print('schema_meta startup-migrations:', cur.fetchall())
cur.execute("SELECT * FROM state_leases WHERE scope='startup-migrations'")
print('lease startup-migrations:', cur.fetchall())
cur.execute("SELECT * FROM state_leases")
print('all leases:', cur.fetchall())
EOF

# 看所有 node 路径(为 Step 1 准备)
ls -la /opt/homebrew/bin/node /opt/homebrew/opt/node@24/bin/node /opt/homebrew/opt/node/bin/node 2>&1
for p in /opt/homebrew/bin/node /opt/homebrew/opt/node/bin/node; do
  echo "$p -> $($p --version 2>&1)"
done
```

### Step 1: 修 plist 的 Node 路径(用 v26.3.0)

```bash
# 先看现状
plutil -p ~/Library/LaunchAgents/ai.openclaw.gateway.plist | grep -A12 ProgramArguments

# 删除 ProgramArguments 整个数组,再插入新数组(JSON 形式,坑 19 法 1)
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

# 同步 Comment
plutil -replace Comment -string "OpenClaw Gateway (v2026.7.1, node@26)" \
       ~/Library/LaunchAgents/ai.openclaw.gateway.plist

# 验证
plutil -lint ~/Library/LaunchAgents/ai.openclaw.gateway.plist
plutil -p ~/Library/LaunchAgents/ai.openclaw.gateway.plist | grep -A12 ProgramArguments
```

### Step 2: 清 SQLite lease + 写 startup-migrations 标记

```bash
# ⚠️ 主人 ABSOLUTE 模式 + 直接 SQL 操作,要主人在场 approve
python3 << 'EOF'
import sqlite3, time
conn = sqlite3.connect('/Users/kk/.openclaw/state/openclaw.sqlite')
cur = conn.cursor()
now = int(time.time()*1000)

# 清残留 lease(已过期但还在)
cur.execute("DELETE FROM state_leases WHERE scope='startup-migrations'")

# 写入 startup-migrations 标记,让 7.1 跳过 migration
cur.execute("""INSERT OR REPLACE INTO schema_meta
               (meta_key, role, schema_version, agent_id, app_version, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ('startup-migrations', 'global', 1, None, '2026.7.1', now, now))
conn.commit()

# 验证
cur.execute("SELECT * FROM state_leases WHERE scope='startup-migrations'")
print('剩余 lease:', cur.fetchall())
cur.execute("SELECT * FROM schema_meta WHERE meta_key='startup-migrations'")
print('schema_meta:', cur.fetchall())
EOF
```

### Step 3: 前台测试启动

```bash
set -a && source ~/.openclaw/service-env/ai.openclaw.gateway.env && set +a
export PATH="/opt/homebrew/opt/node/bin:$PATH"
/opt/homebrew/opt/node/bin/node \
  ~/.openclaw/tools/node-v24.4.0/lib/node_modules/openclaw/dist/index.js \
  gateway run --force
# 应该看到 "Gateway listening on 127.0.0.1:18789"
# Ctrl+C 杀掉
```

### Step 4: 让 launchd 接管 + 验健康

```bash
launchctl kickstart -k gui/$(id -u)/ai.openclaw.gateway
sleep 8
launchctl print gui/$(id -u)/ai.openclaw.gateway | grep -E "active count|state|last exit"
# 期望:active count = 1, state = running, last exit code = 0

curl -sS -m 3 http://127.0.0.1:18789/healthz
# 期望:{"ok":true,"status":"live"}

curl -sS -m 3 -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:18789/
# 期望:HTTP 200
```

## 不该做的事(本次踩坑的反面)

1. **不要 sudo launchctl print system 清 launchd cache** —— 7/4 之前的"经验"说需要,但 7/14 实测发现 launchd cache 不影响,真正问题是 SQLite state 不对
2. **不要 `rm -rf ~/.openclaw/state/`** —— 73 张表全清,飞书 session / 节点 / 频道状态全丢
3. **不要 `sqlite3 ... 'DELETE FROM *'` 全表清空** —— 同上
4. **不要 `mv ~/.openclaw/workspace/memory/.dreams/*.json /tmp/`** —— legacy 文件不是问题源头,是 schema_meta 没记录导致迁移检查器不知道已经迁过了
5. **不要 `npm install -g openclaw@latest`** —— 会装到 homebrew 那条路径(`/opt/homebrew/lib/node_modules/openclaw/`),跟你工作目录里的 tools 路径冲突
6. **不要盲目设 `OPENCLAW_MIGRATION_EXISTING_IMPORT=1`** —— 它能绕过 freshness 检查,但**绕不过 lease gate**;主修还是 SQLite 直接写

## 配套资源

- workspace-hygiene SKILL.md 坑 18/19/20
- `~/.openclaw/tools/node-vXX/lib/node_modules/openclaw/dist/startup-migration-checkpoint-ZitWtlNH.js` — 门控源码
- `~/.openclaw/tools/node-vXX/lib/node_modules/openclaw/dist/setup.migration-import-mgeyEjXF.js` — env var 入口
- launchd plist:`~/Library/LaunchAgents/ai.openclaw.gateway.plist`
- env wrapper:`~/.openclaw/service-env/ai.openclaw.gateway-env-wrapper.sh`