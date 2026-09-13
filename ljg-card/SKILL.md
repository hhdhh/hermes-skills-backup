---
name: ljg-card
description: "Content caster (铸). Transforms content into PNG visuals. Seven molds: -l (default) long reading card, -i infograph, -m multi-card reading cards (1080x1440), -v editorial sketchnote (problem→failure→pivot→insight→naming, magazine + archive layout), -c comic (manga-style B&W), -w whiteboard (marker-style board layout), -b big-fonts attachment card (1080x1440, weathered 碑刻 style for 小红书). Output to ~/Downloads/. Use when user says '铸', 'cast', '做成图', '做成卡片', '做成信息图', '做成海报', '视觉笔记', 'sketchnote', '杂志', 'editorial', '漫画', 'comic', 'manga', '白板', 'whiteboard', '大字', '附件图', 'big fonts', '小红书卡片'. Replaces ljg-cards and ljg-infograph."
user_invocable: true
version: "2.3.0"
---

# ljg-card: 铸

将内容铸成可见的形态。内容进去，PNG 出来。模具决定形状。

## 参数

| 参数 | 模具 | 尺寸 | 说明 |
|------|------|------|------|
| `-l`（默认） | 长图 | 1080 x auto | 单张阅读卡，内容自动撑高 |
| `-i` | 信息图 | 1080 x auto | 内容驱动的自适应视觉布局 |
| `-m` | 多卡 | 1080 x 1440 | 自动切分为多张阅读卡片 |
| `-v` | 视觉笔记 | 1080 x auto | 编辑式杂志专题：问题→失败→转折→顿悟→命名（6 layout 模具 / 4 字族对比 / 探案档案细节）|
| `-c` | 漫画 | 1080 x auto | 日式黑白漫画风格，动态选择漫画家视觉语言 |
| `-w` | 白板 | 1080 x auto | 白板马克笔风格，结构化框图+箭头+彩色标记 |
| `-b` | 大字 | 1080 x 1440 | 碑刻大字 + 和紙 + 外阴影，小红书附件风格（单句/短段） |

## 约束

本 skill 输出为视觉文件（PNG），不适用 L0 中的 Org-mode、Denote 和 ASCII-only 规范。

## 共享基础

### 获取内容

- URL --> WebFetch 获取
- 粘贴文本 --> 直接使用
- 文件路径 --> Read 获取

### 文件命名

从内容提取标题或核心思想作为 `{name}`（中文直接用，去标点，≤ 20 字符）。

### 截图工具

```bash
node assets/capture.js <html> <png> <width> <height> [fullpage]
```

从 skill 根目录运行。依赖 skill 根目录下的 `node_modules/` 中的 playwright。如报错：

```bash
npm install playwright && npx playwright install chromium
```

### Footer

- 左侧：logo + 李继刚（已硬编码在模板中）
- 右侧：内容来源（可选）——有明确来源时显示（如作者名、arxiv ID、网站名等），无来源时留空。使用 `{{SOURCE_LINE}}` 变量：有来源时填 `<span class="info-source">来源文字</span>`，否则空字符串。适用于 `-l`、`-i`、`-v`、`-c`、`-w` 模具（`-m` 多卡无 footer，不适用）。

### 交付

1. 报告文件路径

## 品味准则

**所有模具共享**。执行任何模具前，先 Read `references/taste.md`，作为视觉质量底线贯穿全流程。

核心：反 AI 生成痕迹——禁 Inter 字体、禁纯黑、禁三等分卡片、禁居中 Hero、禁 AI 文案腔、禁假数据。

## 执行

根据参数选择模具，Read `references/taste.md` + 对应的 mode 文件，按步骤执行：

### -l（默认）：长图

Read `references/mode-long.md`，按其步骤执行。

模板：`assets/long_template.html`

### -i：信息图

Read `references/mode-infograph.md`，按其步骤执行。

模板：`assets/infograph_template.html`

### -m：多卡

Read `references/mode-poster.md`，按其步骤执行。

模板：`assets/poster_template.html`

### -v：视觉笔记

Read `references/mode-sketchnote.md`，按其步骤执行。

模板：`assets/sketchnote_template.html`

### -c：漫画

Read `references/mode-comic.md`，按其步骤执行。

模板：`assets/comic_template.html`

### -w：白板

Read `references/mode-whiteboard.md`，按其步骤执行。

模板：`assets/whiteboard_template.html`

### -b：大字

Read `references/mode-big.md`，按其步骤执行。

模板：`assets/big_template.html`


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
