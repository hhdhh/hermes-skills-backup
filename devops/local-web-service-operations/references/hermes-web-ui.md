# Hermes Web UI launch recipe

Use this when the user's established meaning of “网页端” is the separately installed Hermes Web UI rather than the Hermes Agent dashboard.

## Known interface

```bash
hermes-web-ui status
hermes-web-ui start 8648 --no-open
hermes-web-ui stop
hermes-web-ui restart 8648
```

Canonical local URL:

```text
http://localhost:8648/
```

## Validated sequence

```bash
curl -fsS --max-time 5 -o /dev/null -w '%{http_code}\n' http://localhost:8648/
```

If unavailable, start the service with `hermes-web-ui start 8648 --no-open` as a managed background process. Poll until the URL returns HTTP 200 (or another intentional 2xx/3xx response), then run:

```bash
xdg-open http://localhost:8648/
```

A successful observed result was HTTP 200 followed by:

```text
正在现有的浏览器会话中打开。
```

When `xdg-open` is launched from a non-interactive shell, Bash may also print that it cannot set the terminal process group and that job control is unavailable. If the command exits 0 and reports opening in the existing browser session, those messages do not affect use.

## Reporting

A sufficient final report is:

```text
网页端已启动并打开：http://localhost:8648/
已验证 HTTP 200。
```

Do not include startup logs unless readiness failed.
