---
name: ljg-paper-flow
description: "Paper workflow: read papers + cast cards in one go. Takes one or more arxiv links, paper URLs, PDFs, or paper names. For each paper, runs ljg-paper (generates org analysis) then ljg-card -v (generates visual sketchnote PNG). Use when user says '论文流', 'paper flow', '读论文并做卡片', '论文卡片', or provides multiple papers wanting both analysis and cards."
user_invocable: true
version: "1.0.2"
---

# ljg-paper-flow: 论文流

一条命令完成：读论文 → 生成解读 → 铸成卡片。支持多篇并行。

## 模式

**强制 NATIVE 模式。** 本 workflow 是纯 skill 管道（ljg-paper → ljg-card），不需要 Algorithm 的七步流程。直接按下方执行步骤调用 skill，不走 OBSERVE/THINK/PLAN/BUILD/EXECUTE/VERIFY/LEARN。

## 参数

| 参数 | 说明 |
|------|------|
| 无参数 | 对话中已提供的论文链接/文件 |
| `-l` | 卡片模具改用长图模式（默认 `-v` 视觉笔记） |
| `-i` | 卡片模具改用信息图模式 |
| `-c` | 卡片模具改用漫画模式 |

## 执行

### 1. 收集论文列表

从用户消息中提取所有论文来源（arxiv URL、PDF 路径、论文名称等）。

### 2. 并行处理每篇论文

对每篇论文，启动一个 Agent subagent，每个 subagent 按顺序执行两步：

**步骤 A — 读论文（ljg-paper）：**

调用 Skill tool 执行 `ljg-paper`，传入该论文的来源。等待完成，获得生成的 org 文件路径。

**步骤 B — 铸卡片（ljg-card）：**

读取步骤 A 生成的 org 文件，调用 Skill tool 执行 `ljg-card`（默认 `-v`，或按用户指定的模具参数），以 org 文件内容为输入。等待完成，获得 PNG 文件路径。

### 3. 汇总报告

所有论文处理完成后，汇总输出：

```
════ 论文流完成 ═══════════════════════
📄 {论文标题1}
   📝 解读: {org 文件路径}
   🖼️ 卡片: {PNG 文件路径}

📄 {论文标题2}
   📝 解读: {org 文件路径}
   🖼️ 卡片: {PNG 文件路径}
...
```

## 关键约束

- 每篇论文的两步必须串行（先 paper 后 card），但多篇论文之间并行
- ljg-paper 和 ljg-card 各自的质量标准、红线、品味准则不变
- 卡片内容来自生成的 org 文件，不是原始论文


---

## 🔴 使用前 CHECKPOINT

启动本 skill 前自问：
- 🔴 **任务范围明确吗？** — 用户给了具体的论文列表（URL / 名称 / PDF）？
- 🔴 **输入数据已准备好？** — 链接可达 / PDF 存在 / 名称能搜到
- 🔴 **输出格式清楚吗？** — 解读 (org) + 卡片 (PNG) 各一份，多论文汇总报告
- 🔴 **反例与黑名单扫一遍了吗？** — 单论文改用 ljg-paper；多论文纯卡片改用 ljg-card -v

## 失败模式与降级 (Failure Modes & Fallback)

- **如果 ljg-paper 失败（URL 不可达 / PDF 损坏 / 论文太偏）** → 该篇标"论文读取失败"，跳过 ljg-card，其他论文继续
- **如果 ljg-card 失败（PNG 生成超时 / 字体缺失）** → 重试 3 次；仍失败则保留 org 文件，PNG 标"生成失败"
- **如果用户给的论文数量 >5** → 警告可能耗时（每篇 3-8 分钟），询问是否分批
- **如果 ljg-paper 和 ljg-card 的 quality 标准冲突** → 以 ljg-card 为准（最终产物是卡片）
- **如果某篇论文跨多个 subagent 失败** → 汇总报告里清楚标每篇状态，不要假装全成功
- **如果用户要求"重做"某一篇** → 只重做该篇的 ljg-paper + ljg-card，其他论文保留

---

## 🚫 反例与黑名单（绝对不要做）

**ljg-paper-flow 专属反模式**：

- 🚫 **不要**在 ljg-paper 失败时静默跳到 ljg-card — 必须明示该篇论文跳过
- 🚫 **不要**让 ljg-card 凭空生成（无 org 输入）— 卡片内容必须来自 ljg-paper 产物
- 🚫 **不要**对同一篇论文串行里又并行 — 步骤 A→B 是串行，多论文之间才是并行
- 🚫 **不要**在 arxiv URL 错误时硬猜论文名 — 显式标 "URL 不可达" 跳过
- 🚫 **不要**让一张卡片包含 >2 篇论文内容 — 一图一论文，混合 = 不可读
- 🚫 **不要**在 PNG 生成失败时只重试 1 次就放弃 — 至少 3 次重试再降级到 org-only 输出
- 🚫 **不要**省略汇总报告 — 报告是用户回看的入口，跳过 = 失忆

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
