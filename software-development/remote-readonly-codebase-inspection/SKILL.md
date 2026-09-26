---
name: remote-readonly-codebase-inspection
description: Use when inspecting a remote Linux codebase over SSH with...
---

# Remote Read-Only Codebase Inspection

> 完整描述：Use when inspecting a remote Linux codebase over SSH without making changes. Locate target files, trace local dependencies, inventory related artifacts, and verify syntax using strictly non-mutating probes.

Use this skill when the user asks to SSH into a machine and find, inspect, or map a code file and its related files while preserving the remote state.

## Core contract

1. Treat the remote host as read-only. Do not run installers, the target program, formatters, package managers, or commands that can modify configuration or service state.
2. Avoid commands that create caches or generated files. For Python syntax validation, use an in-memory `compile()` probe rather than `py_compile`, because `py_compile` writes `__pycache__`.
3. Never expose or persist the supplied password. Use it only for the current SSH authentication step.
4. Inspect before interpreting: locate the exact target, collect metadata, identify same-directory companions, then trace references and imports.
5. Report evidence with exact absolute paths, sizes, timestamps where useful, and verification results. Distinguish files found from paths merely referenced by source.

## Recommended workflow

1. Establish a password-capable SSH method. Prefer an existing `sshpass`; otherwise use a short-lived `pexpect` wrapper. Use `StrictHostKeyChecking=accept-new` only when appropriate for a first connection.
2. Locate the exact filename with a bounded read-only search. Start with likely roots (`/home`, `/opt`, `/srv`, `/root`) and avoid scanning virtual or cache-heavy trees unless needed.
3. Inspect the target using `stat`, import extraction, and targeted text searches. Do not dump a 200KB source file by default; retrieve focused ranges or symbols unless the user explicitly asks for the whole file.
4. Inventory the target directory and search for related names. Use Python `os.walk` or simple `find` predicates; when remote shell quoting becomes complex, simplify the command instead of adding layers of escaped parentheses.
5. Trace source references: local Python/HTML/config names, `Path` constructions, imports, subprocess targets, package paths, and service/config paths. Then search for those artifacts in bounded roots.
6. Validate syntax without side effects, for example:
   ```bash
   python3 - <<'PY'
   from pathlib import Path
   p = Path('/absolute/target.py')
   compile(p.read_text(encoding='utf-8'), str(p), 'exec')
   print('syntax: PASS')
   PY
   ```
   If encoding is uncertain, read bytes and decode with an explicit fallback only for display; do not silently treat a decode failure as a syntax pass.
7. Before finalizing, verify that no generated artifacts appeared. If an unavoidable diagnostic generated a file, remove only that generated artifact and state the exception clearly; prefer avoiding it in the first place.

## SSH wrapper guidance

- Use byte-mode output (`encoding=None`) when the remote source or terminal may contain non-UTF-8 bytes; decode captured output with `errors='replace'` only for display.
- Handle `password:` and EOF explicitly, set connection and command timeouts, and propagate non-zero remote exit status.
- Keep remote commands small and composable. Complex shell quoting is a common source of false failures; replace escaped `find \(...\)` expressions with simpler name filters or a short remote Python script.
- Store temporary client wrappers under `/tmp`, never inside the inspected repository, and do not retain credentials in files after the task.

## Reporting structure

- Target file: path, metadata, and syntax result.
- Related files: exact matches with a short role/category.
- References that were not found: only if the source explicitly points to them.
- Important observations: missing same-directory frontend, copied/generated config expectations, or runtime-only dependencies.
- State safety: confirm no source/config changes; mention any diagnostic artifact handling.

See `references/readonly-ssh-probe.md` for reusable probe patterns and pitfalls from a real inspection.

## Pitfalls

- Do not claim an inspection was read-only if using `py_compile`, which writes bytecode caches.
- Do not confuse source comments such as `# Source: foo.py` with a separately present file; verify existence.
- Do not infer that a referenced frontend/config exists merely because the main script names it.
- Do not print secrets, shell histories, credential files, or full unrelated home-directory inventories.
