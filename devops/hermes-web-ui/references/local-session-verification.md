# Local Hermes Web UI verification recipe

Observed working sequence on Linux:

1. Check status:
   `hermes-web-ui status`
2. Start without opening a second browser window:
   `hermes-web-ui start 8648 --no-open`
3. Verify both process state and HTTP reachability:
   `hermes-web-ui status`
   `curl -sS -o /dev/null -w '%{http_code}\\n' --max-time 5 http://localhost:8648`
4. Navigate the browser to `http://localhost:8648`.
5. Expected successful browser state: URL `http://localhost:8648/#/hermes/chat`, title `Hermes Studio`.

A stale browser tab can remain on `chrome-error://chromewebdata/` after the service was previously down. Re-navigate the same tab after the service is started; do not treat the stale error page as proof that the service is still unavailable.

In one verified run, the first browser navigation failed because the service was not listening. After starting the service, status reported `hermes-web-ui is running` and curl returned `200`; re-navigation then reached the Studio route successfully.
