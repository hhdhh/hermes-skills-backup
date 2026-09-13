# Cross-agent compatibility for ljg-ppt-design

Same Python skill, exposed to 4 agent platforms.

## Platforms

| Platform | Entry | Install |
|---|---|---|
| **Claude Code** | `SKILL.md` (top-level) | Already in `~/.claude/skills/ljg-ppt-design/` |
| **Codex** | `cross-agent/codex/` | Copy to Codex skill dir |
| **Hermes** | `cross-agent/hermes/` | Copy to Hermes skill dir |
| **Pi** | `cross-agent/pi/` | `npm install` + register |
| **Claude Plugin Marketplace** | `cross-agent/claude-plugin/marketplace.json` | For `/plugin install` in Claude Code |

## Quick install for each

### Claude Code (default location)
Already installed at `~/.claude/skills/ljg-ppt-design/`.

### Codex
```bash
cp -r cross-agent/codex ~/.codex/skills/ljg-ppt-design
```

### Hermes
```bash
cp -r cross-agent/hermes ~/.hermes/skills/ljg-ppt-design
```

### Pi Coding Agent
```bash
cp -r cross-agent/pi ~/.pi/extensions/ljg-ppt-design
cd ~/.pi/extensions/ljg-ppt-design && npm install
```

### Claude Code Marketplace
```bash
mkdir -p ~/.claude/plugins/marketplaces
cp -r cross-agent/claude-plugin ~/.claude/plugins/marketplaces/ljg-ppt-design
# Then in Claude Code: /plugin install ljg-ppt-design
```

## Why this matters

HKUDS/CLI-Anything supports the same 4 platforms (.claude-plugin / .pi-extension / codex-skill / hermes-skill). This makes ljg-ppt-design a peer — installable on any of them.
