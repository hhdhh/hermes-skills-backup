---
name: jev-decision-model-lab
description: Use when 研究 Jev/System-One 决策模型或单 token 打分类决策实验. 含实验场路径与教训.
---

# Jev 决策模型实验场

## 是什么
TypeSafe Jev = 单 token 打分决策模型（非自回归）：候选答案映射到词表 token，一次前向读 logits softmax 出概率。纯 CPU numpy 从零复现仓库已跑通（1.4M 参数，17 分钟训完）。

## 实验场位置
`~/.hermes/workspace/jev-lab/decision-model-from-scratch/`（Gitee: panenming/decision-model-from-scratch）
- 依赖：兄弟仓库 `llm-from-scratch` 的 `data/zh_corpus.txt`（已 copy 就位）
- 用法/结论：见该目录 `README_FAE_TRIAGE.md`

## 核心教训（按重要度）
1. 小模型多任务必拆专家：四问混训 category 55% → 单问专家 100%（同分布）。Jev 官方"并行问题头"同理。但并行头单模型(1.4M)装四任务同分布只到 72%——容量不够时专家分工优于序列拼接（fae_v4_parallel.py 实验证明）。
2. RLCD 简化版正解 = 候选内 label smoothing：target=(1-S)*onehot+S/n*uniform(候选)，SOFT=0.05。精度无损且 OOD 反超、置信更诚实。全词表平滑会把多类任务抹平，禁止。
3. **生产正确性靠架构不靠炼丹（v6 铁律，v7 补强）**：安全红线（鼓包/冒烟/漏液）用确定性规则前置兜底，category 用关键词唯一命中路由；v7 新增规则后校验：模型输出 高严重度+不升级 矛盾组合 → 强制修正 rule=policy_consistency，对抗集 75.0→76.2%。规则后校验和前置同样重要：模型输出过校验层再出门。
4. **词表交叉污染是隐形杀手**：一个词同属主题词表和严重度词表 → 生成"电池掉线"歧义句把 category 专家带偏（v6.1 category 65%，v6.2 重抽歧义句后 95%）。生成器必须过滤 sevkw∈主题词集的样本。
5. OOD 第一杠杆是词汇覆盖：对抗集 51→63.7% 全靠把真实故障词汇写进数据，模型零改动。
6. 运维策略要显式进标签：『高严重度⇒升级』这类规则若只在人脑里，模型学不会；金标自身也要过一致性检查。
7. 温度缩放治不了 OOD 过信 → 置信度必须配闸门（≥0.85 自动 / 0.6-0.85 复核 / <0.6 人工），低置信升级给 LLM 兜底。
8. 验收要分级：硬门禁（安全+明确案，不过即 FAIL）+ 软报告（争议金标仅记录）——工具只承诺它真能做到的。CLI --selftest 退出码可接 CI。
9. Gitee 搜索 API 无 token 返回空；so.gitee.com 是 Indexea，widget id `wong1slagnlmzwvsu5ya`，`GET /v1/search/widget/{id}?q=&from=&size=` 可自用。
10. **三级架构完成态（v8）**：System-0 规则→System-1 小模型→System-2 LLM 复核。System-2 三原则：只复核不越权（低置信<0.6 才触发，规则定案不可覆盖）/失败不降级（保留 S1 原判）/默认关闭（CI 确定性）。对抗集 76.2→78.8%，低置信维度 2/2 修对零误伤——闸门即保护。
11. **真实语料检验（v9）**：合成对抗集 78.8% 在真实工单（太空舱36+交付8=44单）上只拿 34%——类别天花板（84%是E装配/F遥操VR/G系统，模型只会A-D）+自信的偏移（severity 21/24中判高且conf 0.85-96，闸门全程没开）+口径分歧（模型77%复现团队优先级习惯，人手金标仅47%吻合团队）。拓到7类两层路由后 category 77%/overall 58.0%，旧基准零回退。铁律：合成集分数≠能用；OOD危险在自信错误不在低置信；真实金标必建。

## 踩坑记录
- BATCH=32 训练时 OOM（ToDesk 触发 oom-killer 吃掉 11G python 进程）：本机训练用 BATCH=16 + tmux 会话隔离。
- terminal 单次调用上限 ~420s：长训练一律 tmux new-session -d + 日志轮询。
- 后台 terminal 进程在会话切换时可能被 SIGTERM：训练类任务必须 tmux。
- Hermes write_file 偶发报 Errno 2 但文件实际写成功：先 ls 验证再重试。

## 已交付
- `fae_triage_cli.py`：工单→四维判断+处置建议（单条/批量 --out/HTTP --serve+/health/--selftest/--s2，v9 七类两层路由），对抗集 78.8%（category 100%/高危零漏判），真实语料 44 单 category 77%/overall 58.0%
- `fae_system2.py`：System-2 LLM 复核模块（三原则），依赖 QWEN_HUB_API_KEY
- 四个 v6 专家 checkpoint：`checkpoints/fae6_spec_*/`
- 真实语料金标：`../real-corpus/gold_v9.json`（44 单人手标注）+ `eval_v9.py` + `build_gold_v9.py`
- 对抗集 `adversarial_tickets.json`（20 条真实风格工单+金标）

## 下一步候选
- severity 口径对齐：团队优先级字段 vs SLA 纪律金标，需团队拍板后重标
- 4B 本地模型 logprobs 消歧（参考 Gitee atm2012/jev 的 jev-router）
- 排班系统/飞书 webhook 接入在线分诊
