# Remote systemd license-validation failures

Use this sequence when a remote service starts, emits a license/authentication error, exits, and is restarted by systemd.

## Evidence-first probe

1. Capture unit status, source, effective `ExecStart`, working directory, environment-file paths, and recent precise logs. Redact secret values.
2. Trace the license and public-key paths from the exact config passed by `ExecStart`.
3. Check existence, mode, size, modification time, and SHA-256 of the config, license, and public key. Presence and readability do not prove validity.
4. Prefer the product's own offline verifier as the tight feedback loop. Read its `--help`, run it against the exact configured files, and retain its real exit code and diagnostic.
5. If the deployment bundle contains another public key, test both configured and bundled keys. This distinguishes a stale configured key from a license not signed by either expected key.
6. Run the vendor fingerprint/HWID helper and compare with the server log.
7. Build a timestamp timeline for binary, config, unit, license, and first failure.

## Interpret carefully

- Missing file or permission error: deployment/access issue.
- Cryptographic signature equation failure: wrong signing key, altered/truncated file, or incompatible license format/version. It does **not** prove HWID mismatch.
- Valid signature followed by fingerprint failure: correctly signed for another machine identity.
- Manual success but systemd failure: compare user, working directory, effective environment, and path resolution.

Applications sometimes combine several causes into one message such as “HWID mismatch or tampered license.” Prefer the direct verifier's narrower result over repeating the combined message as a proven diagnosis.

## Restart-loop distinction

`Restart=always` and `RestartSec=` explain repeated logs and increasing restart counters; they are not the root application failure. Temporarily stopping the unit can suppress noise only when operational interruption is authorized.

## Credential hygiene for remote probes

Never print passwords, license bodies, private keys, tokens, or database URLs. Use an approved SSH credential mechanism. If a temporary askpass helper is unavoidable, make it mode `0700`, avoid logging its contents, and delete it immediately afterward.

## Completion evidence

Include the service version, observed HWID, configured paths, direct verifier output and exit code, alternate-key comparison, relevant timestamps, and the concrete remaining requirement—for example, reissuance by the holder of the matching private key. Do not claim a fix when only the diagnosis was verified.