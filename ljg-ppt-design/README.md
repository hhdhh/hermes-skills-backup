# ljg-ppt-design

PPT 设计系统 + 可选 .pptx 渲染器。lifestyle for AI agents to create polished .pptx files with design system intelligence.

> 来源: 移植自 [`yb2460/harness-anything`](https://github.com/yb2460/harness-anything) 的 `cli_anything/wps/styles/` 三个模块 + 平台中立 refactor + 跨 4 agent 平台兼容 + HKUDS 生态兼容 ([PR #359](https://github.com/HKUDS/CLI-Anything/pull/359))。

## 能力

- **4 preset 配色** — academic / consultant / business / tech (round5 加 industrial / minimal 共 6 个)
- **12 layouts** — cover / toc / overview / timeline / grid_cards / quadrant / stats / three_col / pipeline / data_table / content_image / closing
- **7 talk types** — conference / business / defense / school / product_launch / tutorial / demo
- **5 维质量审查** — visual (70) / pedagogy (75) / proofreading (80) / parity (85) / substance (90)
- **2 后端** — `python-pptx` (默认) / LibreOffice (可选,真跑)
- **121 tests 全过 (4.02s)**

## 快速使用

```python
from ljg_ppt_design import render_deck, review_deck, get_preset

content = {
    "cover": {"title": "My Talk", "subtitle": "2026"},
    "toc_items": [{"num": "01", "title": "A", "desc": "a"}],
    "overview_cards": [{"label": "x", "value": "1"}],
    "timeline": [{"date": "2020", "event": "x"}],
    "three_col": {"title": "x", "items": [{"col_title": "a", "col_subtitle": "b", "col_content": "c"}]},
    "grid_items": [{"name": "a", "period": "b", "desc": "c"}],
    "quadrants": [{"subtitle": "a", "content": "b"}],
    "stats": {"title": "x", "items": [{"num": "1", "label": "a"}], "summary": "s"},
    "closing": {"summary_title": "x", "summary_text": "y", "motto": "z"},
}

deck = render_deck("academic", "school", content, name="My Talk")
review = review_deck(deck, get_preset("academic"))
print(review["summary"])
# 整体 100分 (9页, 0 警告, 通过)
```

## 出 .pptx / .pdf / .png

```python
# 默认 python-pptx
from ljg_ppt_design.data.pptx_renderer import render_to_pptx
render_to_pptx(deck, "/tmp/out.pptx")

# 智能选 backend (LO → pdf/png)
from ljg_ppt_design.data.backends import render_with_best_backend
render_with_best_backend(deck, "/tmp/out.pdf", output_format="pdf")
```

## CLI

```bash
python3 -m ljg_ppt_design.cli list-presets
python3 -m ljg_ppt_design.cli list-talk-types
python3 -m ljg_ppt_design.cli render \
    --preset academic --talk-type school \
    --input content.json --output out.pptx --review
```

## 跨 skill 整合

跟 ljg-drawio / ljg-freecad / ljg-inkscape / ljg-comfyui / ljg-zotero 整合:
- `integrations.deck_with_drawio_diagram(...)` — 架构图嵌 content_image
- `integrations.deck_with_freecad_geometry(...)` — 3D 嵌 content_image
- `integrations.deck_with_inkscape_svg(...)` — SVG 嵌 content_image
- `integrations.deck_with_comfyui_workflow(...)` — workflow 嵌 content_image

## 跨 agent 兼容

- **Claude Code** — `SKILL.md` 在 `~/.claude/skills/ljg-ppt-design/`
- **Codex / Hermes** — `cross-agent/codex/` / `cross-agent/hermes/`
- **Pi** — `cross-agent/pi/index.ts` (TypeScript wrapper)
- **Claude Plugin Marketplace** — `cross-agent/claude-plugin/marketplace.json`

## HKUDS 生态

- **PR #359**: https://github.com/HKUDS/CLI-Anything/pull/359
- **compat.py**: DeckSpec ↔ HKUDS `cli_anything.libreoffice` project dict 双向
- **hub/**: 装 `cli-anything-ljg-ppt-design` CLI (装在 `~/.claude/skills/ljg-ppt-design/hub/`)

## 安装 / 依赖

```bash
# 0 依赖 (默认)
pip install python-pptx click

# 可选: LibreOffice 后端
brew install --cask libreoffice   # macOS
# Linux: apt install libreoffice
```

## 测试

```bash
cd ~/.claude/skills
pytest -v
# 121 passed in 4.02s
```

## 文档

- [SKILL.md](SKILL.md) — agent 决策树 / 触发条件
- `references/presets.md` — 4 套预设完整字段
- `references/layouts.md` — 12 布局元素详表
- `references/talk-types.md` — 4 演讲类型字段要求
- `references/quality-rubric.md` — 5 维审查算法
- `cross-agent/README.md` — 4 平台安装说明

## License

MIT (来自 yb2460/harness-anything)
