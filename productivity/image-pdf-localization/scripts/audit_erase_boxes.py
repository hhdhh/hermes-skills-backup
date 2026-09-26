#!/usr/bin/env python3
"""Audit erase boxes for an image-PDF localization job.

Usage:
  python3 audit_erase_boxes.py page.png boxes.json [--margin N]

boxes.json: [{"name": "f_L1b", "x0": 100, "y0": 1290, "x1": 700, "y1": 1545, "mode": "dark"}, ...]
modes: bright | dark | darkblue  ("fill" boxes are skipped)

--margin 0 (default): does each box fully cover its own ink?
--margin 30: is there ink ESCAPING the box? Judge each MISS: escaped text =
grow the box; escaped decoration (bullet/marker beside the text) = keep the box.
"""
import argparse
import json

import numpy as np
from PIL import Image
from scipy import ndimage


def ink_mask(crop, mode):
    mean = crop.mean(axis=2)
    blue = (crop[:, :, 2] > crop[:, :, 0] + 25) & (crop[:, :, 2] > 90)
    if mode == "bright":
        return mean > 135
    if mode == "dark":
        return mean < 150
    return (mean < 150) | blue


def ink_bbox(img, xa, ya, xb, yb, mode):
    crop = img[ya:yb, xa:xb]
    m = ink_mask(crop, mode)
    lab, _ = ndimage.label(m)
    bx0 = by0 = 10**9
    bx1 = by1 = -1
    for sl in ndimage.find_objects(lab):
        s = int(m[sl].sum())
        if s < 8:
            continue
        h = sl[0].stop - sl[0].start
        w = sl[1].stop - sl[1].start
        if s < 15 and h < 5 and w < 5:
            continue
        bx0 = min(bx0, sl[1].start + xa)
        bx1 = max(bx1, sl[1].stop + xa)
        by0 = min(by0, sl[0].start + ya)
        by1 = max(by1, sl[0].stop + ya)
    if bx1 < 0:
        return None
    return (bx0, by0, bx1, by1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("boxes")
    ap.add_argument("--margin", type=int, default=0)
    args = ap.parse_args()

    img = np.array(Image.open(args.image).convert("RGB")).astype(int)
    H, W = img.shape[:2]
    boxes = json.load(open(args.boxes))
    for b in boxes:
        name, x0, y0, x1, y1, mode = b["name"], b["x0"], b["y0"], b["x1"], b["y1"], b["mode"]
        if mode == "fill":
            print(f"FILL {name} (not audited)")
            continue
        m = args.margin
        xa, ya = max(0, x0 - m), max(0, y0 - m)
        xb, yb = min(W, x1 + m), min(H, y1 + m)
        bb = ink_bbox(img, xa, ya, xb, yb, mode)
        if bb is None:
            print(f"??   {name}: no ink found near box - wrong mode or already clean")
            continue
        covered = bb[0] >= x0 - 2 and bb[1] >= y0 - 2 and bb[2] <= x1 + 2 and bb[3] <= y1 + 2
        flag = "OK  " if covered else "MISS"
        extra = "" if covered else f"  need x0<={bb[0]-2} y0<={bb[1]-2} x1>={bb[2]+2} y1>={bb[3]+2}"
        print(f"{flag} {name}: box=({x0},{y0},{x1},{y1}) ink={bb}{extra}")


if __name__ == "__main__":
    main()
