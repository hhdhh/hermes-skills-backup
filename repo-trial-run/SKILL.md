---
name: repo-trial-run
description: "Use when 要 clone 第三方仓库真跑验证声明：冒烟→tmux 全量→留出集验收。"
---

# 第三方仓库试跑（clone → 真跑 → 验证声明）

用户标准：新东西必须实测验真——不接受只读 README 就下结论；结论要带真实数字与声明对照。

## 1. Clone 与依赖
- `git clone --depth 1`；`find -name '*.py' | xargs wc -l` 量规模，先读核心入口（模型/数据/训练/推理）再动手
- README 说"零依赖"也要逐个 `python3 -c "import X"` 验证
- 缺语料/权重时先找作者的其他仓库：`.gitignore` 里被忽略的 `data/*.txt`、`checkpoints/` 常是"放在上一本书/上一个项目里"的公共依赖

## 2. 冒烟先行
全量前先跑最小规模（训练 ~50 步）：验证数据管线、shape、checkpoint 保存链路。全量启动时删掉冒烟产物，避免半成品干扰加载。

## 3. 长任务放 tmux
- 长训练/构建用 `tmux new-session -d -s <name> "cd <dir> && python3 ... > log 2>&1"`——与 Hermes 进程树解耦，跨会话/网关重启存活；terminal 的 background 进程不保证存活（会被 SIGTERM 143）
- 前台等待别超时：terminal 前台上限 ~7 分钟，轮询日志要分段 sleep
- 前台命令包 nohup/setsid/disown 会被工具层直接拦截，要后台就 background=true 或 tmux

## 4. 进程静默死亡：先查 OOM 再查代码
日志无异常但进程没了 → `journalctl -k --since <启动时刻> | grep "Killed process"`，OOM 会留 `Out of memory: Killed process <pid> (python3) ... anon-rss`。修法按序：
1. 砍 batch size（激活内存随 batch 近似线性）
2. 清驻留大户（`ps aux --sort=-%mem`，远程桌面/浏览器常吃数 GB）
3. 仍不够再降模型规模

## 5. 验收：留出集，不是训练集
- 测试样本用与训练不同的 seed 生成（训练 0-3 → 评测 900+），防止"背题"假象
- 评测脚本趁训练时写好；调用模型 API 前先读其入参定义，必需字段（如 question 里的 task）别猜
- 报告四件套：准确率 / 正确时置信 / 错误时置信 / 单条延迟——错误样本置信度是校准质量的直接证据
- 性能声明同环境 A/B 实测（两边各跑 ≥20 轮取均值），不引用 README 数字

## 6. 报告口径
结论先行 → 真实数字 → 与声明逐条对照（属实/夸大）→ 产物路径。用户风格：直接给数据和判断，不要铺垫。
