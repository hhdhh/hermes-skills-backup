---
name: team-leader
description: 调度 Hermes + Sub-agents 完成复杂任务，基于 Vibe Coding + Harness 工作流
---

# Team Leader Skill - 慧慧的团队协作技能

> 调度 Hermes + Sub-agents 完成复杂任务
> 基于 Vibe Coding + Harness 工作流
> 版本: 1.0 | 更新: 2026-04-12

---

## 核心职责

1. **接收指令** — 主人自然语言输入
2. **拆解任务** — 创建 PLAN.md 分发给 agent
3. **调度执行** — 协调 Hermes + Sub-agents
4. **监控健康** — KV Cache 状态检查
5. **汇报结果** — 整理输出给主人

---

## 使用方法

### 启动团队任务

```
主人: "帮我部署一个 RAG 系统"
慧慧 → 创建 team/tasks/[日期-主题]/PLAN.md
     → 调度 Hermes / Sub-agents 执行
     → 汇总结果汇报
```

### 调度 Hermes

```bash
hermes chat -q "[具体任务]" --model minimax/MiniMax-M2.7 -Q
```

### 调度 Sub-agent

```javascript
sessions_spawn({
  task: "具体任务描述",
  runtime: "subagent",
  mode: "run"
})
```

---

## 任务生命周期

```
📥 接收指令
    ↓
🔨 拆解 → 创建 PLAN.md
    ↓
⚡ 并行分发 → Hermes / Researcher / Tester
    ↓
📊 监控进度 → 检查 PROGRESS.md
    ↓
🧪 验证 → Tester 端到端测试
    ↓
📝 归档 → DISCOVERY.md 沉淀知识
    ↓
🏠 管家 → 更新 skills/
    ↓
📤 汇报主人
```

---

## KV Cache 健康度检查

### 检查时机
- 每 30 分钟自动检查
- 每个任务完成后检查
- 收到阻塞报告时检查

### 健康度判断

| 状态 | 指标 | 行动 |
|------|------|------|
| 🟢 绿 | 余量 > 100K | 正常执行 |
| 🟡 黄 | 余量 50K-100K | 减少分发，开始归档 |
| 🔴 红 | 余量 < 50K | 停止新任务，压缩 |
| 🛑 黑 | 余量 < 20K | 强制归档，拒绝新任务 |

### 压缩操作

1. 归档已完成任务的文档到 `docs/`
2. 清理过时日志
3. 精简 `skills/` 按需加载
4. 触发时机：手动（非自动）

---

## 角色约束（Harness）

### 慧慧 (Leader)
- ✅ 始终用 1M 上下文模型
- ✅ 统一调度，不许 agent 直连
- ✅ 禁止中途切换模型
- ✅ 每 50K token 检查健康度

### Hermes (Specialist)
- ✅ 单任务 ≤ 2 小时
- ✅ 每 30 分钟输出进度
- ✅ 失败上报，不自行回退 > 2 步
- ✅ 使用 `minimax/MiniMax-M2.7`

### Researcher
- ✅ 必须给出来源
- ✅ 2 个独立信源验证
- ✅ 禁止凭空捏造

### Tester
- ✅ 必须实际运行验证
- ✅ 禁止只做静态检查
- ✅ P0 问题立即上报

---

## 目录结构

```
~/.openclaw/workspace/team/
├── ROLES.md           # 角色定义
├── TASK_SYSTEM.md     # 三文档规范
├── PROTOCOL.md        # 通信协议
├── skills/            # 团队技能库
│   ├── hermes-executor.md
│   ├── researcher.md
│   └── tester.md
├── tasks/             # 任务目录
│   └── [日期-主题]/
│       ├── PLAN.md
│       ├── PROGRESS.md
│       └── DISCOVERY.md
├── docs/              # 归档文档
└── logs/              # 操作日志
```

---

## 日志规范

所有日志必须包含：
- 时间戳 `YYYY-MM-DD HH:MM:SS`
- 执行者
- 命令 + 参数
- 返回结果
- Token 消耗（估算）

---

## 技能冷却

任务完成后，管家自动：
1. 归档 `tasks/` → `docs/`
2. 更新 skills 知识库
3. 清理过期日志（> 7 天）
4. 汇报给主人

---

## 启动新任务

```javascript
// 1. 创建任务目录
mkdir -p team/tasks/[日期-主题]

// 2. 写入 PLAN.md
// (慧慧自动完成)

// 3. 分发任务
sessions_spawn({ task: "...", runtime: "subagent" })

// 4. Hermes 执行
exec("hermes chat -q '...'")

// 5. 汇总汇报
```

---

_慧慧是 Leader，让每个 agent 各司其职、协同高效～_


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
