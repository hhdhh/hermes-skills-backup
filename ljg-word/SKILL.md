---
name: ljg-word
description: Deep-dive English word mastery tool. Deconstructs a single English word into core semantics and epiphany. Use when user asks to explain/master a specific English word.
version: "1.0.1"
user_invocable: true
---

## Usage

<example>
User: Deeply explain the word "Serendipity".
Assistant: [Calls ljg-explain-words with "Serendipity"]
</example>

## Instructions

目标不是翻译，而是让用户掌握这个词的深层含义和用法。

针对输入的 `word`（转换为小写，首字母大写），进行以下分析，直接在对话中用 Markdown 输出：

### 输出结构

#### 1. 标题行

```
## {Word}  /{音标}/  {中文翻译}
```

#### 2. 核心语义

- **原始画面**: 用一句话描述该词源头最物理的画面（例如 Incubate: 母鸡趴在蛋上）。
- **核心意象**: 提炼公式（例如：温暖 + 时间 + 保护 = 孕育）。
- **解释**: 用充满洞见的语言阐述其深层含义与现代用法。分段清晰，**加粗**关键词。要有穿透力，展现词源、多领域含义之间的内在联系。

#### 3. 一语道破

一句中英双语的金句，必须具有哲学高度，总结该词的灵魂。用引用格式：

```
> "English sentence. 中文金句。"
```


---

## 🔴 使用前 CHECKPOINT

启动本 skill 前自问：
- 🔴 **任务范围明确吗？** — 这是一个能"挖画面"的具体单词？（避免对专有名词/缩写误用）
- 🔴 **输入数据已准备好？** — 用户给了具体单词，不是"分析下这类词"
- 🔴 **输出格式清楚吗？** — Markdown 三段式：原始画面 / 核心意象 / 解释 + 一语道破
- 🔴 **反例与黑名单扫一遍了吗？** — 专有名词 / 缩写 / 长句 → 拒用本 skill

## 失败模式与降级 (Failure Modes & Fallback)

- **如果用户给的是短语而不是单词**（如 "kick the bucket"）→ 引导改用 ljg-read 或拆成单词
- **如果词源在标准词源词典（OED / Etymonline）查不到**（自造词 / 极小众术语）→ 标"词源存疑"，基于现代用法解释，不编造词源
- **如果音标系统不明确**（英美差异 / 重音位置）→ 用 IPA 标两套 + 标注地域
- **如果单词有 >5 个核心义项**（多义词如 "set"）→ 不强求覆盖所有义项，挑最深的 1-2 个写透
- **如果用户已经在 ljg-writes 流程中** → 不重复启动 ljg-word（避免输出冗余）
- **如果一语道破想不出哲学高度的句子** → 宁可不写，标"此处存而不论"，不要凑金句

---

## 🚫 反例与黑名单（绝对不要做）

**ljg-word 专属反模式**：

- 🚫 **不要**用本 skill 翻译整段话或长句 — ljg-word 是单词解剖器，句子请用 ljg-read / ljg-plain
- 🚫 **不要**对专有名词（品牌/人名/地名）启动本 skill — 它们没有"词源"可挖，强行用会编造
- 🚫 **不要**对缩写（API、URL、CRUD）启动本 skill — 缩写是约定不是词，没"画面"可还原
- 🚫 **不要**给"金句"硬套金句公式 — 如果一句话没有哲学高度，宁可不写"一语道破"
- 🚫 **不要**重复堆叠同义词 — "原始画面 / 核心意象 / 解释" 三段要分工，不是换皮
- 🚫 **不要**在音标错误的情况下继续 — 音标错了整个"画面还原"都不可信，先查 OED / Forvo
- 🚫 **不要**写超过 800 字 — 单词解剖不是论文，读者要"顿悟"不要"文献综述"

**达尔文 2.0 通用反模式**：

- 🚫 **不要**为简单任务启用本 skill — 开关成本不划算
- 🚫 **不要**跳过 🔴 CHECKPOINT — 跳过 = 自残
- 🚫 **不要**输入未验证的数据 — 先验证后处理
- 🚫 **不要**为凑进度忽略反例黑名单 — 红线就是红线

---

## 📚 References（外部参考）

- **达尔文 2.0** — `~/.claude/skills/darwin-skill/SKILL.md`
- **huihui-core** — 慧慧核心基础设施
- **huihui-engineering** — Karpathy + Matt Pocock 工程原则
- **huihui-writes** — 写作引擎（ljg-writes 改造型）
