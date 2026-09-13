---
name: openspace-integration
description: "Use OpenSpace for skill discovery and delegated execution."
version: 1.0.0
platforms: [linux, macos, windows]
---

# OpenSpace 集成技能

> 让慧慧能够使用 OpenSpace 自进化引擎的能力

## 何时激活

当需要以下能力时激活：
- 执行复杂多步骤任务（需要代码编写、DevOps、浏览器自动化、桌面操作）
- 搜索云端技能库来补足自身能力不足
- 执行需要工具调用（shell/GUI/MCP/web）的工作
- 需要让执行过程中的经验固化为可复用技能

## OpenSpace 能做什么

### 四大核心能力

| 能力 | 说明 | 对慧慧的意义 |
|------|------|------------|
| **Self-Evolution** | 技能自动修复、改进、学习 | 失败→改进，成功→优化 |
| **Collective Intelligence** | 一个 Agent 学 → 所有 Agent 升级 | 网络效应 |
| **Token Efficiency** | 复用成功方案，减少推理开销 | 46% Token 节省 |
| **execute_task** | 多步骤任务执行 + 自动进化 | 复杂任务委托 |

### 与现有技能的关系

```
┌─────────────────────────────────────────────────────────┐
│                    慧慧（主Agent）                        │
│  ├── brain-v1.1.9        → 类大脑认知架构                │
│  ├── toryx-automation    → Playwright + osascript UI自动化│
│  ├── skill-discovery      → OpenSpace 技能搜索（本地+云）  │
│  └── delegate-task        → OpenSpace 任务委托            │
│                                                         │
│  OpenSpace MCP Server (streamable-http :8081)           │
│  └── execute_task / search_skills / fix_skill / upload_skill │
└─────────────────────────────────────────────────────────┘
```

## 工具使用方式

### 1. search_skills — 搜索技能库

在处理不熟悉的任务时，先搜索 OpenSpace 技能库：

```
search_skills(query="docker container restart", source="all")
```

返回结果后：
- **找到匹配** → 自己能执行就自己来，不能执行就 delegate
- **没找到匹配** → 自己处理，或委托 execute_task

### 2. execute_task — 委托复杂任务

当任务需要：
- 多步骤工具调用（shell/GUI/MCP/web）
- 浏览器自动化操作
- 复杂执行循环
- 自动技能进化

使用 delegate-task skill：
```
delegate-task(task="描述任务", search_scope="all", max_iterations=20)
```

### 3. 技能进化后的决策

execute_task 返回 `evolved_skills` 时：
- 来自云端的技能 → 改进后上传回云端（public）
- 通用有用的修复 → 上传（public）
- 项目特定 → 上传（private）或跳过
- 用户说分享 → 按用户要求上传

## 限制与注意事项

- `execute_task` 可能耗时较长（复杂任务正常现象）
- 需要有效的 LLM 凭证（OpenClaw 配置中的 API keys）
- 云端技能搜索需要 `OPENSPACE_API_KEY`（可选，本地功能无需）
- 不确定时先搜索再决定是否委托

## 状态

- **2026-05-15**: 集成到慧慧技能系统
- **MCP**: streamable-http 已注册到 OpenClaw
- **Host Skills**: skill-discovery + delegate-task 已复制到 ~/.openclaw/skills/