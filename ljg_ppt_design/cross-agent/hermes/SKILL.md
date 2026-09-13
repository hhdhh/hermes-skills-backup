---
name: ljg-ppt-design
version: 0.1.0
description: PPT design system for Hermes Agent. 4 presets × 12 layouts × 4 talk types × 5-dim quality review. Lighter than cli-anything-libreoffice with built-in design intelligence.
---

# ljg-ppt-design for Hermes

PPT design system that turns "make a presentation" into structured design decisions.

## Quick start

```python
from ljg_ppt_design import render_deck, review_deck, get_preset, list_presets, list_talk_types
from ljg_ppt_design.data.backends import render_with_best_backend

# Show available options
print(list_presets())
print(list_talk_types())

# Render
deck = render_deck(preset="academic", talk_type="conference",
                   content={"cover": {...}, "toc_items": [...], ...},
                   name="My Talk")
review = review_deck(deck, get_preset("academic"))
out, backend = render_with_best_backend(deck, "/tmp/talk.pptx")
```

## When to use

- User wants any kind of PPT / presentation / slide deck
- User mentions a style (academic/business/consulting/tech)
- User wants a narrative structure (conference/defense/business/school)

## When NOT to use

- Full LibreOffice control → use `cli-anything-libreoffice`
- Just need an outline → call `list_talk_types()` and use the `slides` field directly
