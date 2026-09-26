---
name: agent-harness-customization
description: Use when customizing agent harness models or plugins.
---

# Agent harness customization

> 完整描述：Use when customizing agent harness models or plugins. Configure DeepSeek Harness providers, plugin markets, and safe UI recovery.

## Scope and standing rules

Manage local agent-harness provider configuration, plugin selection, installation, and recovery. DeepSeek Harness (`dsh`) is distinct from Hermes; clarify ambiguous product names before installing or modifying either.

- Preserve the current model, credentials, and existing profile unless the user explicitly requests changing them. Adding models is not permission to switch the default.
- Treat “configure from Awesome” as a catalog-guided selection task, not permission to install the whole catalog. State whether the deliverable is a marketplace only or actual personalization plugins; never present the former as the latter.
- Prioritize restoring an inaccessible main UI over preserving a broken cosmetic plugin. Disable only the offending entry reversibly; keep package files and user data.
- Report concrete changes first, then evidence, and distinguish installed, loaded, API-tested, and browser-verified states. An HTTP 200 market endpoint cannot prove that the main browser UI renders.
- Do not restart an existing service without approval. Inspect live state instead of repeatedly launching onto its occupied port.
- Do not enable remote backup, cloud sync, or automatic restart under general customization authorization. Distinguish daily remote backup from operation-triggered local rollback snapshots.

## Workflow

1. Identify the actual executable, installation, profile, and live process. Read current manifests and scoped configuration; inspect credentials only when necessary for authorized authentication and never print values.
2. Read current product docs and installed package schemas before translating another application's JSON. Similar field names do not imply compatible configuration formats.
3. Back up only the affected configuration/profile metadata with restrictive permissions. Preserve unrelated keys and existing secrets; avoid copying dependency trees into backups.
4. Apply the smallest change. For models, consult the gateway catalog and test a minimal request. For plugins, review the exact pinned package and its defaults before activation.
5. Validate syntax and the harness's semantic schema. Verify the exact running target after external changes. Use isolated ports for startup probes, clean up only the probe process, and keep authentication URLs out of reports.
6. For visible UI changes, run a real browser check for the main frame and absence of plugin-loader errors. If unavailable, explicitly label UI recovery unverified rather than claiming success from server health.
7. Give the user a short result: what changed, what stayed untouched, evidence, and any action actually still required.

## DeepSeek Harness recipes

Load [DeepSeek Harness configuration and recovery](references/deepseek-harness.md) for provider translation, marketplace setup, and plugin-loader recovery. Re-check installed schemas before reusing version-dependent fields.
