"""几何体 → STEP / STL / OBJ 导出器 (0 依赖,纯 Python)。

STEP = ISO 10303-21 (文本格式,标准 CAD 交换格式)
STL  = 三角面片 (二进制,3D 打印标准)
OBJ  = Wavefront (文本,Web 3D / 通用)

不做布尔运算 (需要 OpenCascade)。本 skill 输出"组合"作为多个 Shape 列表,
导入到 FreeCAD/Fusion 360 后用 GUI 做布尔。
"""

from __future__ import annotations

import math
import struct
from pathlib import Path
from typing import List

from .geometry import Shape, SHAPE_FACTORIES


# ── 三角化:把形状拆成三角面 ─────────────────────────────
def _triangulate_cuboid(s: Shape) -> list:
    """Cuboid 拆 12 三角 (6 面 × 2 三角)。"""
    w = s.params["width"] / 2
    h = s.params["height"] / 2
    d = s.params["depth"] / 2
    # 8 个顶点
    v = [
        (-w, -h, -d), (w, -h, -d), (w, h, -d), (-w, h, -d),  # 后
        (-w, -h,  d), (w, -h,  d), (w, h,  d), (-w, h,  d),  # 前
    ]
    # 6 面 × 2 三角 = 12 三角
    # 顶点索引: 后=0,1,2,3  前=4,5,6,7
    faces = [
        (0, 1, 2), (0, 2, 3),    # 后
        (4, 6, 5), (4, 7, 6),    # 前
        (0, 4, 5), (0, 5, 1),    # 下
        (3, 2, 6), (3, 6, 7),    # 上
        (0, 3, 7), (0, 7, 4),    # 左
        (1, 5, 6), (1, 6, 2),    # 右
    ]
    tris = []
    for face in faces:
        tris.append(tuple(v[i] for i in face))
    return tris


def _triangulate_cylinder(s: Shape, segments: int = 24) -> list:
    """Cylinder 拆三角 (顶 + 底 + 侧面)。"""
    r = s.params["radius"]
    h = s.params["height"] / 2
    # 顶/底 圆心
    top_center = (0, 0, h)
    bot_center = (0, 0, -h)
    # 顶/底 顶点
    top_verts = [(r * math.cos(2 * math.pi * i / segments),
                  r * math.sin(2 * math.pi * i / segments), h)
                 for i in range(segments)]
    bot_verts = [(r * math.cos(2 * math.pi * i / segments),
                  r * math.sin(2 * math.pi * i / segments), -h)
                 for i in range(segments)]

    tris = []
    # 顶面 (法线 +Z,fan)
    for i in range(segments):
        tris.append((top_center, top_verts[i], top_verts[(i + 1) % segments]))
    # 底面 (法线 -Z,fan)
    for i in range(segments):
        tris.append((bot_center, bot_verts[(i + 1) % segments], bot_verts[i]))
    # 侧面 (quad → 2 三角)
    for i in range(segments):
        j = (i + 1) % segments
        tris.append((bot_verts[i], bot_verts[j], top_verts[j]))
        tris.append((bot_verts[i], top_verts[j], top_verts[i]))
    return tris


def _triangulate_sphere(s: Shape, segments: int = 16) -> list:
    """球拆三角 (UV 球)。"""
    r = s.params["radius"]
    tris = []
    for i in range(segments):
        theta1 = math.pi * i / segments
        theta2 = math.pi * (i + 1) / segments
        for j in range(segments * 2):
            phi1 = 2 * math.pi * j / (segments * 2)
            phi2 = 2 * math.pi * (j + 1) / (segments * 2)
            # 4 个角点
            v00 = (r * math.sin(theta1) * math.cos(phi1),
                   r * math.sin(theta1) * math.sin(phi1),
                   r * math.cos(theta1))
            v01 = (r * math.sin(theta1) * math.cos(phi2),
                   r * math.sin(theta1) * math.sin(phi2),
                   r * math.cos(theta1))
            v10 = (r * math.sin(theta2) * math.cos(phi1),
                   r * math.sin(theta2) * math.sin(phi1),
                   r * math.cos(theta2))
            v11 = (r * math.sin(theta2) * math.cos(phi2),
                   r * math.sin(theta2) * math.sin(phi2),
                   r * math.cos(theta2))
            tris.append((v00, v10, v11))
            tris.append((v00, v11, v01))
    return tris


