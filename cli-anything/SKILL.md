---
name: cli-anything
description: Use when the user wants OpenClaw to build, refine, test, validate, or list CLI-Anything harnesses for GUI applications or source repositories. Adapts the full CLI-Anything methodology to OpenClaw without changing the generated Python harness format.
---

# CLI-Anything for OpenClaw

Use this skill when the user wants OpenClaw to act like the `CLI-Anything` builder.

## Read the Full Methodology First

Before implementation, use the full methodology source of truth:

1. Read `references/HARNESS.md` relative to this skill directory.
2. Read the matching mode specification under `references/commands/`.
3. Read referenced files under `references/guides/` only when they apply to the target.
4. If the installed resources are unavailable and this skill is being used from inside a
   `CLI-Anything` repository checkout, read `../cli-anything-plugin/HARNESS.md` and
   the resources around it.
5. If neither local source is available, clone or download
   `https://github.com/HKUDS/CLI-Anything` and use `cli-anything-plugin/HARNESS.md`.
6. Only if all full-methodology sources are unavailable, follow the condensed rules below.

The installer vendors the canonical resources from `cli-anything-plugin/` into this
skill so a normal OpenClaw installation is self-contained.

## Resource Map

| Path | Purpose |
|------|---------|
| `references/HARNESS.md` | Complete methodology and quality rules |
| `references/commands/cli-anything.md` | Build-mode specification |
| `references/commands/refine.md` | Refine-mode specification |
| `references/commands/test.md` | Test-mode specification |
| `references/commands/validate.md` | Validation checklist |
| `references/commands/list.md` | Installed/generated harness discovery |
| `references/guides/` | On-demand implementation guidance |
| `scripts/repl_skin.py` | Copy into generated harnesses as `utils/repl_skin.py` |
| `scripts/preview_bundle.py` | Copy into preview-capable harnesses as `utils/preview_bundle.py` |
| `scripts/skill_generator.py` | Generate canonical and packaged CLI skills |
| `scripts/templates/SKILL.md.template` | Skill generation template used by `skill_generator.py` |
| `references/docs/PREVIEW_PROTOCOL.md` | Shared preview bundle protocol |

When reading vendored documents, apply these path remappings instead of resolving
plugin paths against the current working directory:

| Document reference | Installed skill path |
|--------------------|----------------------|
| `guides/...` | `references/guides/...` |
| `cli-anything-plugin/repl_skin.py` | `scripts/repl_skin.py` |

## Inputs

Accept either:

- A local source path such as `./gimp` or `/path/to/software`
- A GitHub repository URL

Derive the software name from the local directory name after cloning if needed.

## OpenClaw Tool Bindings

OpenClaw agents build harnesses by combining these built-in tools:

| Tool | Role in Harness Workflow |
|------|--------------------------|
| `exec` | Run shell commands, install packages, execute CLI tools, run tests |
| `read` / `write` / `edit` / `apply_patch` | Read and write harness source files |
| `web_fetch` / `web_search` | Fetch upstream docs, READMEs, PyPI metadata |
| `sessions_spawn` | Parallelize analysis or generation subtasks |
| `process` | Manage long-running pip/test invocations |
| `gateway` | Read/write OpenClaw gateway config |
| `cron` | Schedule harness test re-runs |
| `wiki_*` | Persist build notes into the workspace knowledge base |
| `skill_workshop` | Promote a finished harness into a reusable OpenClaw skill proposal |

