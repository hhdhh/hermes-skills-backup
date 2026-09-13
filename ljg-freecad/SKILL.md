---
name: ljg-freecad
version: 0.1.0
description: "3D 几何生成器 —— 0 依赖,不需 OpenCascade。5 形状 (cuboid/cylinder/sphere/cone/torus) + 3 预设模板 + STL/OBJ/STEP 导出。机器人公司机械设计、3D 打印、教学几何。STL 任何 3D 打印软件/切片器都能开,OBJ Web 3D,STEP 工业 CAD (简化版)。"
metadata:
  requires:
    bins: ["python3"]
    python: ">=3.9"
  cliHelp: "python3 -c 'from ljg_freecad import cuboid, cylinder, assembly_example, export_stl; print(cuboid(10,20,30))'"
---

# ljg-freecad

3D 几何生成器,0 系统依赖。lifestyle for AI agents to produce 3D files without FreeCAD/Fusion 360 installed.

## 何时调我

| 用户说 | 调什么 |
|---|---|
| "做个 3D 模型" / "3D 打印" / "机械设计" | `cuboid` / `cylinder` / `assembly_example` |
| "出 STL" / "切片文件" | `export_stl(parts, "out.stl")` |
| "出 OBJ" / "Web 3D" | `export_obj(parts, "out.obj")` |
| "出 STEP" / "CAD 交换" | `export_step(parts, "out.step")` |
| "L 型支架" / "装配图" | `bracket_L` / `assembly_example` |

## 何时不调我

- 复杂布尔运算 (OCC 算法) — 装 `cadquery` (1GB+) 直接用
- 实体 mesh 编辑 — 用 FreeCAD / Fusion 360 / Blender
- 用户要"全功能 FreeCAD 控制" — 用 `cli-anything-freecad` (HKUDS 原版)

## 5 形状

| 形状 | 工厂 | 参数 (mm) |
|---|---|---|
| 长方体 | `cuboid(w, h, d)` | width, height, depth |
| 圆柱 | `cylinder(r, h)` | radius, height |
| 球 | `sphere(r)` | radius |
| 圆锥/圆台 | `cone(rb, h, rt=0)` | radius_base, height, radius_top |
| 环 | `torus(R, r)` | major_radius, minor_radius |

## 3 预设

| name | 用途 |
|---|---|
| `bracket_L(thickness, length, width)` | L 型支架 (底板 + 侧板) |
| `box_with_hole(w, h, d, hole_r)` | 带圆孔的盒子 (2 件,导入 CAD 后做布尔) |
| `assembly_example()` | 4 件装配: 底板 + 2 立柱 + 横梁 |

## 变换

```python
from ljg_freecad import cuboid, translate, rotate
part = cuboid(50, 50, 5)
part = translate(part, x=0, y=0, z=100)   # 平移到 z=100
part = rotate(part, x=0.5, y=0, z=0)       # 绕 X 轴旋转 0.5 rad
```

## 快速使用

```python
from ljg_freecad import cuboid, cylinder, translate, assembly_example, export_stl

# 1. 装配示例
parts = assembly_example()  # 4 件
export_stl(parts, "/tmp/assembly.stl")

# 2. L 型支架
from ljg_freecad import bracket_L
parts = bracket_L(thickness=5, length=50, width=30)
export_stl(parts, "/tmp/l-bracket.stl")

# 3. 手画 + 平移
parts = [
    cuboid(100, 60, 5),                          # 底板
    translate(cuboid(5, 5, 50, name="pillar"), 5, 5, 5),  # 立柱
]
export_stl(parts, "/tmp/assembly.stl")
```

## 输出格式

| 格式 | 大小 (assembly 4 件) | 用途 |
|---|---|---|
| STL (二进制) | 2.4KB | 3D 打印 / 切片 |
| OBJ (文本) | 4.3KB | Web 3D (three.js / Babylon.js) |
| STEP (文本) | 2.0KB | CAD 交换 (FreeCAD / Fusion 360 导入) |

STEP 是**简化 B-rep 占位** (ISO 10303-21 框架 + MANIFOLD_SOLID_BREP),FreeCAD/Fusion 360 导入后需要在 GUI 里"重画" / "Apply Mesh"。完整 B-rep 要 OpenCascade (1GB+),本 skill 选 0 依赖路线。

## 跟 ljg-ppt-design 整合

`integrations.deck_with_freecad_geometry(preset, talk_type, name, shapes, content)`:
- shapes → STL → LO → PNG (LO 不支持 STL→png,所以退到 .stl 路径)
- PNG/STL 路径塞进 PPT 的 `content_image` 页

## 已知限制

- 不做布尔运算 (需要 OCC)
- 不做 NURBS 曲面 (跟 FreeCAD GUI 比)
- 不做装配约束 (只是空间位置)
- 三角面密度固定 (cylinder 24 段, sphere 16 段) — 想要更精细自己改 exporter

---

_ljg-freecad · 0 依赖 3D 几何生成器_
_2026-06-18 · 慧慧 从 HKUDS/CLI-Anything freecad 套件简化移植_
