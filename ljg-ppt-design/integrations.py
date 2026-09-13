"""ljg-ppt-design 跨 skill 整合。

lattice of interop helpers for combining ljg-ppt-design with:
  - ljg-drawio: 出 .drawio 架构图 → 转 PNG → 嵌进 content_image 页
  - ljg-comfyui: 出 AI 图 workflow → 跑 (本地/服务) → 嵌进 content_image 页
  - LibreOffice: .pptx → .pdf / .png 全格式

用法:
  from ljg_ppt_design.integrations import (
      drawio_to_pptx_image, comfyui_workflow_to_prompt_spec,
      deck_with_drawio_diagram, deck_with_comfyui_image,
  )

  # 1. drawio 架构图嵌 PPT
  deck = deck_with_drawio_diagram(
      preset="academic", talk_type="business",
      name="System Architecture",
      diagram=diag,                     # ljg-drawio Diagram 对象
      content={...},                    # 其他 content
      image_position="content_image",  # 插哪一页
  )
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

from . import render_deck
from .data.backends import render_with_best_backend
from .slide_spec import DeckSpec, SlideSpec, SlideElement


# ── 1. drawio → PPT image ────────────────────────────────
def drawio_to_png(
    drawio_xml_path: str,
    output_png_path: Optional[str] = None,
    page_index: int = 0,
    timeout: int = 60,
) -> str:
    """用 LibreOffice 把 .drawio 转 .png。

    路径: .drawio → soffice --convert-to png → .png
    需要 LO 已装。

    失败时(没 LO 或转换失败) → 退到 .drawio 本身,返回原路径 + stderr。
    """
    in_p = Path(drawio_xml_path).resolve()
    if not in_p.exists():
        raise FileNotFoundError(f"drawio file not found: {in_p}")

    if output_png_path is None:
        output_png_path = str(in_p.with_suffix(".png"))

    # 优先用 LO
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        # 没 LO:让 caller 退到 .drawio 路径
        raise RuntimeError(
            "LibreOffice not installed. Cannot convert .drawio to .png. "
            "Install: brew install --cask libreoffice"
        )

    out_dir = Path(output_png_path).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        soffice, "--headless", "--nologo", "--nodefault", "--norestore",
        "--nolockcheck", "--nofirststartwizard",
        "--convert-to", "png",
        "--outdir", str(out_dir),
        str(in_p),
    ]
    result = __import__("subprocess").run(
        cmd, capture_output=True, text=True, timeout=timeout
    )
    # soffice 输出文件名: {in_p.stem}.png
    actual = out_dir / f"{in_p.stem}.png"
    if result.returncode == 0 and actual.exists():
        if str(actual.resolve()) != str(Path(output_png_path).resolve()):
            shutil.move(str(actual), output_png_path)
        return output_png_path

    # 失败 → 退到原 .drawio 路径(在 PPT 里当占位)
    print(f"[ljg-ppt-design] drawio → png 失败: rc={result.returncode}", file=sys.stderr)
    raise RuntimeError(
        f"soffice drawio → png 失败 (rc={result.returncode}): "
        f"{(result.stderr or '').strip()[:200]}"
    )


# ── 2. ljg-drawio Diagram 嵌进 PPT content_image 页 ──
def deck_with_drawio_diagram(
    preset: str,
    talk_type: str,
    name: str,
    diagram,                           # ljg_drawio.Diagram
    content: dict,
    image_label: Optional[str] = None,
    image_position: str = "content_image",
) -> DeckSpec:
    """把 drawio 架构图嵌进 ljg-ppt-design 的 content_image 页。

    流程:
      1. diagram.write("tmp.drawio")
      2. (如有 LO) drawio_to_png → tmp.png
      3. image_label = tmp.png (或 fallback tmp.drawio)
      4. content[image_position] = {title, content, image_label}
      5. render_deck(preset, talk_type, content)
    """
    # 1. 写 drawio
    with tempfile.TemporaryDirectory() as tmpdir:
        drawio_path = os.path.join(tmpdir, f"{name.replace(' ', '_')}.drawio")
        diagram.write(drawio_path)

        # 2. 尝试转 PNG
        png_label = None
        try:
            png_path = os.path.join(tmpdir, f"{name.replace(' ', '_')}.png")
            drawio_to_png(drawio_path, png_path)
            png_label = png_path
        except Exception as e:
            print(f"[ljg-ppt-design] {e}; falling back to .drawio path", file=sys.stderr)

        # 3. 注入 content
        label = image_label or png_label or drawio_path
        # 复制到永久位置供 PPT 引用
        permanent_dir = Path.home() / ".openclaw" / "workspace" / "exports" / "diagrams"
        permanent_dir.mkdir(parents=True, exist_ok=True)
        permanent_path = permanent_dir / Path(label).name
        shutil.copy(label, permanent_path)
        final_label = str(permanent_path)

    # 4. 注入 content[image_position]
    content = dict(content)  # 复制
    content[image_position] = {
        "title": content[image_position].get("title", "架构图") if isinstance(content.get(image_position), dict) else "架构图",
        "content": content[image_position].get("content", f"由 ljg-drawio 自动生成,共 {diagram.shape_count()} 个 shape / {diagram.edge_count()} 条边") if isinstance(content.get(image_position), dict) else f"由 ljg-drawio 自动生成,共 {diagram.shape_count()} 个 shape / {diagram.edge_count()} 条边",
        "image_label": final_label,
    }

    return render_deck(preset=preset, talk_type=talk_type, name=name, content=content)


# ── 4. ljg-comfyui workflow 嵌进 PPT ─────────────────────
def deck_with_comfyui_workflow(
    preset: str,
    talk_type: str,
    name: str,
    workflow_json_path: str,
    content: dict,
    image_position: str = "content_image",
    comfyui_server: str = "http://localhost:8188",
    auto_run: bool = False,
) -> DeckSpec:
    """把 ComfyUI workflow 嵌进 ljg-ppt-design 的 content_image 页。

    流程:
      1. 写 workflow JSON 到 ~/.openclaw/workspace/exports/workflows/
      2. (auto_run=True 时) 提交到 ComfyUI 服务
      3. image_label 指向 workflow 路径 + 提示"用 ComfyUI 跑"
    """
    wf_src = Path(workflow_json_path).resolve()
    if not wf_src.exists():
        raise FileNotFoundError(f"workflow not found: {wf_src}")

    # 1. 复制到永久位置
    perm_dir = Path.home() / ".openclaw" / "workspace" / "exports" / "workflows"
    perm_dir.mkdir(parents=True, exist_ok=True)
    perm_path = perm_dir / wf_src.name
    shutil.copy(wf_src, perm_path)

    # 2. (可选) 提交到 ComfyUI 服务
    run_result = None
    if auto_run:
        run_result = _submit_to_comfyui(perm_path, comfyui_server)

    # 3. 注入 content
    content = dict(content)
    label_text = f"ComfyUI workflow: {perm_path.name}"
    if run_result:
        label_text += f" (提交到 {comfyui_server}, prompt_id={run_result.get('prompt_id', '?')})"

    existing = content.get(image_position, {})
    if not isinstance(existing, dict):
        existing = {}
    content[image_position] = {
        "title": existing.get("title", "AI 生成图"),
        "content": existing.get("content", label_text),
        "image_label": str(perm_path),
    }

    return render_deck(preset=preset, talk_type=talk_type, name=name, content=content)


def _submit_to_comfyui(workflow_path: str, server: str) -> dict:
    """POST workflow JSON 到 ComfyUI /prompt 端点。"""
    try:
        import requests
    except ImportError:
        raise RuntimeError(
            "ljg-comfyui auto_run 需要 requests; 装: pip install requests"
        )
    import json as _json
    with open(workflow_path, "r", encoding="utf-8") as f:
        wf = _json.load(f)
    # 去掉 _meta (ComfyUI 不认)
    wf.pop("_meta", None)
    url = f"{server.rstrip('/')}/prompt"
    resp = requests.post(url, json={"prompt": wf}, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ── 5. ljg-freecad 几何 → PPT (via LO/STL 渲染) ─────────
def freecad_to_pptx_image(
    shapes,                          # ljg_freecad Shape list
    output_image_path: Optional[str] = None,
    stl_path: Optional[str] = None,
    timeout: int = 120,
) -> str:
    """freecad shapes → STL → LO 转 PNG → 给 ljg-ppt-design 当 content_image。

    流程:
      1. export_stl(shapes, tmp.stl)
      2. soffice --convert-to png tmp.stl
      3. 输出 PNG 路径
    """
    from ljg_freecad import export_stl
    import subprocess

    if stl_path is None:
        stl_path = (output_image_path or "/tmp/freecad.png").replace(".png", ".stl")
    export_stl(shapes, stl_path)

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        # 没 LO,直接返回 STL 路径 (PPT 引用 .stl 也能开,只是 PowerPoint 不一定支持)
        return stl_path

    if output_image_path is None:
        output_image_path = stl_path.replace(".stl", ".png")
    out_dir = Path(output_image_path).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        soffice, "--headless", "--nologo", "--nodefault", "--norestore",
        "--nolockcheck", "--nofirststartwizard",
        "--convert-to", "png",
        "--outdir", str(out_dir),
        str(stl_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    actual = out_dir / f"{Path(stl_path).stem}.png"
    # LO 即使 rc=0 也可能在 stderr 说 "source file could not be loaded"
    # 还要看 stdout 里的 "Error" 字样
    err_text = (result.stderr or "") + (result.stdout or "")
    has_error = (
        "Error" in err_text or "error" in err_text or
        "could not be loaded" in err_text
    )
    if result.returncode == 0 and actual.exists() and not has_error:
        if str(actual.resolve()) != str(Path(output_image_path).resolve()):
            shutil.move(str(actual), output_image_path)
        return output_image_path
    raise RuntimeError(
        f"freecad → png 失败 (rc={result.returncode}): {err_text.strip()[:200]}"
    )


def deck_with_freecad_geometry(
    preset: str,
    talk_type: str,
    name: str,
    shapes,
    content: dict,
    image_position: str = "content_image",
    image_label: Optional[str] = None,
) -> "DeckSpec":
    """把 ljg-freecad 几何体嵌进 ljg-ppt-design 的 content_image 页。

    流程:
      1. shapes → STL → LO → PNG
      2. PNG 路径塞进 content[image_position].image_label
    """
    from ljg_freecad import shape_bounding_box

    bbox = shape_bounding_box(shapes)
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. STL → PNG
        png_path = os.path.join(tmpdir, f"{name.replace(' ', '_')}.png")
        stl_path = os.path.join(tmpdir, f"{name.replace(' ', '_')}.stl")
        try:
            freecad_to_pptx_image(shapes, png_path, stl_path)
        except Exception as e:
            print(f"[ljg-ppt-design] freecad → png 失败: {e}; 退到 STL", file=sys.stderr)
            png_path = stl_path

        # 2. 复制到永久位置
        permanent_dir = Path.home() / ".openclaw" / "workspace" / "exports" / "freecad"
        permanent_dir.mkdir(parents=True, exist_ok=True)
        permanent_path = permanent_dir / Path(png_path).name
        shutil.copy(png_path, permanent_path)
        final_label = str(permanent_path)

    # 3. 注入 content
    content = dict(content)
    existing = content.get(image_position, {})
    if not isinstance(existing, dict):
        existing = {}
    size_str = f"{bbox['size'][0]:.0f}×{bbox['size'][1]:.0f}×{bbox['size'][2]:.0f} mm"
    content[image_position] = {
        "title": existing.get("title", f"3D 模型"),
        "content": existing.get("content", f"由 ljg-freecad 自动生成,共 {len(shapes)} 个几何体,尺寸 {size_str}"),
        "image_label": final_label,
    }

    return render_deck(preset=preset, talk_type=talk_type, name=name, content=content)


# ── 6. ljg-inkscape SVG → PPT (直接 embed) ─────────────
def deck_with_inkscape_svg(
    preset: str,
    talk_type: str,
    name: str,
    canvas,                          # ljg_inkscape.Canvas
    content: dict,
    image_position: str = "content_image",
    convert_to_png: bool = True,
    use_lo: bool = True,
) -> "DeckSpec":
    """把 ljg-inkscape SVG 嵌进 ljg-ppt-design 的 content_image 页。

    流程:
      1. canvas.write("tmp.svg")
      2. (如 convert_to_png) SVG → PNG via cairosvg / LO / resvg
      3. PNG 路径塞进 content[image_position].image_label
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        svg_path = os.path.join(tmpdir, f"{name.replace(' ', '_')}.svg")
        canvas.write(svg_path)

        final_label = svg_path
        if convert_to_png:
            png_path = os.path.join(tmpdir, f"{name.replace(' ', '_')}.png")
            try:
                # 优先 cairosvg (轻量,0 系统依赖)
                try:
                    import cairosvg
                    cairosvg.svg2png(url=svg_path, write_to=png_path)
                    final_label = png_path
                except ImportError:
                    pass
            except Exception:
                pass
            if final_label == svg_path and use_lo:
                # 退到 LO
                soffice = shutil.which("soffice") or shutil.which("libreoffice")
                if soffice:
                    import subprocess
                    cmd = [soffice, "--headless", "--nologo", "--nodefault",
                           "--norestore", "--nolockcheck", "--nofirststartwizard",
                           "--convert-to", "png", "--outdir", tmpdir, svg_path]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    actual = Path(png_path)
                    if result.returncode == 0 and actual.exists():
                        final_label = str(actual)

        # 复制到永久位置
        permanent_dir = Path.home() / ".openclaw" / "workspace" / "exports" / "inkscape"
        permanent_dir.mkdir(parents=True, exist_ok=True)
        permanent_path = permanent_dir / Path(final_label).name
        shutil.copy(final_label, permanent_path)
        final_label = str(permanent_path)

    content = dict(content)
    existing = content.get(image_position, {})
    if not isinstance(existing, dict):
        existing = {}
    content[image_position] = {
        "title": existing.get("title", "SVG 设计"),
        "content": existing.get("content", f"由 ljg-inkscape 自动生成,共 {len(canvas.elements)} 个元素"),
        "image_label": final_label,
    }

    return render_deck(preset=preset, talk_type=talk_type, name=name, content=content)
