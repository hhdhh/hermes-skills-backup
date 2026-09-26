---
name: privileged-cli-web-consoles
description: Use when adding a Web UI to a privileged CLI/setup tool.
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [web-ui, cli, setup-wizard, security, subprocess, local-tools]
---

# Privileged CLI Web Consoles

## Purpose

Use this skill when wrapping an existing CLI wizard, installer, maintenance utility, hardware tool, or system configuration script in a local browser UI. This class is higher risk than an ordinary dashboard because the backend may invoke `sudo`, interrupt networking, restart services, or move hardware.

The goal is an **Operate** surface that makes the existing tool easier to use without forking its operational logic or weakening its safety model.

## Architecture

1. Inspect the existing command-line entry points, stage registry, prompts, subprocess helpers, and configuration model.
2. Keep the CLI as the source of truth. The Web layer should launch narrow existing leaf actions rather than duplicate shell/system logic.
3. Expose stage metadata from the backend through a manifest endpoint. Do not maintain a second hard-coded task list in JavaScript.
4. Use an in-process job registry only for local, single-host tooling. Each job should expose an ID, stage, title, status, exit code, timestamps, bounded output, and cancellation.
5. Retain the original CLI workflow and provide a one-command launcher for the Web mode.

## TDD Slices

Build vertically:

1. Manifest endpoint returns setup/integration actions from the real registries.
2. Invalid browser input is rejected before process creation.
3. Valid input normalizes into the child configuration/environment.
4. A job starts, streams bounded output, records an exit code, and can be stopped.
5. The server exposes only the intended page and API routes.

Watch each test fail before implementing it, then run the focused test and full suite.

## Input Validation

Validate on both client and server. Server validation is authoritative.

- Identifiers: exact shape and width, including leading zeroes when meaningful.
- Numeric domains: parse and enforce semantic ranges.
- MAC/IP values: strict syntax; normalize MAC case; reject duplicate interface assignments.
- URLs: allow only expected schemes such as `ws`/`wss` when required.
- Stage keys: resolve only against the real registry.
- Request bodies: require JSON objects and impose a small maximum size.

Do not silently repair malformed identifiers or rely on downstream interactive prompts to catch browser input.

## Secret Handling

- Never place passwords or tokens in command arguments, log lines, job snapshots, files, or API responses.
- Pass secrets only through child stdin/environment when necessary.
- Immediately delete the parent job object's secret-bearing environment entries after the child has spawned.
- Provide a visible “clear sensitive input” action in the page.
- Bind to loopback by default. If LAN access is required, clearly state that the service must remain on a trusted network; add authentication before exposure beyond that boundary.

## HTTP Surface

- Serve only the intended frontend artifact and explicit API routes. Avoid an unrestricted static-file handler rooted at the script directory.
- Return `404` for unknown paths.
- Use `Cache-Control: no-store` for local configuration, jobs, and the app page.
- Add `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, and `Referrer-Policy: no-referrer` to the app page.
- Bound retained logs and request bodies.

## UX Requirements

Treat this as an **Operate** surface:

- Parameters and detected local state are visible near the task list.
- Tasks are searchable and grouped by workflow.
- Selection state and task descriptions are clear.
- Dangerous stages receive an explicit confirmation naming the consequence.
- Live output, progress/status, exit code, cancellation, and copy-log controls are present.
- Password fields explain that values are used only for the current task.
- Responsive behavior should preserve operability, not merely shrink the desktop layout.

## Verification Ladder

A claim of “done” requires evidence at each available layer:

1. Unit tests: manifest, validation, normalization, and command construction.
2. Static checks: Python compile, JavaScript syntax, shell syntax.
3. Real server smoke test: page, manifest, local-config, job endpoints, headers, and stage counts.
4. Browser interaction: rendered task count, selection, validation, start/stop, logs, responsive layout, and console errors.

If browser inspection is blocked by local permission state, report it precisely and do not call the UI browser-verified. Passing HTTP and syntax checks is useful but is not visual acceptance.

## Pitfalls

- A pre-existing `--web` flag does not mean the Web deliverable is complete; confirm the referenced frontend artifact actually exists and its endpoints match.
- `SimpleHTTPRequestHandler` can accidentally expose neighboring source and documentation files.
- A JavaScript stage array drifts from the Python registry.
- Auto-confirm flags can bypass meaningful safety prompts; retain a browser-side risk confirmation and restrict Web launches to leaf stages.
- Secrets left in a long-lived job object's environment remain recoverable after spawn.
- Do not claim “browser verified” when only HTTP responses or source markers were checked.

See `references/implementation-checklist.md` for a concise reusable checklist.
