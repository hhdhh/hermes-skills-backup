---
name: openclaw-dashboard-troubleshooting
description: 排查 OpenClaw Dashboard (http://127.0.0.1:18789/dashboard/) 加载失败问题。覆盖 JS module import 失败、登录 gate 渲染、Gateway password 获取、浏览器缓存与 hash 不匹配问题。触发词：dashboard 加载失败、面板打不开、Importing a module script failed、OpenClaw Dashboard 报错、login gate 卡住。
---

# openclaw-dashboard-troubleshooting

> Class-level skill：OpenClaw Gateway Dashboard 端到端排错。当主人说"面板加载失败"或 dashboard 报任何浏览器侧错误时触发。

## 核心事实（2026-07-14 实战沉淀）

OpenClaw 7.1+ 的 Dashboard 是 **Vite prebuild** + ES module + Lit components + React 路由混合栈：
- HTML 入口：`http://127.0.0.1:18789/dashboard/` → 引用 `./assets/index-<hash>.js`
- JS 主 bundle：`index-zot7ymVq.js`（7/14 实测 ~378KB）
- 依赖 ~50 个 chunk（plugin-page / decorate / lit-runtime / i18n / config-runtime 等）
- **没有 `<script type="importmap">`** —— Vite 用 `__vite__mapDeps` 数组内联映射

## 常见症状与根因

### 症状 1："Importing a module script failed"

**浏览器侧根因**：
- 浏览器缓存了**旧 HTML**，引用旧 hash 的 JS 文件
- 当前服务的 HTML 引用**新 hash** 的 JS，但旧 HTML 还在 Service Worker / 浏览器缓存里
- 浏览器加载旧 HTML → 找不到旧 hash JS（已经被新版本替换）

**服务端验证**：
```bash
# 1. 确认 HTML 和 JS 都还活着
curl -sS -o /dev/null -w "HTML %{http_code}\n" http://127.0.0.1:18789/dashboard/
curl -sS http://127.0.0.1:18789/dashboard/ | grep -oE 'src="[^"]+"'
# 拿到当前 hash,比如 index-zot7ymVq.js

curl -sS -o /dev/null -w "JS %{http_code} size=%{size_download}\n" \
  http://127.0.0.1:18789/assets/index-zot7ymVq.js
# 必须 HTTP 200 + size > 100KB

# 2. 确认 gateway 服务本身活着
curl -sS http://127.0.0.1:18789/healthz
# 必须 {"ok":true,"status":"live"}
```

**修复（告诉主人在浏览器侧做）**：
```
1. chrome://settings/clearBrowserData → 时间"全部时间" → 勾"缓存的图片和文件"+"Cookie 和其他网站数据"
2. 关掉所有 OpenClaw 标签页
3. 重新访问 http://127.0.0.1:18789/dashboard/（注意用 127.0.0.1，不是 localhost）
4. 输入 Gateway password 登录
```

### 症状 2：Dashboard 渲染出 login gate 卡住

**这不是 bug，是预期行为**——OpenClaw 7.1 默认 `auth.mode = "token"`，dashboard 必须先登录。

**Gateway password 在哪**：
```bash
# Gateway password = OPENCLAW_GATEWAY_TOKEN env var（不是 gateway.password 配置）
set -a && source ~/.openclaw/service-env/ai.openclaw.gateway.env && set +a
echo "$OPENCLAW_GATEWAY_TOKEN"
# 64 字符 hex,以 8577 / 类似 prefix 开头（主人机器实测）
```

**给主人显示完整 token 的规则**：
- ✅ token 是主人自己的环境变量（不是第三方凭据）—— 可以直接 echo 给主人
- ❌ **不要显示 OpenAI/Anthropic/GitHub/HF 的 API key** 给主人（第三方凭据应让主人自己从 .env 复制）

**主人输入 password 后的下一步**：
- 如果报"Invalid token"→ token 不对，再 `echo $OPENCLAW_GATEWAY_TOKEN` 验证
- 如果登录成功但页面空白→ 还是症状 1（缓存），再强刷
- 如果登录成功页面正常→ 成功，不需要任何后续

### 症状 3：Chrome headless 调试 Dashboard（agent 端）

**不要开 Chrome 窗口给主人**——用 headless 模式跑出 DOM + 抓 console 错误：

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --headless=new \
  --no-sandbox \
  --disable-gpu \
  --user-data-dir=/tmp/chrome-debug \
  --enable-logging=stderr \
  --v=1 \
  --virtual-time-budget=10000 \
  --dump-dom \
  http://127.0.0.1:18789/dashboard/ \
  > /tmp/chrome-dump.out 2> /tmp/chrome-dump.err
```

**重要约束**：
- `timeout=30` 在 `subprocess.run` / `terminal` foreground 里会卡——Chrome headless 即使 `--virtual-time-budget=10000` 也可能不返回（macOS 系统 headless 偶尔挂窗口事件循环）
- **`--dump-dom` 输出到 stdout**（前缀是完整 HTML），**stderr 是 Chrome 内部日志**（带 module import / 404 / 错误的 debug 信息）
- 推荐用 Hermes `terminal(background=true)` 模式 + 25-30s 后 `pkill -f "Google Chrome"` 收尾，再 `tail` / `grep` 日志
- 用 `execute_code` 跑 Chrome 时**务必不要 `subprocess.run(... timeout=30)`**，改 background + read /tmp/chrome-dump.out

**抓 module import 失败**：
```bash
grep -iE "module|import|404|fail|exception|chunk|cors" /tmp/chrome-dump.err | head -40
```

**抓 console 输出**：
```bash
grep -iE "CONSOLE|^\[|Uncaught" /tmp/chrome-dump.err | head -30
```

**判别 Dashboard 渲染状态**：
```bash
# 看是不是渲染出 login gate（成功路径）
grep -oE 'class="[^"]+"' /tmp/chrome-dump.out | head -10

# 期望: 看到 login-gate / login-gate__card 等 class
# 如果空白 → JS 加载失败（症状 1）
# 如果只有 <head> 无 <body> 内容 → JS 解析失败
```

## 排查决策树

```
Dashboard 加载失败
├─ 服务端存活?
│   ├─ curl /healthz → {"ok":true,"status":"live"} → 服务 OK
│   └─ 服务挂了 → 跳到 workspace-hygiene skill 的坑 18（migration gate）
│
├─ HTML 引用 JS hash 与服务端一致?
│   ├─ curl HTML 拿到 src → curl JS 200 → 一致
│   └─ 不一致 → 主人浏览器缓存,告诉主人强清缓存
│
├─ Chrome headless --dump-dom 出什么?
│   ├─ 看到 login-gate class → 服务端完全 OK,是浏览器侧缓存问题
│   ├─ 看到空白 <body> → JS 解析失败,看 stderr 找具体哪个 chunk
│   └─ Chrome 30s timeout 没返回 → WebSocket 长连接,Vite HMR 卡住,刷新页面
│
└─ 主人输入 password 后?
    ├─ 登录成功页面正常 → 解决
    ├─ 报 Invalid token → echo $OPENCLAW_GATEWAY_TOKEN 验
    └─ 登录后空白 → 还是缓存,再强刷
```

## 反例（不该做的事）

❌ **不要 `plutil -replace` 改 dashboard 的 static asset 路径**——dashboard 资源由 OpenClaw 服务自己 serve,改 plist 没用
❌ **不要尝试用 `service worker unregister` 给主人**——owner 浏览器侧,agent 改不了
❌ **不要 echo $OPENCLAW_GATEWAY_TOKEN 到自己的 conversation memory**——token 写到日志/MEMORY 会泄露,只在响应里给主人看一次
❌ **不要让主人用 `localhost:18789`**——OWNER.md 偏好明确"用 127.0.0.1"
❌ **不要把 token 当 "API key" 类凭据保护**——它是 Gateway password,跟 OPENAI_API_KEY 不是一回事

## 联动

- `workspace-hygiene` 坑 18/19/20：磁盘清理与 hermes self-cleanup；与本 skill 正交
- **`openclaw-gateway-upgrade-recovery`**：Gateway **启动阶段**的所有失败（升级后启动卡 migration、Node 版本下限、plist 损坏、env 被裁、Secret 严格校验、launchd breaker）→ **先看那个 skill**，确认 gateway 启动 OK 后再跳到本 skill 看浏览器侧
- 本 skill 只负责 Gateway 启动成功后**浏览器侧**的 dashboard 问题
- `OWNER.md` 偏好：主人 dashboard 入口是 `http://127.0.0.1:18789/dashboard/`，用 127.0.0.1

## 验证清单（每次帮主人排查 dashboard 前必跑）

```bash
# 1. gateway 健康
curl -sS http://127.0.0.1:18789/healthz

# 2. dashboard HTML 200
curl -sS -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:18789/dashboard/

# 3. JS asset 200
JS=$(curl -sS http://127.0.0.1:18789/dashboard/ | grep -oE 'index-[^"]+\.js' | head -1)
curl -sS -o /dev/null -w "JS HTTP %{http_code} size=%{size_download}\n" \
  http://127.0.0.1:18789/assets/$JS

# 4. token 在 env 里
set -a && source ~/.openclaw/service-env/ai.openclaw.gateway.env && set +a
[ -n "$OPENCLAW_GATEWAY_TOKEN" ] && echo "TOKEN OK len=${#OPENCLAW_GATEWAY_TOKEN}" || echo "TOKEN MISSING"

# 5. chrome headless 渲染验证
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --headless=new --no-sandbox --disable-gpu \
  --user-data-dir=/tmp/chrome-debug \
  --dump-dom http://127.0.0.1:18789/dashboard/ \
  2>/dev/null | grep -oE 'class="[^"]+"' | head -3
# 期望看到 login-gate（成功）或空（缓存问题）
```

四项全 OK + Chrome headless 出 login-gate = **服务端完全健康，问题在主人浏览器缓存**，告诉主人强清即可。