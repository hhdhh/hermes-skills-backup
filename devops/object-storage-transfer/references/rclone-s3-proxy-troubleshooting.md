# rclone + S3-compatible storage proxy troubleshooting

Use this reference when DNS works but rclone hangs or TLS fails against a private/self-hosted S3 endpoint.

## Tight diagnostic loop

Replace the endpoint and remote name; do not expose credentials.

```bash
echo '== proxy env =='
env | grep -iE '^(http|https|all|no)_proxy=' || true

echo '== DNS =='
getent hosts endpoint.example.com || true

echo '== direct HTTPS =='
curl --noproxy '*' -kIsS --connect-timeout 10 --max-time 20 \
  'https://endpoint.example.com:8444/' | head -5

echo '== direct TCP =='
timeout 10 bash -c '</dev/tcp/endpoint.example.com/8444' \
  && echo reachable || echo unreachable

echo '== rclone without proxies =='
env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY \
    -u http_proxy -u https_proxy -u all_proxy \
  rclone lsd 'remote:' --no-check-certificate \
    --contimeout 10s --timeout 30s -vv
```

## Decision tree

### DNS fails

Investigate resolver/VPN/company-network access. Do not change rclone credentials yet.

### TCP direct fails

Escalate routing/firewall for destination host and port.

### Direct curl returns HTTP but proxy curl fails

The service is reachable; the proxy path is the problem. For S3 roots, HTTP 403 or 501 can still prove transport reachability because the request may be unauthenticated or use HEAD against an unsupported route.

### Direct rclone succeeds

Credentials, endpoint, and S3 compatibility are working. Configure proxy bypass:

```bash
export NO_PROXY="${NO_PROXY:+$NO_PROXY,}endpoint.example.com,IP_ADDRESS"
export no_proxy="$NO_PROXY"
```

For a wrapper that reliably bypasses proxy variables:

```bash
rclone-direct() {
  env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY \
      -u http_proxy -u https_proxy -u all_proxy \
    rclone "$@"
}
```

### Direct rclone fails

Read the final verbose error:

- `InvalidAccessKeyId`: wrong access key.
- `SignatureDoesNotMatch`: wrong secret, signing mismatch, or clock issue.
- `AccessDenied`: credentials valid but insufficient bucket/object permission.
- `RequestTimeTooSkewed`: repair NTP/time synchronization.
- `x509`: install the correct CA; use `--no-check-certificate` only as an explicit temporary workaround.

## Script design lesson

Do not hide stderr from the only connectivity probe. A friendly wrapper may print a short summary, but it should expose a verbose/debug mode or preserve the underlying rclone error so network, proxy, TLS, and credential failures remain distinguishable.
