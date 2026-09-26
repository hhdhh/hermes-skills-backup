# Review and Test Matrix

Use this as a compact checklist for safety-critical configuration orchestration.

| Invariant | Unit/component proof | Sandbox/VM proof |
|---|---|---|
| Dry-run is non-mutating | Mutation adapters never called; state/config/backup stores untouched | Before/after source and target tree hashes identical |
| Preflight fails closed | Inject FAIL and assert zero identity/network/settings calls | Missing required env/MAC exits before sudo or writes |
| Stage order is fixed | Selected stages resolve through dependency DAG | Command/event log matches expected order |
| Resume is trustworthy | Reject changed config/plan/host; stale RUNNING revalidated | Kill after each stage and resume from persisted state |
| Manual gates survive | Network activation and motion absent from automatic stage set | SSH activation rejected before backup/write; motion API never invoked |
| Rollback coverage is complete | Every mutation target has backup-or-created registration and allowlist acceptance | Apply, fail midway, recover; original bytes/modes restored |
| Reports are honest | Distinguish PREVIEW, DEFERRED, PASS, FAIL, WAITING_MANUAL | JSON survives interruption; no stage falsely marked success |
| Concurrent runs are excluded | Second lock acquisition fails | Two processes: exactly one mutates |
| Secrets stay private | Redaction and mode tests | State/report/backup permissions are 0600 under 0700 dirs |
| Review snapshot is stable | Manifest comparison helper detects change | Rerun affected checks when source SHA changes during review |

## Fault-injection points

Inject failure immediately before and after:

1. preflight completion
2. first identity write
3. identity completion
4. Netplan install
5. Netplan generation
6. network manual checkpoint creation
7. settings backup/write
8. final diagnosis/report write

For every point assert: no later stage ran, state is atomic/parseable, the original error is retained, backup metadata matches actual mutations, and recovery instructions are executable.
