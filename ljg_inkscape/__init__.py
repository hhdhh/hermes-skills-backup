"""ljg-inkscape — SVG XML 生成器 (0 依赖)。

来源: HKUDS/CLI-Anything (inkscape 套件) 简化版。
不依赖 Inkscape 本身,直接生成 SVG 1.1 XML。

15 元素 (factory): Rect / Circle / Ellipse / Line / Text / Path / Polygon / Polyline / Group
5 风格 preset: academic / consultant / business / tech / minimal
2 模板: poster_simple / icon_set_3

用法:
  from ljg_inkscape import Canvas, Rect, Circle, Text, poster_simple
  c = poster_simple("Hello World", "subtitle", style="tech")
  c.write("/tmp/poster.svg")
"""

from __future__ import annotations

from .svg import (
    Element,
    Rect, Circle, Ellipse, Line, Text, Path, Polygon, Polyline, Group,
    STYLE_PRESETS, get_style, list_styles,
    Canvas, poster_simple, icon_set_3,
)

__version__ = "0.1.0"
__all__ = [
    # 元素
    "Element", "Rect", "Circle", "Ellipse", "Line", "Text", "Path",
    "Polygon", "Polyline", "Group",
    # 风格
    "STYLE_PRESETS", "get_style", "list_styles",
    # Canvas
    "Canvas",
    # 模板
    "poster_simple", "icon_set_3",
]
