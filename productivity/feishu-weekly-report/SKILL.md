---
name: feishu-weekly-report
description: Use when the user gives a rough one-line summary of their...
---


# Feishu Weekly Report (周报)

> 完整描述："Use when the user gives a rough one-line summary of their week's work and needs it expanded into the standard four-section weekly report (周报) for Feishu. Produces 本周总结/复盘与判断/需要的支持/下周规划 in a concise formal style."

Expand the user's rough weekly description into the company's fixed four-section form, ready to paste into Feishu. Triggered by: a rough work summary ("这周负责X和Y"), the pasted "本人填写层" form headers, or any mention of 周报/weekly report.

Distinct from `lark-workflow-standup-report` (that one auto-aggregates calendar+tasks; this one expands the user's own words into the fixed form).

## Fixed output contract

`**本人填写层**` header, then four sections with EXACT headers, in this order:

- **本周总结** — personally completed + concrete results
- **复盘与判断** — one effective judgment + one adjustment
- **需要的支持** — actionable asks
- **下周规划** — delivery + action items

Rules: no emojis inside the report body; bold headers on their own lines; deliver clean final text only — never include reasoning/thinking content in the reply.

## Expansion rules

- Turn each rough item into one formal clause: verb + object + outcome ("完成X需求对接，保障Y正常进行"). Stay factual — never invent numbers, dates, or metrics the user did not give.
- 复盘 pattern: effective = 提前对齐需求 / 边装边测尽早暴露问题； adjustment = 标准化流程 / 沉淀问题清单 / 完善检查项. Vary the wording — never reuse the same sentence across iterations or weeks.
- 需要的支持 must be concrete: 确认验收标准、同步排期、协助闭环软硬件问题 — not "希望多多支持".
- 下周规划 mirrors this week's open threads and closes their loops (跟进问题闭环、完善方案、沉淀文档).

## Iteration commands

- "再换个说法" → rewrite all four sections: different sentence structure and vocabulary, same facts, similar length.
- "再简短一点" → one sentence per section; stay that short on all later repeats unless asked to expand.
- "回复一下" → output the current report again (lightly polished), no meta commentary, no questions.

## Input modes

- Rough text → expand directly. Do NOT ask clarifying questions; the one-liner is always sufficient (missing facts stay generic).
- "根据飞书内容回答" with an attached/linked doc → a spec or statistics doc (e.g. 数采规范汇编) is NOT the user's weekly work. Extract personal deliverables only if identifiable; otherwise ask ONE short line for their actual work items rather than passing doc content off as personal accomplishments.
- No input at all → ask one short line for the week's work items.

## User context

FAE at 智动未来 (AutoLife Robotics). Recurring vocabulary: 遥操数据清洗、机器人装机/检修/测试、现场比赛或酒店技术支持保障、出货准备、机器人软硬件与工具学习。Reports go to a workplace audience — keep the register formal, humble-but-factual, and compact.