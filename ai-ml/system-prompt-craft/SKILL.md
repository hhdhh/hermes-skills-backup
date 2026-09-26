---
name: system-prompt-craft
description: Use when 写/调机器人或agent的系统提示词、要人味、对标官方prompt.
---

# System prompt 调教与对标

触发：写/改机器人对话 prompt（AutoLife 各机、321 人味金标准方向）、调 agent 系统提示词、用户嫌输出"机器味重"、或要参考业界官方 prompt 写法。

## 本地语料

- 全库：`~/.hermes/workspace/system_prompts_leaks/`（451 个泄露官方系统提示词；Anthropic 274 / OpenAI 87 / Google 24 / xAI 15 / Kimi / Qwen / DeepSeek；GLM 无隐藏系统提示词）
- 精华提炼：`~/.hermes/knowledge/wiki/agent-prompt-patterns.md`（诚实汇报/权限分级/写作风格/记忆设计，四家对照）
- 官方技能范本：`Anthropic/claude-code/skills/`（36 个 SKILL.md：code-review/debug/verify/security-review/doctor/deep-research，写技能时对标结构）

## 流程

1. 定目标：对话机器人（要人味、口语自然）还是 agent（要纪律、可验证）？两者判据不同，别用同一套。
2. 对标选型：去语料找同场景官方 prompt——对话→claude-ai 主 prompt；编程 agent→`Anthropic/claude-code/claude-code-fable-5.1.md`；编排/权限→`OpenAI/Codex/gpt-6-astra.md`。
3. 版本 diff 法：同产品两个版本（fable-5 vs fable-5.1 vs opus-5.5）跑 unified diff，新增段=官方认为最重要的迭代方向，比单看一个版本信息量大。
4. 提结构不提措辞：抽出"它规定了什么判据、什么顺序、什么禁令"，用自己的话重写进目标 prompt。
5. 人味扫尾：对话类 prompt 用下面禁词表逐条扫一遍。

## Pitfalls

- 禁止整段照抄泄露 prompt——有指纹，会污染输出，且各家措辞互相打架。
- AI 味禁词（Codex 官方清单，对话 prompt 必扫）：Bottom Line / delve / foster / leverage / "it's worth noting" / importantly / "Question? Answer." / "This isn't about X. It's about Y." / 连字符复合形容词 / 未被问就引入对比框架（"X, not Y"）。
- agent prompt 首要段放"诚实汇报"：done/sent/fixed 必须基于本会话工具输出；失败或跳过的步骤放汇报第一句。官方把它放开篇第一条不是偶然。
- 权限规则写成"审批具体可审的结果，不审批意图；授权跨回合持久"——避免 agent 反复请示惹恼用户。
- 汇报写作（agent 类）参考 Claude Code "Writing for the user"：结论先行、禁破折号插入语、数字进表格不进正文、内容说完就停不加收尾客套。