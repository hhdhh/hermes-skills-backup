"""ComfyUI workflow JSON 生成器。

来源: HKUDS/CLI-Anything (comfyui 套件) — 简化版,只保留 JSON 生成,不做 REST client (那是另一层)。

生成的 workflow JSON 兼容 ComfyUI 的 "API Format":
- dict (node graph)
- 每个 node 有 class_type + inputs
- 可以直接 Save (API Format) 进 ComfyUI,改 prompt/seed 后批量跑

预设 workflow:
  - txt2img: 文字 → 图 (CheckpointLoaderSimple + CLIPTextEncode + KSampler + EmptyLatentImage + VAEDecode + SaveImage)
  - img2img: 图 + 文字 → 图 (加 LoadImage + VAEEncode)
  - upscale: 图 → 高清图 (加 UpscaleModelLoader + ImageUpscaleWithModel)

用法:
  from ljg_comfyui import txt2img, img2img, upscale
  wf = txt2img(prompt="a cat sitting on a chair", seed=42, width=1024, height=1024)
  wf.write("/tmp/cat.json")  # → 拖进 ComfyUI 跑
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


def _uid() -> str:
    """生成节点 ID (ComfyUI 用数字字符串)。"""
    return str(uuid.uuid4().int % 10**9)


@dataclass
class Workflow:
    """ComfyUI workflow JSON (API format)。"""

    name: str = "untitled"
    nodes: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            **self.nodes,
            "_meta": {"name": self.name, **self.metadata},
        } if self.metadata else self.nodes

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def write(self, path: str) -> str:
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())
        return path

    def node_count(self) -> int:
        return len([k for k in self.nodes if k != "_meta"])


# ── 预设 1: txt2img ─────────────────────────────────────
def txt2img(
    prompt: str = "a beautiful landscape, mountains, sunset, high quality",
    negative_prompt: str = "blurry, low quality, watermark, text",
    seed: int = 42,
    steps: int = 20,
    cfg: float = 7.0,
    sampler: str = "euler",
    scheduler: str = "normal",
    width: int = 1024,
    height: int = 1024,
    checkpoint: str = "v1-5-pruned-emaonly.ckpt",
    denoise: float = 1.0,
    batch_size: int = 1,
) -> Workflow:
    """生成 text-to-image workflow JSON。

    节点 (8 个):
      1. CheckpointLoaderSimple
      2. CLIPTextEncode (positive)
      3. CLIPTextEncode (negative)
      4. EmptyLatentImage
      5. KSampler
      6. VAEDecode
      7. SaveImage
      8. (可选) RepeatLatentBatch
    """
    ckpt_id = _uid()
    pos_id = _uid()
    neg_id = _uid()
    latent_id = _uid()
    sampler_id = _uid()
    vae_id = _uid()
    save_id = _uid()

    nodes: dict = {
        ckpt_id: {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        pos_id: {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": [ckpt_id, 1]},
        },
        neg_id: {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative_prompt, "clip": [ckpt_id, 1]},
        },
        latent_id: {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": width, "height": height, "batch_size": batch_size,
            },
        },
        sampler_id: {
            "class_type": "KSampler",
            "inputs": {
                "model": [ckpt_id, 0],
                "positive": [pos_id, 0],
                "negative": [neg_id, 0],
                "latent_image": [latent_id, 0],
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler,
                "scheduler": scheduler,
                "denoise": denoise,
            },
        },
        vae_id: {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": [sampler_id, 0],
                "vae": [ckpt_id, 2],
            },
        },
        save_id: {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "ljg_txt2img",
                "images": [vae_id, 0],
            },
        },
    }

    return Workflow(
        name=f"txt2img_{seed}",
        nodes=nodes,
        metadata={"prompt": prompt[:80], "size": f"{width}x{height}",
                  "steps": steps, "seed": seed, "type": "txt2img"},
    )


# ── 预设 2: img2img ─────────────────────────────────────
def img2img(
    image_path: str,
    prompt: str = "enhance this image, high quality, sharp",
    negative_prompt: str = "blurry, low quality",
    seed: int = 42,
    steps: int = 20,
    cfg: float = 7.0,
    denoise: float = 0.65,
    checkpoint: str = "v1-5-pruned-emaonly.ckpt",
) -> Workflow:
    """生成 image-to-image workflow JSON。

    节点 (8 个):
      1. CheckpointLoaderSimple
      2. CLIPTextEncode (positive)
      3. CLIPTextEncode (negative)
      4. LoadImage
      5. VAEEncode
      6. KSampler
      7. VAEDecode
      8. SaveImage
    """
    ckpt_id = _uid()
    pos_id = _uid()
    neg_id = _uid()
    load_id = _uid()
    encode_id = _uid()
    sampler_id = _uid()
    vae_id = _uid()
    save_id = _uid()

    nodes: dict = {
        ckpt_id: {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        pos_id: {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": [ckpt_id, 1]},
        },
        neg_id: {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative_prompt, "clip": [ckpt_id, 1]},
        },
        load_id: {
            "class_type": "LoadImage",
            "inputs": {"image": image_path},
        },
        encode_id: {
            "class_type": "VAEEncode",
            "inputs": {
                "pixels": [load_id, 0],
                "vae": [ckpt_id, 2],
            },
        },
        sampler_id: {
            "class_type": "KSampler",
            "inputs": {
                "model": [ckpt_id, 0],
                "positive": [pos_id, 0],
                "negative": [neg_id, 0],
                "latent_image": [encode_id, 0],
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": denoise,
            },
        },
        vae_id: {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": [sampler_id, 0],
                "vae": [ckpt_id, 2],
            },
        },
        save_id: {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "ljg_img2img",
                "images": [vae_id, 0],
            },
        },
    }

    return Workflow(
        name=f"img2img_{seed}",
        nodes=nodes,
        metadata={"prompt": prompt[:80], "denoise": denoise,
                  "image": os.path.basename(image_path), "type": "img2img"},
    )


# ── 预设 3: upscale ──────────────────────────────────────
def upscale(
    image_path: str,
    upscale_model: str = "RealESRGAN_x4plus.pth",
    seed: int = 42,
) -> Workflow:
    """生成 image upscale workflow JSON。

    节点 (4 个):
      1. UpscaleModelLoader
      2. LoadImage
      3. ImageUpscaleWithModel
      4. SaveImage
    """
    loader_id = _uid()
    load_id = _uid()
    up_id = _uid()
    save_id = _uid()

    nodes: dict = {
        loader_id: {
            "class_type": "UpscaleModelLoader",
            "inputs": {"model_name": upscale_model},
        },
        load_id: {
            "class_type": "LoadImage",
            "inputs": {"image": image_path},
        },
        up_id: {
            "class_type": "ImageUpscaleWithModel",
            "inputs": {
                "upscale_model": [loader_id, 0],
                "image": [load_id, 0],
            },
        },
        save_id: {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "ljg_upscale",
                "images": [up_id, 0],
            },
        },
    }

    return Workflow(
        name=f"upscale_{seed}",
        nodes=nodes,
        metadata={"upscale_model": upscale_model,
                  "image": os.path.basename(image_path), "type": "upscale"},
    )


# ── 预设 4: txt2img + LoRA stack ───────────────────────
def txt2img_with_lora(
    prompt: str = "a beautiful landscape",
    negative_prompt: str = "blurry, low quality",
    seed: int = 42,
    steps: int = 25,
    cfg: float = 7.0,
    width: int = 1024,
    height: int = 1024,
    checkpoint: str = "v1-5-pruned-emaonly.ckpt",
    loras: list = None,
) -> Workflow:
    """带 LoRA stack 的 txt2img。loras=[{name, strength_model, strength_clip}, ...]"""
    loras = loras or []
    ckpt_id = _uid()
    pos_id = _uid()
    neg_id = _uid()
    latent_id = _uid()
    nodes: dict = {
        ckpt_id: {"class_type": "CheckpointLoaderSimple",
                  "inputs": {"ckpt_name": checkpoint}},
        pos_id: {"class_type": "CLIPTextEncode",
                 "inputs": {"text": prompt, "clip": [ckpt_id, 1]}},
        neg_id: {"class_type": "CLIPTextEncode",
                 "inputs": {"text": negative_prompt, "clip": [ckpt_id, 1]}},
        latent_id: {"class_type": "EmptyLatentImage",
                    "inputs": {"width": width, "height": height, "batch_size": 1}},
    }
    # LoRA chain (model + clip 串联)
    prev_model = [ckpt_id, 0]
    prev_clip = [ckpt_id, 1]
    for i, lora in enumerate(loras):
        lora_id = _uid()
        nodes[lora_id] = {
            "class_type": "LoraLoader",
            "inputs": {
                "model_net": prev_model, "clip_net": prev_clip,
                "lora_name": lora.get("name", f"lora_{i}.safetensors"),
                "strength_model": lora.get("strength_model", lora.get("strength", 0.8)),
                "strength_clip": lora.get("strength_clip", lora.get("strength", 0.8)),
            },
        }
        prev_model = [lora_id, 0]
        prev_clip = [lora_id, 1]
    nodes[pos_id]["inputs"]["clip"] = prev_clip
    nodes[neg_id]["inputs"]["clip"] = prev_clip

    sampler_id = _uid()
    vae_id = _uid()
    save_id = _uid()
    nodes[sampler_id] = {
        "class_type": "KSampler",
        "inputs": {
            "model": prev_model, "positive": [pos_id, 0], "negative": [neg_id, 0],
            "latent_image": [latent_id, 0],
            "seed": seed, "steps": steps, "cfg": cfg,
            "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
        },
    }
    nodes[vae_id] = {"class_type": "VAEDecode",
                     "inputs": {"samples": [sampler_id, 0], "vae": [ckpt_id, 2]}}
    nodes[save_id] = {"class_type": "SaveImage",
                     "inputs": {"filename_prefix": "ljg_lora", "images": [vae_id, 0]}}

    return Workflow(
        name=f"txt2img_lora_{seed}", nodes=nodes,
        metadata={"prompt": prompt[:80], "loras": [l.get("name") for l in loras],
                  "type": "txt2img_lora", "lora_count": len(loras)},
    )


# ── 预设 5: txt2img + ControlNet ────────────────────────
def txt2img_with_controlnet(
    prompt: str = "a beautiful landscape",
    negative_prompt: str = "blurry",
    seed: int = 42,
    steps: int = 25,
    cfg: float = 7.0,
    width: int = 1024,
    height: int = 1024,
    checkpoint: str = "v1-5-pruned-emaonly.ckpt",
    controlnet_model: str = "control_v11p_sd15_canny",
    control_image: str = "control.png",
    control_strength: float = 1.0,
) -> Workflow:
    """带 ControlNet (canny/depth/openpose) 的 txt2img。"""
    ckpt_id = _uid()
    pos_id = _uid()
    neg_id = _uid()
    cn_loader_id = _uid()
    cn_image_id = _uid()
    cn_apply_id = _uid()
    latent_id = _uid()
    sampler_id = _uid()
    vae_id = _uid()
    save_id = _uid()

    nodes: dict = {
        ckpt_id: {"class_type": "CheckpointLoaderSimple",
                  "inputs": {"ckpt_name": checkpoint}},
        pos_id: {"class_type": "CLIPTextEncode",
                 "inputs": {"text": prompt, "clip": [ckpt_id, 1]}},
        neg_id: {"class_type": "CLIPTextEncode",
                 "inputs": {"text": negative_prompt, "clip": [ckpt_id, 1]}},
        cn_loader_id: {"class_type": "ControlNetLoader",
                       "inputs": {"control_net_name": controlnet_model}},
        cn_image_id: {"class_type": "LoadImage",
                      "inputs": {"image": control_image}},
        cn_apply_id: {"class_type": "ControlNetApply",
                      "inputs": {"conditioning": [pos_id, 0],
                                 "control_net": [cn_loader_id, 0],
                                 "image": [cn_image_id, 0],
                                 "strength": control_strength}},
        latent_id: {"class_type": "EmptyLatentImage",
                    "inputs": {"width": width, "height": height, "batch_size": 1}},
        sampler_id: {
            "class_type": "KSampler",
            "inputs": {
                "model": [ckpt_id, 0],
                "positive": [cn_apply_id, 0],
                "negative": [neg_id, 0],
                "latent_image": [latent_id, 0],
                "seed": seed, "steps": steps, "cfg": cfg,
                "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
            },
        },
        vae_id: {"class_type": "VAEDecode",
                 "inputs": {"samples": [sampler_id, 0], "vae": [ckpt_id, 2]}},
        save_id: {"class_type": "SaveImage",
                 "inputs": {"filename_prefix": "ljg_cn", "images": [vae_id, 0]}},
    }

    return Workflow(
        name=f"txt2img_cn_{seed}", nodes=nodes,
        metadata={"prompt": prompt[:80], "controlnet": controlnet_model,
                  "type": "txt2img_controlnet"},
    )


# ── 预设 6: img2img + IPAdapter (style transfer) ─────────
def img2img_with_ipadapter(
    image_path: str,
    style_image_path: str,
    prompt: str = "match style",
    negative_prompt: str = "blurry",
    seed: int = 42,
    steps: int = 25,
    cfg: float = 7.0,
    denoise: float = 0.7,
    ipadapter_strength: float = 0.8,
    checkpoint: str = "v1-5-pruned-emaonly.ckpt",
    ipadapter_model: str = "ip-adapter_sd15.safetensors",
) -> Workflow:
    """img2img + IPAdapter (style transfer / image prompt)。"""
    ckpt_id = _uid()
    pos_id = _uid()
    neg_id = _uid()
    content_id = _uid()
    style_id = _uid()
    ipa_loader_id = _uid()
    ipa_apply_id = _uid()
    encode_id = _uid()
    sampler_id = _uid()
    vae_id = _uid()
    save_id = _uid()

    nodes: dict = {
        ckpt_id: {"class_type": "CheckpointLoaderSimple",
                  "inputs": {"ckpt_name": checkpoint}},
        pos_id: {"class_type": "CLIPTextEncode",
                 "inputs": {"text": prompt, "clip": [ckpt_id, 1]}},
        neg_id: {"class_type": "CLIPTextEncode",
                 "inputs": {"text": negative_prompt, "clip": [ckpt_id, 1]}},
        content_id: {"class_type": "LoadImage", "inputs": {"image": image_path}},
        style_id: {"class_type": "LoadImage", "inputs": {"image": style_image_path}},
        ipa_loader_id: {"class_type": "IPAdapterLoader",
                        "inputs": {"ipadapter_name": ipadapter_model}},
        ipa_apply_id: {"class_type": "IPAdapterApply",
                       "inputs": {"ipadapter": [ipa_loader_id, 0],
                                  "model": [ckpt_id, 0],
                                  "image": [style_id, 0],
                                  "weight": ipadapter_strength,
                                  "noise": 0.1}},
        encode_id: {"class_type": "VAEEncode",
                    "inputs": {"pixels": [content_id, 0], "vae": [ckpt_id, 2]}},
        sampler_id: {
            "class_type": "KSampler",
            "inputs": {
                "model": [ckpt_id, 0],
                "positive": [pos_id, 0], "negative": [neg_id, 0],
                "latent_image": [encode_id, 0],
                "seed": seed, "steps": steps, "cfg": cfg,
                "sampler_name": "euler", "scheduler": "normal", "denoise": denoise,
            },
        },
        vae_id: {"class_type": "VAEDecode",
                 "inputs": {"samples": [sampler_id, 0], "vae": [ckpt_id, 2]}},
        save_id: {"class_type": "SaveImage",
                 "inputs": {"filename_prefix": "ljg_ipa", "images": [vae_id, 0]}},
    }

    return Workflow(
        name=f"img2img_ipa_{seed}", nodes=nodes,
        metadata={"prompt": prompt[:80], "ipadapter": ipadapter_model,
                  "type": "img2img_ipadapter"},
    )


# ── 风格预设 (常用 prompt 模板) ──────────────────────────
STYLE_PRESETS: dict[str, dict] = {
    "realistic": {
        "positive": ", realistic, photographic, 8k, high detail, sharp focus, natural lighting",
        "negative": ", cartoon, anime, painting, drawing, blurry, low quality",
        "sampler": "dpmpp_2m",
        "steps": 30,
        "cfg": 7.0,
    },
    "anime": {
        "positive": ", anime style, vibrant colors, clean lineart, masterpiece",
        "negative": ", realistic, photographic, 3d, blurry, lowres",
        "sampler": "euler_a",
        "steps": 25,
        "cfg": 7.5,
    },
    "oil_painting": {
        "positive": ", oil painting, brush strokes, impasto, classical art style",
        "negative": ", photograph, digital art, 3d, modern",
        "sampler": "euler",
        "steps": 30,
        "cfg": 7.0,
    },
    "cyberpunk": {
        "positive": ", cyberpunk, neon lights, futuristic city, night, blade runner style",
        "negative": ", daylight, rural, vintage, low quality",
        "sampler": "dpmpp_2m",
        "steps": 25,
        "cfg": 7.5,
    },
    "watercolor": {
        "positive": ", watercolor painting, soft colors, paper texture, artistic",
        "negative": ", photograph, digital, sharp, modern",
        "sampler": "euler",
        "steps": 25,
        "cfg": 7.0,
    },
}


def list_styles() -> list[dict]:
    return [{"key": k, **v} for k, v in STYLE_PRESETS.items()]


def txt2img_with_style(
    base_prompt: str,
    style: str = "realistic",
    **kwargs,
) -> Workflow:
    """txt2img + 风格预设。"""
    s = STYLE_PRESETS.get(style, STYLE_PRESETS["realistic"])
    full_prompt = base_prompt + s["positive"]
    full_negative = kwargs.pop("negative_prompt", "") + s["negative"]
    defaults = dict(s)
    defaults.pop("positive", None)
    defaults.pop("negative", None)
    defaults.update(kwargs)
    return txt2img(prompt=full_prompt, negative_prompt=full_negative, **defaults)
