# Systemd + WebSocket + Proxy Read-only Checklist

Use this when a remote user service reports WebSocket opening-handshake timeouts.

## Service and journal

```bash
export SYSTEMD_PAGER=cat PAGER=cat
systemctl --user status SERVICE --no-pager -l
systemctl --user cat SERVICE --no-pager
systemctl --user show SERVICE \
  -p FragmentPath -p ExecStart -p WorkingDirectory \
  -p Environment -p MainPID -p ActiveState -p SubState \
  -p Result -p NRestarts -p ExecMainCode -p ExecMainStatus
journalctl --user -u SERVICE --since 'TIME' --no-pager -o short-precise
```

## Runtime proxy state

```bash
pid=$(systemctl --user show SERVICE -p MainPID --value)
tr '\0' '\n' < /proc/$pid/environ 2>/dev/null \
  | grep -E '^(VPN_SOCKS_PROXY_URL|ALL_PROXY|HTTPS_PROXY|HTTP_PROXY|NO_PROXY)='
ss -lntp
```

Redact all values before returning output. Check configuration separately for an enable flag and URL. A URL in a TOML/YAML file does not mean the application uses it.

## Network layers

```bash
ip -brief addr
ip route
resolvectl status
getent ahostsv4 PROVIDER_HOST
timeout 5 bash -c '</dev/tcp/PROVIDER_HOST/443'
curl -4 -sS -o /dev/null --connect-timeout 5 --max-time 8 \
  -w 'remote_ip=%{remote_ip} http=%{http_code} connect=%{time_connect} tls=%{time_appconnect} err=%{errormsg}\n' \
  https://PROVIDER_HOST/
```

Probe the exact `wss://` endpoint when source/config reveals it. Generic provider HTTPS success is only a lower-layer control.

## Interpretation matrix

| Evidence | Interpretation |
|---|---|
| Local signaling WebSocket connected; cloud realtime socket timed out | Separate channels; local success does not clear cloud path |
| Proxy URL configured; enable flag false | Configured but intentionally inactive |
| Proxy enabled/injected; address refuses connection | No listener or wrong address |
| TCP/TLS provider domain works; opening handshake times out | Investigate exact WSS path, region, headers/auth, and application client |
| Journal says `Stopping`; exit is TERM; `Result=success` | Explicit external stop, not crash |
| VAD flushes buffered chunks after connection failure | Usually downstream audio behavior, not proof of network cause |

## Scope guard

In inspect-only mode, do not run `restart`, `stop`, `start`, `enable`, `daemon-reload`, package managers, editors, redirects, or remote temp-file creation. If state changes independently, report the timestamp and evidence without guessing who initiated it.
