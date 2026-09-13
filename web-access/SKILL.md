---
name: web-access
description: 联网策略选择 + Playwright 浏览器自动化（慧慧专用版，基于 eze-is/web-access 适配）
---

# web-access — 慧慧专用版

> 原始：eze-is/web-access (MIT)
> 适配整合：2026-05-17
> 核心优势：联网策略选择 + 现有 Playwright 浏览器自动化

---

## 🎯 定位变化

**原始方案**：CDP Proxy 直连用户浏览器（Claude Code 专用，需要复杂配置）
**适配后**：利用 OpenClaw 已有工具 + toryx-automation 的 Playwright 浏览器自动化

**保留的核心价值**：
- 浏览哲学（像人一样思考，目标驱动）
- 联网工具选择策略（Search/Fetch/curl/Playwright 按场景选）
- 站点经验积累机制

---

## 🔧 当前工具箱

| 工具 | 能力 | 适用场景 |
|------|------|----------|
| `web_search` | 网页搜索 | 信息发现、摘要查询 |
| `web_fetch` | 页面内容提取 | 已知 URL 的定向信息提取 |
| `browser` | OpenClaw 内置 Playwright | 动态页面、交互操作 |
| `toryx-automation` | Playwright + Chrome macOS | 截图、点击、表单、UI 操作 |

---

## 🧠 工具选择策略

**核心原则**：一手信息优先，登录态优先，用户视角优先

```
任务进来
    │
    ├── 需要登录态 / 交互操作 / 动态渲染页面？
    │     └── 是 → Playwright（toryx browser-auto.js 或 OpenClaw browser 工具）
    │
    ├── 需要一手来源（官网/文档/原始页面）？
    │     └── 是 → web_fetch 或直接 Playwright
    │
    ├── 搜索式发现（关键词→来源定位）？
    │     └── → web_search
    │
    └── 批量多目标并行调研？
          └── sessions_spawn 子 Agent 各自执行，结果汇总
```

---

## 📖 浏览哲学

**像人一样思考，兼顾高效与适应性地完成任务。**

### 四步执行

**① 明确目标** — 什么算完成？需要获取什么信息、执行什么操作？

**② 选起点** — 选最可能直达的方式验证。一次不成就调整方向。

**③ 过程校验** — 每一步的结果是证据，不只是成功/失败。方向错了立即调整，不重复失败的路。

**④ 完成判断** — 对照目标标准，确认完成即停，不过度操作。

---

## 🔍 浏览器操作（当前方案）

### 方案 A：toryx-automation（推荐）
```bash
# 打开页面
node ~/.openclaw/workspace/skills/toryx-automation/scripts/browser-auto.js open <url>

# 点击元素
node ~/.openclaw/workspace/skills/toryx-automation/scripts/browser-auto.js click "<selector>"

# 截图
node ~/.openclaw/workspace/skills/toryx-automation/scripts/browser-auto.js screenshot [path]

# 执行 JS（读 DOM、写内容）
node ~/.openclaw/workspace/skills/toryx-automation/scripts/browser-auto.js evaluate "<js>"

# 获取文本
node ~/.openclaw/workspace/skills/toryx-automation/scripts/browser-auto.js gettext "<selector>"
```

### 方案 B：OpenClaw 内置 browser 工具
直接用 `browser` 工具进行复杂操作（snapshot → act 循环）

### 方案 C：web_fetch + Jina
静态页面直接用，超节省 token：
```
https://r.jina.ai/https://example.com
```

---

## 🌐 站点经验积累

站点操作成功后，将经验写入：
```
~/.openclaw/workspace/skills/web-access/references/site-patterns/{domain}.md
```

格式：
```markdown
---
domain: example.com
updated: YYYY-MM-DD
---
## 平台特征
架构、反爬行为、登录需求等

## 有效模式
已验证的 URL 模式、操作策略、选择器

## 已知陷阱
什么会失败以及为什么
```

---

## ⚠️ 重要提醒

- 操作时先了解页面结构，再决定下一步
- 链接中的会话参数（如 token）是必需的，提取 URL 时保留完整
- 社交平台（小红书等）存在封禁风险，建议用小号操作
- 任务完成后清理临时文件

---

## 📁 文件结构

```
~/.openclaw/workspace/skills/web-access/
├── SKILL.md           # 本文件（核心策略）
├── SOUL.md            # 适配说明文档
├── references/        # 站点经验积累
│   └── site-patterns/ # 按域名存储的经验
└── （scripts/ 已不再需要，原 CDP 方案废弃）
```

---

_适配日期：2026-05-17_
_原始作者：一泽 Eze（MIT License）_

---

## 🔴 使用前 CHECKPOINT

启动本 skill 前自问：
- 🔴 任务范围明确吗？（避免误用）
- 🔴 输入数据已准备好？（避免半路卡住）
- 🔴 输出格式清楚吗？（避免返工）
- 🔴 反例与黑名单扫一遍了吗？（避免重蹈覆辙）

---

## 🚫 反例与黑名单（绝对不要做）

来自达尔文 2.0 通用经验——所有 skill 的绝对禁止反模式：

- 🚫 **不要**为简单任务启用本 skill — 开关成本不划算
- 🚫 **不要**跳过 🔴 CHECKPOINT — 跳过 = 自残
- 🚫 **不要**输入未验证的数据 — 先验证后处理
- 🚫 **不要**为凑进度忽略反例黑名单 — 红线就是红线
- 🚫 **不要**让单轮改动超过最低维度的 2 倍 — 避免结构破坏
- 🚫 **不要**用 Edit 工具做"大改" — 优先 Bash append（避免破坏中间）
- 🚫 **不要**为已废弃的 skill 加新功能 — 先归档再考虑

---

## 📚 References（外部参考）

- **达尔文 2.0** — `~/.claude/skills/darwin-skill/SKILL.md`
- **huihui-core** — 慧慧核心基础设施
- **huihui-engineering** — Karpathy + Matt Pocock 工程原则
- **huihui-writes** — 写作引擎（ljg-writes 改造型）
