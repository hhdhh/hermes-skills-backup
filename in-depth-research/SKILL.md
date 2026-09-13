---
name: "Deep Research"
description: "Conduct exhaustive multi-source investigation with methodology tracking, source evaluation, and iterative depth."
---

## Core Role

Deep Research = investigate thoroughly until the question is answered. Not surface search — systematic exploration with documented methodology.

**Not:** quick lookups (→ just search), combining existing docs (→ Synthesize), ongoing monitoring (→ Digest)

## Protocol

```
Scope → Search → Evaluate → Deepen → Synthesize → Document → Deliver
```

### 1. Scope

Before searching, clarify:
- What exactly needs answering?
- What depth is required? (Overview / Thorough / Exhaustive)
- What's the decision this enables?
- Time/effort budget?

Reframe vague questions into specific, answerable queries.

### 2. Search

Multi-vector approach (see `methodology.md`):
- Start broad, then narrow
- Multiple search engines/sources
- Follow citation trails
- Check primary sources when secondary cite them
- Look for contradicting viewpoints

Track every source. Nothing unattributed.

### 3. Evaluate

For each source (see `sources.md`):
- Authority: Who wrote this? What credentials?
- Recency: When? Still valid?
- Evidence: Claims backed by data?
- Bias: Any agenda or conflict?
- Corroboration: Do others confirm this?

Flag low-credibility sources. Weight findings accordingly.

### 4. Deepen

Research is iterative:
- Initial findings reveal new questions
- Follow promising threads
- Fill gaps identified
- Stop when: answer is clear, returns diminish, or budget exhausted

Document decision to stop and why.

### 5. Synthesize

Merge findings (use Synthesize skill patterns):
- Reconcile contradictions explicitly
- Weight by source quality
- Note confidence levels
- Identify remaining unknowns

### 6. Document

Research trail matters:
- Sources consulted (with links)
- Search queries used
- Why certain sources were weighted higher
- What was NOT found (gaps)

### 7. Deliver

Format per user needs (see `output-formats.md`):
- Executive: BLUF + key findings + confidence
- Academic: Full methodology + citations
- Working doc: All findings for further work

## Output Format (Default)

```
🔬 DEEP RESEARCH: [Topic]

⚡ ANSWER
[Direct answer to the question — 2-3 sentences]

📊 CONFIDENCE: [High/Medium/Low] — [why]

🔍 KEY FINDINGS
• [Finding 1] — [source]
• [Finding 2] — [source]
• [Finding 3] — [source]

⚠️ CAVEATS
• [Important limitation or uncertainty]

🕳️ GAPS
• [What couldn't be determined]

📚 SOURCES ([count])
[Numbered list with credibility notes]

🔎 METHODOLOGY
[Brief: what was searched, how sources were evaluated]
```

## Depth Levels

| Level | Effort | Sources | When |
|-------|--------|---------|------|
| Quick | 5-10 min | 3-5 | Simple factual questions |
| Standard | 30-60 min | 8-15 | Most research requests |
| Thorough | 2-4 hours | 20-30 | Important decisions |
| Exhaustive | Days | 50+ | Critical, high-stakes |

Confirm depth before starting. Adjust if findings warrant.

---

*References: `methodology.md`, `sources.md`, `output-formats.md`*


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
