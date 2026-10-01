---
name: cangjie-distillation-ops
description: "Use when 蒸馏/拆书/把文档库做成技能包——仓雀流水线实操：降级、compile 坑、晋级门机检。"
---

# 仓雀蒸馏实操（cangjie-skill 运营层）

> 方法论本体在 `~/.hermes/skills/cangjie-skill/methodology/00-07`（勿重复）。本技能只记：跑完整流水线时实际会踩的坑、降级路径、机检门、以及与 darwin-skill 的衔接。

## 触发

- 用户说"把 X 蒸馏成 skill""拆书""把文档库做成技能包"（含飞书多文档语料）
- 新语料 = 书/飞书文档集/长视频转录稿；先确认能拿到全文 md（飞书用 lark-cli `docs +fetch --api-version v2 --doc-format markdown` 批拉）

## 流水线骨架（每阶段有硬门，过不了不进下一段）
1. **Stage 0 Adler**：全语料骨架扫描 → BOOK_OVERVIEW.md（主旨/骨架/术语/关键任务清单）+ PIPELINE_STATE.md（每阶段边界更新）
2. **Stage 1 提取**：候选带 source_quote（≤150字）+ 出处 + 自述 summary + task_ids 映射；无原文不提取
3. **Stage 1.5 三重验证**（V1 来源/V2 可执行/V3 任务增益）→ verified.md + coverage-audit.md → **🔴 用户轻确认后才进 1.6**
4. **Stage 1.6 晋级门**：五判据（前 3 必过），写 promotion.destination；程序校验零失联零重复
5. **Stage 2 RIA++ 卡**：R/I/A1/A2/E/B 六段逐卡写；A2 语言信号中英双写
6. **Stage 4 压测**：should_trigger 3-5 + 诱饵 2-3（至少 1 条跨 skill 混淆）+ edge 1-3，无诱饵必打回
7. **Stage 5 compile + 安装**：装进 `~/.hermes/skills/`（默认决定不问）+ Darwin 压测（默认跑），完成后汇报决定与理由。🔴 必问的只剩：合 main 推远端前的确认（用户未明确委托时）、语料含敏感凭据时的发布范围。

> 用户偏好：交付尾部的低风险决策（安装位置/命名前缀/是否压测/是否合并）直接拍板并报告理由，不要列为问题等回答——阶段 1.5 的轻确认（★）才是唯一硬门。

## 坑与规则
- **compile 需 book/ 双文件**：SKILL.md 模板无条件引用 `references/overview.md` 和 `references/glossary.md`，编译器只在 `bundle/book/` 下存在时才复制——先放 BOOK_OVERVIEW.md 和 GLOSSARY.md 进 `.cangjie/capabilities/book/`，否则 staging 校验报 broken-ref 硬门拒绝发布。
- **compile 原子覆盖清空 dist**：test-prompts.json / test-results.md 等测试文件放 dist 会被下次 compile 抹掉——每次 compile 后重写，或从快照找回。
- **slug 改名（如统一加前缀）是全链操作**：verified.yaml + 全部 cards/*.md + GLOSSARY + book/ 里的旧 slug 逐个 token 替换 + 卡文件重命名，capability_id 不动（它是稳定身份）；改完程序校验 slug 唯一/卡文件存在/id 未被误改。
- **晋级门后必跑程序校验**：候选总数==有去向数，promoted∩router=∅，slug 无重复——用人眼对 40 条必错。
- **语料噪音先判后弃**：无关文档（如地产话术混入运维库）在 Stage 0 全篇扫描定性，在 BOOK_OVERVIEW 批判段写明排除理由，不留暗坑。

## 降级路径（后端不稳时）
- **提取子 agent 503**：重试一次，再败→主 agent 串行提取（cangjie 文档化的 fallback，同角色同产出格式），PIPELINE_STATE 注明"串行降级"。
- **盲测/盲评子 agent 503**：重试一次，再败→主流程自测 + 机械文本匹配双轨判卷，test-results 标 `fallback（可信度低于独立盲测）`，后端恢复建议补测。
- **Darwin 打分 dry_run**：盲评不可用时按 9 维 rubric 机打；公式 = Σ(维度分×权重)/10，**跳过 dim8 时分母要归一化（×满分/实际权重和）**，写 results.tsv 前先断言分数在 0-100——量纲错写入的坏行要立即清除再重写。

## Darwin 衔接

新包装好后：机打基线回填 darwin-skill/results.tsv（标 dry_run+fallback 及原因），短板维度（如无🔴显性标记的 d4、软措辞的 d5）记入下轮改进清单；隔离分支 `auto-optimize/*` 改，用户确认后合 main。

## 产物位置惯例
- 工作区：`~/.hermes/workspace/books/<slug>/`（sources/ + candidates/ + .cangjie/capabilities/ 是唯一可编译事实源 + dist/）
- 安装：dist 下各 skill 目录拷入 `~/.hermes/skills/`（拷完逐个断言 frontmatter name==目录名）
- 回滚：compile 自动留快照于 `.cangjie/snapshots/`，`cangjie.py rollback --list` 查看
