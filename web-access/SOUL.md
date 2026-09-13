# web-access Skill — 慧慧适配版

> 原始：eze-is/web-access (MIT)
> 适配：2026-05-17，针对 OpenClaw + MacBook Air M5 环境

---

## 🎯 定位

web-access 是**联网和浏览器操作的统一入口**，补充 OpenClaw 原生 WebSearch/WebFetch 缺少的：
1. **联网策略**：根据场景自主选择工具（Search/Fetch/curl/Jina/CDP）
2. **CDP 浏览器**：直连用户日常 Chrome，携带登录态，支持动态页面和交互操作
3. **并行分治**：多目标时分发子 Agent 并行执行

**与现有 browser-automation skill 的分工：**

| Skill | 擅长 | 场景 |
|-------|------|------|
| `web-access` | CDP 直连浏览器、登录态、社交媒体、复杂交互 | 需要登录/交互/动态内容 |
| `browser-automation` | Playwright 结构化操作、截图、多标签页管理 | 表单填充、批量操作、截图 |

---

## 🔧 前置条件

**Node.js 版本检查**（要求 22+，当前 v25.9.0 ✅）

**浏览器准备**（用户需要做一次）：
1. 打开 **Google Chrome**
2. 地址栏输入 `chrome://inspect/#remote-debugging`
3. 勾选 "Allow remote debugging for this browser instance"
4. 可能需要重启 Chrome

**首次使用前必须完成浏览器配置**，否则 CDP 会失败并给出明确指引。

---

## 🚀 启动 CDP Proxy

在需要 CDP 操作前，执行前置检查：

```bash
node ~/.openclaw/workspace/skills/web-access/scripts/check-deps.mjs
```

脚本会检查：
- Node.js 版本 ✅（v25.9.0 兼容）
- 浏览器远程调试端口是否打开
- Proxy 是否已连接（未运行则自动启动）

**成功** → 回复中展示须知：
> 温馨提示：部分站点对浏览器自动化操作检测严格，存在账号封禁风险。已内置防护措施但无法完全避免，Agent 继续操作即视为接受。

**失败** → 按输出错误信息处理，不自行猜测。

---

## 📡 CDP Proxy API

前置检查通过后，Proxy 运行在 `http://localhost:3456`，通过 curl 调用：

```bash
# 新建后台 tab（URL 走 POST body）
curl -s -X POST --data-raw 'https://example.com' http://localhost:3456/new

# 执行 JS（读 DOM、写内容、提交表单）
curl -s -X POST "http://localhost:3456/eval?target=ID" -d 'document.title'

# 点击元素（JS click）
curl -s -X POST "http://localhost:3456/click?target=ID" -d 'button.submit'

# 截图
curl -s "http://localhost:3456/screenshot?target=ID&file=/tmp/shot.png"

# 关闭 tab
curl -s "http://localhost:3456/close?target=ID"
```

---

## 🔀 工具选择策略

```
任务开始
    │
    ├── 需要登录态 / 交互操作 / 动态页面？
    │     └── 是 → CDP (web-access)
    │
    ├── 需要一手信息（官网/官方文档）？
    │     └── 是 → WebFetch 或直接 CDP
    │
    ├── 多独立目标并行调研？
    │     └── 是 → 分治给子 Agent（各自 CDP）
    │
    └── 通用搜索/信息发现
          └── WebSearch
```

---

## 📋 适配要点（对比 Claude Code 原版）

| 差异 | 调整 |
|------|------|
| OpenClaw 无 `CLAUDE_SKILL_DIR` | 路径硬编码为 `~/.openclaw/workspace/skills/web-access` |
| 子 Agent 机制不同 | 使用 OpenClaw `sessions_spawn` 并行任务 |
| 无需手动管理 Proxy 生命周期 | 每次 CDP 操作前跑 check-deps，自动启动 |
| MacBook Air 内存有限 | 避免密集开大量 tab，用完即关 |

---

## ⚠️ 重要提醒

- 所有操作都在 **新建的后台 tab** 中进行，不动用户已有 tab
- 任务结束必须 `/close` 自己创建的 tab，保持环境整洁
- Proxy 长期运行，不主动停止；切换浏览器需要 `pkill -f cdp-proxy.mjs`
- 社交平台（小红书等）存在封禁风险，建议用小号操作

---

## 📁 文件结构

```
~/.openclaw/workspace/skills/web-access/
├── SKILL.md              # 主 skill 说明
├── config.env            # 浏览器偏好（首次运行自动创建）
├── scripts/
│   ├── check-deps.mjs   # 环境检查 + Proxy 启动
│   ├── cdp-proxy.mjs     # CDP Proxy 核心
│   ├── browser-discovery.mjs
│   ├── find-url.mjs      # 本地书签/历史检索
│   └── match-site.mjs    # 站点经验匹配
├── references/
│   ├── cdp-api.md
│   └── site-patterns/    # 站点经验积累
└── templates/
    └── config.env.template
```

---

_适配日期：2026-05-17_
_原始作者：一泽 Eze（MIT License）_