# Example: Build a CLI-Anything Harness from OpenClaw

This is a worked example of the recommended build workflow when this skill is
loaded by OpenClaw.

## Target

A local copy of [some-app](https://github.com/example/some-app) (or any GUI app
the user names).

## Step 0 — Acquire source

```bash
# If the user gave a GitHub URL, clone it
git clone --depth 1 https://github.com/example/some-app.git /tmp/some-app
cd /tmp/some-app
```

If a local path was given, `cd` into it directly.

## Step 1 — Read the methodology

OpenClaw should call `read` on `references/HARNESS.md` first, then on
`references/commands/cli-anything.md`. Both are vendored into the installed
skill so no network access is required.

## Step 2 — Analyze the source

Use `read`, `exec`, and `web_fetch` to:

1. Identify the backend engine
2. Map GUI actions to API calls
3. Identify the data model and native file format
4. Find any existing CLI tools shipped with the app
5. Catalog command/undo systems

Tip: parallelize the analysis by `sessions_spawn`ing sub-agents that each
inspect a different module of the source tree.

## Step 3 — Write `<SOFTWARE>.md`

Document the findings in `<software>/agent-harness/<SOFTWARE>.md` so future
runs (and other agents) can pick up where you left off.

## Step 4 — Scaffold the harness

Create the directory tree:

```text
some-app/
└── agent-harness/
    ├── SOME-APP.md
    ├── setup.py
    └── cli_anything/
        └── some_app/
            ├── __init__.py
            ├── __main__.py
            ├── README.md
            ├── some_app_cli.py
            ├── core/
            │   ├── __init__.py
            │   ├── project.py
            │   ├── export.py
            │   └── session.py
            ├── utils/
            │   ├── __init__.py
            │   ├── some_app_backend.py
            │   └── repl_skin.py
            └── tests/
                ├── TEST.md
                ├── test_core.py
                └── test_full_e2e.py
```

Copy `scripts/repl_skin.py` from the installed skill into
`cli_anything/some_app/utils/repl_skin.py`.

## Step 5 — Write `setup.py` and install

Follow `references/guides/pypi-publishing.md` for the namespace-package
template. Then:

```bash
cd some-app/agent-harness
pip install -e .
```

The CLI is now on PATH as `cli-anything-some-app`.

## Step 6 — Write TEST.md FIRST

OpenClaw should write `tests/TEST.md` before writing any test code, listing:

- Planned test files and counts
- Modules to test with edge cases
- Real-world workflow scenarios
- E2E output verification plan

## Step 7 — Implement tests

Three layers:

- `test_core.py` — unit tests, synthetic data
- `test_full_e2e.py` — real-file E2E with the actual backend
- Subprocess tests — invoke the installed `cli-anything-some-app` command

Always verify real output (magic bytes, ZIP structure, etc.) — never trust
"it exited successfully."

## Step 8 — Run the tests

```bash
CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/some_app/tests/ -v -s
```

The `-s` flag shows artifact paths so the agent (or the user) can manually
inspect outputs.

## Step 9 — Persist notes to the workspace

Use `wiki_apply` to file a build-notes synthesis under
`wiki/<software>-harness-build.md` so future sessions can resume the work.

## Step 10 — Promote to an OpenClaw skill (optional)

If the harness is genuinely useful, propose promoting it as a top-level
OpenClaw skill:

```text
skill_workshop action=create \
  name=cli-anything-some-app \
  description="Agent CLI for <Some App> via real backend" \
  proposal_content=...
```

The user (or owner) can then run `skill_workshop action=apply` to install it.
