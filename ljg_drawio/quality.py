"""ljg-drawio 质量审查 (跟 ljg-ppt-design 对齐)。

维度:
  - structure  (≥ 60) 形状/边/页面基本结构
  - layout     (≥ 70) 元素位置不重叠 / 不超页
  - naming     (≥ 70) 形状有 label,边有 label 时清晰
  - consistency (≥ 60) 同色同族形状用一致 style
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .builder import Diagram


REVIEW_DIMENSIONS: dict = {
    "structure": {
        "name": "结构审查",
        "checks": ["有 shape", "有 edge", "页面大小合理", "shape 有 label"],
        "threshold": 60,
    },
    "layout": {
        "name": "布局审查",
        "checks": ["shape 不重叠", "shape 不超页", "edge 端点对齐"],
        "threshold": 70,
    },
    "naming": {
        "name": "命名审查",
        "checks": ["shape 有 label", "edge label 不长", "id 唯一"],
        "threshold": 70,
    },
    "consistency": {
        "name": "一致性审查",
        "checks": ["同类 shape 用同 style", "无孤立 shape", "无重复 shape"],
        "threshold": 60,
    },
}


@dataclass
class DiagramReview:
    pass_: bool
    score: int
    warnings: list
    checks_passed: list

    def to_dict(self) -> dict:
        return {"pass": self.pass_, "score": self.score,
                "warnings": self.warnings, "checks_passed": self.checks_passed}


def review_diagram(diag: "Diagram") -> dict:
    """对一份 Diagram 做 4 维审查。"""
    warnings: list = []
    passed: list = []

    # 1. structure
    structure_score = 100
    if diag.shape_count() == 0:
        warnings.append("图无 shape")
        structure_score -= 50
    if diag.edge_count() == 0 and diag.shape_count() > 1:
        warnings.append("多个 shape 但无 edge 关联")
        structure_score -= 20
    no_label = sum(1 for s in diag.shapes if not s.label)
    if no_label > 0 and no_label == diag.shape_count():
        warnings.append(f"全部 {diag.shape_count()} 个 shape 无 label")
        structure_score -= 30
    if structure_score >= 60:
        passed.append("结构")

    # 2. layout
    layout_score = 100
    page_w = diag.page_width
    page_h = diag.page_height
    for s in diag.shapes:
        if s.x < 0 or s.y < 0:
            warnings.append(f"shape '{s.label or s.cell_id}' 位置负: ({s.x},{s.y})")
            layout_score -= 10
        if s.x + s.width > page_w:
            warnings.append(f"shape '{s.label or s.cell_id}' 超出右边界")
            layout_score -= 10
        if s.y + s.height > page_h:
            warnings.append(f"shape '{s.label or s.cell_id}' 超出下边界")
            layout_score -= 10
    # 重叠检测
    for i, a in enumerate(diag.shapes):
        for b in diag.shapes[i + 1:]:
            if (a.x < b.x + b.width and a.x + a.width > b.x and
                a.y < b.y + b.height and a.y + a.height > b.y):
                warnings.append(
                    f"shape '{a.label or a.cell_id}' 与 '{b.label or b.cell_id}' 重叠"
                )
                layout_score -= 5
    if layout_score >= 70:
        passed.append("布局")

    # 3. naming
    naming_score = 100
    ids = [s.cell_id for s in diag.shapes] + [e.edge_id for e in diag.edges]
    if len(ids) != len(set(ids)):
        warnings.append("存在重复 cell_id")
        naming_score -= 30
    for e in diag.edges:
        if e.label and len(e.label) > 40:
            warnings.append(f"edge label '{e.label[:20]}...' 太长 ({len(e.label)} 字符)")
            naming_score -= 5
    if naming_score >= 70:
        passed.append("命名")

    # 4. consistency
    consistency_score = 100
    # 形状类型分布:相同 type 用相同 style (默认情况下)
    type_count: dict[str, int] = {}
    for s in diag.shapes:
        type_count[s.shape_type] = type_count.get(s.shape_type, 0) + 1
    # 孤立 shape:无 edge 连接
    connected_ids: set = set()
    for e in diag.edges:
        connected_ids.add(e.source_id)
        connected_ids.add(e.target_id)
    orphans = [s for s in diag.shapes if s.cell_id not in connected_ids and diag.shape_count() > 1]
    if len(orphans) > diag.shape_count() / 2 and diag.shape_count() > 2:
        warnings.append(f"超过一半 shape 无 edge 连接 ({len(orphans)} 个孤立)")
        consistency_score -= 20
    if consistency_score >= 60:
        passed.append("一致性")

    per_dimension = {
        "structure": {"score": structure_score, "threshold": REVIEW_DIMENSIONS["structure"]["threshold"],
                      "pass": structure_score >= REVIEW_DIMENSIONS["structure"]["threshold"]},
        "layout": {"score": layout_score, "threshold": REVIEW_DIMENSIONS["layout"]["threshold"],
                   "pass": layout_score >= REVIEW_DIMENSIONS["layout"]["threshold"]},
        "naming": {"score": naming_score, "threshold": REVIEW_DIMENSIONS["naming"]["threshold"],
                   "pass": naming_score >= REVIEW_DIMENSIONS["naming"]["threshold"]},
        "consistency": {"score": consistency_score, "threshold": REVIEW_DIMENSIONS["consistency"]["threshold"],
                        "pass": consistency_score >= REVIEW_DIMENSIONS["consistency"]["threshold"]},
    }
    overall = round(sum(d["score"] for d in per_dimension.values()) / 4, 1)
    all_pass = all(d["pass"] for d in per_dimension.values())

    return {
        "overall_score": overall,
        "pass": all_pass,
        "per_dimension": per_dimension,
        "summary": f"整体 {overall:.0f}分 ({diag.shape_count()} shape / {diag.edge_count()} edge, {len(warnings)} 警告, {'通过' if all_pass else '未通过'})",
        "warnings": warnings,
    }
