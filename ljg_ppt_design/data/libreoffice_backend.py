"""LibreOffice 后端 — 简化为"格式转换器"。

不依赖 HKUDS cli-anything-libreoffice (那个要 Python 3.10+)。
直接调系统 soffice 把 python-pptx 出的 .pptx 转 .pdf / .png / .odp / .docx。

用法:
  from ljg_ppt_design import render_deck
  from ljg_ppt_design.data.libreoffice_backend import convert_pptx_via_libreoffice
  deck = render_deck("academic", "school", content)
  convert_pptx_via_libreoffice("/tmp/x.pptx", "pdf", "/tmp/x.pdf")

需要:
  - 系统装了 LibreOffice (brew install --cask libreoffice / apt install libreoffice)
  - soffice / libreoffice 在 PATH 里
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


def is_libreoffice_available() -> bool:
    """检查系统是否装了 LibreOffice。"""
    return shutil.which("libreoffice") is not None or shutil.which("soffice") is not None


def _get_soffice() -> str:
    """获取 soffice / libreoffice 绝对路径。"""
    p = shutil.which("soffice") or shutil.which("libreoffice")
    if not p:
        raise RuntimeError(
            "LibreOffice 没装。装: \n"
            "  macOS: brew install --cask libreoffice\n"
            "  Linux: apt install libreoffice\n"
            "  Windows: winget install TheDocumentFoundation.LibreOffice"
        )
    return p


def convert_pptx_via_libreoffice(
    input_path: str,
    output_format: str = "pdf",
    output_path: Optional[str] = None,
    timeout: int = 120,
) -> str:
    """用 LibreOffice headless 把 .pptx 转其他格式。

    Args:
        input_path: 输入文件路径 (.pptx)
        output_format: 输出格式 (pdf / png / odp / docx / ...)
        output_path: 输出文件路径 (默认: input_path 同目录 + .{fmt})
        timeout: 超时秒数

    Returns:
        实际输出文件路径
    """
    soffice = _get_soffice()
    in_p = Path(input_path).resolve()
    if not in_p.exists():
        raise FileNotFoundError(f"Input not found: {in_p}")

    if output_path is None:
        out_dir = in_p.parent
        output_path = str(out_dir / f"{in_p.stem}.{output_format}")
    out_dir = Path(output_path).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # Headless flags 跟原版 HKUDS 一致 (防 macOS SIGABRT 等)
    cmd = [
        soffice,
        "--headless",
        "--nologo",
        "--nodefault",
        "--norestore",
        "--nolockcheck",
        "--nofirststartwizard",
        "--convert-to", output_format,
        "--outdir", str(out_dir),
        str(in_p),
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            f"soffice conversion timed out after {timeout}s. "
            f"Try: killall soffice; rm -rf ~/.config/libreoffice"
        ) from e

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        # macOS SIGABRT 回退路径
        if "Trace/BPT trap" in stderr or "Abort trap" in stderr:
            return _macos_fallback(soffice, in_p, output_format, out_dir, timeout)
        raise RuntimeError(
            f"soffice failed (rc={result.returncode}): {stderr}\n"
            f"  cmd: {' '.join(cmd)}"
        )

    # soffice 写出的文件名跟输入 stem 一样,加新后缀
    actual = out_dir / f"{in_p.stem}.{output_format}"
    if not actual.exists():
        # 兜底:soffice 可能写到 out_dir 但用了别的名字
        candidates = list(out_dir.glob(f"{in_p.stem}.*"))
        if candidates:
            actual = candidates[0]
        else:
            raise RuntimeError(
                f"soffice did not produce output. "
                f"Expected {actual}, found: {list(out_dir.iterdir())}"
            )

    # 如果用户指定了 output_path 且不是默认的,move
    if str(actual.resolve()) != str(Path(output_path).resolve()):
        shutil.move(str(actual), output_path)
        return output_path
    return str(actual)


def _macos_fallback(soffice, in_p, output_format, out_dir, timeout):
    """macOS headless 失败时,用 open -W -n 走 LaunchServices 路径。"""
    soffice_path = Path(soffice).resolve()
    app_bundle = None
    for ancestor in soffice_path.parents:
        if ancestor.suffix == ".app":
            app_bundle = str(ancestor)
            break
    if not app_bundle:
        raise RuntimeError(
            "soffice headless failed on macOS and no .app bundle found. "
            "Try: open -W -n -a LibreOffice --args --headless --convert-to ..."
        )
    cmd = [
        "open", "-W", "-n", "-a", app_bundle, "--args",
        "--headless", "--nologo", "--nodefault", "--norestore", "--nolockcheck",
        "--convert-to", output_format, "--outdir", str(out_dir), str(in_p),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    actual = out_dir / f"{in_p.stem}.{output_format}"
    if result.returncode == 0 and actual.exists():
        return str(actual)
    raise RuntimeError(
        f"macOS fallback also failed (rc={result.returncode}): "
        f"{(result.stderr or '').strip()}"
    )


# ── 抽象层:跟 python-pptx 协作 ─────────────────────────
def render_with_libreoffice(
    pptx_input: str,
    output_format: str = "pdf",
    output_path: Optional[str] = None,
) -> tuple[str, str]:
    """LO 格式转换 wrapper。返回 (output_path, format)。"""
    out = convert_pptx_via_libreoffice(pptx_input, output_format, output_path)
    return out, output_format
