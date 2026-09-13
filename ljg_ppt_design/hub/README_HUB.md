# cli-anything-ljg-ppt-design

> HKUDS [CLI-Anything](https://github.com/HKUDS/CLI-Anything) hub entry for **ljg-ppt-design** — a lighter, platform-neutral PPT design system.

## What it adds

The base `ljg-ppt-design` skill (at `~/.claude/skills/ljg-ppt-design/`) is a Claude Code SKILL.md + Python package. This hub entry wraps it as a HKUDS-compatible `cli-anything-*` package so that:

1. It can be installed via `pip install cli-anything-ljg-ppt-design`
2. It can be registered in HKUDS [cli-hub](https://github.com/HKUDS/CLI-Anything) `registry.json`
3. The `cli-anything-ljg-ppt-design` command works alongside the other 18 apps

## Install

```bash
# 1. Make sure ljg-ppt-design skill is in your Python path
#    (default location: ~/.claude/skills/ljg-ppt-design/ — already in sys.path on most systems)

# 2. Install this hub wrapper
pip install -e ~/.claude/skills/ljg-ppt-design/hub

# 3. (Optional) For LibreOffice backend
pip install "cli-anything-ljg-ppt-design[libreoffice]"
brew install --cask libreoffice  # macOS, 1GB
```

## Usage

```bash
# List presets / layouts / talk types
cli-anything-ljg-ppt-design list-presets
cli-anything-ljg-ppt-design list-talk-types
cli-anything-ljg-ppt-design list-layouts

# Render a deck from JSON content
cli-anything-ljg-ppt-design render \
    --preset academic --talk-type school \
    --input content.json --output out.pptx --review
```

## What's included

| Layer | Component | Origin |
|---|---|---|
| Design system | 4 presets × 12 layouts × 4 talk types | yb2460/harness-anything (WPS section) |
| Quality review | 5-dim slide-excellence rubric | yb2460/harness-anything |
| Platform refactor | Semantic colors → renderable | ljg-ppt-design (this fork) |
| Backends | python-pptx (default), LibreOffice (optional) | this fork |
| Compat layer | DeckSpec ↔ HKUDS project dict | this fork |

## Differences from `cli-anything-libreoffice`

| | cli-anything-libreoffice | cli-anything-ljg-ppt-design |
|---|---|---|
| Source of design | None (just tool control) | yb2460's 4-preset system |
| Quality review | None | 5-dim slide-excellence |
| Talk types | None | 4 (conference/business/defense/school) |
| Default backend | LibreOffice UNO | python-pptx (lighter) |
| Requires LibreOffice | Yes | No (optional) |
| Cross-platform | Yes (with LO installed) | Yes (python-pptx works on all 3) |

## License

MIT (inherited from yb2460/harness-anything design system).
