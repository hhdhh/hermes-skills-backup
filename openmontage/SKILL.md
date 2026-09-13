---
name: openmontage
description: OpenMontage agentic video production — install + 12 pipelines (animated-explainer, cinematic, etc.) + Remotion/HyperFrames render. 装在 ~/.openclaw/workspace/projects/openmontage/。零 key demo 视频已渲过。Edge TTS/Lark publish/huihui-writes 集成完毕。
---

# OpenMontage Skill

> **What this is:** OpenMontage = agentic video production system. The agent reads pipeline manifests (YAML) + stage director skills (MD), then drives Python tools. Designed to work from any AI coding assistant (Claude Code, Codex, ohmo, Cursor, Copilot).

> **Status (2026-06-25):** Installed at `~/.openclaw/workspace/projects/openmontage/`. Pre-flight passed, 3 demo videos rendered. Two Remotion bugs patched. Edge TTS + Lark publish + huihui-writes 7-section wrapper + multi-search research + taste-skill style adapter all wired.

## When to use

Use this skill when the user wants to:
- Produce any video (explainer, animation, montage, doc, podcast clip, etc.)
- Render a Remotion / HyperFrames composition
- Use a free, no-API-key TTS (Microsoft Edge via edge-tts) for narration
- Publish a finished video to Lark/Feishu
- Drive a multi-stage video production pipeline (research → script → scenes → assets → render)

**Do NOT use** for static images, GIF-only outputs, or pure audio podcasts.

## Quick start

```bash
cd ~/.openclaw/workspace/projects/openmontage
source venv/bin/activate

# One-shot: topic → script → TTS → render → preview
python make_video.py "30秒讲讲 OpenMontage 怎么用" --auto-yes --preview

# Just render the 3 zero-API-key demos
python render_demo.py

# Publish a finished video to Lark
python publish_to_lark.py /path/to/video.mp4 --title "My video"

# Or drive the full animated-explainer pipeline
# (read AGENT_GUIDE.md → PROJECT_CONTEXT.md → pipeline_defs/animated-explainer.yaml)
```

## What's available (capabilities + providers)

| Capability | Configured | Providers |
|------------|------------|-----------|
| composition runtimes | 3/3 | ffmpeg, remotion, hyperframes |
| research | 1/1 | multi-search (16 engines via OpenClaw web_fetch) |
| style | 1/1 | taste-skill (curated mappings → OpenMontage playbooks) |
| tts | 2/6 | edge (zh-CN-XiaoxiaoNeural, free), piper (offline) |
| video_post | 9/9 | (full) |
| character_animation | 6/6 | (full) |
| audio_processing | 2/2 | (full) |
| screen_capture | 2/2 | (full) |
| subtitle | 2/2 | (full) |

## Customizations applied to this user's install

1. **Python 3.12 venv** at `openmontage/venv/`
2. **Edge TTS provider** added to `tools/audio/edge_tts.py` — auto-discovered
3. **`render_demo.py` patched** with `--browser-executable` to bypass macOS chrome unpack bug
4. **`@remotion/google-fonts` monkey-patched** at `.chrome-headless-shell/patch-google-fonts.js`
5. **chrome-headless-shell pre-extracted** at `.chrome-headless-shell/chrome-headless-shell-mac-arm64/`
6. **config.yaml** set to `provider: minimax / model: MiniMax-M3`
7. **Multi-search research tool** at `tools/research/multi_search_research.py` (two-phase: plan + compile)
8. **taste-skill adapter** at `tools/style/taste_skill_adapter.py` (22 style ID mappings)
9. **Lark publish script** at `publish_to_lark.py`
10. **End-to-end wrapper** at `make_video.py` (topic → script → TTS → render → preview)
11. **OpenFlow workflow** at `~/.openclaw/workspace/projects/openflow/examples/openmontage-make-video.yaml`

## What was customized for the user's network (China-restricted)

- github.com blocked → use `gh-proxy.com` mirror to clone
- fonts.googleapis.com blocked → patch @remotion/google-fonts to skip network
- baidu/google/duckduckgo direct HTTPS timeouts → use OpenClaw web_fetch instead

