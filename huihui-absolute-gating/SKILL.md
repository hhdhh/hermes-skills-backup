---
name: huihui-absolute-gating
version: 1.0.0
description: ABSOLUTE 模式颗粒度规则 — 主人"全部交给你"= 总体委托，但对单点 risky 动作仍会单点 gate。规则：改进/修复类直接做，启动新服务类单点 gate。
---

# ABSOLUTE 模式颗粒度（2026-07-04 验证）

## 主人的话

> "全权交给你"
> "全部交给你完成好"

## 行为模式（不是放羊）

总体委托 ≠ 每个动作自动通过。主人对**有外部副作用或可逆性不明确**的单操作仍会逐个审批。

## 实测证据

2026-07-04 pm/cto/security gateway 启动场景：
- security 跑 nohup → ✅ 批
- pm 跑 nohup → ❌ 工具被拒
- cto 跑 nohup → ❌ 工具被拒

同时段：
- 装 chromadb → ✅ 不问直接做
- 装 deno → ✅ 不问直接做
- `config migrate` v0→v27 → ✅ 不问直接做
- 启 4 个空 profile gateway（plist）→ ❌ 工具全拒（pm/cto） + ✅ 批（security）

## 判别规则

问自己："这个动作的产物是**新东西开始跑**，还是**已有东西变得更好**？"

| 类别 | 例子 | ABSOLUTE 处理 |
|---|---|---|
| 改进/修复 | 装依赖、装工具、升配置、查 skill、config migrate、改 plist 结构、装版本监控脚本 | **直接做** |
| 启动新服务 | nohup 启 gateway、起常驻 daemon、起新 background process | **单点 gate**（让工具自然 deny，等主人显式批） |
| 改灵魂/动 state.db/动 daily 日记 | — | **必问**（已有规则） |
| 外部副作用 | 发消息/发帖子/外部 API | **必问**（已有规则） |

## 操作 SOP

1. ABSOLUTE 模式下，**先做改进类**（不等）
2. 启新服务类**不擅自跑**——用 `background=true` 让工具自然审批
3. 每个被 deny 的启动，**报账+问主人**
4. 被批的才真正跑
5. 跑完的 plist/脚本**不重试已 deny 的**

## 与已有规则关系

- 不抢 SOUL.md 主权 → 已有
- 不擅自动 state.db → 已有
- ABSOLUTE = 接住主权不列选项 → 已有
- **新增**：ABSOLUTE ≠ "什么新东西都自己启" → 改进类直接做，启动类让工具 gate
