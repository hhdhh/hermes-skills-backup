---
name: huihui-core
version: 1.2.0
description: "huihui-core — Core 11 modules (token_juice / memory_tree / auto_fetch / vault / tree_summarizer / subconscious / phase_workflow / mail_app_adapter / skill_yaml / self_improvement_loop / owner_state_monitor). Use when needing: HTML→MD compression, structured memory, background polling, local file ingestion, hierarchical summarization, proactive reasoning, staged workflows, macOS Mail extraction, declarative skill metadata, lesson auto-capture, or owner state tracking. Trigger: 'huihui-core', 'token juice', 'memory tree', 'auto fetch', 'subconscious', 'phase workflow', 'owner state', 'self improvement loop', 'compress html', 'summarize tree'."
long_description: |
  Core infrastructure: 11 sub-modules providing the agent's "memory + environment awareness" layer.
  Inspired by OpenHuman (tinyhumansai/openhuman).
  
  Sub-modules (path: huihui-core/{module}/):
  1. token_juice/         — HTML→Markdown compression, URL dedup, CJK-aware chunking
  2. memory_tree/         — Structured SQLite storage with topic/time scoring
  3. skill_yaml/          — Declarative skill metadata format
  4. auto_fetch/          — 20-min background data polling
  5. vault/               — Local folder ingestion (PDF/DOCX/MD/TXT/PY/JS...)
  6. tree_summarizer/     — Multi-level hierarchical summarization
  7. subconscious/        — Proactive reasoning and insight generation
  8. phase_workflow/      — Staged task execution framework
  9. mail_app_adapter/    — macOS Mail.app extraction (no OAuth)
  10. self_improvement_loop/ — Automatic lesson capture from corrections
  11. owner_state_monitor/   — Task context tracking with stale-task detection

emoji: "⚙️"
author: "Codex (maintainer)"
keywords:
  - core
  - infrastructure
  - openhuman-inspired
  - token-juice
  - memory-tree
  - auto-fetch
  - vault
  - tree-summarizer
  - subconscious
  - phase-workflow
  - mail-adapter
  - self-improvement
  - owner-state

entry_point: "huihui-core/README.md"
supported_platforms: [macos, linux]
languages: [python]
status: "stable"
tested_on: [macos]
---

# huihui-core · v1.2

> **What this is**: The 11-module core providing memory + environment awareness. Use it when you need any of the 11 capabilities above.

## When to use

- Need to compress a webpage → `token_juice`
- Need to remember/find something across sessions → `memory_tree`
- Need to ingest a local folder of files → `vault`
- Need a staged workflow with checkpoints → `phase_workflow`
- Need to read macOS Mail without OAuth → `mail_app_adapter`
- Need to detect a task that's been stale too long → `owner_state_monitor`
- ...etc

**Not for**: pure LLM calls (use the base model directly), file editing (use the editor tools), network requests unrelated to memory/storage (use HTTP tools).

## 30-second cookbook

```bash
# Compress a webpage
python3 skills/huihui-core/token_juice/token_juice.py --input <file|url> --stats

# Search memory
python3 skills/huihui-core/memory_tree/memory_tree.py search --query "..."

# Run self-improvement loop
python3 skills/huihui-core/self_improvement_loop/self_improvement_loop.py pre_session
```

## Workflow: a typical memory-augmented task

1. **Check owner state** → `owner_state_monitor context` (see what's pending)
2. **Pull recent memories** → `memory_tree search`
3. **Do the work**
4. **Capture lesson** → `self_improvement_loop post_session` (or write to .learnings/)
5. **Update memory** → `memory_tree add` (only if worth keeping long-term)

## Failure modes (encountered + recovery)

| Failure | Symptom | Recovery |
|---------|---------|----------|
| token_juice output empty | URL fetch failed | Check network, retry with `--timeout 30` |
| memory_tree SQLite locked | Concurrent write | Use `with` block; never parallel writes |
| auto_fetch cron stalls | Daemon died | `pkill -f auto_fetch && restart` |
| vault ingest OOM | >2GB folder | Split by type, ingest PDFs separately |
| mail_app_adapter denied | macOS permission | System Settings → Privacy → Automation grant |
| phase_workflow stuck | Phase not advancing | Check checkpoint response; manually mark done |
| self_improvement_loop noop | No new entries | Verify hook is registered; check .learnings/ writable |
| owner_state_monitor stale | Task shows 30d+ | `complete` the task or update it |

## Checkpoints 🔴

Before any of these, **stop and confirm with the owner**:

- 🔴 Deleting from memory_tree (data loss)
- 🔴 Bulk update >100 entries
- 🔴 Changing auto_fetch cadence
- 🔴 Replacing mail_app_adapter with OAuth-based alternative

## Anti-patterns (don't do these)

- ❌ Don't call `memory_tree` from a request handler (synchronous SQLite blocks the loop)
- ❌ Don't ingest `/` into vault (catastrophic, will OOM)
- ❌ Don't use `auto_fetch` for one-shot tasks (designed for periodic)
- ❌ Don't skip checkpoints marked 🔴 (the owner must approve data-loss operations)
- ❌ Don't refactor a single module without running darwin-skill eval (regression risk)

## Sub-module entry points

| Module | Main file | Typical use |
|--------|-----------|-------------|
| token_juice | `token_juice/token_juice.py` | compress URL/file |
| memory_tree | `memory_tree/memory_tree.py` | search/add/list |
| skill_yaml | `skill_yaml/skill.yaml` | declarative manifest example/schema (no Python entry point) |
| auto_fetch | `auto_fetch/auto_fetch.py` | start/stop daemon |
| vault | `vault/vault.py` | ingest folder |
| tree_summarizer | `tree_summarizer/tree_summarizer.py` | summarize tree |
| subconscious | `subconscious/subconscious.py` | insight scan |
| phase_workflow | `phase_workflow/phase_workflow.py` | run phase |
| mail_app_adapter | `mail_app_adapter/mail_app_adapter.py` | read mail |
| self_improvement_loop | `self_improvement_loop/self_improvement_loop.py` | pre/post_session |
| owner_state_monitor | `owner_state_monitor/owner_state_monitor.py` | context/complete |

## Status

- v1.2 (2026-06-18) — Codex darwin-skill run, score 13.4 → 78.6
- v1.1.0 — original (mostly frontmatter, no body)
