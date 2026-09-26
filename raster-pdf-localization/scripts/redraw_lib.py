"""Erase + redraw + pixel-scan helpers for raster PDF localization.
Dependencies: numpy, PIL only. Load page PNGs as RGB numpy arrays."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

_fonts = {}


def font(path, size, index=1):
    k = (path, size, index)
    if k not in _fonts:
        _fonts[k] = ImageFont.truetype(path, size, index=index)
    return _fonts[k]


def erase(a, x0, y0, x1, y1, pad=6, strip=24):
    """In-place: fill rect with median of side strips so horizontal gradients survive.
    pad widens the rect; strip sets how far left/right the background is sampled."""
    H, W = a.shape[:2]
    x0 = max(0, x0 - pad); y0 = max(0, y0 - pad)
    x1 = min(W, x1 + pad); y1 = min(H, y1 + pad)
    strips = []
    if x0 - strip >= 0:
        strips.append(a[y0:y1, x0 - strip:x0].reshape(-1, 3))
    if x1 + strip <= W:
        strips.append(a[y0:y1, x1:x1 + strip].reshape(-1, 3))
    if strips:
        bg = np.median(np.vstack(strips), axis=0)
    else:
        bg = np.median(a[y0:y1, x0:x1].reshape(-1, 3), axis=0)
    a[y0:y1, x0:x1] = bg.astype(np.uint8)


def text(img, xy, s, size, color, path, index=1, anchor='lm'):
    ImageDraw.Draw(img).text(xy, s, font=font(path, size, index),
                             fill=color, anchor=anchor)


def rowscan(gray, x0, x1, y0, y1, thr=120, minh=8, minrow=3):
    """y-ranges of text lines inside column band [x0,x1). gray = RGB mean."""
    dark = gray[y0:y1, x0:x1] < thr
    rows = dark.sum(axis=1)
    out, s = [], None
    for i, n in enumerate(rows):
        if n > minrow and s is None:
            s = i
        elif n <= minrow and s is not None:
            if i - s >= minh:
                out.append((s + y0, i + y0))
            s = None
    return out


def colscan(gray, x0, x1, y0, y1, thr=120, minw=10):
    """x-ranges of glyph/element columns inside row band [y0,y1)."""
    dark = gray[y0:y1, x0:x1] < thr
    cols = dark.sum(axis=0)
    out, s = [], None
    for i, n in enumerate(cols):
        if n > 3 and s is None:
            s = i
        elif n <= 3 and s is not None:
            if i - s > minw:
                out.append((s + x0, i + x0))
            s = None
    return out


def zone_diff(orig, new, rect):
    """Sum of abs pixel diff in rect (x0,y0,x1,y1). 0 = untouched graphic
    (photo / QR / logo) — use to prove erasures never bled into artwork."""
    x0, y0, x1, y1 = rect
    return int(np.abs(orig[y0:y1, x0:x1].astype(int)
                      - new[y0:y1, x0:x1].astype(int)).sum())


def dark_extent(a, x0, x1, y0, y1, thr=120):
    """Min/max x of dark pixels in a band — QC check that redrawn text
    stays inside its zone limit."""
    g = a[y0:y1, x0:x1].mean(axis=2)
    cols = np.where((g < thr).sum(axis=0) > 0)[0]
    if not len(cols):
        return None
    return int(cols.min() + x0), int(cols.max() + x0)
