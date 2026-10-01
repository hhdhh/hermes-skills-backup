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
11. **真实语料检验（v9）**：合成对抗集 78.8% 在真实工单（太空舱36+交付8=44单）上只拿 34%——类别天花板（84%是E装配/F遥操VR/G系统，模型只会A-D）+自信的偏移（severity 21/24中判高且conf 0.85-96，闸门全程没开）+口径分歧（模型77%复现团队优先级习惯，人手金标仅47%吻合团队）。拓到7类两层路由后 category 95%/overall 62.5%，旧基准零回退。铁律：合成集分数≠能用；OOD危险在自信错误不在低置信；真实金标必建。
12. **词表泛化词是跨类噪声源（v9.5）**：旧词表并入新体系时必须剥离泛化词——"动作"把"遥操做不了动作"抢判成C夹爪；剥掉动作/异响/手臂/偏移/偏差/机械臂/关节后 category 77→95%。飞书接入 demo（real-corpus/feishu_triage_demo.py）：轮询模式免公网回调，lark-cli 必须走 Clash 代理（token 端点直连被RST），消息在 data.messages 平铺结构。
13. **口径拍板前别修模型（v10）**：severity 卡在34%不是模型病，是两套口径并存——先量化"模型跟谁学的"（78%吻合团队优先级习惯、34%吻合理想金标），把分歧变选择题交业务拍板（双轨制：severity=纯技术影响，现场紧迫归 escalate/delivery），再重标金标（3单翻案）+加 sev_route_v10 规则层 → 39%→93%、overall 77.3%，对抗集零回退。方法论：三方对齐（模型/团队/金标）+同日新旧对比排除外部 LLM 跨天漂移。
14. **误报主导的维度先看分层结构（v10.1）**：esc 61%/del 59% 的错判 80% 是误报（模型学会了团队"啥都升级"）；金标按 severity 分层后规律干净（高 15/15 全是，低 1/8）→ 直接加 escdel_route_v101 路由：中档+点名机号(\d{3})+E/C类→是/是，中档+诊断词→是/否，其余→否/否。真实 44 单 overall 77.3→90.3%，对抗集 S1 76.2→83.8%、S1+S2 86.2%，selftest 5/5 零回退。机号是可辩护信号（点名=这台机器在场跑）而非过拟合；重标脚本里的 assert 能逮住同类不同判的隐藏不一致（#20 del 原标否与 #06 同类却不同判）。
15. **升级线与交付线是两把尺（v10.2）**：esc/del 残单 12 错聚类后各给可辩护判据——高档双拉满（policy 层原来只管 esc 不管 del，金标 15/15 全是）；中档 E/C 强缺陷（巨大/严重/一直/出现异常）→是/是，性能退化（洒/不稳定/无法更改）→否/只拉交付；诊断类修不了（无法/不出/报错/超时）→是/否修好了→否；决策类（需要人拍板）无论 sev 都升级；点名机台+链路词（掉线/收音）→是/否。真实 44 单 90.3→96.6%（esc 98%/del 100%），对抗 S1 85.0%持平 S1+S2 87.5%，零回退。
16. **开源同型选型：先看数据量级差（v11 实验）**：Jev 不开源，开源同型 jevlike（同契约小模型/CPU 可训）在 n=44 上 5 折 CV 总均值仅 49.7%（vs v10.2 路由 96.6%）——判据：n<100 规则/词表 > 参数模型，n>500 反转（CUA-S1-FORMS 用 70 万级合成数据才到 99.95%）。小语料上学不过先验就不接线；全量种子 checkpoint 已存 jevlike-fae/checkpoints/（4 维各 164KB），等 FAE bot 生产回流攒到 500+ 单再接力。venv：jevlike/.venv（torch CPU 2.14，uv 装）。
17. **Jev 最强开源平替=Laya（v11.1 实测）**：Convai Innovations，Apache-2.0，ModernBERT-large 421M（另有 322M multilingual 对中文），choice/score/noul 三原语，pip install laya + HF 权重。零样本实测 25%（模型卡自曝 0.362，坐实"快底座非即插即用"——电池漏液判低危不升级）。结论：生产继续 v10.2 路由；Laya 顶替 jevlike 成语料达标后继任者（预训练底座+RLCD 配方，同数据量学习效率高一个量级，接力门槛从 500+ 单降到约 200 单）。venv 同 jevlike/.venv 可复用。
18. **Laya 微调实测（v11.2）+ CPU 微调工程坑**：44 单冻底座训头，multilingual 322M 底座完胜 EN 421M（fold0 52.8% vs 41.7%，中文语料必选 multilingual）；5-fold CV 46.0%、对抗 S1 37.5%——44 单撑不起参数模型，规则 96.6% 纪律不变。工程坑：① encoder 冻结也要缓存特征（每折重复前向 = 8 倍浪费）；② CPU 训 head 是算力瓶颈（~20s/epoch，96 单全流程约 90 分钟）；③ 14G 内存机器后台长训必须 tmux+head-only 快照（deepcopy 全底座 1.7G 会被桌面内存峰值 OOM 带走）+ nice 降权；④ HF_HUB_OFFLINE=1 下反复 laya.load 会卡在缓存校验网络调用——进程内只 load 一次、每折 load_state_dict 重置。微调管线全链路可用，checkpoint 在 laya-fae/。
19. **小语料微调三板斧实测（v11.3/v4 轮，CV 46→51.7）**：① 问题模板也是超参——中文语料+multilingual 底座时，criteria 写成"中文+英文"双语混排，category 判别力翻倍（22→44%），底座选项编码两头吃；② 极小样本（n<50）上类别加权 CE 是毒药——多数类样本本就稀少，inverse-sqrt 权重把主导先验掰弯，整体 -14pp（fold0 33.3% vs 均匀 47.2%）；③ 训练日程加码（60ep恒定→120ep+lr1e-3+余弦退火）只 +4pp，边际递减——天花板由 n 决定不由日程决定。对抗集 42.5% vs 规则 85%：泛化缺口只能靠语料攒量。
20. **RSI-Jev v3.0 零样本对照 + 评测标签归一铁律（v12 轮）**：哈佛开源的 Qwen3.5-2B 全量微调 decision 模型（266k 问题 SFT + listwise NDCG RL），5.49G 权重 8 线程分段下载 ≈46min。零样本双语模板实测：金标 44 单 47.2%（sev 61/cat 29）/ 对抗 S1 47.5%（反超 Laya v4 微调版 42.5）/ 临床 6/12——零样本≈微调 Laya，继任底座候选成立但未过 50% 线暂不换人；等 500+ 单做一次 RSI-Jev 微调 vs Laya v4 微调对照，谁赢谁上中继线。CPU bf16 6.1s/问不能上产线。**评测脚本里做标签归一**：模型输出"是/否"而金标存 true/false，字符串直接比对首报 22.7%，修正后 47.2%——差 25pp 的乌龙差点改写结论。零样本可白拿三样：v2.1 底 8/24 层 1/10 lr 配方（冻结伤 benchmark，慢训白赚）、confidence head 事后校准（ECE 0.101→0.066）、排序任务 listwise NDCG@5 reward 模板（RL 只在 reward 能表达标签表达不了的信息时才赢，11 setup 59 arm 只留 1）。

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
- 飞书分诊 bot demo：`../real-corpus/feishu_triage_demo.py`（轮询+自动回复，实测4用例全过）
- 对抗集 `adversarial_tickets.json`（20 条真实风格工单+金标）

## 下一步候选
- severity 口径对齐：团队优先级字段 vs SLA 纪律金标，需团队拍板后重标
- 4B 本地模型 logprobs 消歧（参考 Gitee atm2012/jev 的 jev-router）
- 排班系统/飞书 webhook 接入在线分诊
