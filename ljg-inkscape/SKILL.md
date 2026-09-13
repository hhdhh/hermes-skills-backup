---
name: ljg-inkscape
version: 0.1.0
description: "SVG XML 生成器 —— 0 依赖,不需 Inkscape 本身。15 元素 (rect/circle/line/text/path/group 等) + 5 风格 (academic/consultant/business/tech/minimal) + 2 模板 (海报/图标集)。Inkscape / Illustrator / 浏览器 / 任何矢量编辑器都能开。配合 ljg-ppt-design 出矢量插图。"
metadata:
  requires:
    bins: ["python3"]
    python: ">=3.9"
  cliHelp: "python3 -c 'from ljg_inkscape import Canvas, poster_simple; c = poster_simple(\"Hi\"); c.write(\"/tmp/x.svg\")'"
---

# ljg-inkscape

SVG XML 生成器,0 系统依赖。lifestyle for AI agents to produce vector graphics without Inkscape/Illustrator installed.

## 何时调我

| 用户说 | 调什么 |
|---|---|
| "做张海报" / "画矢量图" | `poster_simple` / 手画 |
| "画个 logo" | `Canvas` + 几何 + `Text` |
| "图标集" / "icon set" | `icon_set_3` |
| "出 SVG" | `canvas.write("out.svg")` |
| "想要学术/科技/极简风格" | 5 个 `STYLE_PRESETS` |

## 何时不调我

- 复杂位图处理 (滤镜/渐变/路径编辑) — 装 Inkscape
- 全功能 Inkscape 控制 — 用 `cli-anything-inkscape` (HKUDS 原版)
- 已经会 Python 写 SVG — 不用我

## 15 元素

| Factory | 类型 | 关键参数 |
|---|---|---|
| `Rect(x, y, w, h)` | rect | fill, rx (圆角), opacity |
| `Circle(cx, cy, r)` | circle | fill, opacity |
| `Ellipse(cx, cy, rx, ry)` | ellipse | fill |
| `Line(x1, y1, x2, y2)` | line | stroke, stroke_width |
| `Text(x, y, text)` | text | font_size, anchor, weight |
| `Path(d)` | path | d (SVG path 字符串) |
| `Polygon(points)` | polygon | fill |
| `Polyline(points)` | polyline | stroke |
| `Group(children)` | g | transform |

## 5 风格

| key | 配色 |
|---|---|
| `academic` | 深蓝 #1A3C8B / 橙 #E67733 / 绿 #188050 |
| `consultant` | 深蓝 #003366 / 亮青 #00A8E8 / 橙 #FF8C00 |
| `business` | 商务蓝 #005294 / 红 #C82828 / 绿 #2DA050 |
| `tech` | 近黑 #0F1423 / 亮青 #00C8FF / 橙红 #FF643C (暗色) |
| `minimal` | 近黑 #1A1A1A / 灰 #666666 / 蓝 #0066FF |

**配色跟 ljg-ppt-design 一致** — 同一份 deck 里 PPT + SVG 风格统一。

## 2 模板

```python
from ljg_inkscape import poster_simple, icon_set_3

# 简单海报 (400×600,带标题/副标题/装饰线)
c = poster_simple("My Title", "subtitle", style="tech")
c.write("/tmp/poster.svg")

# 3 图标横排 (300×100, circle + rect + triangle)
c2 = icon_set_3()
c2.write("/tmp/icons.svg")
```

## 语义色自动解析

`Canvas` 渲染时会把 `fill="primary"` 这种语义名替换成风格的实际 hex:

```python
c = Canvas(style="tech")
c.add(Rect(0, 0, 100, 100, fill="primary"))  # → 实际 #0F1423
c.add(Text(50, 50, "Hi", fill="text"))        # → 实际 #FFFFFF
```

避免硬编码颜色,改风格时整 deck 自动适配。

## 快速使用

```python
from ljg_inkscape import Canvas, Rect, Circle, Text, Line

c = Canvas(width=400, height=300, style="academic")
c.add(Rect(20, 20, 100, 60, fill="primary", rx=8))
c.add(Circle(200, 150, 40, fill="secondary"))
c.add(Text(200, 200, "Hello", font_size=24, fill="text", anchor="middle"))
c.add(Line(120, 50, 160, 150, stroke="accent", stroke_width=2))
c.write("/tmp/diagram.svg")
```

## 跟 ljg-ppt-design 整合

`integrations.deck_with_inkscape_svg(preset, talk_type, name, canvas, content, convert_to_png=False)`:
- `convert_to_png=True` → SVG → cairosvg/LO → PNG → PPT
- `convert_to_png=False` → 直接用 SVG 路径 (PowerPoint 支持嵌入 SVG)

## 输出格式

SVG 1.1 (含 namespace),Inkscape / Illustrator / 浏览器 / 任何矢量编辑器都开。

---

_ljg-inkscape · 0 依赖 SVG 生成器_
_2026-06-18 · 慧慧 从 HKUDS/CLI-Anything inkscape 套件简化移植_
