"""几何体定义 (0 依赖,跟 ljg-freecad 同 lattice)。"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple


# ── 类型别名 ─────────────────────────────────────────────
Vec3 = Tuple[float, float, float]   # (x, y, z)


# ── 几何体 ───────────────────────────────────────────────
@dataclass
class Shape:
    """3D 几何体 (cuboid/cylinder/sphere/cone/torus/mesh)。"""
    shape_type: str
    params: dict
    # 可选 transform
    translate: Vec3 = (0.0, 0.0, 0.0)
    rotate: Vec3 = (0.0, 0.0, 0.0)        # 弧度,绕 (x, y, z) 轴

    def transformed(self):
        """返回应用 transform 后的新 Shape。"""
        return Shape(self.shape_type, dict(self.params),
                     self.translate, self.rotate)


# ── 工厂方法 (dataclass 后置) ─────────────────────────────
def cuboid(width: float, height: float, depth: float, name: str = "box") -> Shape:
    """长方体 (mm)。"""
    return Shape("cuboid", {"width": width, "height": height, "depth": depth, "name": name})


def cylinder(radius: float, height: float, name: str = "cyl") -> Shape:
    """圆柱 (mm)。"""
    return Shape("cylinder", {"radius": radius, "height": height, "name": name})


def sphere(radius: float, name: str = "sphere") -> Shape:
    """球 (mm)。"""
    return Shape("sphere", {"radius": radius, "name": name})


def cone(radius_base: float, height: float, radius_top: float = 0.0, name: str = "cone") -> Shape:
    """圆锥/圆台 (mm)。radius_top=0 是尖锥,>0 是圆台。"""
    return Shape("cone", {"radius_base": radius_base, "height": height,
                          "radius_top": radius_top, "name": name})


def torus(major_radius: float, minor_radius: float, name: str = "torus") -> Shape:
    """环 (mm)。"""
    return Shape("torus", {"major_radius": major_radius, "minor_radius": minor_radius, "name": name})


def translate(shape: Shape, x: float, y: float, z: float) -> Shape:
    """平移。返回新 Shape (不修改原)。"""
    return Shape(shape.shape_type, dict(shape.params),
                 (x, y, z), shape.rotate)


def rotate(shape: Shape, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> Shape:
    """旋转 (弧度)。返回新 Shape。"""
    return Shape(shape.shape_type, dict(shape.params),
                 shape.translate, (x, y, z))


# ── 形状目录 (供 agent 决策) ─────────────────────────────
SHAPE_FACTORIES = {
    "cuboid": cuboid,
    "cylinder": cylinder,
    "sphere": sphere,
    "cone": cone,
    "torus": torus,
}


def list_shape_types() -> list[dict]:
    return [
        {"key": "cuboid", "name": "长方体", "params": "width, height, depth (mm)"},
        {"key": "cylinder", "name": "圆柱", "params": "radius, height (mm)"},
        {"key": "sphere", "name": "球", "params": "radius (mm)"},
        {"key": "cone", "name": "圆锥/圆台", "params": "radius_base, height, radius_top (mm)"},
        {"key": "torus", "name": "环", "params": "major_radius, minor_radius (mm)"},
    ]


# ── 预设模板 (机械常见件) ───────────────────────────────
def bracket_L(thickness: float = 5.0, length: float = 50.0, width: float = 50.0) -> list:
    """L 型支架。返回 [底板, 侧板] 两个 cuboid。"""
    base = cuboid(length, width, thickness, name="L_base")
    side = cuboid(thickness, width, length, name="L_side")
    # side 立起来 (Y 方向变 Z)
    side = translate(side, 0, 0, thickness)
    return [base, side]


def bracket_L_centered(length: float = 60, width: float = 40, thickness: float = 5,
                       arm_height: float = 50) -> list:
    """L 型支架 (中心对齐版,适合打印)。"""
    return bracket_L(thickness, length, width)


def box_with_hole(outer_w: float, outer_h: float, outer_d: float,
                  hole_radius: float, hole_depth: float = None) -> list:
    """带圆孔的盒子 (返回 [外盒, 圆柱减材料标记])。
    注意:这是简化表示,实际 STEP 导出需要布尔运算 OCC。
    """
    if hole_depth is None:
        hole_depth = outer_d
    box = cuboid(outer_w, outer_h, outer_d, name="box_with_hole")
    hole = cylinder(hole_radius, hole_depth, name="hole_cutter")
    return [box, hole]


def assembly_example() -> list:
    """3 件装配示例:底板 + 2 立柱 + 横梁。"""
    base = cuboid(100, 60, 5, name="base_plate")
    pillar_l = translate(cuboid(5, 5, 50, name="pillar_l"), 5, 5, 5)
    pillar_r = translate(cuboid(5, 5, 50, name="pillar_r"), 90, 5, 5)
    beam = translate(cuboid(90, 10, 5, name="beam"), 5, 50, 30)
    return [base, pillar_l, pillar_r, beam]
