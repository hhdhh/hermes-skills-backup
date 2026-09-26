---
name: local-web-service-operations
description: Use when launching or recovering a local web UI.
version: 1
license: MIT
metadata:
  hermes:
    tags: [localhost, web-ui, service, browser, health-check, linux]
    related_skills: []
---

# Local web service operations

> 完整描述：Use when launching or recovering a local web UI. Verify service readiness, open it, and report only actionable status.

Launch, recover, and open browser-based applications hosted on localhost. This covers developer dashboards, admin panels, local agents, preview servers, and similar user-session services.

## Core workflow

1. Resolve the intended product and its canonical URL from user context or durable profile information. Do not substitute a similarly named dashboard.
2. Probe the exact URL with a short timeout before starting anything. Treat HTTP 2xx/3xx as ready.
3. If unavailable, discover the application's own status/start interface and existing logs before improvising a raw process command.
4. Start it non-interactively, then poll the URL with bounded retries. A spawned PID is not readiness.
5. Only after an HTTP-ready response, open the exact URL with the desktop's standard URL opener.
6. Verify the opener exited successfully or explicitly reported reuse of an existing browser session.
7. Report the URL and readiness result. Mention stderr only when it affects use.

## Linux pattern

```bash
URL=http://localhost:<port>/

curl -fsS --max-time 5 -o /dev/null -w '%{http_code}\n' "$URL"
# If down, use the product's documented start command.

for _ in 1 2 3 4 5 6 7 8 9 10; do
  code=$(curl -sS --max-time 2 -o /dev/null -w '%{http_code}' "$URL" || true)
  case "$code" in 2*|3*) break ;; esac
  sleep 1
done
case "$code" in 2*|3*) ;; *) exit 1 ;; esac

xdg-open "$URL"
```

Run a long-lived server as a managed background process. Run `xdg-open` separately after the readiness probe so browser startup cannot obscure service failure.

## Verification rules

- Server command exit/start output alone is insufficient; probe the HTTP endpoint.
- Opening the browser alone is insufficient; ensure the endpoint was ready first.
- "Opening in an existing browser session" is success.
- Shell messages about no job control or an unavailable terminal process group can be harmless when a GUI opener is launched from a non-interactive shell. Judge by opener exit status and browser-session message, not those lines alone.
- Avoid declaring a specific UI healthy when only its port is listening if a lightweight application health endpoint exists; prefer that endpoint.

## Pitfalls

- Do not launch a duplicate server before checking whether one is already listening.
- Do not put `xdg-open ... &` inside a foreground terminal-tool command when the runtime rejects shell backgrounding; use the tool's background mode instead.
- Do not turn a one-time missing executable or PATH mismatch into a durable rule. Use the installed product's supported command and keep environment repair separate.
- Keep final status short for simple launch requests: opened URL, verified HTTP result, and any remaining blocker.

## References

- `references/hermes-web-ui.md` — validated Hermes Web UI start/readiness/open recipe and benign opener output.
