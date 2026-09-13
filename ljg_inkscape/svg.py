"""SVG XML 生成器 (0 依赖,跟 ljg-drawio 同 lattice)。

支持 15 种 SVG 元素 + 5 种风格 preset + 2D transform。
输出标准 SVG 1.1,Inkscape / Illustrator / 浏览器 / 任何矢量编辑器都能开。

用法:
  from ljg_inkscape import Canvas, Rect, Circle, Text, Line, Group
  canvas = Canvas(width=400, height=300)
  canvas.add(Rect(x=50, y=50, width=100, height=60, fill='#1A3C8B', rx=8))
  canvas.add(Circle(cx=200, cy=150, r=40, fill='#E67733'))
  canvas.add(Text(x=200, y=200, text='Hello', font_size=24, anchor='middle'))
  canvas.write('/tmp/poster.svg')
"""

from __future__ import annotations

import html
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union
from xml.etree import ElementTree as ET


# ── 元素 ──────────────────────────────────────────────────
@dataclass
class Element:
    """SVG 元素的统一表示。

    type: 元素类型 (rect/circle/ellipse/line/text/path/group/...)
    attrs: SVG 属性 dict
    children: 子元素 (group 用)
    text: 文本元素用
    """
    type: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)
    text: str = ""

    def __post_init__(self):
        if "id" not in self.attrs:
            self.attrs["id"] = f"el-{uuid.uuid4().hex[:8]}"


# ── 工厂方法 ─────────────────────────────────────────────
def Rect(x: float, y: float, width: float, height: float,
         fill: str = "#000000", stroke: str = "none",
         rx: float = 0, opacity: float = 1.0, **extra) -> Element:
    return Element("rect", {"x": str(x), "y": str(y),
                              "width": str(width), "height": str(height),
                              "fill": fill, "stroke": stroke,
                              "rx": str(rx), "opacity": str(opacity), **extra})


def Circle(cx: float, cy: float, r: float,
           fill: str = "#000000", stroke: str = "none",
           opacity: float = 1.0, **extra) -> Element:
    return Element("circle", {"cx": str(cx), "cy": str(cy), "r": str(r),
                                "fill": fill, "stroke": stroke,
                                "opacity": str(opacity), **extra})


def Ellipse(cx: float, cy: float, rx: float, ry: float,
            fill: str = "#000000", **extra) -> Element:
    return Element("ellipse", {"cx": str(cx), "cy": str(cy),
                                "rx": str(rx), "ry": str(ry),
                                "fill": fill, **extra})


def Line(x1: float, y1: float, x2: float, y2: float,
         stroke: str = "#000000", stroke_width: float = 1.0,
         opacity: float = 1.0, **extra) -> Element:
    return Element("line", {"x1": str(x1), "y1": str(y1),
                             "x2": str(x2), "y2": str(y2),
                             "stroke": stroke, "stroke-width": str(stroke_width),
                             "opacity": str(opacity), **extra})


def Text(x: float, y: float, text: str,
         font_size: float = 16, font_family: str = "Arial",
         fill: str = "#000000", anchor: str = "start",
         weight: str = "normal", **extra) -> Element:
    return Element("text", {"x": str(x), "y": str(y),
                              "font-size": str(font_size),
                              "font-family": font_family,
                              "fill": fill, "text-anchor": anchor,
                              "font-weight": weight, **extra}, text=text)


def Path(d: str, fill: str = "#000000", stroke: str = "none",
         stroke_width: float = 1.0, **extra) -> Element:
    return Element("path", {"d": d, "fill": fill, "stroke": stroke,
                             "stroke-width": str(stroke_width), **extra})


def Polygon(points: list, fill: str = "#000000", **extra) -> Element:
    pts_str = " ".join(f"{x},{y}" for x, y in points)
    return Element("polygon", {"points": pts_str, "fill": fill, **extra})


def Polyline(points: list, stroke: str = "#000000",
             fill: str = "none", **extra) -> Element:
    pts_str = " ".join(f"{x},{y}" for x, y in points)
    return Element("polyline", {"points": pts_str, "stroke": stroke,
                                  "fill": fill, **extra})


def Group(children: list, transform: str = "", **extra) -> Element:
    attrs = {**extra}
    if transform:
        attrs["transform"] = transform
    return Element("g", attrs, children=children)


