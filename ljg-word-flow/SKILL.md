---
name: ljg-word-flow
description: "Word flow: deep-dive word analysis + infograph card in one go. Takes one or more English words, runs ljg-word (generates deep semantics analysis) then ljg-card -i (generates infograph PNG). Use when user says '词卡', 'word card', 'word flow', or provides English words wanting both analysis and visual card."
user_invocable: true
version: "1.0.1"
---

# ljg-word-flow: 词卡

一条命令完成：解词 → 铸信息图。支持多词并行。

## 模式

**强制 NATIVE 模式。** 本 workflow 是纯 skill 管道（ljg-word → ljg-card -i），不需要 Algorithm 的七步流程。直接按下方执行步骤调用 skill，不走 OBSERVE/THINK/PLAN/BUILD/EXECUTE/VERIFY/LEARN。

## 参数

直接传入一个或多个英文单词，空格分隔。

```
/ljg-word-flow Obstacle
/ljg-word-flow Serendipity Resilience Entropy
```

## 执行

### 1. 收集单词列表

从用户消息中提取所有英文单词。

### 2. 处理每个单词

对每个单词，串行执行两步：

**步骤 A — 解词（ljg-word）：**

调用 Skill tool 执行 `ljg-word`，传入单词。在对话中输出 Markdown 解析结果。

**步骤 B — 铸信息图（ljg-card -i）：**

以步骤 A 的解析内容为输入，调用 Skill tool 执行 `ljg-card -i`。生成 PNG 文件到 `~/Downloads/`。

### 3. 多词并行

多个单词时，每个单词启动一个 Agent subagent 并行处理（每个 subagent 内部 A→B 串行）。

### 4. 汇总报告

```
════ 词卡完成 ═══════════════════════
📖 {Word1}
   🖼️ ~/Downloads/{Word1}.png

📖 {Word2}
   🖼️ ~/Downloads/{Word2}.png
...
```

## 关键约束

- 先解词后铸卡，顺序不可逆
- ljg-word 和 ljg-card -i 各自的质量标准不变
- 信息图内容来自解词结果，不是字典释义


---

## 🔴 使用前 CHECKPOINT

启动本 skill 前自问：
- 🔴 **任务范围明确吗？** — 用户给了具体的英文单词列表（不是中文 / 不是句子 / 不是专有名词）
- 🔴 **输入数据已准备好？** — 单词是英文 + 可拼写（不是拼音 / 不是缩写）
- 🔴 **输出格式清楚吗？** — 解析 (对话 Markdown) + 信息图 (~ /Downloads/ PNG) 各一份，多词汇总报告
- 🔴 **反例与黑名单扫一遍了吗？** — 单词用 ljg-word；句子用 ljg-read；多词纯信息图改用 ljg-card -i

## 失败模式与降级 (Failure Modes & Fallback)

- **如果 ljg-word 失败**（专有名词 / 缩写 / 词源缺失）→ 该词标"解析失败"，跳过信息图，其他词继续
- **如果 ljg-card -i 失败**（PNG 生成超时 / 字体缺失）→ 重试 3 次；仍失败保留 Markdown，信息图标"生成失败"
- **如果用户给的单词数量 >10** → 警告耗时（每个 ~3min），询问是否分批
- **如果某个单词是 brand 名称**（Apple / Nike）→ 不启动本 skill，提示用 ljg-paper 拆 logo 历史
- **如果 ~ /Downloads/ 写失败**（磁盘满 / 权限）→ 改写到 /tmp/ 并告知用户路径
- **如果用户要求"重做"某一词** → 只重做该词的解词+信息图，其他词保留

---

## 🚫 反例与黑名单（绝对不要做）

**ljg-word-flow 专属反模式**：

- 🚫 **不要**对中文词 / 短语 / 句子启动本 skill — 单词解剖器只对英文单词
- 🚫 **不要**让 ljg-card 凭空生成（无 ljg-word 解析）— 信息图内容必须来自解词结果
- 🚫 **不要**让一张信息图包含 >2 个单词 — 一图一词，混合 = 不可读
- 🚫 **不要**在单词数量 >5 时不警告 — 耗时 = N × (解词 1-2min + 信息图 1-2min)
- 🚫 **不要**省略 ~ /Downloads/ 路径 — PNG 默认下载目录
- 🚫 **不要**让单 ljg-card 失败阻塞其他单词 — 单词间独立并行，单卡失败 = 该词标"卡失败"继续下一个
- 🚫 **不要**为已有 ~ /Downloads/{Word}.png 时不询问 — 静默覆盖会让用户失去旧版本

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
