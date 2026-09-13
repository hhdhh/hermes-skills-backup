"""ljg-drawio — Draw.io XML 生成器 (纯 Python, 0 依赖)。

来源: HKUDS/CLI-Anything (drawio 套件) 简化版。
不依赖系统 drawio,直接生成 .drawio XML 文件 (mxfile/mxGraphModel/mxCell 格式)。
.drawio 文件 VSCode drawio 扩展 / draw.io 在线 / drawio desktop 都能开。

主 API:
  from ljg_drawio import Diagram, Shape, Edge
  diag = Diagram(name="...")
  shape = diag.add_shape("rectangle", x=100, y=100, w=120, h=60, label="...")
  diag.add_edge(shape, other_shape, style="arrow", label="...")
  diag.write("/tmp/arch.drawio")

预设:
  - architecture_3_tier()  — 3 层架构图 (web / app / db)
  - flowchart_3_steps(steps)  — 简单流程图

下游消费:
  - VSCode drawio 扩展: 直接 .drawio 文件
  - draw.io 在线: 拖入或 import
  - drawio desktop: 打开文件
  - Confluence drawio 宏: 嵌入
"""

from __future__ import annotations

from .shapes import (
    SHAPE_STYLES,
    EDGE_STYLES,
    SHAPE_CATEGORIES,
    list_shapes,
    list_edge_styles,
    list_categories,
    get_shape_style,
    get_edge_style,
)
from .builder import Diagram, Shape, Edge, architecture_3_tier, flowchart_3_steps

__version__ = "0.1.0"
__all__ = [
    # 字典
    "SHAPE_STYLES", "EDGE_STYLES", "SHAPE_CATEGORIES",
    # 形状 / 边
    "Shape", "Edge", "Diagram",
    # 预设
    "architecture_3_tier", "flowchart_3_steps",
    # 查询
    "list_shapes", "list_edge_styles", "list_categories",
    "get_shape_style", "get_edge_style",
]
