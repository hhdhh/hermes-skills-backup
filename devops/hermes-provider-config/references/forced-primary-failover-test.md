# Forced primary failover test — proving fallback actually triggers

The only reliable way to confirm a Hermes fallback chain actually cuts over (vs just being written to config.yaml).

## Why this is necessary

- `hermes fallback list` confirms the YAML loaded
- `hermes chat -m <fallback-entry-model>` confirms the fallback entry *can* answer
- Neither tells you that, **when the primary dies mid-call**, Hermes automatically uses the fallback

Without this test, a "configured" fallback can sit there for months — silently broken because no one ever actually hit the trigger condition.

## The test recipe (verified 2026-08-14)

Goal: make the primary call fail for sure, then verify a real Hermes subprocess still returns a response (i.e. the fallback took it).

### Step 1: register a deliberately broken primary

Add a temporary alias whose base URL and model ID both don't exist:

```bash
hermes config set model.aliases.test-broken-primary "provider: custom
model: nonexistent-model-999
base_url: https://this-domain-does-not-exist.invalid/v1
key_env: YOUR_EXISTING_VALID_KEY"
```

Key points:
- The base URL must resolve to NXDOMAIN or connection-refused — Hermes should give up after the connection fails
- The model ID must not exist on the fallback provider either (otherwise it might accidentally succeed for the wrong reason)
- The `key_env` should be a valid one (so the fallback, which uses the same key, can still authenticate)

### Step 2: run hermes chat pointing at the broken primary

```bash
hermes chat -m test-broken-primary -q "fallback test, just reply OK"
```

Expected: ~5-15 seconds of failure attempts against the bad host, then a successful response. The duration depends on how aggressive Hermes' retry/backoff is for connection errors.

### Step 3: confirm the response came from the fallback

- **Worst check**: just observe that a response arrived at all (it couldn't have come from the broken primary)
- **Better check**: in the test prompt, ask for a token the *fallback* provider is known to produce (e.g. a signature phrase, a specific language, a tool-call style)
- **Best check**: temporarily disable the fallback (`hermes config unset fallback_providers` step), re-run step 2, observe that now it fails completely — proving the success in step 2 was due to fallback, not some other mechanism

### Step 4: clean up

```bash
hermes config unset model.aliases.test-broken-primary
```

## What "passed" looks like in real output

Real transcript from 2026-08-14 (primary: nonexistent-model at invalid domain; fallback: gpt-5.5 at sub2api proxy):

```
$ hermes chat -m test-broken-primary -q "fallback test, just reply OK"
⚠️  Context file AGENTS.md TRUNCATED: 80689 chars exceeds limit of 61440

╭─ ⚕ Hermes ───────────────────────────────────────────────────────────────────╮
OK
╰──────────────────────────────────────────────────────────────────────────────────╯

Session:        20260814_220910_bb9fa5
Title:          Fallback test reply ok
Duration:       6s
```

6-second total, "OK" arrived. The broken-primary path provably failed; the response came from the fallback chain.

## Variations

- **Rate-limit test**: register a primary alias pointing at a proxy you control and have it return 429 for the test prompt. Same recipe.
- **5xx test**: same, return 500/502/503. Hermes' fallback triggers on rate-limit, overload, and connection errors (per `hermes fallback --help`).
- **Auth-error test**: temporarily set the `key_env` to a wrong key. **Caveat**: Hermes may treat auth errors as non-retryable — the fallback might not trigger. Test this case separately if it matters for your deployment.

## What this test does NOT prove

- That the fallback chain is correctly ordered (if you have multiple entries, only the first one gets exercised here)
- That the fallback is reached within a particular latency budget
- That Hermes' failure detection catches every error class your real primary might emit (it doesn't — see `hermes fallback --help` for the supported trigger conditions)

For ordering: register multiple fallback entries and run separate broken-primary tests pointing at each one in turn (change the temporary alias's model ID).