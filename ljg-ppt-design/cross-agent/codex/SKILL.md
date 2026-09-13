---
name: ljg-ppt-design
version: 0.1.0
description: Use when the user wants Codex to create, design, or render a PPT/PPTX file. Provides 4 design presets (academic/consultant/business/tech), 12 layouts, 4 talk types (conference/business/defense/school), and 5-dim quality review.
---

# ljg-ppt-design for Codex

Use this skill when the user wants Codex to act like an expert PPT designer with a design system.

## When to use

- "做一份 PPT" / "prepare a presentation" / "create slides for X"
- User mentions a specific style (academic, business, technical, consulting)
- User wants a particular structure (defense, conference, school recruitment, business pitch)

## Quick start

```python
import sys
sys.path.insert(0, "~/.claude/skills")  # or wherever ljg-ppt-design is installed
from ljg_ppt_design import render_deck, review_deck, get_preset
from ljg_ppt_design.data.backends import render_with_best_backend

# 1. Build content
content = {
    "cover": {"title": "...", "subtitle": "..."},
    "toc_items": [...],
    "overview_cards": [...],
    "timeline": [...],
    "three_col": {...},
    "grid_items": [...],
    "quadrants": [...],
    "stats": {"title": "...", "items": [...], "summary": "..."},
    "closing": {"summary_title": "...", "summary_text": "...", "motto": "..."},
}

# 2. Render
deck = render_deck(preset="academic", talk_type="school", content=content, name="...")

# 3. Quality check
review = review_deck(deck, get_preset("academic"))
if not review["pass"]:
    print("WARN:", review["warnings"][:3])

# 4. Output
out, backend = render_with_best_backend(deck, "/tmp/output.pptx")
print(f"Output: {out} via {backend}")
```

## When NOT to use

- LibreOffice full feature control → use `cli-anything-libreoffice`
- Online PPT to Feishu/Lark → use `lark-slides` skill (this skill's JSON is compatible)

## Resource map

| Path | Purpose |
|---|---|
| `~/.claude/skills/ljg-ppt-design/SKILL.md` | Main agent-facing doc |
| `~/.claude/skills/ljg-ppt-design/__init__.py` | Public API: render_deck, review_deck, get_preset |
| `~/.claude/skills/ljg-ppt-design/data/backends.py` | Auto-select python-pptx / LibreOffice backend |
| `~/.claude/skills/ljg-ppt-design/compat.py` | Cross-compat with HKUDS cli-anything-libreoffice project dict |
