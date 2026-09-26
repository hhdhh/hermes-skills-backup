---
name: image-pdf-localization
description: Use when an image-PDF needs translation with layout kept.
version: 1.0.0
---

# Image-PDF Localization（图片型 PDF 整版翻译）

> 完整描述：Use when a flattened/image-based PDF (no text layer) must be translated into another language with layout, images and branding kept.

Workflow for 「把这个 PDF 翻译成 X 语言，排版不变」 when the PDF is a full-page image (marketing one-pagers, flyers, brochures).

## 0. Classify the PDF first
`page.get_text("dict")` — 0 non-empty text spans + exactly one full-page image per page = image-based → this skill. Text-layer PDFs are a different, much easier job.
Extract the embedded image at native resolution with `pymupdf.Pixmap(doc, xref)`; never rasterize the page at lower dpi — clean inpainting needs the original ~300dpi pixels.

## 1. Audit the environment before promising anything
One shell pass: `pymupdf`, `cv2`, `numpy`, `scipy.ndimage`, `PIL`; `tesseract --list-langs`; `fc-list :lang=<target>`. Korean needs NotoSansCJK-*.ttc — the **KR face is ttc index 1** (0=JP). OCR runs in the SOURCE language only (chi_sim suffices for a Chinese source — you write the target translation yourself); a target-language OCR pack is never needed.

## 2. Locate text with three cross-checked sources
1. `tesseract ... tsv` in the source language → line boxes (coordinates only).
2. Pixel detection: scipy connected components on brightness (`mean>135` for bright-on-dark), darkness (`mean<150`), blue (`b>r+25 & b>90`) masks → precise boxes + colors (median of the ink pixels, not point samples).
3. `vision_analyze` for accurate full transcription + layout description. Full 2480×3508 pages often time out — crop to regions and retry.

## 3. The erase table is the single source of truth
Keep `(name, x0, y0, x1, y1, mode)` lists inside the render script; every fix is a one-line patch + rerun.
- mode: `bright` / `dark` / `darkblue` (dark|blue) / `fill:<BAR color>`.
- Erase text only. Language-independent ink stays: blue table VALUES, icons, QR codes, logos.
- **Compute the ink mask strictly inside the box.** A padded working window (±24px) lets the mask swallow neighbouring decorations sitting 20–30px away (list bullets, bar markers) — they get inpainted away and then must be redrawn by hand.
- `fill` only on truly flat colour; photo/gradient bars bleed past box edges → use the bright-mask inpaint there too.
- Inpaint recipe: `cv2.INPAINT_NS` radius 7, then write a GaussianBlur(σ6) back only into the dilated mask — kills the streaky ghosting inpaint leaves on gradient/dark backgrounds.

## 4. Redraw with measured, not guessed, typography
PIL `ImageFont.truetype("<NotoSansCJK-Weight>.ttc", size, index=1)`; match the measured weight/size/color/alignment; per-character tracking via a `textlength` loop. Redraw every decoration the erase destroyed (12×12 square bullets, blue bar markers, vertical tag matrices). **Check pixel shape before drawing**: vision models misreport squares as dots and glyph fragments as bullets.

## 5. Verify before delivering
1. Box audit vs detected ink (`scripts/audit_erase_boxes.py`): run `--margin 0` (coverage) and `--margin 30` (escaped ink — manually keep boxes whose "escape" is a neighbour decoration you intend to preserve).
2. OCR the new page with a CJK model — hits are HINTS ONLY; chi_sim hallucinates hanzi on hangul constantly. Confirm each hit with a zoomed crop or an ASCII pixel-art dump before moving a box.
3. `vision_analyze` crop-by-crop QA (header / each column / footer), expecting timeouts → shrink the crop and retry.
4. Render the saved PDF back to PNG; confirm page count and size.

## 6. Reassemble + deliver
`page.clean_contents()` then `page.insert_image(page.rect, filename=...)`; `doc.save(out, garbage=4, deflate=True)`. Never touch the mediabox (keep 595×842pt A4). Name the output after the source convention with the target-language marker, into the user's download dir (e.g. 中文简体版915.pdf → 韩文版919.pdf in ~/下载).

## Pitfalls
- Write helper/audit code to files (write_file) instead of nested bash heredocs — heredoc quoting eats backslashes and newlines in regex; parse the render script's config lists with `ast.literal_eval`.
- All boxes/positions live in the script's config lists, so a fix is one `patch` + rerun (~10s). Never freehand coordinates in shell one-liners.
