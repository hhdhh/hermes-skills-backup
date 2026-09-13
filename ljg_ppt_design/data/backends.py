"""后端抽象层 — pptx 默认 + LibreOffice 格式转换。

链: render_deck() → python-pptx → .pptx → [可选] LibreOffice → .pdf / .png / .odp
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from ..slide_spec import DeckSpec
from .pptx_renderer import render_to_pptx
from .libreoffice_backend import is_libreoffice_available, convert_pptx_via_libreoffice


def render_with_best_backend(
    deck: DeckSpec,
    output_path: str,
    output_format: str = "pptx",
) -> tuple[str, str]:
    """智能选 backend。

    流程:
      1. 总是先用 python-pptx 出 .pptx (tmpfile 或 output_path)
      2. 如果 output_format == 'pptx' → 直接返回
      3. 如果 output_format != 'pptx' 且 LO 可用 → 用 LO 转格式
      4. 否则报错:格式需要 LO

    Returns:
        (output_path, backend_name)
    """
    from .pptx_renderer import render_to_pptx as render_via_pptx

    # Step 1: 出 .pptx
    if output_format == "pptx":
        render_via_pptx(deck, output_path)
        return output_path, "python-pptx"

    # Step 2: 出别的格式 — 先出 .pptx 中间,再用 LO 转
    tmp_pptx = str(Path(output_path).with_suffix(".pptx"))
    render_via_pptx(deck, tmp_pptx)
    if not is_libreoffice_available():
        print(
            f"[ljg-ppt-design] 输出格式 {output_format!r} 需要 LibreOffice,降级到 pptx",
            file=sys.stderr,
        )
        # 把 tmp_pptx 移到 output_path
        if tmp_pptx != output_path:
            import shutil
            shutil.move(tmp_pptx, output_path)
        return output_path, "python-pptx"

    # Step 3: LO 转
    actual = convert_pptx_via_libreoffice(tmp_pptx, output_format, output_path)
    # 清掉 tmp
    if Path(tmp_pptx).exists() and Path(tmp_pptx).resolve() != Path(actual).resolve():
        Path(tmp_pptx).unlink()
    return actual, "libreoffice"


__all__ = [
    "is_libreoffice_available",
    "convert_pptx_via_libreoffice",
    "render_with_best_backend",
]
