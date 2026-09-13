---
name: ljg-drawio
version: 0.1.0
description: "Draw.io XML 生成器 —— 15 种形状 + 6 种边样式 + 2 预设模板。纯 Python,0 依赖,出 .drawio XML 文件 (mxfile/mxGraphModel/mxCell 格式)。当用户要画架构图 / 流程图 / UML / ER 图 / 网络拓扑 / 思维导图时使用。VSCode drawio 扩展 / draw.io 在线 / drawio desktop 都能直接打开 .drawio 文件。"
metadata:
  requires:
    bins: ["python3"]
    python: ">=3.9"
  cliHelp: "python3 -c 'from ljg_drawio import list_shapes, list_edge_styles, list_categories, architecture_3_tier, flowchart_3_steps; print(list_shapes())'"
---

# ljg-drawio

Draw.io XML 生成器。lifestyle 工具 for AI agents to create professional diagrams without GUI or system dependencies.

## 何时调我

| 用户说 | 调什么 |
|---|---|
| "画个架构图" / "出架构" | `Diagram` + `add_shape` + `add_edge` |
| "画流程图" / "做流程" | `flowchart_3_steps` 预设 |
| "画 3 层架构" / "画前后端架构" | `architecture_3_tier` 预设 |
| "图里有啥形状可用" / "能画什么" | `list_shapes` / `list_categories` |
| "用 … 风格" (学术/咨询/...) | 不直接对应,drawio 走 shape preset |

## 何时不调我

- 用户要"全功能 drawio 控制" → 用 `cli-anything-drawio` (HKUDS 原版,需系统 drawio)
- 用户要"渲染成 PNG" → 用 `ljg-ppt-design` 的 LO 后端转 .pptx 然后 .png
- 简单 box-and-arrow 草图 → 直接用 `flowchart_3_steps(steps)` 即可

## 15 种形状

| 分类 | 形状 |
|---|---|
| **flow** | rectangle, rounded, process, diamond, ellipse |
| **data** | cylinder, document, note |
| **control** | diamond, callout |
| **ui** | rectangle, rounded, text |
| **cloud** | cloud, rectangle |
| **actor** | actor |
| **architecture** | rectangle, cylinder, cloud, actor |

## 6 种边样式

| key | 用途 |
|---|---|
| `straight` | 直线 |
| `orthogonal` | 折线 (默认) |
| `curved` | 曲线 |
| `entity-relation` | ER 图 (1-to-many 等) |
| `arrow` | 带箭头 (默认推荐) |
| `dashed-arrow` | 虚线箭头 (弱依赖) |

## 快速使用

```python
from ljg_drawio import Diagram

# 1. 手画
diag = Diagram(name="系统架构")
web = diag.add_shape("rectangle", x=300, y=40, w=200, h=60, label="Web Client")
api = diag.add_shape("rounded", x=300, y=160, w=200, h=60, label="API Gateway")
db = diag.add_shape("cylinder", x=300, y=400, w=200, h=80, label="PostgreSQL")
diag.add_edge(web, api, label="HTTPS")
diag.add_edge(api, db, style="arrow", label="SQL")
diag.write("/tmp/arch.drawio")  # → VSCode drawio 扩展可直接打开

# 2. 预设模板
from ljg_drawio import architecture_3_tier, flowchart_3_steps
d1 = architecture_3_tier()                                    # 6 shape + 6 edge
d2 = flowchart_3_steps(["用户输入", "处理", "输出"])            # 3 shape
```

## 输出格式

输出标准 `mxfile` (drawio XML) — 包含 `<mxfile><diagram><mxGraphModel><root><mxCell>` 层级,VSCode drawio 扩展、draw.io 在线、drawio desktop 都能直接打开。

跨 skill 整合:
- 跟 `ljg-ppt-design` 整合: drawio 出的图 → 转 PNG → 嵌进 ljg-ppt-design 的 `content_image` 页

## 数据契约

`Diagram.to_string()` 返回 UTF-8 XML 字符串,`to_bytes()` 返回字节,`write(path)` 写到文件并返回路径。

---

_ljg-drawio · 0 依赖 .drawio XML 生成器_
_2026-06-18 · 慧慧 从 HKUDS/CLI-Anything drawio 套件简化移植_
