# OpenClaw Gateway LaunchAgent 开机自启验证清单

> 主人说"将 OpenClaw 设为开机自启"或问"现在是不是已经开机自启了"时使用。
> 关联主技能：`openclaw-gateway-upgrade-recovery`（陷阱 2/3 处理 plist）。

## 必备要素（一项缺失就不算开机自启）

| 要素 | 检查命令 | 期望结果 |
|---|---|---|
| plist 存在 | `ls ~/Library/LaunchAgents/ai.openclaw.gateway.plist` | 文件存在 |
| plist 合法 | `plutil -lint ~/Library/LaunchAgents/ai.openclaw.gateway.plist` | `OK` |
| RunAtLoad | `plutil -p .../...plist \| grep RunAtLoad` | `=> true` |
| KeepAlive | `plutil -p .../...plist \| grep KeepAlive` | `=> true` |
| launchd 加载 | `launchctl print gui/$UID/ai.openclaw.gateway` | 含 `path = ~/Library/LaunchAgents/...` |
| label 唯一 | `launchctl list \| grep ai.openclaw.gateway` | 有这一行 |

## 一键验证脚本（直接跑）

```bash
UID_VAL=$(id -u)
PLIST=~/Library/LaunchAgents/ai.openclaw.gateway.plist

echo "① plist 存在    ：" $( [ -f "$PLIST" ] && echo ✅ || echo ❌ )
echo "② plist 合法    ：" $(plutil -lint "$PLIST" 2>&1 | grep -q "^OK$" && echo ✅ || echo ❌ )
echo "③ RunAtLoad     ：" $(plutil -p "$PLIST" | grep -q '"RunAtLoad" => true' && echo ✅ || echo ❌)
echo "④ KeepAlive     ：" $(plutil -p "$PLIST" | grep -q '"KeepAlive" => true' && echo ✅ || echo ❌)
echo "⑤ launchd 加载  ：" $(launchctl print "gui/$UID_VAL/ai.openclaw.gateway" 2>&1 | grep -q "path = /Users/kk/Library/LaunchAgents" && echo ✅ || echo ❌)
echo "⑥ service 健康  ：" $(curl -sS -m 3 http://127.0.0.1:18789/healthz 2>&1 | grep -q '"ok":true' && echo ✅ || echo "❌ 服务挂了,先看 gateway-upgrade-recovery")
```

## 用户常见误解

**"开机自启配置" ≠ "开机后一定能正常起服务"**。前者是 plist 是否就绪，后者取决于服务本身能不能解析所有 secret / 通过 migration checkpoint。

如果验证清单全 ✅ 但服务起不来，去 `openclaw-gateway-upgrade-recovery` 看 7 个陷阱（重点陷阱 5 Secret 严格校验 / 陷阱 6 Migration gate）。

## plist 持久自启的"最小可接受版"

```xml
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
  <dict>
    <key>Label</key><string>ai.openclaw.gateway</string>
    <key>ProgramArguments</key>
    <array>
      <string>/bin/sh</string>
      <string>/Users/kk/.openclaw/service-env/ai.openclaw.gateway-env-wrapper.sh</string>
      <string>/Users/kk/.openclaw/service-env/ai.openclaw.gateway.env</string>
      <string>/opt/homebrew/opt/node/bin/node</string>
      <string>/Users/kk/.openclaw/tools/node-v24.4.0/lib/node_modules/openclaw/dist/index.js</string>
      <string>gateway</string>
      <string>--port</string>
      <string>18789</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>WorkingDirectory</key><string>/Users/kk/.openclaw</string>
    <key>StandardOutPath</key><string>/Users/kk/Library/Logs/openclaw/gateway.log</string>
    <key>StandardErrorPath</key><string>/dev/null</string>
  </dict>
</plist>
```

**关键约束**：
- `ProgramArguments[3]` 必须是满足 OpenClaw Node 版本下限的 node（7.1+ 要 ≥25.9.0）
- 用 wrapper script 把 env 文件 source 进子进程——直接 EnvironmentVariables 字段在 launchd 启动时不读 ~/.openclaw/service-env/ai.openclaw.gateway.env
- 不要用 sed 改 plist，用 `plutil`（参考主技能陷阱 2/3）

## 反例

❌ 把 plist 复制到 `/Library/LaunchDaemons/`（那是 root 级，主人 user-level 服务用 `~/Library/LaunchAgents/`）
❌ 漏了 `RunAtLoad`（只在 launchd bootstrap 时起，**不** 开机自启）
❌ `KeepAlive` 漏掉崩了不自启——网关 OOM / npm 升级后死循环都需要它
❌ 不验证 launchd `print` 输出 `path =`——plist 文件存在不代表 launchd 加载了（trash 误删 / 之前 bootout 没 bootstrap 回来都常见）
