# Implementation Checklist

## Discovery
- [ ] Read CLI parser and main dispatch.
- [ ] Trace stage/action registry to each leaf handler.
- [ ] Inspect confirmation, subprocess, sudo, and output helpers.
- [ ] Check whether a referenced frontend file already exists.

## Backend
- [ ] Manifest generated from the real action registries.
- [ ] Strict server-side validation and normalization.
- [ ] Allowlisted stage/action resolution.
- [ ] Bounded JSON body and retained logs.
- [ ] Job status, timestamps, exit code, output, and stop endpoint.
- [ ] Secrets absent from commands/snapshots and removed after spawn.
- [ ] Only app page and explicit API routes are served.
- [ ] Security/no-cache headers set.

## Frontend
- [ ] Operate-surface composition, not a marketing hero.
- [ ] Local detection, parameter source, and editable values.
- [ ] Searchable/grouped tasks sourced from manifest.
- [ ] Client validation mirrors backend for quick feedback.
- [ ] Explicit high-risk confirmation.
- [ ] Live logs, terminal status, stop, and copy controls.
- [ ] Clear-sensitive-input control.
- [ ] Responsive layout remains usable.

## Verification
- [ ] Tests were observed failing before implementation.
- [ ] Unit tests pass.
- [ ] Python compiles.
- [ ] JavaScript syntax passes.
- [ ] Launcher shell syntax passes.
- [ ] Real HTTP page/API smoke test passes.
- [ ] Header and unknown-route behavior checked.
- [ ] Browser render, interaction, console, and responsive checks pass—or limitation is explicitly reported.
