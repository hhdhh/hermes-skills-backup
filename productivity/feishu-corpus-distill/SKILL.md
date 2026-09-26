---
name: feishu-corpus-distill
description: 飞书语料→仓雀蒸馏操作链。Use when 蒸馏飞书文档/飞书知识库做成 skill.
---

# feishu-corpus-distill — 飞书语料→仓雀蒸馏操作链

## 定位与分工

- `cangjie-skill`：蒸馏方法论（RIA-TV++ 七阶段）——照它执行，不重造
- `lark-knowledge-corpus-ingest`：语料盘点/存档/审读（学习视角）
- 本技能：两者之间的**操作 glue** ——怎么把飞书语料拉成仓雀能吃的形态，以及在 Hermes 环境下流水线各阶段的降级路径

## 工作目录约定

```
<workspace>/books/<corpus-slug>/
├── sources/              # 每篇一个 .md，带 frontmatter 溯源头
├── source-manifest.json  # slug/title/token/folder/size ——拉取台账+断点续跑基准
├── PIPELINE_STATE.md     # 仓雀阶段状态（仓雀自带，每阶段更新）
├── BOOK_OVERVIEW.md / candidates/ / verified.md / coverage-audit.md
```

## 流程

1. **盘点（inventory）**：递归遍历 Drive 根目录。用单个 Python 循环 subprocess 调 `lark-cli drive files list --folder-token <t> --page-size 200`，递归 queue 子 folder token；**不要**每层 folder 起一个 shell 调用——逐层 shell 会因数百次进程创建而超时，单循环几秒出结果。
2. **去重**：同名文档（跨文件夹拷贝）按 `modified_time` 最新者胜，败者 token 记入 manifest。
3. **拉取**：逐篇 `lark-cli docs +fetch --api-version v2 --doc <token> --doc-format markdown`，导出为 `sources/NN-slug.md`，文件头写 frontmatter（title/source_url/folder/token）。每次调用间 sleep 0.3s 避限流；≥30 篇时以后台脚本跑（通知制），manifest 就是断点基准——已存在且 >100B 的文件直接跳过。
4. **阶段 0 骨架扫描**：先程序化提取每篇标题结构（h1-h3 + 正文行数）再精读核心篇；噪音篇（异域内容/纯数据表/客户侧文档）在 BOOK_OVERVIEW 的批判节显式降权，**不静默丢弃**——manifest 里留 skip 理由。
5. **阶段 1 提取**：优先并行子 agent（按语料主题切 2-3 份，每个覆盖 framework/principle/counter-example 三视角）；子 agent 后端 503/超时 → 立即降级主 agent 串行提取，候选格式不变，PIPELINE_STATE.md 记录降级模式。
6. **阶段 1.5 验证**：V1 来源充分性（quote 非空）/ V2 可执行性（summary 含命令/路径/判据信号，正则可判）/ V3 任务增益（task_ids 映射）；程序化可判的分流交给脚本，LLM 只裁模糊件。产出 verified.md + coverage-audit.md（每项任务有候选或写明降级依据，零未解释遗漏）。
7. **检查点**：阶段 0 确认骨架、阶段 1.5 轻确认四类分流——两处都必须停下等用户，不得静默进入下一阶段。

## Pitfalls

- 子 agent 全灭不阻塞：503 时串行降级即刻做，产出同格式；勿把"后端不可用"当成停工理由。
- frontmatter description 从源文档复制时可能被截断成半句——从源引用重写完整版，勿继承省略号。
- 引用文件（references/*.md 等）写入候选前先 ls 验实存——断链引用是干跑评分最常漏的机械病。
- 台账路径不写死 `.claude/skills/` 等 runtime 专属前缀，用技能自身目录相对解析。
- 异域/客户侧/纯数据文档：记录在 manifest + coverage-audit 后放行，不算遗漏也不伪装覆盖。
