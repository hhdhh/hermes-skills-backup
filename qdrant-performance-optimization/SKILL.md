---
name: qdrant-performance-optimization
description: "Different techniques to optimize the performance of Qdrant, including indexing strategies, query optimization, and hardware considerations. Use when you want to improve the speed and efficiency of your Qdrant deployment."
allowed-tools:
  - Read
  - Grep
  - Glob
---


# Qdrant Performance Optimization

There are different aspects of Qdrant performance, this document serves as a navigation hub for different aspects of performance optimization in Qdrant.


## Search Speed Optimization

There are two different criteria for search speed: latency and throughput. 
Latency is the time it takes to get a response for a single query, while throughput is the number of queries that can be processed in a given time frame.
Depending on your use case, you may want to optimize for one or both of these metrics.

More on search speed optimization can be found in the [Search Speed Optimization](search-speed-optimization/SKILL.md) skill.


## Indexing Performance Optimization

Qdrant needs to build a vector index to perform efficient similarity search. The time it takes to build the index can vary depending on the size of your dataset, hardware, and configuration.

More on indexing performance optimization can be found in the [Indexing Performance Optimization](indexing-performance-optimization/SKILL.md) skill.


## Memory Usage Optimization

Vector search can be memory intensive, especially when dealing with large datasets.
Qdrant has a flexible memory management system, which allows you to precisely control which parts of storage are kept in memory and which are stored on disk. This can help you optimize memory usage without sacrificing performance.

More on memory usage optimization can be found in the [Memory Usage Optimization](memory-usage-optimization/SKILL.md) skill.

## 失败模式与降级 (Failure Modes & Fallback)

- **如果 `<sub-skill>/SKILL.md` 找不到** → 提示用户该子领域文件缺失，跳过该子领域继续其他
- **如果 Qdrant 实例不可达**（curl `${QDRANT_URL}/healthz` 失败）→ 提醒检查 QDRANT_URL / 网络 / 防火墙
- **如果用户给的优化目标不明确**（latency vs throughput vs memory）→ 先问清楚再下手
- **如果硬件规格未知** → 默认假设中等配置 (8 CPU / 16GB RAM / NVMe SSD)，先按此推荐
- **如果数据集规模 < 10K 向量** → 优化收益小，明确告知用户"可能不值得"

## 反例与黑名单 (Anti-Patterns)

- ❌ **不要在生产环境直接改 indexing 配置** — 先在 staging / 小数据集验证
- ❌ **不要忽略 HNSW 参数与数据规模的关系** — 大数据集必须调 `ef_construct` 和 `m`
- ❌ **不要把向量量化（quantization）当银弹** — 有召回率代价，先量化代价
- ❌ **不要在没有 baseline 测量的情况下优化** — 先用 `qdrant` 的 telemetry / `/metrics` 量化当前问题
- ❌ **不要盲目提高 `ef` 值** — recall 提升有边际，超过 200 几乎没增益
- ⚠️ **不要推荐变更后立刻 `qdrant restart`** — 索引会重建，影响线上

## 检查点 (Checkpoints)

- 🔴 **CHECKPOINT**: 切换 indexing 策略前必须先要 baseline 数据 (p50/p99 latency, recall@10)
- 🔴 **CHECKPOINT**: 推荐 quantization 前先告知用户召回率预期下降幅度
- 🛑 **STOP**: 用户说"激进优化"但没给数据 → 引导先做 baseline，再回来