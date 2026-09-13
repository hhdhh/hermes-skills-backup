---
name: memory-optimization
description: >
  Profile and optimize application memory usage. Identify memory leaks, reduce
  memory footprint, and improve efficiency for better performance and
  reliability.
---

# Memory Optimization

## Table of Contents

- [Overview](#overview)
- [When to Use](#when-to-use)
- [Quick Start](#quick-start)
- [Reference Guides](#reference-guides)
- [Best Practices](#best-practices)

## Overview

Memory optimization improves application performance, stability, and reduces infrastructure costs. Efficient memory usage is critical for scalability.

## When to Use

- High memory usage
- Memory leaks suspected
- Slow performance
- Out of memory crashes
- Scaling challenges

## Quick Start

Minimal working example:

```javascript
// Browser memory profiling

// Check memory usage
performance.memory: {
  jsHeapSizeLimit: 2190000000,    // Max available
  totalJSHeapSize: 1300000000,    // Total allocated
  usedJSHeapSize: 950000000       // Currently used
}

// React DevTools Profiler
- Open React DevTools → Profiler
- Record interaction
- See component renders and time
- Identify unnecessary renders

// Chrome DevTools
1. Open DevTools → Memory
2. Take heap snapshot
3. Compare before/after
4. Look for retained objects
5. Check retained sizes

// Node.js profiling
node --inspect app.js
// Open chrome://inspect → "Open dedicated DevTools for Node"
// Trigger the suspected leak
// Take heap snapshot in DevTools → Memory tab
// Compare 2 snapshots (before/after interaction) to find retained objects
```

## Reference Guides

Detailed implementations in the `references/` directory:

| Guide | Contents |
|---|---|
| [Memory Profiling](references/memory-profiling.md) | Memory Profiling |
| [Memory Leak Detection](references/memory-leak-detection.md) | Memory Leak Detection |
| [Optimization Techniques](references/optimization-techniques.md) | Optimization Techniques |
| [Monitoring & Targets](references/monitoring-targets.md) | Monitoring & Targets |

## Best Practices

### ✅ DO

- Follow established patterns and conventions
- Write clean, maintainable code
- Add appropriate documentation
- Test thoroughly before deploying

### ❌ DON'T

- Skip testing or validation
- Ignore error handling
- Hard-code configuration values

## 失败模式与降级 (Failure Modes & Fallback)

- **如果 `performance.memory` 在生产环境不可用**（跨域隔离 / 隐私模式）→ 改用 `performance.measureUserAgentSpecificMemory()` 或 server-side profiling
- **如果 React DevTools Profiler 没装** → 改用 React Profiler API（`<Profiler>` 组件）编程式采集
- **如果 Chrome DevTools heap snapshot 超过 1GB** → 改用 Allocation instrumentation 模式或 Node.js 的 `v8.writeHeapSnapshot()`
- **如果 `node --inspect` 启动后 chrome://inspect 看不到 target** → 检查 9229 端口是否被占用，target 主机头是否匹配
- **如果用户给的内存数据是采样而非真实数据**（perf counter / RSS）→ 明确告知这是估算值，不要断言"这是 leak"
- **如果泄漏源是闭包**（closure 持有 DOM 引用）→ 引导用户用 DevTools 的 "Retainers" 面板而不是堆大小

## 反例与黑名单 (Anti-Patterns)

- ❌ **不要只看 `usedJSHeapSize` 单调上升就断定是泄漏** — 单调上升可能是 GC 没运行，先强制 `gc()` 再判断
- ❌ **不要把内存优化当作单一指标优化** — latency / startup / FPS 都要综合考虑
- ❌ **不要用 `delete obj.prop` 试图"释放"内存** — V8 不保证立即回收；用 `obj.prop = null` 解除引用即可
- ❌ **不要在生产环境频繁 `console.log` 大对象** — 序列化会复制内存，反而泄漏
- ❌ **不要相信"内存优化完性能一定提升"** — 小内存占用可能伴随更高 GC 频率，先 benchmark 再决定
- ⚠️ **不要在 SSR / Node.js Worker 线程里假设有 DOM** — Profiling API 不一样

## 检查点 (Checkpoints)

- 🔴 **CHECKPOINT**: 优化前必须先有 baseline（peak / average / p99 memory 数据）
- 🔴 **CHECKPOINT**: 改完代码必须先在 staging 重测 memory profile，不要直接上生产
- 🔴 **CHECKPOINT**: 报告"优化了 X% 内存"前必须说明 measurement window 和 GC 状态
- 🛑 **STOP**: 用户说"内存爆了"但没提供 metrics / 报错 → 先要数据再优化，不靠猜