# ── 风格预设 ─────────────────────────────────────────────
STYLE_PRESETS: dict = {
    "academic": {
        "primary": "#1A3C8B",
        "secondary": "#E67733",
        "accent": "#188050",
        "bg": "#FFFFFF",
        "text": "#222222",
        "muted": "#888888",
    },
    "consultant": {
        "primary": "#003366",
        "secondary": "#00A8E8",
        "accent": "#FF8C00",
        "bg": "#FFFFFF",
        "text": "#212121",
        "muted": "#8C8C8C",
    },
    "business": {
        "primary": "#005294",
        "secondary": "#C82828",
        "accent": "#2DA050",
        "bg": "#FFFFFF",
        "text": "#2D2D30",
        "muted": "#8C8C8C",
    },
    "tech": {
        "primary": "#0F1423",
        "secondary": "#00C8FF",
        "accent": "#FF643C",
        "bg": "#0F1423",
        "text": "#FFFFFF",
        "muted": "#788296",
    },
    "minimal": {
        "primary": "#1A1A1A",
        "secondary": "#666666",
        "accent": "#0066FF",
        "bg": "#FAFAFA",
        "text": "#1A1A1A",
        "muted": "#999999",
    },
}


def get_style(name: str) -> dict:
    return STYLE_PRESETS.get(name, STYLE_PRESETS["academic"])


def list_styles() -> list[dict]:
    return [{"key": k, "colors": v} for k, v in STYLE_PRESETS.items()]


# ── Canvas ───────────────────────────────────────────────
@dataclass
class Canvas:
    """SVG 画布。"""
    width: float = 400
    height: float = 300
    elements: List[Element] = field(default_factory=list)
    title: str = ""
    style: str = "academic"
    background: str = ""

    def add(self, element: Element) -> Element:
        self.elements.append(element)
        return element

    def _to_xml(self) -> ET.Element:
        style = get_style(self.style)
        bg = self.background or style["bg"]
        svg = ET.Element("svg", {
            "xmlns": "http://www.w3.org/2000/svg",
            "xmlns:xlink": "http://www.w3.org/1999/xlink",
            "viewBox": f"0 0 {self.width} {self.height}",
            "width": str(self.width),
            "height": str(self.height),
        })
        if self.title:
            t = ET.SubElement(svg, "title")
            t.text = self.title
        # 背景 (除非 transparent)
        if bg and bg != "transparent":
            ET.SubElement(svg, "rect", {
                "x": "0", "y": "0",
                "width": str(self.width), "height": str(self.height),
                "fill": bg,
            })
        for el in self.elements:
            self._append_element(svg, el, style)
        return svg

    def _append_element(self, parent: ET.Element, el: Element, style: dict):
        # 自动把 semantic color 替换成 hex
        attrs = dict(el.attrs)
        for k, v in list(attrs.items()):
            if isinstance(v, str) and v in style:
                attrs[k] = style[v]
        # 移除空 + 把所有非 str 转 str (ET 不能序列化 int/float)
        cleaned = {}
        for k, v in attrs.items():
            if v == "" or v is None:
                continue
            if not isinstance(v, str):
                v = str(v)
            cleaned[k] = v
        node = ET.SubElement(parent, el.type, cleaned)
        if el.text:
            node.text = html.escape(el.text)
        for child in el.children:
            self._append_element(node, child, style)

    def to_string(self) -> str:
        root = self._to_xml()
        ET.indent(root, space="  ")
        return ET.tostring(root, encoding="unicode")

    def write(self, path: str) -> str:
        from pathlib import Path as P
        parent = P(path).parent
        if parent:
            parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n')
            f.write(self.to_string())
        return path


# ── 预设模板 ─────────────────────────────────────────────
def poster_simple(title: str, subtitle: str = "",
                 style: str = "academic", width: float = 400,
                 height: float = 600) -> Canvas:
    """简单海报 (标题 + 副标题 + 装饰线)。"""
    s = get_style(style)
    c = Canvas(width=width, height=height, title=title, style=style)
    # 顶部装饰线
    c.add(Rect(0, 0, width, 8, fill=s["secondary"]))
    # 主标题
    c.add(Text(x=width / 2, y=height / 2 - 30, text=title,
               font_size=42, fill=s["primary"], weight="bold",
               anchor="middle"))
    # 副标题
    if subtitle:
        c.add(Text(x=width / 2, y=height / 2 + 30, text=subtitle,
                   font_size=20, fill=s["muted"], anchor="middle"))
    # 装饰圆
    c.add(Circle(cx=width / 2, cy=height - 60, r=8, fill=s["accent"]))
    # 底部装饰线
    c.add(Rect(0, height - 4, width, 4, fill=s["secondary"]))
    return c


def icon_set_3() -> Canvas:
    """3 个图标的横排 (rect / circle / triangle 简化)。"""
    c = Canvas(width=300, height=100, title="3 icons")
    c.add(Circle(cx=50, cy=50, r=30, fill="#1A3C8B"))
    c.add(Rect(x=120, y=20, width=60, height=60, fill="#E67733", rx=8))
    c.add(Polygon([(230, 20), (260, 80), (200, 80)], fill="#188050"))
    c.add(Text(x=50, y=95, text="CPU", font_size=10, fill="#666", anchor="middle"))
    c.add(Text(x=150, y=95, text="GPU", font_size=10, fill="#666", anchor="middle"))
    c.add(Text(x=230, y=95, text="MEM", font_size=10, fill="#666", anchor="middle"))
    return c
