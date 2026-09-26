# numpy 2.x 兼容 shim 与崩溃循环修复

<!-- capability_id: autolife-ops.numpy-shim | revision: 1 | status: active -->
<!-- 来源: 案例005 · numpy 2.x 移除 2 维向量 np.cross 支持（飞书语料） -->

## R — 原文

> 修复：在robot_env写sitecustomize.py兼容shim（出错时自动垫3维），重启gv-slam即恢复，不动包、不降级numpy。
> —— 《案例005 · numpy 2.x 移除 2 维向量 np.cross 支持》

## I — 自述

numpy 2.0 移除了 2 维向量的 np.cross 支持。gv 包的 laser_line_finder.py 用 2D 调用 np.cross，在新 numpy 环境必抛 ValueError，gv-slam 进入崩溃循环（重启 70+ 次）——服务看似 active，实际一直在死循环。

三条修复路线对比：降级 numpy（破坏其他依赖，不可取）；改 .so 内源码（闭源不可行）；**sitecustomize.py shim**（Python 解释器启动时自动加载该文件，monkey-patch np.cross：2D 输入抛 ValueError 时自动垫成 3 维再算再降回）——无侵入、不动包、不降级，重启即生效。

这个模式可推广：任何三方闭源包与新版本依赖的兼容问题，都可以用 sitecustomize 在启动层垫兼容层。位置必须放 robot_env（随环境走），不能放系统 site-packages（升级丢失）。

## A1 — 书中案例

**案例类型：书中亲历案例**（案例005 完整链路）

- 输入/问题：机器人导航用不了，gv-slam 反复重启
- 方法执行：NRestarts 采样=崩溃循环实锤 → journalctl 找第一个异常=np.cross ValueError → 源头是 numpy 2.x 移除 2D 支持 → 评估三条路线 → 选 sitecustomize shim 写入 robot_env → restart gv-slam
- 结论：崩溃循环停止，导航恢复；后续话题数验证 2→113（配合 URI 修复）

## A2 — 未来触发 ★

**情境：**

1. gv/视觉服务崩溃循环，日志见 np.cross 或其他 numpy API 报错
2. 机器人环境升级 numpy 后某些服务起不来
3. 任何闭源包与新版本 Python 依赖不兼容
4. 想降级 numpy 前先找替代方案

**语言信号：**

- "崩溃循环" / "反复重启" / "NRestarts 涨"
- "np.cross" / "numpy 2" / "ValueError"
- "降级 numpy" / "兼容 shim"
- EN: "crash loop after numpy upgrade" / "np.cross 2d removed"

**区分：**

- ≠ autolife-slam-troubleshooting：那支是建图空白全链排查；本卡是其中"numpy 崩溃循环"根因的专项深修
- ≠ autolife-ops-robot-diagnosis：那找断点；本卡是断点已在 numpy API 时的修法
- ≠ 系统 Python 环境管理：本卡只垫 gv robot_env，不动系统层

## E — 可执行步骤

**输入契约**：机号（必填）；崩溃服务名+日志中的报错（必填）；确认报错源于 numpy API 变更（必填——非 numpy 类崩溃不适用）。

**Step 1 确认崩溃循环**：`systemctl --user show gv-slam -p NRestarts` 前后 60s 采样，增量>0 实锤
**Step 2 定位首异常**：`journalctl --user -u gv-slam --since "..." | grep -m1 -B2 ValueError`——确认是 np.cross 2D 调用
**Step 3 写 shim**（robot_env 目录，非系统 site-packages）：
```python
# sitecustomize.py — numpy 2.x 兼容垫片
import numpy as np
_orig_cross = np.cross
def _cross_compat(*args, **kwargs):
    try:
        return _orig_cross(*args, **kwargs)
    except ValueError:
        # 2 维向量自动垫 3 维再算
        padded = [np.pad(np.asarray(a).astype(float), (0,1)) for a in args[:2]]
        return _orig_cross(*padded, **kwargs)[..., :2] if padded[0].shape[-1]==2 else _orig_cross(*padded, **kwargs)
np.cross = _cross_compat
```
**Step 4 重启验证**：`systemctl --user restart gv-slam` → NRestarts 稳定 + journalctl 无 ValueError + 话题恢复
**判停点**：shim 后仍崩（非 np.cross 类）→ 撤 shim 回诊断链，不带病叠加 monkey-patch；报错在 .so 内部且与 numpy 无关 → 不适用本卡

**输出契约**：shim 文件路径+内容 + 修复前后 NRestarts 对比 + 服务稳定证据。

## B — 边界

- **不适用**：非 numpy 类崩溃；系统 Python 环境问题；SDK 层 bug
- **反场景**：一上来就降级 numpy（连带伤）；shim 写进系统 site-packages（升级丢）；不明报错就垫 monkey-patch（掩盖真病）
- **失败模式**：垫片逻辑改变数值语义（必须只垫维度不改算法）；多服务抢同名 shim 冲突
- **相邻易混**：DDS 参与者上限也是"互相看不见"，但修 URI 不修包
