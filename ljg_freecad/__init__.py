"""ljg-freecad — 3D 几何生成器 (0 依赖)。

来源: HKUDS/CLI-Anything (freecad 套件) 简化版。
不依赖 OpenCascade (那要 1GB+),纯 Python 输出 STL/OBJ/简化 STEP。

5 种基本几何: cuboid / cylinder / sphere / cone / torus
4 个预设: bracket_L / box_with_hole / assembly_example / bracket_L_centered

用法:
  from ljg_freecad import cuboid, cylinder, translate, export_stl
  parts = [
      cuboid(100, 50, 5),                                    # 底板
      translate(cuboid(5, 5, 50, name='pillar'), 5, 5, 5),  # 立柱
  ]
  export_stl(parts, '/tmp/assembly.stl')  # → 3D 打印 / FreeCAD
"""

from __future__ import annotations

from .geometry import (
    Shape, cuboid, cylinder, sphere, cone, torus,
    translate, rotate, list_shape_types,
    bracket_L, bracket_L_centered, box_with_hole, assembly_example,
)
from .exporter import (
    export_stl, export_obj, export_step, shape_bounding_box,
)

__version__ = "0.1.0"
__all__ = [
    "Shape", "cuboid", "cylinder", "sphere", "cone", "torus",
    "translate", "rotate", "list_shape_types",
    "bracket_L", "bracket_L_centered", "box_with_hole", "assembly_example",
    "export_stl", "export_obj", "export_step", "shape_bounding_box",
]
