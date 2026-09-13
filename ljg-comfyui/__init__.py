"""ljg-comfyui — ComfyUI workflow JSON 生成器 (0 依赖)。

来源: HKUDS/CLI-Anything (comfyui 套件) 简化版。
不依赖 ComfyUI 服务,不调 REST API,只产 API Format JSON 供 ComfyUI 拖入执行。

预设:
  - txt2img: 文字 → 图 (7 节点)
  - img2img: 图 + 文字 → 图 (8 节点)
  - upscale: 图 → 高清图 (4 节点)
  - txt2img_with_lora: LoRA stack (10+ 节点)
  - txt2img_with_controlnet: ControlNet 引导 (9 节点)
  - img2img_with_ipadapter: 风格迁移 (10 节点)
  - 5 风格: realistic / anime / oil_painting / cyberpunk / watercolor

用法:
  from ljg_comfyui import txt2img_with_style, txt2img_with_lora
  wf = txt2img_with_style("a cat in space", style="cyberpunk", seed=42)
  wf.write("/tmp/cat.json")
  # → 拖进 ComfyUI UI 跑 / 用 cli-anything-comfyui 跑
"""

from __future__ import annotations

from .workflows import (
    Workflow,
    txt2img,
    img2img,
    upscale,
    txt2img_with_style,
    txt2img_with_lora,
    txt2img_with_controlnet,
    img2img_with_ipadapter,
    STYLE_PRESETS,
    list_styles,
)

__version__ = "0.1.0"
__all__ = [
    "Workflow",
    "txt2img", "img2img", "upscale", "txt2img_with_style",
    "txt2img_with_lora", "txt2img_with_controlnet", "img2img_with_ipadapter",
    "STYLE_PRESETS", "list_styles",
]
