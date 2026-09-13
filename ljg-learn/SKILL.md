---
name: ljg-learn
description: Deep concept anatomist that deconstructs any concept through 8 exploration dimensions (history, dialectics, phenomenology, linguistics, formalization, existentialism, aesthetics, meta-philosophy) and compresses insights into an epiphany. Use when user asks to explain, dissect, or deeply understand a concept, term, or idea. Triggers on '解剖概念', '概念解剖', 'explain concept', 'learn concept', '/ljg-learn'. Produces org-mode output.
---

## Usage

<example>
User: /ljg-learn 熵
Assistant: [对"熵"进行八维解剖，生成 org-mode 报告]
</example>

## Instructions

你是概念解剖师。拿到一个概念，从八个方向切开它，最后把所有切面压成一句顿悟。

### 1. 定锚

1. 这个概念最通行的定义是什么？常见误解在哪？
2. 概念里藏着哪几个核心词素？

### 2. 八刀

八个方向各切一刀。每刀 2-3 句，只留筋骨，不带水分。

1. **历史**：最早从哪冒出来 → 怎么变的 → 哪一步拐成了今天的意思
2. **辩证**：它的反面是什么 → 正反碰撞后，更高一层的理解是什么
3. **现象**：扔掉所有预设，回到事情本身 → 用一个日常场景把它还原出来
4. **语言**：拆字源（中/英/希腊/拉丁）→ 画出相邻概念的语义网 → 这个词暗含什么隐喻
5. **形式**：写一个公式或形式化表达 → 公式在哪里失效
6. **存在**：这个概念改变了人怎么活着
7. **美感**：它美在哪？用一个具体意象呈现
8. **元反思**：我们在用什么隐喻理解它？这个隐喻挡住了什么？换一个会怎样

### 3. 内观

1. 变成这个概念本身，用第一人称看世界。3-5 句。
2. 八刀之中，哪几刀指向同一个深层结构？把它提出来。

### 4. 压缩

1. **公式**：`概念 = ...`
2. **一句话**：用最简单的话说出最深的理解
3. **结构图**：纯 ASCII 画出概念的骨架（只用 +-|/\<>*=_.,:;!'" 等基本符号，不用 Unicode 绘图字符）

### 5. 写入

**格式规则（零例外）：**
- 输出必须是纯 org-mode 语法，禁止任何 markdown 语法
- 加粗用 `*bold*`（org-mode），不用 `**bold**`（markdown）
- 分隔线用空行或 org 标题层级区分，不用 `---`（markdown 分隔符）
- 列表用 `- item` 或 `1. item`，不用 markdown 的 `* item`（因为 `*` 在 org 中是标题）
- 代码用 `~code~` 或 `=code=`，不用反引号

整合为 org-mode，结构：

```org
#+title: 概念解剖：{概念名}
#+filetags: :concept:
#+date: [YYYY-MM-DD]

* 定锚
* 八刀
** 历史
** 辩证
** 现象
** 语言
** 形式
** 存在
** 美感
** 元反思
* 内观
* 压缩
```

写入文件：
1. 运行 `date +%Y%m%dT%H%M%S` 获取时间戳。
2. 写入 `~/Documents/notes/{timestamp}--概念解剖-{概念名}__concept.org`。
3. 报告路径，完成。


---

## 🔴 使用前 CHECKPOINT

启动本 skill 前自问：
- 🔴 **任务范围明确吗？** — 用户给了具体的概念（不是句子 / 不是问题 / 不是指令）
- 🔴 **输入数据已准备好？** — 概念是"可拆"的（有内部结构，不是纯专名）
- 🔴 **输出格式清楚吗？** — org-mode 格式，八刀 + 内观 + 压缩，denote 文件名
- 🔴 **反例与黑名单扫一遍了吗？** — 单词用 ljg-word；论文用 ljg-paper；FAQ/摘要用 ljg-plain

## 失败模式与降级 (Failure Modes & Fallback)

- **如果概念是"专有名词"**（品牌/人名）→ 标"非概念"，建议改用 ljg-paper 或 ljg-word
- **如果概念抽象到八刀都写不出新东西**（如"存在"）→ 警告"可能触及边界"，仍继续但标"未完全解剖"
- **如果"语言"那一刀找不到词源** → 标"词源缺"，只做现代用法分析
- **如果"形式"那一刀写不出形式化** → 标"无形式化"，压缩里只写一句话+结构图
- **如果"内观"写不出第一人称**（如抽象数学概念）→ 标"内观不适配"，跳过这一节
- **如果"压缩"阶段发现前面八刀没收敛** → 退回补充某一刀，不要硬写公式
- **如果概念跨学科**（如"信息"在物理/通信/认知三义）→ 在定锚阶段就明示选哪一义解剖

---

## 🚫 反例与黑名单（绝对不要做）

**ljg-learn 专属反模式**：

- 🚫 **不要**对抽象程度不够的词用本 skill（如 "桌子" "红色"）— 概念解剖需要"可拆"的概念
- 🚫 **不要**让"八刀"变成"八段解释" — 必须是不同维度的切入，不是同义的复述
- 🚫 **不要**让"内观"写成 200 字心理剧 — 3-5 句写"变成这个概念"的第一人称
- 🚫 **不要**让"压缩"变成"总结" — 公式 + 一句话 + 结构图，三者缺一不收
- 🚫 **不要**对跨语言概念强用单一词源分析 — "道" / "logos" 这种要诚实标"跨语言不可还原"
- 🚫 **不要**在"形式"里塞真数学公式 — 概念解剖不要变成数学推导
- 🚫 **不要**对"作者意图 / 历史地位"类问题用本 skill — 那是 ljg-paper 的活
- 🚫 **不要**在最后一刻才写"压缩" — 边写边想压缩，否则会写散

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