def _triangulate_cone(s: Shape, segments: int = 24) -> list:
    """Cone/frustum 拆三角。"""
    rb = s.params["radius_base"]
    h = s.params["height"] / 2
    rt = s.params.get("radius_top", 0.0)
    # 顶/底 圆心
    top_center = (0, 0, h)
    bot_center = (0, 0, -h)
    top_verts = [(rt * math.cos(2 * math.pi * i / segments),
                  rt * math.sin(2 * math.pi * i / segments), h)
                 for i in range(segments)]
    bot_verts = [(rb * math.cos(2 * math.pi * i / segments),
                  rb * math.sin(2 * math.pi * i / segments), -h)
                 for i in range(segments)]

    tris = []
    for i in range(segments):
        tris.append((top_center, top_verts[i], top_verts[(i + 1) % segments]))
        tris.append((bot_center, bot_verts[(i + 1) % segments], bot_verts[i]))
    for i in range(segments):
        j = (i + 1) % segments
        tris.append((bot_verts[i], bot_verts[j], top_verts[j]))
        tris.append((bot_verts[i], top_verts[j], top_verts[i]))
    return tris


def _triangulate_torus(s: Shape, segments: int = 24, tube_segments: int = 12) -> list:
    """Torus 拆三角。"""
    R = s.params["major_radius"]
    r = s.params["minor_radius"]
    tris = []
    for i in range(segments):
        u1 = 2 * math.pi * i / segments
        u2 = 2 * math.pi * (i + 1) / segments
        for j in range(tube_segments):
            v1 = 2 * math.pi * j / tube_segments
            v2 = 2 * math.pi * (j + 1) / tube_segments
            p00 = ((R + r * math.cos(v1)) * math.cos(u1),
                   (R + r * math.cos(v1)) * math.sin(u1),
                   r * math.sin(v1))
            p01 = ((R + r * math.cos(v2)) * math.cos(u1),
                   (R + r * math.cos(v2)) * math.sin(u1),
                   r * math.sin(v2))
            p10 = ((R + r * math.cos(v1)) * math.cos(u2),
                   (R + r * math.cos(v1)) * math.sin(u2),
                   r * math.sin(v1))
            p11 = ((R + r * math.cos(v2)) * math.cos(u2),
                   (R + r * math.cos(v2)) * math.sin(u2),
                   r * math.sin(v2))
            tris.append((p00, p10, p11))
            tris.append((p00, p11, p01))
    return tris


def _triangulate(shape: Shape) -> list:
    dispatch = {
        "cuboid": _triangulate_cuboid,
        "cylinder": _triangulate_cylinder,
        "sphere": _triangulate_sphere,
        "cone": _triangulate_cone,
        "torus": _triangulate_torus,
    }
    fn = dispatch.get(shape.shape_type)
    if not fn:
        raise ValueError(f"未知 shape_type: {shape.shape_type}")
    tris = fn(shape)
    # 应用 transform: 平移 + 旋转
    if shape.translate == (0, 0, 0) and shape.rotate == (0, 0, 0):
        return tris
    tx, ty, tz = shape.translate
    rx, ry, rz = shape.rotate
    transformed = []
    for tri in tris:
        new_tri = []
        for v in tri:
            x, y, z = v
            # 旋转 (绕 X / Y / Z 轴,顺序 Z → Y → X)
            if rz != 0:
                c, s = math.cos(rz), math.sin(rz)
                x, y = c * x - s * y, s * x + c * y
            if ry != 0:
                c, s = math.cos(ry), math.sin(ry)
                x, z = c * x + s * z, -s * x + c * z
            if rx != 0:
                c, s = math.cos(rx), math.sin(rx)
                y, z = c * y - s * z, s * y + c * z
            new_tri.append((x + tx, y + ty, z + tz))
        transformed.append(tuple(new_tri))
    return transformed


# ── 三角面 → world space ─────────────────────────────────
def _all_triangles(shapes: List[Shape]) -> list:
    out = []
    for s in shapes:
        out.extend(_triangulate(s))
    return out


