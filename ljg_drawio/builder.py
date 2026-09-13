"""drawio XML 写入器 + 高级 API。

用法:
  from ljg_drawio import Diagram, Shape, Edge

  diag = Diagram(name="架构图")
  web = diag.add_shape("rectangle", x=100, y=100, w=120, h=60, label="Web Server")
  db = diag.add_shape("cylinder", x=300, y=100, w=120, h=80, label="PostgreSQL")
  diag.add_edge(web, db, style="arrow", label="reads")
  diag.write("/tmp/arch.drawio")
"""

from __future__ import annotations

import os
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from xml.etree import ElementTree as ET

from .shapes import get_shape_style, get_edge_style


@dataclass
class Shape:
    """一个 drawio 形状 (vertex)。"""
    shape_type: str
    x: float
    y: float
    width: float
    height: float
    label: str = ""
    cell_id: Optional[str] = None
    style_override: Optional[str] = None  # 覆盖默认 style

    def __post_init__(self):
        if self.cell_id is None:
            self.cell_id = f"shape-{uuid.uuid4().hex[:8]}"


@dataclass
class Edge:
    """一个 drawio 边 (connector)。"""
    source_id: str
    target_id: str
    style: str = "arrow"
    label: str = ""
    edge_id: Optional[str] = None

    def __post_init__(self):
        if self.edge_id is None:
            self.edge_id = f"edge-{uuid.uuid4().hex[:8]}"


class Diagram:
    """一份 drawio 图 (1 个 diagram 元素,可包含多 shape / edge)。"""

    def __init__(
        self,
        name: str = "Page-1",
        page_width: int = 850,
        page_height: int = 1100,
        grid_size: int = 10,
    ):
        self.name = name
        self.page_width = page_width
        self.page_height = page_height
        self.grid_size = grid_size
        self.shapes: List[Shape] = []
        self.edges: List[Edge] = []
        self._id_counter = 100  # 给 cell_id 起点

    def add_shape(
        self,
        shape_type: str = "rectangle",
        x: float = 100,
        y: float = 100,
        width: float = 120,
        height: float = 60,
        label: str = "",
        cell_id: Optional[str] = None,
        # 别名 (w/h 跟 width/height 等价,方便 agent 写短)
        w: Optional[float] = None,
        h: Optional[float] = None,
    ) -> Shape:
        """加一个形状,返回 Shape (给后续 edge 用)。"""
        actual_w = w if w is not None else width
        actual_h = h if h is not None else height
        s = Shape(shape_type=shape_type, x=x, y=y, width=actual_w, height=actual_h,
                  label=label, cell_id=cell_id)
        self.shapes.append(s)
        return s

    def add_edge(
        self,
        source: "Shape | str",
        target: "Shape | str",
        style: str = "arrow",
        label: str = "",
    ) -> Edge:
        """加一个边。source / target 可以是 Shape 对象或 cell_id 字符串。"""
        source_id = source.cell_id if isinstance(source, Shape) else source
        target_id = target.cell_id if isinstance(target, Shape) else target
        e = Edge(source_id=source_id, target_id=target_id, style=style, label=label)
        self.edges.append(e)
        return e

    def shape_count(self) -> int:
        return len(self.shapes)

    def edge_count(self) -> int:
        return len(self.edges)

    # ── XML 序列化 ──────────────────────────────────────
    def _to_xml(self) -> ET.Element:
        """生成 drawio XML 树。"""
        mxfile = ET.Element("mxfile")
        mxfile.set("host", "ljg-drawio")
        mxfile.set("agent", "ljg-drawio/0.1.0")
        mxfile.set("version", "24.0.0")

        diagram = ET.SubElement(mxfile, "diagram")
        diagram.set("id", f"diagram-{uuid.uuid4().hex[:8]}")
        diagram.set("name", self.name)

        model = ET.SubElement(diagram, "mxGraphModel")
        model.set("dx", "1200")
        model.set("dy", "800")
        model.set("grid", "1")
        model.set("gridSize", str(self.grid_size))
        model.set("guides", "1")
        model.set("tooltips", "1")
        model.set("connect", "1")
        model.set("arrows", "1")
        model.set("fold", "1")
        model.set("page", "1")
        model.set("pageScale", "1")
        model.set("pageWidth", str(self.page_width))
        model.set("pageHeight", str(self.page_height))
        model.set("math", "0")
        model.set("shadow", "0")

        root = ET.SubElement(model, "root")

        # mxCell id=0 (root container) + id=1 (default layer)
        cell0 = ET.SubElement(root, "mxCell")
        cell0.set("id", "0")

        cell1 = ET.SubElement(root, "mxCell")
        cell1.set("id", "1")
        cell1.set("parent", "0")

        # 形状
        for s in self.shapes:
            cell = ET.SubElement(root, "mxCell")
            cell.set("id", s.cell_id)
            cell.set("value", s.label)
            cell.set("style", s.style_override or get_shape_style(s.shape_type))
            cell.set("vertex", "1")
            cell.set("parent", "1")
            geom = ET.SubElement(cell, "mxGeometry")
            geom.set("x", str(s.x))
            geom.set("y", str(s.y))
            geom.set("width", str(s.width))
            geom.set("height", str(s.height))
            geom.set("as", "geometry")

        # 边
        for e in self.edges:
            cell = ET.SubElement(root, "mxCell")
            cell.set("id", e.edge_id)
            cell.set("value", e.label)
            cell.set("style", get_edge_style(e.style))
            cell.set("edge", "1")
            cell.set("parent", "1")
            cell.set("source", e.source_id)
            cell.set("target", e.target_id)
            geom = ET.SubElement(cell, "mxGeometry")
            geom.set("relative", "1")
            geom.set("as", "geometry")

        return mxfile

    def to_string(self) -> str:
        """返回 XML 字符串 (UTF-8)。"""
        root = self._to_xml()
        ET.indent(root, space="  ")
        return ET.tostring(root, encoding="unicode")

    def to_bytes(self) -> bytes:
        """返回 XML 字节。"""
        return self.to_string().encode("utf-8")

    def write(self, path: str) -> str:
        """写到 .drawio 文件,返回 path。"""
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "wb") as f:
            f.write(self.to_bytes())
        return path


