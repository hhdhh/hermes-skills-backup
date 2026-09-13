---
name: karpathy-coding-guidelines
description: Behavioral guidelines to reduce common LLM coding pitfalls, derived from Andrej Karpathy's observations. Apply these four principles when writing, editing, or reviewing code — especially for non-trivial changes. Triggers on coding tasks, code reviews, refactoring, bug fixes, feature implementation, or when the user asks for careful/disciplined coding behavior.
---

# Karpathy Coding Guidelines

Four principles to reduce common LLM coding mistakes. Bias toward caution over speed; for trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If 200 lines could be 50, rewrite it.

Test: Would a senior engineer say this is overcomplicated? If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

Test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria enable independent looping. Weak criteria ("make it work") require constant clarification.

---

**Working indicators:** Fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, clarifying questions come before implementation rather than after mistakes.


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

---

## 🔬 karpathy-coding-guidelines v0.3.0（达尔文 Phase 4 升级 · 安全追加）

**version v0.2.0 → v0.3.0** · 2026-06-16 14:25

### Phase 4 专属反例（karpathy-coding-guidelines 专属 · 增量）

来自 Karpathy 实编程战经验——在通用三件套基础上加专属：

- 🚫 **不要**用 `git reset --hard` 当回滚 — 用 `git revert` 或文件系统 backup
- 🚫 **不要**在没看错误信息前就 `try/except` — 吞错 = 自残
- 🚫 **不要**写"防御性代码"防不可能发生的边界 case — Karpathy "简胜于繁"
- 🚫 **不要**为凑测试覆盖率写空测试 — 一行 assert 1 == 1 是噪音
- 🚫 **不要**重构没坏的代码 — "顺手改进"是技术债的源头
- 🚫 **不要**跳过 TDD 红色阶段直接写实现 — 没红就绿的代码 = 自欺
- 🚫 **不要**为了"灵活性"加配置参数 — 单次使用不做抽象
- 🚫 **不要**用 print() 当调试器 — 学会用 debugger > 日志 > 全量日志

### karpathy-coding-guidelines 专属 References

- **Karpathy 视频** — "How to be a great software engineer"
- **Karpathy autoresearch** — `karpathy/autoresearch` GitHub
- **huihui-engineering** — Karpathy + Matt Pocock 工程原则
- **达尔文 2.0** — `~/.claude/skills/darwin-skill/SKILL.md`