## Restoration scripts (re-run if npm/pip reinstalls)

```bash
cd ~/.openclaw/workspace/projects/openmontage

# Re-patch Google Fonts (1817 files, ~1s)
node .chrome-headless-shell/patch-google-fonts.js

# Clear webpack cache (forces re-bundle with patched fonts)
rm -rf remotion-composer/node_modules/.cache

# Re-extract chrome
cd .chrome-headless-shell
unzip -o remotion-composer/node_modules/.remotion/chrome-headless-shell/chrome-headless-shell-mac-arm64.zip \
  'chrome-headless-shell-mac-arm64/*'
```

## How to drive the full animated-explainer pipeline (agent guide)

1. **Read** `AGENT_GUIDE.md` (in the project root) — explains the meta-protocol
2. **Read** `PROJECT_CONTEXT.md` — architecture, key files, conventions
3. **Read** `pipeline_defs/animated-explainer.yaml` — the stages for this pipeline
4. **Read** `skills/pipelines/explainer/<X>-director.md` for each stage in the pipeline:
   - `research-director.md` — uses `multi_search_research` tool (we just wired it)
   - `idea-director.md` — generates angle options
   - `proposal-director.md` — picks a concept
   - `script-director.md` — writes the script
   - `scene-director.md` — plans scenes
   - `asset-director.md` — generates images/video/audio
   - `edit-director.md` — assembles the timeline
   - `compose-director.md` — renders the final video
5. **Run** `python -c "from tools.tool_registry import registry; registry.discover(); print(registry.provider_menu_summary())"` to see real capabilities
6. **Execute** each stage, writing artifacts to `projects/<project>/artifacts/`
7. **Checkpoint** after each stage via `lib/checkpoint.py`
8. **Present** to human for approval at human_approval_default: true stages

## Pipelines (12+)

animated-explainer · talking-head · screen-demo · clip-factory · podcast-repurpose · cinematic · animation · character-animation · hybrid · avatar-spokesperson · localization-dub · documentary-montage · framework-smoke

## Style playbooks (4 built-in + taste-skill)

- `styles/clean-professional.yaml` — corporate / SaaS / education
- `styles/minimalist-diagram.yaml` — whiteboard / architecture / CS
- `styles/flat-motion-graphics.yaml` — data-viz / motion graphics
- `styles/anime-ghibli.yaml` — narrative / warm / emotional

Map taste-skill IDs to playbooks via the adapter:
- `brandkit` / `corporate` → clean-professional
- `minimalist` / `diagram` → minimalist-diagram
- `data-viz` / `flat` → flat-motion-graphics
- `soft` / `ghibli` / `illustration` / `story` → anime-ghibli

## Gotchas (from real deployment)

1. **No LLM calls from OpenMontage itself.** The agent is the brain.
2. **Manifests drive everything.** Go through `pipeline_defs/`.
3. **3-runtimes rule.** When both Remotion + HyperFrames are available, MUST present both.
4. **Money is real.** State cost before paid actions. Default approval: $0.50.
5. **Checkpoints are sacred.** Don't skip `lib/checkpoint.py`.

## Files added by integrations (this install)

- `tools/audio/edge_tts.py` — Microsoft Edge TTS provider
- `tools/research/multi_search_research.py` — multi-source research (plan + compile)
- `tools/style/taste_skill_adapter.py` — taste-skill → playbook mapping
- `publish_to_lark.py` — Send rendered video to Lark/Feishu
- `make_video.py` — End-to-end wrapper
- `.chrome-headless-shell/patch-google-fonts.js` — Re-applies font patch
- `~/.openclaw/workspace/projects/openflow/examples/openmontage-make-video.yaml` — OpenFlow workflow
- `.env` — Extended with `OPENMONTAGE_LARK_*`, `OPENMONTAGE_DEFAULT_VOICE`, `OPENMONTAGE_AUTO_*`

## See also

- `wiki/openmontage-deployment.md` — full install + bug analysis
- `wiki/openmontage-integrations.md` — integration details + restoration scripts
