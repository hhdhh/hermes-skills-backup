---
name: agent-harness-deployment
description: Use when installing or configuring agent harnesses.
---

# Agent harness deployment

> 完整描述：Use when installing or configuring agent harnesses. Verify startup, translate provider settings, and simplify launch commands.

## Workflow

1. Resolve the product before installing. Distinguish similarly named independent harnesses from connecting a model provider to an existing agent; ask once when the ambiguity changes the installation target.
2. Read the target's official installation and safety documentation and inspect its manifest. Prefer a documented packaged distribution for ordinary usage; use a source checkout when required. Keep an independent harness separate from existing agent configuration and credentials.
3. Install dependencies using the manifest's package-manager version, then build if using source. Ensure the package manager is on PATH for nested build scripts, not merely invoked by absolute path at the top level.
4. Provide a short launcher after installation, without waiting for the user to request a simpler command. Check for an existing command before creating a user-local wrapper; verify version/help from outside the checkout. Preserve the user's working-directory semantics unless the documented source entry requires the repository directory.
5. For provider changes, inspect the destination's actual schema before translating input. An OpenCode JSON document is input data, not a configuration file another harness can consume unchanged. Preserve model identifiers and capacity assertions; do not invent variant mappings.
6. Back up the exact configuration before edits. Keep supplied keys in the destination's supported credential store, referenced by name from ordinary settings; avoid printing keys or copying unrelated credentials.
7. Separate three verification layers: schema resolution, authenticated model discovery, and an actual minimal inference request. Discovery alone does not prove inference, and absence from a catalog does not prove a manually configured route cannot work. Report the exact tested models and distinguish untested entries.
8. Preserve the default model and reasoning level when refreshing a catalog unless the user requests a default change. When changing only the default model, make a surgical edit and preserve other settings.
9. Verify startup with a managed background process and an explicit health check. A foreground timeout is not lifecycle management: inspect an occupied port before starting another instance, and never restart an existing service merely to apply settings that support hot reload.
10. Report concise results: what changed, verification evidence, short launch command, and whether existing sessions retain their model. Do not claim a live UI selected a model solely because a file was written.

## Target-specific references

- [DeepSeek Harness configuration and verification](references/deepseek-harness.md): native settings/credential schema, OpenAI-compatible routes, catalog refreshes, and source launcher checks.
