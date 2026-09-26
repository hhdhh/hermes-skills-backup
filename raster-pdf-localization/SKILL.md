---
name: raster-pdf-localization
description: Use when a pure-image PDF (brochure/flyer, no text layer)...
---

# Raster PDF localization — erase source text, redraw translated text

> 完整描述：Use when a pure-image PDF (brochure/flyer, no text layer) needs another language with layout, photos, QR codes and logos kept intact.

For PDFs whose pages are exported images (design-tool exports, scans). Deliverable: a same-size PDF that looks identical except every string is in the target language.

## Procedure (in order)

1. **Diagnose & extract.** `pymupdf`: `page.get_text()` empty ⇒ raster pages. Render each page full-res (300 DPI) to `pageN_full.png`. Record the original page rect — the output PDF must reuse it exactly.
2. **Transcribe into a mapping doc.** tesseract OCR (source-language pack + eng) for anchors; a vision model over tight crops for exact copy. Store every string with its geometry (x, y, size, color) in a PLAN file. Translate there first and settle brand-name handling (transliterate vs. keep Latin) and slogan wording with the user up front — these are the expensive things to redraw.
3. **Map geometry by pixel scan, not eyeballing.** Row/column projections of dark pixels give line y-ranges and x-spans; font size = glyph height; vertical titles show as a narrow tall dark column. Bright-text-on-dark areas need an inverted threshold. Sample per-region colors (title color ≠ body color ≠ faint label).
4. **Erase + redraw in stages**, one script per zone chaining PNG→PNG (header → body blocks → tables → footer). Erase = fill rect with the median of ±24px side strips — preserves horizontal gradients; flat fill leaves visible patches. Draw with `PIL.ImageDraw.text(..., anchor=...)` through a per-(path,size) font cache.
5. **QC every stage twice: pixels first, vision second.**
   - Pixel: re-scan the drawn region — max dark-x vs the zone's layout limit (translated text runs longer; re-wrap or shrink before it crosses into photos).
   - Vision: downscale the crop to ~1200px-wide JPEG and ask "list problems: source-language residue, overlap, misalignment". Treat vision warnings as hypotheses — verify each with a pixel scan before acting.
6. **Diff final vs original before assembly.** Photo zones, QR codes, logos must diff to 0. Any graphic that changed (erase rects can clip neighboring icons even when the rect looks safe) → copy that exact region back from the original.
7. **Assemble the PDF.** `pymupdf`: `new_page` with the ORIGINAL rect, `insert_image(page.rect, ...)`. Feed JPEG (quality ~92) versions of the pages — visually identical, ~⅓ the size of PNG-fed output. Render the saved PDF back to images for the final visual pass.

## Pitfalls
- Target-language text is usually longer than the Chinese source — check wrap width by pixel scan per line, not font metrics alone.
- Noto Sans CJK `.ttc` files are collections: pass `index=1` for the KR face and render one hangul string first to confirm the face before mass-drawing.
- Vision models misread rendered Korean/Japanese (garbled transliterations of your own output) and fabricate positions when asked "where is X" with confident arithmetic. Ask only "list problems", then arbitrate with pixels.
- Faint decorative labels (spec tables) may be invisible to OCR and vision — extreme contrast boost (`(g - med) * 25`) reveals them; decide fidelity vs. readability and tell the user which you chose.

## Scripts
- `scripts/redraw_lib.py` — erase (side-strip median), cached-font text draw, row/col projection scanners, and zone-diff check used throughout steps 3–6.
