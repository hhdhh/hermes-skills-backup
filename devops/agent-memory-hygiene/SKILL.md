---
name: agent-memory-hygiene
description: Use when 记忆库将满、写入失败或待审积压。三动词运营 Hermes 原生记忆。
---

# agent-memory-hygiene — Hermes 原生记忆运营规则

> 来源：2026-09-26 记忆库 96% 爆库事故复盘 + 本地/GitHub 方案选型（胜出：danyuchn/memory-engineering 的 WRITE/ROUTE/PRUNE 方法论，融合 smixs/agent-memory-skill 的分层衰减思想，适配 Hermes 原生记忆系统）。本地另有 smart-memory-manager/elite-longterm-memory/brain/fluid-memory 四个"平行记忆系统"技能——均依赖不存在的运行时（TS API/LanceDB/MCP/openclaw 原生工具），不解决原生库健康，勿用。

## 核心原则：删与写同等重要

MEMORY.md（2,200 字符）和 USER.md（1,375 字符）每会话全量注入，是**永远在线的税**。目标是让常驻上下文随时间变小而非变大。

## WRITE — 入库测试

写之前问：**"这条没了，我会犯错吗？"**
- 不会（任务性知识/流程/坑）→ 不进 memory，写技能，memory 只留指针 `见 skill: xxx`
- 会，且每次会话都可能用到 → memory/USER
- 只对某个任务重要 → session 里留着即可，刻意**不**持久化
- 写入时带上**为什么**（日期+来源），没 why 的条目将来没法审计
- 硬预算意识：单条超 150 字符就该拆或指向技能

## ROUTE — 分层路由表

| 知识类型 | 去处 | Hermes 对应 |
|---|---|---|
| 身份/偏好/硬边界（永远真） | 常驻层 | USER.md |
| 环境/机队/约定（跨任务事实） | 常驻层 | MEMORY.md，一行一事实 |
| 流程/方法/坑（怎么做事） | 程序层 | skills/<task>/SKILL.md（按需加载，零税）|
| 做了什么事（何时发生） | 日志层 | session 历史 + session_search（勿进 memory）|
| 完成的/过时的 | 归档层 | ~/.hermes/backups/ + knowledge/（出上下文）|

矛盾事实必须收敛到**唯一一条**（只留现行版）。

## PRUNE — 清理三触发

遇到任一情况主动清理（memory 工具 batch 一次成型，先备份）：
1. **错** → 立即删（被新事实取代的快照、已改的规则）
2. **完成** → 归档（展会结束的机号细节、一次性安装记录；这类属于技能/案例库）
3. **衰减** → 质疑：连续 2 个月未被任何会话用到、或技能指针可覆盖 → 删或缩成指针。灵感艾宾浩斯：不被提及的知识自然淡出，别硬留

## 满库应急（>=90% 或写入报 over the limit）

1. 三重备份：`cp -a memories/ pending/ → ~/.hermes/backups/pre-consolidation-<ts>/`，md5 校验
2. 官方 batch 整合：remove/replace 腾位 + add 新知一次成型（**勿对着满库反复 add**——断路器 3 次失败后熔断连坐）
3. 待审队列逐条定去向：已沉淀进技能→丢弃；已覆盖→丢弃；真新知→蒸馏合并。grep 技能锚点验证零丢失后再清（归档进备份）
4. 终态验证：双库 <90%、队列归零、盘上文件 cat 确认

队列积压处理细节（老→新回放、失败分类表、断路器复位）见 skill: hermes-write-approval-queue。

## 多工具组合架构（2026-09-26 二轮选型固化）

对比过 Letta/MemGPT、Zep/Graphiti、Mem0、anthropics/skills 官方库（无专用记忆技能，记忆内建产品）、basic-memory、mcp-zettel 后的落地方案：

| 层 | 工具 | 职责 |
|---|---|---|
| 常驻层 | MEMORY.md/USER.md（原生） | 每会话必需要的事实，字符预算硬约束 |
| 程序层 | skills/（原生） | 流程/坑/方法论，按需加载零税 |
| 检索层 | session_search（原生） | 会话历史同顾（episodic） |
| 图谱层 | **basic-memory**（MCP 已接入，`bm` CLI） | 长期沉淀知识图谱：~/basic-memory/notes/*.md，FTS+语义检索，Observations/Relations 结构 |
| 巡检层 | **cron 周一 09:00 记忆库巡检** | 水位/积压/索引健康周报 |

- basic-memory 装在 uv tool（Python 3.13 独立 env，不碰系统 Python）：写笔记直接 markdown 进 ~/basic-memory/notes/ + `bm reindex`；检索 `bm tool search-notes` 或 MCP 工具
- 事实有效性思想棄自 Zep：新事实推翻旧事实时，memory 里只留现行版（同 ROUTE 规则）
- Mem0 研究验证预算路线：精选记忆比全量塞上下文准 26%、省 90% token
- 知识进图谱层的时机：从 skills/memory 里退役下来的稳定知识、跨技能主题笔记、案例存档——不是另一个垃圾场，是归档层的结构化升级

## 防复发

- **replace 的 old_text 必须逐字节等于盘上文件内容**：从渲染上下文复制会把直引号 " 变弯引号 “”，导致永久 no-entry-matched、batch 全败（2026-09-26 三连败根因）。写入前先 read_file 拿文件本体；old_text 必须是完整条目全文而非片段
- 记忆侧 write_approval 开着必然重演积压：满库状态下每个后台写入都进 pending。要么关（`hermes config set memory.write_approval false`），要么每周巡检一次 pending/ 数量
- 后台复盘（background_review）是积压主产源，其产物多为任务性知识——本应直接进技能
- memories/ 下的 .bak.* 是历史快照，不是当前状态，审计时只看 MEMORY.md 本体

## hermes cron 操作硬规则（2026-09-26 误删事故教训）

1. **`hermes cron create` 参数顺序**：schedule 和 prompt 必须前置，选项（--name/--deliver/--provider/--model）必须后置；选项前置会被解析成 unrecognized arguments。`--args` 类吞尾参数的同理，后面不能再接其它选项
2. **测试/二分脚本绝不直接 remove job**：清理逻辑要按 job name 精确匹配，不能拿“列表最后一个 id”当刚建的那条（FAIL 分支也会误删真实 job）。事故复盘：二分测试脚本把两个生产 FAE 通知 job 误删了，靠 state.db 会话历史反查出原 prompt 才还原
3. **cron job 误删恢复路径**：`state.db` messages 表按 `session_id LIKE 'cron_<job_id>_%'` 找该 job 历史会话，首条 user 消息 = 系统模板头 + 用户原始 prompt，剥掉 `[IMPORTANT: You are running as a scheduled cron job...]` 包裹即可还原
4. 动 cron 前先备份：`cp ~/.hermes/cron/jobs.json ~/.hermes/cron/jobs.json.bak.$(date +%s)`
