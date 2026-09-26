---
name: local-web-app-operations
description: Use when opening or operating a local web app.
---


# Local web app operations

> 完整描述："Use when opening or operating a local web app. Verify, start, wait, open, and report."

Open and operate localhost web applications as real services, not merely as URLs. The standard is: determine the intended app, probe it, start it if needed, wait for readiness, open it in the user's browser, and report only the verified result.

## When to use

- The user says “打开网页端”, “open the web UI”, or asks to launch a locally hosted dashboard.
- A browser URL depends on a local server process being alive.
- A local UI must be restarted or its listening endpoint verified.

## Workflow

1. Resolve the intended application from user context or persistent memory. Do not substitute a similarly named dashboard.
2. Probe the exact URL with a short timeout. Treat expected HTTP success/redirect/auth statuses as alive.
3. If down, identify the installed launcher from known configuration, package metadata, or executable discovery. Do not infer a command solely from a product name.
4. Start bounded applications with the process-aware background tool. Avoid shell wrappers such as `nohup ... &` when the runtime can track the process directly.
5. Poll the exact HTTP endpoint until ready, with a finite deadline. A spawned PID is not readiness.
6. Run the platform opener (`xdg-open` on Linux) only after readiness succeeds.
7. Verify both the HTTP result and opener exit status. Report the URL and whether it opened; keep the final response to one line unless blocked.

## Fast path

If the endpoint already responds, open it immediately. Do not inspect logs, processes, package metadata, or help output unless the health probe fails.

## Failure handling

- If startup fails, inspect the current application log and launcher help/package metadata, then retry with the verified command.
- If the server starts but readiness never arrives, report the blocker instead of opening a dead URL.
- Do not preserve transient `command not found`, stale PID, or old-log errors as permanent constraints.
- Never type stored credentials into a page. Opening a login screen is fine; authentication remains user-controlled unless explicitly requested and policy permits it.

## Verification checklist

- Exact target URL selected
- HTTP endpoint returned an expected status
- Browser opener exited successfully
- No claim that the page opened before both checks pass

## References

- `references/hermes-studio-local.md` — known local Hermes Studio endpoint and verified launch sequence for this environment.
