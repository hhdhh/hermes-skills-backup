# Cross-Skill Routing Matrix — Obscura × Taste-Skill × Impeccable

After installing these three families, Claude Code can route design/UI/UX tasks
across them. This file documents the boundaries so the right skill is picked
first time.

## Skill families at a glance

| Family | Skills | Size | Trigger (one-liner) |
|---|---|---|---|
| **Obscura** | `obscura` | 252 行 | "抓 / 解析 / 提取 — Rust headless 浏览器 + 35 MCP 工具（**不渲染 CSS**）" |
| **Taste-skill** (13) | `taste-skill`, `taste-skill-v1`, `brutalist-skill`, `minimalist-skill`, `soft-skill`, `stitch-skill`, `redesign-skill`, `output-skill`, `imagegen-frontend-web`, `imagegen-frontend-mobile`, `image-to-code-skill`, `brandkit`, `gpt-tasteskill` | 88KB 主 + 12 风格变体 | "好看 / anti-slop / 不像 AI 默认模板" |
| **Impeccable** | `impeccable` (含 39 scripts + 27 references) | 1.9MB | "production UI / 设计系统 / 工艺 / 审查" |

## Routing rules

### Pick by **intent** (what the user wants)

| User says… | Route to | Why |
|---|---|---|
| "抓 https://x.com 的 markdown" | `obscura` | One-shot page grab |
| "抓 reference site 看一下设计" | `obscura` first（拿 DOM + tokens）, then `impeccable audit`（设计审查）| 抓 + 设计审查组合（Obscura 不做视觉验证，只做结构抓取）|
| "做一个 landing page" | `taste-skill` (anti-slop) → if "production-grade" then `impeccable shape/craft` | taste-skill 强在 anti-default；impeccable 强在 production polish |
| "做一个 dashboard" | `impeccable shape` | Dashboard = app UI = product register，impeccable 主场 |
| "做一个 portfolio" | `taste-skill` (editorial / kinetic) | portfolio = brand register，taste-skill 主场 |
| "做一个 minimalist 风格 X" | `minimalist-skill` 或 `taste-skill` | 风格特定走子 skill |
| "做一个 brutalist 风格 X" | `brutalist-skill` | 同上 |
| "重做 / redesign 已有站点" | `redesign-skill` (audit-first) → `impeccable shape/polish` | 重设计两步走 |
| "用图生代码" | `image-to-code-skill` | 图片 → 代码直转 |
| "做品牌指南" | `brandkit` | 高端品牌物料 |
| "audit 现有 UI 设计" | `impeccable audit` | 系统化审查 |
| "批判 / critique UI 决定" | `impeccable critique` | 结构化批评 |
| "动画 / motion 设计" | `impeccable animate` (有 reference/animate.md) | Motion 主场 |
| "改字号 / 排版" | `impeccable typeset` (有 reference/typeset.md) | Typography 主场 |
| "改色 / 调色" | `impeccable colorize` (有 reference/colorize.md) | Color 主场 |
| "做 mobile UI" | `imagegen-frontend-mobile` | Mobile-specific |
| "fetch + E2E 验证 UI" | `obscura serve --port 9222` + headless browser iteration | obscura 提供 CDP 调试面 |

### Pick by **register** (设计对象的性质)

| Register | Skill 偏好 | 原因 |
|---|---|---|
| **Brand register** (landing page, marketing, campaign) | `taste-skill` + `impeccable brand` | Design IS the product |
| **Product register** (app UI, dashboard, settings) | `impeccable product` | Design SERVES the product |
| **Hybrid** (B2B SaaS landing → product) | Both, sequence taste-skill first then impeccable product | 一致性优先 |

### Pick by **stage** (工作流阶段)

| Stage | Skill |
|---|---|
| **0. Brief inference** (read the room) | `taste-skill` §0.A-0.D 出色 |
| **1. Direction setting** (aesthetic, dial values) | `taste-skill` (3 dials: variance, motion, density) |
| **2. Audit existing** (redesign only) | `impeccable audit` |
| **3. Initial build** (draft the design) | `taste-skill` first pass; `impeccable craft` for production |
| **4. Polish / harden** (commit to details) | `impeccable polish/harden` |
| **5. Validate in browser** | `mavis-browser` (实 Chrome) 做视觉验证；`obscura` 做 DOM/token/链接结构验证 |
| **6. Live iterate** | `impeccable live` (has reference/live.md, 60KB) |

## Disambiguation examples

❓ "**做一个 X 网站**" — 不知道是 brand 还是 product？
1. 听 cue 词：`"landing page"` / `"portfolio"` / `"campaign"` → brand register
2. 看目标页：`"dashboard"` / `"app"` / `"admin"` → product register
3. **若 ambiguous** → `taste-skill` (它 §0.C 主动问 1 个澄清问题)

❓ "**把这个站改好看点**" — 是 redesign
1. 跑 `redesign-skill` 先 audit（不破坏已有品牌资产）
2. 切到 `impeccable shape` 给 production 落地
3. 最后 `mavis-browser` 反复验证视觉（**不用 obscura**：obscura headless 不应用 inline `<style>`）

❓ "**Linear-style 风格**" — 风格明确
1. `taste-skill` (它在 §0 显式提到 "Linear-style minimalist")
2. 子风格 → `minimalist-skill` 也可（更紧凑的 minimalist guide）

## Boundary check (avoid loading the wrong skill)

| Don't load | When |
|---|---|
| `impeccable` | 后端 / non-UI 任务（impeccable 的 description 显式说 "Not for backend-only or non-UI tasks"）|
| `taste-skill` | Dashboard / data table / multi-step product UI（taste-skill 显式说 "Not dashboards, not data tables, not multi-step product UI"）|
| `obscura` | 登录态页面、Python spider 项目、交互式 click/type（用 mavis-browser / scrapling / agent-browser） |

## Cross-references (each skill's own reference to this matrix)

- `obscura/SKILL.md` §6 (Boundaries) — points to recipe-pipeline.md (now also this file)
- `obscura/references/recipe-pipeline.md` — Recipe 5: moco + Obscura
- `obscura/references/cross-skill-routing.md` — **this file**
- `taste-skill/SKILL.md` §11 (Redesign) — natural entry to impeccable
- `impeccable/SKILL.md` §Setup step 5 — brand seed color via palette.mjs (Node script)

## Quick reference card (3 sentences)

> **Obscura** fetches and parses web pages headlessly (NOT a visual renderer — see §5 Blacklist).
> **Taste-skill** keeps the design from looking like AI slop.
> **Impeccable** polishes UI to production-grade craft with a 27-reference design system.
>
> **Flow**: brief → taste-skill (direction) → impeccable (craft) → obscura (validate in browser).
