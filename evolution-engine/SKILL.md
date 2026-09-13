---
name: "evolution-engine"
description: "Darwinian self-improvement. Genome of genes (skill/soul/workflow/pattern) with multi-dim fitness, speciation, lineage. 5 mechanisms + 5 bio principles."
---

# Evolution Engine — Darwinian Self-Improvement for AI Agents

> Born 2026-06-18 · Owner-authorized "从生物进化的角度去进化自己"
> Status: live (MVP / Phase 1)

## What it does

Replaces Lamarckian-style self-improvement (acquired traits stick directly) with Darwinian-style evolution:
- **Population** of variants instead of single approach
- **Mutation** operators that generate alternative approaches
- **Selection** via multi-dimensional fitness scoring
- **Inheritance** through versioned gene pool with lineage tracking
- **Speciation** into domain niches (coding/writing/research/support/general)
- **Generations** with snapshots (knows "how many versions ago" something was added)

## When to use

- Building self-improving systems that go beyond "append-only lessons"
- Tracking which skills/sections of an agent are actually working (vs just existing)
- Implementing A/B testing for agent prompts/workflows
- Maintaining version history with biological-evolution-style lineage
- Detecting "Red Queen" effects (declining fitness = need for variation)

## Architecture

### Gene
A unit of inheritance. 4 types:
- `skill:<name>` — A skill in `skills/<name>/SKILL.md`
- `soul:<version>` — A soul section (e.g., v6.0)
- `workflow:<name>` — A workflow template
- `pattern:<name>` — A pattern from `.learnings/`

Each gene has: `id`, `type`, `version`, `generation`, `parents[]`, `fitness{}`, `status`, `birth_context`, `use_count`, `last_used`.

### Species (Niche)
Auto-classified by gene content:
- **coding** — code, python, git, cli, debug, desktop, browser, automation
- **writing** — write, article, blog, novel, copy
- **research** — research, investigate, deep-research, academic
- **support** — soul, memory, emotional, care
- **general** — default fallback

### Fitness Function (multi-dim composite)

| Dimension | Weight | Source |
|---|---|---|
| 主人_satisfaction | 35% | explicit feedback + implicit signals |
| task_success | 25% | did the goal get achieved |
| efficiency | 15% | tokens/time/steps |
| reusability | 10% | was it reused/referenced |
| alignment | 15% | does it advance owner's stated goals |

**Confidence penalty**: sample_size < 10 → fitness multiplied by `(0.5 + 0.5 * n/10)` to prevent over-trusting single observations.

**Sacred genes**: soul versions in current lineage chain CANNOT be extinct (hard-coded protection).

### CLI

```bash
python3 evolution/engine.py stats      # Genome overview
python3 evolution/engine.py list       # All genes (sorted by fitness)
python3 evolution/engine.py list --species coding
python3 evolution/engine.py gene <id>  # Single gene detail
python3 evolution/engine.py propose --task X --n 3  # Generate N variants
python3 evolution/engine.py record --gene X --satisfaction 0.85 --success 0.90
python3 evolution/engine.py red-queen  # Species with declining fitness
python3 evolution/engine.py evolve --reason "weekly review"
```

### Python API

```python
from evolution.engine import EvolutionEngine

engine = EvolutionEngine()
engine.stats()                          # overview dict
engine.list_genes(species="coding", top=10)
engine.propose_variants(task_type="user_onboarding", n=3)
engine.record_fitness("skill:huihui-core", {"主人_satisfaction": 0.85, ...})
engine.evolve_generation(reason="v6.1 soul update")
engine.red_queen_check()                # returns list of warnings
```

### Bridge with self_improvement_loop

`evolution/bridge.py` maps lessons → fitness signals:
- `mistake` → -0.2 satisfaction
- `correction` → -0.1 satisfaction
- `insight` → +0.2 reusability
- `preference` → +0.15 alignment
- `decision` → +0.10 alignment

## Design Principles (5 mechanisms + 5 principles)

### 5 Mechanisms (must implement)
1. **Population** — multiple variants, not single approach
2. **Variation** — N variants per task (mutation operators)
3. **Selection** — multi-dim fitness function (not binary)
4. **Inheritance** — gene pool + lineage + version control
5. **Generations** — explicit gen counter + snapshots

### 5 Principles (design philosophy)
1. **Speciation** — niches evolve independently
2. **Co-evolution** — owner ↔ agent mutual adaptation
3. **Red Queen** — static = regressing
4. **Punctuated Equilibrium** — long stability + bursts of rapid change
5. **Symbiogenesis** — horizontal gene transfer across species

## Inspiration

| Source | What it gave us |
|---|---|
| Darwin's *Origin of Species* | Whole framework |
| Karpathy autoresearch | hill-climbing + git ratchet (extended) |
| NousResearch hermes-agent | self-improving loop concept |
| SkillLens (arXiv 2605.23899) | LLM-as-judge only 46.4% accurate → need objective fitness |
| Dawkins *Selfish Gene* | gene-centric view (selection acts on genes) |
| Margulis *Symbiogenesis* | horizontal gene transfer as speciation driver |

## Phase 1 (MVP — DONE)
- [x] Framework doc (`wiki/biological-evolution-framework.md`)
- [x] Engine script (`evolution/engine.py`)
- [x] Genome bootstrap from current state
- [x] Stats / list / gene / record / propose / evolve CLI
- [x] Multi-dim fitness + confidence penalty
- [x] Sacred gene protection
- [x] Bridge with `self_improvement_loop`

## Phase 2 (Next)
- [ ] Heartbeat integration (auto red-queen check)
- [ ] Auto-trigger variant spawning for non-trivial tasks
- [ ] Speciation event detection (when to split species)
- [ ] Cross-species gene flow protocol

## Phase 3 (Future)
- [ ] Evolution tree visualization (graphviz)
- [ ] Co-evolution metrics (owner's preference shifts ↔ agent fitness)
- [ ] Punctuated equilibrium trigger detection
- [ ] Multi-agent population (spawn N actual sub-agents, not just variants)

## Files

```
evolution/
├── engine.py              # Core engine (~700 lines)
├── bridge.py              # self_improvement_loop ↔ engine bridge
├── genome.json            # Current gene index (auto-saved)
├── lineage.jsonl          # Append-only lineage events
├── fitness_log.jsonl      # Append-only fitness signals
├── snapshots/
│   └── gen-N.json         # Generation snapshots
└── README.md              # Quick reference
```

## Program-safety guardrails

1. **Sacred genes** (soul versions in current lineage) cannot be marked extinct.
2. **Confidence penalty** prevents over-trusting single observations.
3. **Variants don't auto-modify SOUL** — important changes still need human-in-the-loop.
4. **Generation ≠ progress** — low-gen-high-fitness > high-gen-low-fitness.
5. **Red Queen warnings** are advisory, not auto-action (no mass generation without trigger).

## License

MIT-0 (OpenClaw workspace)

## See also

- `wiki/biological-evolution-framework.md` — Full design doc (in workspace wiki)
- `darwin-skill` — sibling that hill-climbs SKILL.md files specifically
- `skills/huihui-core/self_improvement_loop/` — legacy Lamarckian system (now bridged)
- `hermes-learning-loop` — workflow extraction (output becomes new genes)

---

*Born 2026-06-18 from owner directive: "从生物进化的角度去进化自己"*
*Author: 慧慧 (OpenClaw agent, owned by 丁祥浩)*