# ── 预设模板 (给 agent 用) ───────────────────────────────
def architecture_3_tier() -> Diagram:
    """3 层架构图模板 (web → app → db)。"""
    d = Diagram(name="3-Tier Architecture")
    web = d.add_shape("rectangle", x=300, y=40, w=200, h=60, label="Web Client")
    lb = d.add_shape("rectangle", x=300, y=160, w=200, h=60, label="Load Balancer")
    app = d.add_shape("rounded", x=120, y=280, w=200, h=60, label="App Server 1")
    app2 = d.add_shape("rounded", x=380, y=280, w=200, h=60, label="App Server 2")
    db = d.add_shape("cylinder", x=300, y=400, w=200, h=80, label="Database")
    cache = d.add_shape("cylinder", x=560, y=280, w=120, h=70, label="Cache")
    d.add_edge(web, lb, label="HTTPS")
    d.add_edge(lb, app)
    d.add_edge(lb, app2)
    d.add_edge(app, db)
    d.add_edge(app2, db)
    d.add_edge(app, cache, style="dashed-arrow", label="read")
    return d


def flowchart_3_steps(steps: list[str]) -> Diagram:
    """简单 3 步流程图 (rectangle + arrow)。"""
    d = Diagram(name="Flow")
    n = len(steps)
    start_x = 100
    spacing = 250
    w = 200
    h = 60
    y = 200
    prev = None
    for i, step in enumerate(steps):
        s = d.add_shape("rectangle", x=start_x + i * spacing, y=y, w=w, h=h, label=step)
        if prev:
            d.add_edge(prev, s, label=f"step {i+1}")
        prev = s
    return d
