# Command Matrix Format

Use a JSON array. Each row declares its expectation before execution.

```json
[
  {
    "id": "root-help",
    "argv": ["bash", "./tool.sh", "--config", "./config.example.json", "--help"],
    "command": "./tool.sh --config ./config.example.json --help",
    "category": "help",
    "expected_exit": 0,
    "reason": "Root help must be reachable",
    "timeout": 15
  },
  {
    "id": "preflight",
    "argv": ["bash", "./tool.sh", "--config", "./config.example.json", "check"],
    "category": "diagnostic",
    "expected_exit": 2,
    "reason": "The non-target host intentionally lacks the required runtime"
  }
]
```

`expected_exits` may replace `expected_exit` only when more than one outcome is genuinely allowed by the documented contract. Prefer one exact expected code when host context predicts it.

Run the matrix through Hermes `terminal`:

```text
python <skill-dir>/scripts/run_command_matrix.py \
  /tmp/cli-audit/matrix.json \
  --output /tmp/cli-audit/results.json \
  --cwd /path/to/project \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --env HOME=/tmp/cli-audit/home
```

The harness supplies EOF on stdin, uses argument arrays rather than a shell, records real integer exit codes, and marks timeouts as exit `124`. Its summary checks process exits and crash markers only; the auditor must separately evaluate semantic output, fixtures, artifacts, and side effects.

## Recommended Row Fields

- `id`: stable unique identifier.
- `argv`: exact argument array; required.
- `command`: human-readable rendering.
- `category`: `help`, `read-only`, `dry-run`, `diagnostic`, `fixture`, or `artifact`.
- `expected_exit` / `expected_exits`: declared before execution.
- `reason`: why the expected result follows from the contract and host context.
- `timeout`: per-row override.
- Optional auditor-side fields: required markers, forbidden markers, allowed write root, fixture classification.

## Final Aggregation Rules

1. Keep exploratory probes out of the authoritative matrix.
2. Assert every authoritative row has an integer `exit`.
3. Classify semantic false positives as unexpected even if `is_expected_exit` is true.
4. Generate totals from `results.json`.
5. Ensure each row is counted once and only once.
