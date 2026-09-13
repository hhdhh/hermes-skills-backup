---
name: lark-attendance
version: 1.0.0
description: "飞书考勤打卡：查询自己的考勤打卡记录。Use when 用户说「查考勤」「我今天打卡了吗」「考勤记录」「打卡时间」「这个月出勤怎么样」或英文 'check attendance', 'clock-in record', 'attendance this month', 'did I clock in today'。如果用户想查别人的考勤，必须先确认权限，否则拒绝。"
metadata:
  requires:
    bins: ["lark-cli"]
  cliHelp: "lark-cli attendance --help"
---

# attendance (v1)

**CRITICAL — 开始前 MUST 先用 Read 工具读取 [`../lark-shared/SKILL.md`](../lark-shared/SKILL.md)，其中包含认证、权限处理**

## 默认参数自动填充规则

调用任何 API 时，以下参数 **必须自动填充，禁止向用户询问**：

| 参数 | 固定值 | 说明                                 |
|------|--------|------------------------------------|
| `employee_type` | `"employee_no"` | `employee_type`始终等于`"employee_no"` |
| `user_ids` | `[]`（空数组） | `user_ids`始终等于`[]`                 |

### 填充示例

当构建 `--params` 参数时，自动注入上述字段：
- `employee_type` 保持 `"employee_no"` 不变

当构建 `--data` 参数时，自动注入上述字段：
```json
{
  "user_ids": [],
  ...用户提供的参数
}
```

> **注意**：`user_ids` 数组保持为空[]，`employee_type` 保持 `"employee_no"` 不变。

## API Resources

```bash
lark-cli schema attendance.<resource>.<method>   # 调用 API 前必须先查看参数结构
lark-cli attendance <resource> <method> [flags]  # 调用 API
```

> **重要**：使用原生 API 时，必须先运行 `schema` 查看 `--data` / `--params` 参数结构，不要猜测字段格式。

### user_tasks

- `query` — 查询用户考勤打卡记录

## 权限表

| 方法 | 所需 scope |
|------|-----------|
| `user_tasks.query` | `attendance:task:readonly` |

## 失败模式与降级 (Failure Modes & Fallback)

- **如果 lark-shared 加载失败**（找不到 `../lark-shared/SKILL.md`）→ 提示用户检查 lark-cli 是否安装、是否完成 `lark-cli auth login`
- **如果 API 返回 403 / `permission denied`** → 提示用户去飞书 admin 后台开启 `attendance:task:readonly` scope，重新 auth
- **如果 API 返回 200 但 data.list=[]**（空数据）→ 可能是：(a) 当月没打过卡 (b) 时区不匹配 (c) employee_type 不对。先告知用户空结果，建议切时区参数重试
- **如果网络超时 / 5xx** → 提示用户稍后重试（lark API 限流常见），不要无限重试
- **如果用户想查别人的考勤（给了 user_id 或名字）** → 🛑 STOP 拒绝。需要额外审批 `attendance:task:readonly:others` scope；引导用户自己用 lark admin 查询
- **如果 schema 返回字段缺失**（不是 user_id / employee_type / check_in_time）→ 立即报错，不允许猜测字段名

## 反例与黑名单 (Anti-Patterns)

- ❌ **不要跳过 lark-shared 直接调用** — auth 上下文会丢失
- ❌ **不要传 `user_ids` 数组（必须保持 `[]`）** — 改了就 403
- ❌ **不要假设 `employee_type` 默认值** — 必须显式传 `"employee_no"`
- ❌ **不要用 `lark-cli attendance user_tasks query` 而不先看 schema** — 参数错会报奇奇怪怪的错
- ❌ **不要把考勤数据写入 `~/Documents/`** — 这是个人隐私，留在终端输出即可
- ⚠️ **不要在用户没确认时调用写操作**（user_tasks 暂只有 query，但未来加 patch/create 之前必须先问）

## 检查点 (Checkpoints)

- 🔴 **CHECKPOINT**: 调用任何 API 前先 `lark-cli schema attendance.<resource>.<method>` 一次，让用户看到参数结构
- 🔴 **CHECKPOINT**: 如果返回空数据，先告诉用户"空结果可能是 X / Y / Z"，不要假装调用失败
- 🛑 **STOP**: 用户给的人名 / user_id 与自己不一致时 → 先问"你想查谁的考勤？" 不假设是用户自己

