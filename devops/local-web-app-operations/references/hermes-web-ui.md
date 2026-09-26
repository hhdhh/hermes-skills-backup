# Hermes Web UI local launch recipe

Use this only when the user's established “网页端” refers to Hermes Web UI.

## Known shape

- Default endpoint: `http://localhost:8648/`
- State/log directory: `~/.hermes-web-ui/`
- Launcher is commonly available as `hermes-web-ui` on PATH (a user-global npm install is also possible).

Do not persist credentials in this reference.

## Recovery sequence

```bash
curl -fsS -o /dev/null -w 'HTTP %{http_code}\n' http://localhost:8648/
command -v hermes-web-ui
```

If the endpoint is unavailable, inspect `~/.hermes-web-ui/server.pid` and recent `~/.hermes-web-ui/server.log`, but verify any PID before trusting it. Start the discovered launcher with the terminal tool's `background=true` mode, then use a bounded curl loop until the endpoint returns HTTP 200. Finally:

```bash
xdg-open http://localhost:8648/
```

A correct completion report states that the endpoint returned HTTP 200 and that the browser opener succeeded.
