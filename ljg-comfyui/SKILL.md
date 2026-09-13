---
name: ljg-comfyui
version: 0.1.0
description: "ComfyUI workflow JSON 生成器 —— 0 依赖,出 API Format JSON 供 ComfyUI 拖入执行。3 预设 (txt2img/img2img/upscale) + 5 风格 (realistic/anime/oil_painting/cyberpunk/watercolor)。当用户要做 AI 出图、写 ComfyUI workflow、调 Stable Diffusion 风格 prompt 时使用。"
metadata:
  requires:
    bins: ["python3"]
    python: ">=3.9"
  cliHelp: "python3 -c 'from ljg_comfyui import list_styles, txt2img_with_style; print(list_styles())'"
---

# ljg-comfyui

ComfyUI workflow JSON 生成器。lifestyle for AI agents to design image-generation pipelines without ComfyUI server running.

## 何时调我

| 用户说 | 调什么 |
|---|---|
| "做一张图" / "AI 出图" / "stable diffusion" | `txt2img_with_style` |
| "图改图" / "改这张图" | `img2img` |
| "高清化" / "放大" / "upscale" | `upscale` |
| "赛博朋克风格" / "写实风" / "油画" | 5 风格 preset |
| "写个 ComfyUI workflow" | `txt2img` (基础 8 节点) |

## 何时不调我

- 用户要"完整 ComfyUI 控制" → 用 `cli-anything-comfyui` (HKUDS 原版,需服务在跑)
- 用户要 Midjourney / DALL-E 风格 API → 不接,ComfyUI 是 SD 系
- 主人没装 ComfyUI → 我只能产 JSON,不能跑

## 3 预设 workflow

| name | 节点数 | 用途 |
|---|---|---|
| `txt2img` | 8 | 文字 → 图 (主用) |
| `img2img` | 8 | 图 + 文字 → 图 (改图) |
| `upscale` | 4 | 图 → 高清图 (放大) |

## 5 风格预设

| key | 加在 prompt 后 | 用途 |
|---|---|---|
| `realistic` | `, realistic, photographic, 8k, ...` | 写实摄影 |
| `anime` | `, anime style, vibrant colors, ...` | 二次元 |
| `oil_painting` | `, oil painting, brush strokes, ...` | 油画 |
| `cyberpunk` | `, cyberpunk, neon lights, ...` | 赛博朋克 |
| `watercolor` | `, watercolor painting, soft colors, ...` | 水彩 |

## 快速使用

```python
from ljg_comfyui import txt2img_with_style, img2img, upscale, list_styles

# 1. 文字出图
wf = txt2img_with_style("a cat in space", style="cyberpunk", seed=42, width=1024, height=1024)
wf.write("/tmp/cat.json")
# → 拖进 ComfyUI 跑

# 2. 改图
wf2 = img2img("/tmp/source.png", prompt="enhance, sharpen, high detail", denoise=0.4)
wf2.write("/tmp/enhanced.json")

# 3. 高清化
wf3 = upscale("/tmp/photo.png", upscale_model="RealESRGAN_x4plus.pth")
wf3.write("/tmp/4x.json")

# 4. 列风格
print(list_styles())  # 5 个 dict
```

## 输出格式

`Workflow.write(path)` 写 ComfyUI "API Format" JSON,可以直接:
- 拖进 ComfyUI UI 跑 (Load → 改 prompt/seed → Queue)
- 用 `cli-anything-comfyui queue` 命令批量跑
- 用任何 ComfyUI client 加载

JSON 结构:
```json
{
  "<node_id>": {
    "class_type": "KSampler",
    "inputs": {"model": [...], "positive": [...], "seed": 42, ...}
  },
  ...
}
```

## 跟 ljg-ppt-design 整合

`ljg-ppt-design` 的 `content_image` 页可以嵌入 ljg-comfyui 出的图:
1. ComfyUI 跑 workflow → 存 PNG
2. 把 PNG 路径作为 ljg-ppt-design 的 `image_label`
3. 渲染时 PNG 直接进 content_image 页 (需要 ljg-ppt-design 的 image_placeholder 升级)

## 已知限制

- 只支持 API Format JSON,不支持 ComfyUI UI Graph Format (老格式)
- 不调 ComfyUI 服务 (0 依赖,只产 JSON)
- 节点 ID 随机生成 (ComfyUI 加载时会重排)
- 部分高级节点 (ControlNet / IPAdapter / LoRA stack) 不在内置 preset 里 —— 需要时手动加

---

_ljg-comfyui · 0 依赖 ComfyUI workflow 生成器_
_2026-06-18 · 慧慧 从 HKUDS/CLI-Anything comfyui 套件简化移植_
