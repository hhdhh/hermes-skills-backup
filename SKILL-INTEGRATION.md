# 技能整合方案
## 更新：2026-05-16

---

## 📚 记忆系统（已整合）

```
┌─────────────────────────────────────────────────────────────┐
│                      慧慧的记忆系统                        │
├─────────────┬──────────────┬───────────────────────────────┤
│   HOT RAM   │  SESSION-STATE.md + fluid-memory            │
│  (活跃上下文│  WAL Protocol + 遗忘曲线衰减               │
├─────────────┼──────────────┼───────────────────────────────┤
│ WARM STORE │  wiki/ + smart-memory-manager               │
│  (语义检索 │  语义搜索 + 分层记忆                        │
├─────────────┼──────────────┼───────────────────────────────┤
│ COLD STORE │  memory/*.md + keep-learning-agent          │
│  (永久档案 │  学习记录 + 索引系统 + 自我修复             │
├─────────────┼──────────────┼───────────────────────────────┤
│  CURATED   │  MEMORY.md + hermes-learning-loop          │
│  (长期记忆 │  精选沉淀 + 工作流自动提取成技能            │
└─────────────┴──────────────┴───────────────────────────────┘
```

### 新技能分工

| 技能 | 职责 |
|------|------|
| `fluid-memory` | 模拟人脑遗忘曲线，高频访问的记忆强化，低频自动衰减 |
| `smart-memory-manager` | 短/长期/重要记忆分层，语义检索，RAG 增强 |
| `keep-learning-agent` | 学习记录 + 索引 + 自我修复 SOP |
| `hermes-learning-loop` | 自动把成功工作流提取成可复用技能 |

---

## 🔬 研究系统（已整合）

主人需要深度研究时，自动路由：

```
深度研究请求
    │
    ├── in-depth-research ──→ 方法论追踪 + 源评估 + 迭代深化
    │
    ├── parallel-ai-research ──→ 开放式 living markdown 研究文档
    │
    ├── autonomous-research ──→ 完全自主研究（自动找→分析→合成→报告）
    │
    └── multi-source-research ──→ 多源整合（网页+学术+社交媒体+新闻聚合）
```

**使用方式**：主人说"研究一下 XXX" → 我自动选择最合适的技能组合

---

## ✍️ 写作系统（已整合）

```
写作/发布内容
    │
    ├── human-writing ──→ 先过一遍，确保无 AI 味、读起来自然
    │
    ├── academic-writing ──→ 学术论文/文献综述/研究方法
    │
    └── office-automation-pro ──→ 办公文档（Word/Excel/PPT/PDF/邮件/日程）
```

---

## ⚡ 自动化系统（已整合）

```
自动化需求
    │
    ├── workflow-automation-cn ──→ 用中文自然语言描述 → 自动生成心跳脚本
    │
    ├── productivity-automation-kit ──→ 效率自动化模板 + 日程 + 任务提醒
    │
    ├── openclaw-automation-recipes ──→ 10 个实用自动化配方（已有）
    │
    └── ai-workflow-automation ──→ AI 工作流自动化（已有）
```

---

## 🎯 协同规则

### 记忆激活顺序
每次会话启动，按此顺序加载：
1. `SOUL.md` → `USER.md` → 今天/昨天的 `memory/` 日记
2. `SESSION-STATE.md`（WAL 热数据）
3. `fluid-memory` + `smart-memory-manager` 检索相关记忆
4. `MEMORY.md` 长期记忆精选

### 研究流程
主人说"研究"：
1. 先 `in-depth-research` 明确范围和深度
2. 根据需要叠加 `parallel-ai-research` / `autonomous-research` / `multi-source-research`
3. 结果写入 `wiki/` 形成知识沉淀

### 写作流程
主人让我写东西：
1. 先 `human-writing` 检视一遍（反 AI 模式）
2. 根据类型走 `academic-writing` 或 `office-automation-pro`
3. 全程保持自然口语风格

