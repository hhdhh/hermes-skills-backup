---
name: lark-skill-maker
version: 1.0.0
description: "创建 lark-cli 的自定义 Skill。当用户需要把飞书 API 操作封装成可复用的 Skill（包装原子 API 或编排多步流程）时使用。"
metadata:
  requires:
    bins: ["lark-cli"]
---

# Skill Maker

基于 lark-cli 创建新 Skill。Skill = 一份 `SKILL.md`，教 AI 用 CLI 命令完成任务。

## CLI 核心能力

```bash
lark-cli <service> <resource> <method>          # 已注册 API
lark-cli <service> +<verb>                      # Shortcut（高级封装）
lark-cli api <METHOD> <path> [--data/--params]  # 任意飞书 OpenAPI
lark-cli schema <service.resource.method>       # 查参数定义
```

优先级：Shortcut > 已注册 API > `api` 裸调。

## 调研 API

```bash
# 1. 查看已有的 API 资源和 Shortcut
lark-cli <service> --help

# 2. 查参数定义
lark-cli schema <service.resource.method>

# 3. 未注册的 API，用 api 直接调用
lark-cli api GET /open-apis/vc/v1/rooms --params '{"page_size":"50"}'
lark-cli api POST /open-apis/vc/v1/rooms/search --data '{"query":"5F"}'
```

如果以上命令无法覆盖需求（CLI 没有对应的已注册 API 或 Shortcut），使用 [lark-openapi-explorer](../lark-openapi-explorer/SKILL.md) 从飞书官方文档库逐层挖掘原生 OpenAPI 接口，获取完整的方法、路径、参数和权限信息，再通过 `lark-cli api` 裸调完成任务。

通过以上流程确定需要哪些 API、参数和 scope。

## SKILL.md 模板

文件放在 `skills/lark-<name>/SKILL.md`：

```markdown
---
name: lark-<name>
version: 1.0.0
description: "<功能描述>。当用户需要<触发场景>时使用。"
metadata:
  requires:
    bins: ["lark-cli"]
---


# <标题>

> **前置条件：** 先阅读 [`../lark-shared/SKILL.md`](../lark-shared/SKILL.md)。

## 命令

\```bash
# 单步操作
lark-cli api POST /open-apis/xxx --data '{...}'

# 多步编排：说明步骤间数据传递
# Step 1: ...（记录返回的 xxx_id）
# Step 2: 使用 Step 1 的 xxx_id
\```

## 权限

| 操作 | 所需 scope |
|------|-----------|
| xxx | `scope:name` |
```

## 关键原则

- **description 决定触发** — 包含功能关键词 + "当用户需要...时使用"
- **认证** — 说明所需 scope，登录用 `lark-cli auth login --domain <name>`
- **安全** — 写入操作前确认用户意图，建议 `--dry-run` 预览
- **编排** — 说明数据传递、失败回滚、可并行步骤

## 失败模式与降级 (Failure Modes & Fallback)

- **如果 `lark-cli <service> --help` 无输出**（CLI 未装 / 路径错）→ 告知用户装 lark-cli 或检查 PATH
- **如果 `lark-cli schema` 报 "method not found"** → 用 `lark-openapi-explorer` 找原生 OpenAPI 路径
- **如果用户给的 API 还没在 lark-cli 注册** → 用 `lark-cli api <METHOD> <path> --data` 裸调
- **如果新 Skill 缺权限 scope**（403）→ 在 SKILL.md 权限表里写清楚，让用户去 admin 后台申请
- **如果用户要封装的 API 不存在**（拼写错 / 飞书已下线）→ 立即告知，不要写一个会永远失败的 Skill
- **如果编排多步且 Step 1 失败** → 在 SKILL.md 显式写"Step 1 失败时停止后续步骤"
- **如果生成的 SKILL.md description 缺少触发词** → 用 darwin-skill 的 frontmatter 规则校验后告诉用户补

## 反例与黑名单 (Anti-Patterns)

- ❌ **不要**把生成的 SKILL.md description 写成"灵活应用，按需调用" — 必须包含功能关键词 + 触发场景
- ❌ **不要**在 SKILL.md 省略权限表 — 用户不知道要开哪个 scope
- ❌ **不要**让编排多步时缺数据传递说明 — Step 2 用 Step 1 的 ID 必须显式标注
- ❌ **不要**让 Shortcut 描述和已注册 API 描述完全重复 — Shortcut 是高级封装，应有差异
- ❌ **不要**在 SKILL.md 用 emoji — 飞书 API 文档风格偏严肃，emoji 显得不专业
- ❌ **不要**让同一资源在多个 SKILL.md 重复 — 引用其他 skill 而非复制（如 [lark-shared](../lark-shared/SKILL.md)）
- ❌ **不要**忘记 `metadata.requires.bins` 声明 lark-cli 依赖 — 缺了用户不知道要先装什么

## 检查点 (Checkpoints)

- 🔴 **CHECKPOINT**: 生成 SKILL.md 前先确认用户要封装哪个 API（不要瞎猜）
- 🔴 **CHECKPOINT**: SKILL.md 完成后用 darwin-skill 跑一次 9 维评分，< 70 分返工
- 🔴 **CHECKPOINT**: 任何写操作（创建/覆盖/删除）必须在 SKILL.md 标"需用户确认"
- 🛑 **STOP**: 用户的 API 调用涉及删除/批量操作 → 显式列 dry-run 命令让用户验证
