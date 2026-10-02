---
name: hf-weighted-model-eval
description: Use when 无 GPU 小内存机下载/评测 HF 大权重模型或复用 jev-lab 资产.
version: 1.0.0
author: curator
license: MIT
---

# HF 加权模型本地评测（无 GPU · 14G 内存机）

## When to Use
- 要把 HF/GitHub 上的带权重模型（G 级 safetensors）拉到本机做零样本或对照评测
- 要对比某新模型与 jev-lab 既有基线（Laya/RSI-Jev/规则）
- 要复用 jev-lab 的下载器、venv、金标/对抗集或评测脚本模板

适用：把 HF 上的带权重模型（如 decision 模型、微调底座）拉到本地做零样本/对照评测。所有路径以 `/home/kk/.hermes/workspace/jev-lab/`（下称 `LAB`）为根。

## 流程总览

1. 摸底（仓库 → 加载范式 → 磁盘/依赖三查）
2. 下载权重（代理直链分程下载，勿信 snapshot_download）
3. 写评测脚本（同口径模板 + 标签归一内建 + OOM 预算）
4. tmux 后台跑 + 前台 ≤400s 轮询收数
5. 结果 JSON 落盘（含逐维分数与延迟）→ 对比表 → 沉淀

## 步骤 1 · 摸底三查

- **仓库**：clone 走 `ghfast.top/https://github.com/<owner>/<repo>.git`（GitHub 慢时代理）；先读 `versions/*.md`、`docs/`、`EXPLORE.md` 类实验记录——里面是作者自己踩过的失败账本，价值高于 README。
- **加载范式**：找仓库自带的加载脚本（如 `scripts/load_release.py`），抄官方路径：底座 AutoModel + tower 权重 strict=False 灌入（缺失键白名单只许 embedding）+ scorer 恒 fp32 + calibration 必装。**不要自造前向**。
- **环境三查**：磁盘 `df -h /`、依赖（venv 里 `transformers`/`torch` 版本对齐仓库 requirements）、内存预算（见步骤 3）。

## 步骤 2 · 下载：分程下载器纪律

此代理上 `snapshot_download` 必卡死（0 字节 .incomplete 挂 12min+）——**任何 >100M 权重一律用自写 8 线程分程下载器**（`LAB/par_dl.py` 通用版 + `par_dl_tower.py` 可改 URL/size 复刻）：

- urllib + `ProxyHandler(127.0.0.1:7890)` + Range 头；每线程一段，短读自动续传重试 15 次；~1.6MB/s×8。
- 分段文件名要与 `index.json` 里的**实名**一致（HF 分片命名可能是 `model.safetensors-00001-of-00001.safetensors` 这种带连字符全名，别自己拼）。
- 下载器尾接断言可能差几个 KB（短读尾段未补齐）——**完整性验证别信下载器，信 safetensors 头解析**：
  ```python
  n = struct.unpack('<Q', f.read(8))[0]; hdr = json.loads(f.read(n))
  assert 8 + n + max(v['data_offsets'][1] for v in hdr.values()) == os.path.getsize(path)
  ```
  差尾段就 curl `-r <start>-<end>` 单独补，`cat tpart_* >` 拼接后重验。
- curl 的 `-C -` 与 `-r` 互斥；tmux 里内联复杂转义会静默失败——长命令一律写脚本文件再执行。

## 步骤 3 · 评测脚本三条铁律

1. **标签归一必须在脚本内**：模型输出与金标的词表形态（"是/否" vs `true/false`、字母大小写）先归一再比对——事后修 map 会把 47% 错报成 22%，差点改写选型结论。
2. **同口径才可比**：新模型评测沿用既有问题模板（如双语混排 criteria）+ 同一份金标/对抗/临床集，逐维分数对齐旧榜单字段。
3. **内存预算**：bf16 底座 + `safe_open` 逐张量流式灌 tower（峰值 ≈ 模型体积 + 单张量）；scorer 恒 fp32（官方警告 bf16 scorer 毁过版本）；绝不 fp32 tower + bf16 模型同时在内存（≈10G 直接 OOM）。

## 步骤 4 · 运行纪律

- tmux `new-session -d` + `nice -n 10` + `python -u` 重定向日志；前台 terminal 硬上限 ~420s，轮询 sleep ≤400。
- CPU bf16 2B 模型 ≈6s/问：评测前先算总问题数估时长，写进启动前汇报。
- 收数看两层：日志逐题行（pred/gold 对比）+ 结果 JSON（overall/dims/sec）。JSON 里逐题 rows 保留 pred/gold/conf 三元组，事后可重算。

## 基线榜（jev-lab FAE 分诊语料，2026-10 口径）

| 模型 | 金标44 | 对抗S1 | 临床 | 延迟 |
|---|---|---|---|---|
| 规则 v10.2 | 96.6% | 85.0% | — | 毫秒级 |
| Laya v4 微调（multilingual 322M） | 51.7% | 42.5% | 8/12 | 339ms/单 |
| RSI-Jev v3.0-2B 零样本 | 47.2% | 47.5% | 6/12 | 6.1s/问 |
| Laya 零样本 | 25% | — | 3/12 | — |

- 判据：n<100 规则称王；参数模型接力线 500+ 单。RSI-Jev 零样本未过 50% 不换人，500 单后做 RSI-Jev 微调 vs Laya v4 微调对照。
- 语料来源：FAE 群 triage bot `--log-corpus` 回流（`real-corpus/bot_corpus.jsonl`）。

## 资产索引（LAB 根）

- `models/`：qwen3.5-2b-base（底座）、rsi-jev-v3.0-2b（tower+scorer+calibration 全套）
- `rsi-jev-fae/`：eval_rsi_jev.py（加载链+双语模板评测，可作模板）+ rsi_result.json
- `laya-fae/`：微调管线 + v4 checkpoint + v3/v4_result.json
- `jevlike/.venv`：transformers 5.17 + torch 2.14 CPU（推理够用；缺 fastapi 无所谓）
- `par_dl.py` / `par_dl_tower.py`：分程下载器
- `decision-model-from-scratch/README_FAE_TRIAGE.md`：全实验账本（v1→v12）
- `real-corpus/`：gold_v10.json（44 金标）+ adversarial_tickets.json（20 对抗）+ feishu_triage_demo.py（bot）

## 可迁移结论（从 RSI-Jev 白拿）

- 微调配方：底 8/24 层 1/10 lr——冻结底部伤 3 个 benchmark，慢训白赚 +0.054 MMLU-Pro。
- confidence head 事后校准：ECE 0.101→0.066。
- 排序类任务（工单路由/排班）用 listwise NDCG@5 reward：RL 只在 reward 能表达标签表达不了的信息时才赢（11 setup 59 arm 只留 1；有标签时 RL 梯度=SFT 梯度）。
- 2.48M bulk 数据侵蚀通用知识；hard-item mining 比随机差；蒸馏歧义项上 teacher 分歧全负。

## 常驻 bot 语料回流设计规则（配套）

- 反馈识别在工单模式匹配之前且不触发群回复：窗口（30min）内同人短消息（"对/判错/应该是X"）记 confirm/corrected，收完 continue——顺序反了要么误判新工单刷屏要么丢反馈。
- 判定落盘与 PENDING 登记（sender+ts）同帧成对——反馈按 src_msg_id 回联，判了没登记等于白判。
- 常驻 bot 加新行为时，看门狗要带版本自愈：`pgrep -af` 查启动参数里有无新 flag，无则杀会话重拉——保活只防死，不防旧。