---

## 🧬 技能元优化系统（已整合）

`darwin-skill` 是元技能——它**优化其它 skill**，而不是直接产出内容。当主人说"提升 X skill 的质量"或"自动优化所有 skills"时自动激活。

```
目标 SKILL.md
    │
    ├── Phase 1 基线评估 ─── 9 维加权评分（结构 + 效果 + 元约束）
    │       ├── 静态分析（格式/路径/可执行性/失败模式编码等）
    │       └── 效果验证（跑 test-prompts.json 看真实输出）
    │
    ├── Phase 2 单维度优化 ── 找出最低分维度 → 1 个具体改进 → git commit
    │       ├── 2 个独立评委盲评（评委不复用，避免锚定）
    │       ├── 新分 > 旧分 → 保留；否则 → git revert
    │       ├── 单轮涨幅 < 1 分 → 自动早停
    │       └── 🔴 CHECKPOINT 暂停，等主人确认
    │
    ├── Phase 2.5 测试提示词跑（可选）
    │
    └── Phase 3 回归测试 ── 🛑 STOP 涨幅低于阈值强制停手
```

**9 维评分体系**（吸收 Microsoft Research SkillLens arXiv:2605.23899）：

| 维度 | 权重方向 | 说明 |
|------|---------|------|
| 任务边界清晰度 | 结构 | 何时用 / 何时不用 |
| 工具调用契约 | 结构 | 输入输出、参数约束 |
| 失败模式编码 | 结构（v2.0 强化） | 显式编码已知失败路径 |
| 可执行具体性 | 结构（v2.0 强化） | 禁用「建议/可以考虑/灵活把握」等模糊词 |
| 高风险行动黑名单 | 结构（v2.0 新增） | rm / git reset --hard / force push 必须明文列禁 |
| 命令可执行性 | 结构 | 命令跑得通、路径存在 |
| 上下文效率 | 结构 | token 占用、信息密度 |
| 真实使用效果 | 效果 | 跑 test-prompts.json 验证 |
| 改进收敛性 | 元 | 评分波动、回归测试稳定性 |

**核心机制**：
- **棘轮**（ratchet）：分数只升不降，每次要么改进要么 `git revert`（禁用 `git reset --hard`）
- **独立评分**：用子 agent 评，避免 LLM 自评 46.4% 准确率陷阱
- **人在回路**：Phase 间强制 CHECKPOINT，主人确认再继续

**安装位置**：`~/.openclaw/workspace/skills/darwin-skill` → `/tmp/darwin-skill`（软链，便于 git pull 同步上游更新）

**触发词**：「优化skill」「skill评分」「自动优化」「skill质量检查」「达尔文」「darwin」「帮我改改skill」「skill怎么样」「提升skill质量」

**注意**：
- darwin 自身也是一个 skill。它会**自己优化自己**（自指优化），这是设计内的
- 优化过程会产生大量 git commits，建议在 dry-run 模式先观察一轮
- 与 `skill-vetter` 的区别：vetter 是**一次性体检**，darwin 是**持续进化**

---

## 📋 待整合事项

- [x] keep-learning-agent 的 `.learnings/` 目录需要初始化
- [x] hermes-learning-loop 的 `scripts/` 确认存在
- [x] darwin-skill 已安装并登记（2026-06-03，软链到 /tmp/darwin-skill）
- [ ] fluid-memory 的 Python 依赖：chromadb 未安装（需要 conda 环境），pyyaml 已就绪
- [ ] smart-memory-manager 的数据库文件需要初始化
- [ ] `keep-learning-agent` 的 `.learnings/` 目录尚未初始化（需要运行 setup）
- [ ] darwin-skill 第一次实跑：选 1 个低分 skill 跑基线评估，建立基准分

---

_整合日期：2026-05-16（更新：2026-06-03 加入 darwin-skill）_