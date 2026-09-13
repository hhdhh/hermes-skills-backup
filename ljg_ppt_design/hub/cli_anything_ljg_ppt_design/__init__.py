"""cli-anything-ljg-ppt-design — HKUDS hub entry 包装层。

把 HKUDS cli-anything-* 标准接口桥接到 ljg-ppt-design skill。

用法:
  # 装本包
  pip install -e ~/.claude/skills/ljg-ppt-design/hub

  # 之后任意位置都能用
  cli-anything-ljg-ppt-design list-presets
  cli-anything-ljg-ppt-design list-talk-types
  cli-anything-ljg-ppt-design render -p academic -t school -i content.json -o out.pptx

为什么需要这个包:
  - HKUDS hub 期望包名 cli-anything-*,命名空间 cli_anything.*
  - 我们的 ljg-ppt-design 是 ljg_ppt_design 命名空间
  - 这个包 = 一层薄包装,让 hub 找到
"""

from __future__ import annotations

# 关键:确保 ljg_ppt_design 在 sys.path
# 路径层级: .../hub/cli_anything_ljg_ppt_design/__init__.py
# 所以 .parent.parent.parent = ~/.claude/skills/ (ljg_ppt_design symlink 在这)
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SKILLS_ROOT = _HERE.parent.parent.parent  # ~/.claude/skills/
for _p in (str(_SKILLS_ROOT), str(_HERE.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# Re-export 一切
from ljg_ppt_design import (  # noqa: E402
    PRESETS,
    LAYOUTS,
    TALK_PRESETS,
    CONTENT_SCHEMA,
    DesignPreset,
    LayoutTemplate,
    SlideSpec,
    SlideElement,
    DeckSpec,
    get_preset,
    list_presets,
    get_layout,
    list_layouts,
    get_talk_preset,
    list_talk_types,
    rgb_to_hex,
    hex_to_rgb,
    render_deck,
    REVIEW_DIMENSIONS,
    validate_slide,
    review_deck,
    contrast_ratio,
    __version__,
)
from ljg_ppt_design.compat import deck_to_lo_project, lo_project_to_deck  # noqa: E402
from ljg_ppt_design.data.backends import (  # noqa: E402
    is_libreoffice_available,
    is_cli_anything_libreoffice_available,
    render_with_best_backend,
)

__version__ = f"hub-0.1.0 / ljg-{__version__}"

__all__ = [
    # 数据
    "PRESETS", "LAYOUTS", "TALK_PRESETS", "CONTENT_SCHEMA",
    # 类型
    "DesignPreset", "LayoutTemplate", "SlideSpec", "SlideElement", "DeckSpec",
    # 查询
    "get_preset", "list_presets",
    "get_layout", "list_layouts",
    "get_talk_preset", "list_talk_types",
    # 颜色
    "rgb_to_hex", "hex_to_rgb",
    # 渲染
    "render_deck", "render_with_best_backend",
    # 兼容
    "deck_to_lo_project", "lo_project_to_deck",
    # 审查
    "REVIEW_DIMENSIONS", "validate_slide", "review_deck", "contrast_ratio",
    # 状态
    "is_libreoffice_available", "is_cli_anything_libreoffice_available",
]