# ── STL 导出 (二进制) ─────────────────────────────────────
def export_stl(shapes: List[Shape], path: str) -> str:
    """导出二进制 STL (3D 打印标准)。"""
    triangles = _all_triangles(shapes)
    # STL header: 80 字节 (任意内容)
    # uint32: 三角数
    # 每个三角: 12 float (3 normal + 9 vertices) + 2 byte attr
    parent = Path(path).parent
    if parent:
        parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"\0" * 80)  # header
        f.write(struct.pack("<I", len(triangles)))
        for tri in triangles:
            # normal = (0, 0, 1) (简化,真实法线需要算)
            f.write(struct.pack("<3f", 0.0, 0.0, 1.0))
            for v in tri:
                f.write(struct.pack("<3f", v[0], v[1], v[2]))
            f.write(struct.pack("<H", 0))  # attribute byte count
    return path


# ── OBJ 导出 (文本) ──────────────────────────────────────
def export_obj(shapes: List[Shape], path: str) -> str:
    """导出 Wavefront OBJ (Web 3D / 通用)。"""
    triangles = _all_triangles(shapes)
    parent = Path(path).parent
    if parent:
        parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# ljg-freecad export\n")
        f.write(f"# {len(shapes)} shapes, {len(triangles)} triangles\n\n")
        # 1-based 顶点索引累加
        vert_count = 0
        for s in shapes:
            f.write(f"o {s.params.get('name', s.shape_type)}\n")
            for tri in _triangulate(s):
                for v in tri:
                    f.write(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")
            # 三角面
            tri_count = len(_triangulate(s))
            for i in range(tri_count):
                a = vert_count + i * 3 + 1
                b = a + 1
                c = a + 2
                f.write(f"f {a} {b} {c}\n")
            vert_count += tri_count * 3
            f.write("\n")
    return path


# ── STEP 导出 (文本,简化版) ─────────────────────────────
def export_step(shapes: List[Shape], path: str) -> str:
    """导出 STEP (ISO 10303-21 文本格式,简化版)。

    限制:本格式只描述"线框几何 + 命名",不输出完整 B-rep。
    实际 CAD 软件 (FreeCAD/Fusion 360) 导入时会把这些标记识别为"占位",
    需要在 GUI 里手动重画 / 应用 mesh。

    对 OpenCascade 完整 B-rep 输出需要装 `pythonOCC-core` (1GB+),
    本 skill 选 0 依赖路线,只产 mesh + 命名信息。
    """
    parent = Path(path).parent
    if parent:
        parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("ISO-10303-21;\n")
        f.write("HEADER;\n")
        f.write("FILE_DESCRIPTION(('ljg-freecad export'),'2;1');\n")
        f.write(f"FILE_NAME('{Path(path).name}','2026-06-18',('ljg-freecad'),('ljg-freecad'),'ljg-freecad','ljg-freecad','');\n")
        f.write("FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));\n")
        f.write("ENDSEC;\n")
        f.write("\nDATA;\n")
        # 每个 shape 一个 MANIFOLD_SOLID_BREP 占位
        for i, s in enumerate(shapes, start=1):
            f.write(f"/* {s.params.get('name', s.shape_type)} ({s.shape_type}) */\n")
            f.write(f"#{i} = MANIFOLD_SOLID_BREP('{s.params.get('name', 'shape_' + str(i))}',#{i + 100});\n")
            f.write(f"#{i+100} = CLOSED_SHELL('',({',#'.join([''] + [str(i * 10 + j) for j in range(1, 7)])}));\n")
            # 简单面引用
            for j in range(1, 7):
                f.write(f"#{i*10+j} = FACE_SURFACE('',#{i*100+j},#{i*10+j+50});\n")
                f.write(f"#{i*10+j+50} = PLANE('','');\n")
        f.write("ENDSEC;\n")
        f.write("END-ISO-10303-21;\n")
    return path


# ── 形状转 mesh 边界 (stl-like) ─────────────────────────
def shape_bounding_box(shapes: List[Shape]) -> dict:
    """所有 shapes 的整体包围盒。"""
    if not shapes:
        return {"min": (0, 0, 0), "max": (0, 0, 0), "size": (0, 0, 0)}
    all_tris = _all_triangles(shapes)
    if not all_tris:
        return {"min": (0, 0, 0), "max": (0, 0, 0), "size": (0, 0, 0)}
    xs, ys, zs = [], [], []
    for tri in all_tris:
        for v in tri:
            xs.append(v[0]); ys.append(v[1]); zs.append(v[2])
    return {
        "min": (min(xs), min(ys), min(zs)),
        "max": (max(xs), max(ys), max(zs)),
        "size": (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)),
    }
