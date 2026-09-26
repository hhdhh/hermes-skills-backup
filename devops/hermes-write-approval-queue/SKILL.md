---
name: hermes-write-approval-queue
description: Use when 批量批准/清理 Hermes 技能与记忆写审批积压队列（pending）。
---

# Hermes 写审批队列批量批准

`skills.write_approval` / `memory.write_approval` 开启时，skill_manage 与 memory 写入不落盘，而是排队到 `~/.hermes/pending/skills/`、`~/.hermes/pending/memory/`（JSON 记录：id/subsystem/summary/created_at/payload）。积压数周后会混入跨版本格式的写入，直接 approve all 会大面积失败——按本流程分层处理。

## 交互入口（少量待审时够用）

- `/skills pending` 列队 · `/skills diff <id>` 看 diff · `/skills approve|reject <id|all>`
- `/memory pending` · `/memory approve|reject <id|all>`

## 批量流程（大量积压）

官方批准路径的程序化版本，与斜杠命令同一套函数。用源码树自带 venv 执行（系统 python3 缺依赖）：

```
/home/kk/.hermes/hermes-agent/.venv/bin/python <脚本>
```

脚本内先 `sys.path.insert(0, "/home/kk/.hermes/hermes-agent")`，然后：

1. `tools.write_approval.list_pending(subsystem)` — 已按 created_at 排序，**老→新回放**，保证链式 patch 按正确顺序应用
2. 技能：`json.loads(tools.skill_manager_tool.apply_skill_pending(payload))`
3. 记忆：`tools.memory_tool.apply_memory_pending(payload, store)`，store 来自 `load_on_disk_store()`
4. 仅在 success 时 `wa.discard_pending(subsystem, rid)`；失败留队，按分类表修复后重放

现成脚本：`scripts/batch_approve_official.py`（含记忆断路器复位 + 失败报告输出），可直接跑第一步粗筛。

### 步骤顺序

1. 盘点：两 subsystem 的 pending 数量
2. **三重备份**：`cp -a` 整目录备份 skills/ + memories/ + pending/ 到 `~/.hermes/backups/`，md5 抽查校验
3. 跑批量应用，收集失败清单
4. 按失败分类表逐类修复、重放
5. 记忆侧若满载，先整合重写（见下），再清蒸馏后的 pending
6. 终验：双队列归零；SKILL.md frontmatter 100% 可解析；MEMORY/USER.md 在字符预算内

## 失败分类与修复表

| 症状 | 根因 | 修复 |
|---|---|---|
| `Description is N chars — new skills must fit the 60-char budget` | 新技能描述超 60 字符（`SKILL_PROMPT_DESC_LIMIT=60`），积压 create 多为旧格式 | 浓缩 description 为触发词开头的一句话（≤60），原文以 `> 完整描述：…` blockquote 保存在 H1 之后，零信息损失。**常与冒号错叠加**：浓缩后的新描述若含冒号必须同时整体加双引号，否则修完长度又倒在 YAML 解析 |
| `A skill named X already exists` | 队列卡住期间每个新会话都整体重建同名技能 | 同名重复 create 按 created_at **最新快照胜出**，转成 `action: edit` 全量重写；旧的按"被取代"丢弃 |
| `Could not find a match for old_string` | 陈旧 patch：目标技能已被更新的快照整体覆盖 | 锚点测试：new_string 首行在盘上文件中已存在 → 丢弃；不存在 → 说明是**从未落地的新知识**，以 `## 补充` 段落 append 进技能正文 |
| `not found in active profile` | patch/write_file 目标技能目录不存在 | 先 create 壳技能（合法 frontmatter + 指向 references 的说明），再重放原操作 |
| `file_content is required for 'write_file'` | 老格式用 `content` 传正文 | 映射为 `file_content` |
| `YAML frontmatter parse error: mapping values are not allowed` | description 含未加引号的冒号 | description 整体加双引号 |
| `Frontmatter must include 'name' field` / `Skill name is required` | create 缺 name 或 name 被误填为文件路径 | 从 content frontmatter 提取真实技能名；纯参考文档型 content 转成 write_file 写进合适宿主技能的 references/ |
| `Blocked: content matches threat pattern` | 记忆正文含 `.env` 等机密路径字面量 | 改写措辞（如"密码在 Hermes 机密配置里"），绝不绕对抗扫描器 |

## 记忆侧专章

- **断路器连坐**：MemoryStore 的 `_consolidation_failures` 计数在 3 次超预算后熔断，之后所有写入无论本身是否合规都报 "consolidation failed N times"。批处理脚本必须在**每条记录前**调 `store.reset_consolidation_failures()`。
- **满载是积压根因**：MEMORY.md 打满 2200/USER.md 1375 字符预算后，写入物理上无法落盘、反复重入队。对着满仓库重试 add 是死路；正解是一次官方 batch 整合重写（remove 全部旧条目 + add 压缩去重后的新条目，预算内一次成型），然后逐条审计 pending：内容已被覆盖/已沉淀进技能的丢弃，真新知蒸馏合并。
- 蒸馏标准照 memory schema：每会话都需要的紧凑事实进 memory；任务性知识（流程/坑）指向对应技能。

## 通用坑

- 复杂多行 python 以 heredoc 内联进 terminal 会被命令解析器硬拦（blocklist，不可绕）——先 write_file 落成脚本文件再 `python <file>` 执行。
- 批次是 all-or-nothing（"batch aborted, all touched skills rolled back"）：一个畸形 op 会拖回滚整批，此时逐 op 拆开重放。
- 验证 frontmatter 时只把 `t[3:3+m.start()]`（m = 偏移 3 后第一个 `\n---`）喂给 yaml.safe_load——把闭合 fence 加正文一起喂会产生假阳性 "expected a single document in the stream"。
- 清完队列向用户确认 write_approval 是否继续开：继续开会再次积压；要关用 `hermes config set skills.write_approval false`。