Consult the [OpenClaw documentation](https://docs.openclaw.ai) for exact tool invocation syntax.

## Modes

### Build

Read `references/commands/cli-anything.md`. Build a complete harness through source
analysis, architecture design, implementation, test planning, test implementation,
test documentation, CLI-specific `SKILL.md` generation, and local installation.

### Refine

Read `references/commands/refine.md`. Inventory current commands and tests, compare
them against the target software, then incrementally add high-impact capabilities
without removing existing commands unless the user requests a breaking change.

### Test

Read `references/commands/test.md`. Run the harness tests against the real backend,
verify installed-command subprocess coverage, and update `TEST.md` only with passing
results.

### Validate

Read `references/commands/validate.md`. Validate the harness against the complete
directory, implementation, test, documentation, packaging, and code-quality checklist.

### List

Read `references/commands/list.md`. Discover installed and generated CLI-Anything tools
and support human-readable or JSON output as requested.

## Condensed Fallback Rules

Use these only when the full methodology cannot be retrieved.

### Harness Structure

Produce:

```text
<software>/
└── agent-harness/
    ├── <SOFTWARE>.md
    ├── setup.py
    └── cli_anything/
        └── <software>/
            ├── README.md
            ├── __init__.py
            ├── __main__.py
            ├── <software>_cli.py
            ├── core/
            ├── utils/
            └── tests/
```

### Required Behavior

- Prefer the real software backend over reimplementation.
- Provide one-shot Click subcommands and default REPL mode.
- Support `--json` machine-readable output.
- Add session state with undo/redo where the target supports it.
- Auto-save one-shot session mutations and support `--dry-run`.
- Use locked session-file writes to avoid concurrent JSON corruption.
- Copy and use the unified `ReplSkin`.
- Add truthful preview commands for software with meaningful visual or inspection state.
- Generate both canonical and packaged CLI-specific `SKILL.md` files.

### Testing

- Write `TEST.md` before test code.
- Keep `test_core.py` for unit coverage.
- Keep `test_full_e2e.py` for real-file workflows and real backend validation.
- Verify rendered/exported output programmatically, not only process exit codes.
- Test the installed `cli-anything-<software>` command via `_resolve_cli()`.
- Run release validation with `CLI_ANYTHING_FORCE_INSTALLED=1`.

### Packaging

- Use `find_namespace_packages(include=["cli_anything.*"])`.
- Keep `cli_anything/` as a namespace package without a top-level `__init__.py`.
- Expose `cli-anything-<software>` through `console_scripts`.
- Include the packaged CLI-specific `skills/SKILL.md`.

## OpenClaw-Specific Installation

This skill installs to OpenClaw's standard skill directories:

| Target | Path | Use when |
|--------|------|----------|
| User-global | `~/.agents/skills/cli-anything/` | All agents under this user (recommended) |
| Workspace | `~/.openclaw/workspace/skills/cli-anything/` | Only this workspace (project-scoped) |

```bash
# User-global install (recommended)
bash scripts/install.sh --global

# Workspace install (project-scoped)
bash scripts/install.sh --workspace

# Custom target
bash scripts/install.sh --target /path/to/skills

# Verify
bash tests/test_install.sh
```

The installer:
1. Stages the skill directory into a tmp folder
2. Vendors `HARNESS.md`, `commands/*.md`, `guides/*.md`, and `scripts/*.py` from `cli-anything-plugin/`
3. Writes `SKILL.md` (this file), `agents/openclaw.yaml`, and tests
4. Refuses to overwrite an existing install — remove manually first if reinstalling

## Workspace Integration

Once installed, this skill works alongside OpenClaw's other capabilities:

| OpenClaw capability | How this skill uses it |
|---------------------|------------------------|
| `wiki_apply` / `wiki_search` | Persist per-harness build notes into `wiki/` |
| `skill_workshop` | Promote a finished harness as a reusable OpenClaw skill proposal |
| `cron` | Schedule nightly test reruns for installed harnesses |
| `gateway` config | Toggle `cli-anything-hub` install behavior per workspace |
| `message` (feishu/etc.) | Notify the owner when a harness test fails |
| `sessions_spawn` | Parallelize Phase 1 analysis across multiple sub-agents |

A typical OpenClaw build workflow:

```text
1. sessions_spawn → clone target repo (if GitHub URL)
2. read + write   → produce <software>/agent-harness/* scaffold
3. exec           → run cli-anything-<software> --help / --json smoke
4. exec           → run CLI_ANYTHING_FORCE_INSTALLED=1 pytest -v
5. wiki_apply     → file build notes into wiki/<software>-harness-build.md
6. skill_workshop → propose promoting the harness to a top-level skill
```

## Output Expectations

When reporting progress or final results, include:

- target software and source path
- files added or changed
- validation commands run
- open risks or backend limitations
- whether `--json` was verified end-to-end
- whether real-backend E2E tests passed (with artifact paths)

## Related Skills

- `codex-skill` — same methodology, Codex adapter
- `hermes-skill` — same methodology, Hermes Agent adapter
- `opencode-commands` — command-only adapter (no vendored resources)
- `toryx-automation` — OpenClaw Playwright automation that pairs well with the
  browser harness for GUI-screenshot validation
