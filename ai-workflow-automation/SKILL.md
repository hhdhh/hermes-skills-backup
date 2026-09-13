---
name: ai-workflow-automation
description: AI Workflow Automation Expert skill. Helps users automate repetitive tasks using AI agents, OpenClaw skills, and multi-agent orchestration. Triggers on "workflow automation", "automate tasks", "AI agent setup", "build automation", "process automation", "OpenClaw automation", "multi-agent", "task orchestration". Provides end-to-end workflow design, skill recommendations, and implementation guides.
---

# AI Workflow Automation Expert

Turn repetitive work into autonomous AI workflows. This skill guides you through analyzing, designing, and implementing automation solutions using OpenClaw and its skill ecosystem.

## When This Skill Triggers

- "Help me automate [task/process]"
- "Build an AI agent workflow for..."
- "How do I set up automation with OpenClaw?"
- "I want to use multiple agents to..."
- "Create an automated pipeline for..."
- "Design a workflow that..."

## Core Workflow

### Step 1: Analyze the Process

Before automating, understand what needs automation:

1. **Map the current process**
   - What are the input and output?
   - What steps are currently manual?
   - What decisions require human judgment?
   - What tools/platforms are involved?

2. **Identify automation candidates**
   - Repetitive tasks (daily/weekly)
   - Rule-based decisions
   - Data transformation steps
   - Multi-platform sync needs

3. **Assess complexity**
   - Simple: Single tool, straightforward logic
   - Medium: Multiple tools, conditional branching
   - Complex: Multi-agent coordination, state management

### Step 2: Design the Workflow

Match complexity to the right approach:

| Complexity | Approach | Tools |
|------------|----------|-------|
| Simple | Single skill + cron | OpenClaw + cron skill |
| Medium | Multi-skill pipeline | agent-orchestrator + automation-workflows |
| Complex | Multi-agent system | autonomous-tasks + proactive-agent |

**Design principles:**
- Start small, iterate
- Each step should have clear input/output
- Include error handling and retries
- Log everything for debugging

### Step 3: Select Skills

Browse the skill ecosystem for relevant tools:

**Content Automation:**
- `content-repurposer` - Transform content across formats
- `twitter-autopilot` - Social media automation
- `newsletter-generator` - Email newsletter creation

**Data Processing:**
- `xlsx` / `xlsx-cn` - Spreadsheet manipulation
- `pdf` / `nano-pdf` - PDF operations
- `docx` / `docx-cn` - Word document handling

**Agent Orchestration:**
- `autonomous-tasks` - Self-driven task execution
- `agent-orchestrator` - Multi-agent coordination
- `proactive-agent` - Anticipatory actions

**API Integration:**
- `api-gateway` - 100+ API connections (OAuth managed)
- `brave-search` / `online-search` - Web search
- `tencent-docs` - Tencent Docs integration

### Step 4: Implement

**Pattern 1: Simple Cron Job**
```yaml
# Use OpenClaw cron skill
schedule: "0 9 * * *"  # Daily at 9am
task: "Check emails and summarize important ones"
skills: ["email-skill", "summarize"]
```

**Pattern 2: Triggered Pipeline**
```yaml
# Use automation-workflows skill
trigger: "new_file_in_folder"
steps:
  - skill: "pdf"
    action: "extract_text"
  - skill: "content-repurposer"
    action: "convert_to_blog"
  - skill: "twitter-autopilot"
    action: "schedule_post"
```

**Pattern 3: Multi-Agent System**
```yaml
# Use agent-orchestrator skill
agents:
  - role: "researcher"
    skills: ["brave-search", "deep-research-pro"]
  - role: "writer"
    skills: ["docx-cn", "seo-article-gen"]
  - role: "publisher"
    skills: ["twitter-autopilot", "newsletter"]
coordinator: "autonomous-tasks"
```

### Step 5: Test & Iterate

1. **Dry run** - Execute manually first
2. **Monitor** - Check logs for errors
3. **Iterate** - Refine based on results
4. **Scale** - Add complexity gradually

## Quick Templates

### Daily Report Automation
```
Trigger: Every day at 6pm
Steps:
1. Query data sources (API/DB)
2. Generate summary with charts
3. Format as PDF/HTML report
4. Send via email
Skills: api-gateway, xlsx, pdf, email-skill
```

### Content Pipeline
```
Trigger: New blog post published
Steps:
1. Extract key points
2. Generate social media posts
3. Create newsletter snippet
4. Schedule across platforms
Skills: content-repurposer, twitter-autopilot, newsletter-generator
```

### Customer Inquiry Handler
```
Trigger: New support email
Steps:
1. Classify inquiry type
2. Generate draft response
3. Route to appropriate agent
4. Track resolution
Skills: email-skill, ecommerce-customer-service-pro, autonomous-tasks
```

## Best Practices

1. **Fail gracefully** - Always have fallback behavior
2. **Log everything** - Debug without guessing
3. **Version control** - Track workflow changes
4. **Document decisions** - Future-you will thank you
5. **Start simple** - Add complexity after it works

## Common Pitfalls

- Over-engineering from day one
- Not handling API rate limits
- Missing error states
- Forgetting to test edge cases
- No human oversight for critical decisions

## References

For detailed implementation guides, see:
- [references/cron-patterns.md](references/cron-patterns.md) - Scheduling patterns
- [references/multi-agent-patterns.md](references/multi-agent-patterns.md) - Agent coordination


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
