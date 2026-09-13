# OAuth Device Flow handoff (Lark/Feishu CLI)

Exact end-to-end recipe for binding a lark-cli app to an agent workspace and authorizing it via the CLI's designed-for-agents handoff pattern.

## The pattern in one line

```text
config bind (once) → auth login --no-wait --json (get URL) → END TURN →
[user clicks URL / scans QR in their browser] → auth login --device-code (poll) → verify
```

The CLI literally instructs the agent to do this in the `--no-wait --json` response. Follow the instruction.

## Step-by-step

### Phase A: Bind (one-shot, in this turn)

```bash
lark-cli config bind \
  --source hermes \
  --app-id "cli_xxxxxxxx" \
  --identity user-default \
  --force 2>&1 | tail -10
```

Expect: `{"ok":true, "replaced":false, "workspace":"hermes", ...}` plus a hint pointing at `auth login --recommend`. The bind is non-blocking and fast.

Bind writes `~/.lark-cli/hermes/config.json` with the app id and identity mode. Don't re-bind unless the app changes (use `config strict-mode` for policy-only changes).

### Phase B: Get URL, end turn

```bash
# CRITICAL: --no-wait means don't block, --json means machine-readable
lark-cli auth login --no-wait --json --recommend
```

The response is JSON:

```json
{
  "device_code": "OzbqAbAwyy...truncated...",
  "verification_url": "https://accounts.feishu.cn/oauth/v1/device/verify?flow_id=ONMIRtcb...&user_code=ULFD-JFNU",
  "expires_in": 600,
  "hint": "**MUST generate QR code AND display it:** ..."
}
```

Extract:
- `device_code` — save it for Phase D
- `verification_url` — send to user
- `expires_in` — usually 600s (10 min). If user takes longer, re-run Phase B.

**End the turn here.** The CLI's hint will literally tell you to. Polling `auth login --device-code` in the same turn defeats the pattern.

### Phase C: User authorizes

Two paths the user can take:

1. **Desktop browser**: open `verification_url` → log in to Feishu → click "Agree" (同意授权)
2. **Mobile Feishu App**: scan QR code (generated in optional Phase B')

If generating a QR for mobile:

```bash
mkdir -p /tmp/lark-qr && cd /tmp/lark-qr
lark-cli auth qrcode "<verification_url>" -o qr.png --size 512
# Display the PNG inline in your response
```

Then `END TURN`. Wait for user confirmation.

### Phase D: Poll & complete (in the user's next turn)

```bash
lark-cli auth login --device-code "<device_code_from_phase_B>"
```

This **blocks** until either:
- User completes authorization → CLI prints success + token info
- `expires_in` (600s) elapses → CLI prints timeout error

If timeout, re-run Phase B for a fresh `device_code` + `verification_url`. Don't cache device codes across runs.

### Phase E: Verify

```bash
lark-cli auth status    # shows the authorized user + scopes
lark-cli config show    # confirms app binding still valid
lark-cli calendar +agenda   # calls a +shortcut to exercise the user-data path
```

If `+agenda` returns real calendar data, the full chain works. If it returns a scope error, the app needs more scopes enabled + re-published + re-authorized (start over from Phase B).

## Common mistakes

| Mistake | Fix |
|---|---|
| `auth login` without `--no-wait` | Use `--no-wait --json` to get the URL, end turn, then `--device-code` to complete |
| Trying to navigate to the URL with `browser_navigate` etc. | The auth must happen in the user's browser, not the agent's. Send the URL, don't open it |
| Caching `device_code` across runs | Re-run `--no-wait` each time you need a fresh code |
| Running `--device-code` before user confirms | Wait. The CLI's hint says "After the user confirms authorization: YOU must execute `--device-code`" — it means after they've clicked Agree |
| Forgetting to `cd /tmp/lark-qr` before `qrcode -o` | The `-o` flag requires a relative path within the current working directory |

## What to do if it breaks

| Symptom | Likely cause | Fix |
|---|---|---|
| `auth login --device-code` returns "authorization_pending" forever | User hasn't clicked yet, or clicked but not consented | Wait, or ask user to re-check the browser tab |
| Returns "expired_token" | `device_code` expired (10 min) | Re-run `--no-wait --json` for fresh URL |
| Returns "invalid_scope" | App config missing scopes the `--recommend` mode asked for | Re-add scopes to the app at https://open.feishu.cn/app, republish, re-bind, restart from Phase B |
| QR code generated but user says it doesn't scan | `qrcode --output` rejected absolute path; PNG is at a relative path under cwd | `cd` first, then check the actual generated path |
| `auth login --no-wait` itself errors | Likely `--recommend` scope mismatch or app not yet published | Run `lark-cli config show` to confirm binding; check app version is published |