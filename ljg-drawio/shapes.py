"""drawio 形状 + 边样式字典。

来源: HKUDS/CLI-Anything (drawio 套件) — 简化版,只保留必要的 style preset。
原版 dict 在 `cli_anything/drawio/utils/drawio_xml.py:SHAPE_STYLES / EDGE_STYLES`。
"""

from __future__ import annotations

from typing import Tuple


# ── 形状 (vertex) 样式 ──────────────────────────────────
# key: 短名 (给 agent 用)  value: drawio style string
SHAPE_STYLES: dict[str, str] = {
    "rectangle": "rounded=0;whiteSpace=wrap;html=1;",
    "rounded":   "rounded=1;whiteSpace=wrap;html=1;",
    "ellipse":   "ellipse;whiteSpace=wrap;html=1;",
    "diamond":   "rhombus;whiteSpace=wrap;html=1;",
    "triangle":  "triangle;whiteSpace=wrap;html=1;",
    "hexagon":   "shape=hexagon;perimeter=hexagonPerimeter2;whiteSpace=wrap;html=1;",
    "cylinder":  "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;",
    "cloud":     "ellipse;shape=cloud;whiteSpace=wrap;html=1;",
    "parallelogram": "shape=parallelogram;perimeter=parallelogramPerimeter;whiteSpace=wrap;html=1;",
    "process":   "shape=process;whiteSpace=wrap;html=1;backgroundOutline=1;",
    "document":  "shape=document;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;",
    "callout":   "shape=callout;perimeter=calloutPerimeter;whiteSpace=wrap;html=1;",
    "note":      "shape=note;whiteSpace=wrap;html=1;backgroundOutline=1;darkOpacity=0.05;",
    "actor":     "shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;html=1;",
    "text":      "text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;",
}


# ── 边 (edge) 样式 ──────────────────────────────────────
EDGE_STYLES: dict[str, str] = {
    "straight":          "edgeStyle=none;html=1;",
    "orthogonal":        "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;",
    "curved":            "edgeStyle=orthogonalEdgeStyle;curved=1;rounded=1;html=1;",
    "entity-relation":   "edgeStyle=entityRelationEdgeStyle;fontSize=12;html=1;",
    "arrow":             "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=classic;",
    "dashed-arrow":      "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=classic;dashed=1;",
}


# ── 形状分类 (给 agent 决策) ─────────────────────────────
SHAPE_CATEGORIES: dict[str, list[str]] = {
    "flow":          ["rectangle", "rounded", "process", "diamond", "ellipse"],
    "data":          ["cylinder", "document", "note"],
    "control":       ["diamond", "callout"],
    "ui":            ["rectangle", "rounded", "text"],
    "cloud":         ["cloud", "rectangle"],
    "actor":         ["actor"],
    "architecture":  ["rectangle", "cylinder", "cloud", "actor"],
}


# ── 辅助函数 ─────────────────────────────────────────────
def list_shapes() -> list[dict]:
    """列出所有形状 (供 agent 决策)。"""
    return [{"key": k, "style": v} for k, v in SHAPE_STYLES.items()]


def list_edge_styles() -> list[dict]:
    return [{"key": k, "style": v} for k, v in EDGE_STYLES.items()]


def list_categories() -> list[dict]:
    return [{"category": k, "shapes": v} for k, v in SHAPE_CATEGORIES.items()]


def get_shape_style(shape_type: str) -> str:
    """按 key 取 shape style,未知返回 rectangle 兜底。"""
    return SHAPE_STYLES.get(shape_type, SHAPE_STYLES["rectangle"])


def get_edge_style(edge_style: str) -> str:
    return EDGE_STYLES.get(edge_style, EDGE_STYLES["arrow"])
