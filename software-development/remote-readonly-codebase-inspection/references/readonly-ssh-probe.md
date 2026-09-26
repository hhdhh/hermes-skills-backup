# Read-only SSH probe reference

## Minimal password-authenticated wrapper

Use a short-lived `pexpect` client when no password helper is available. Run a bounded remote command, match `password:`, send the password only through the live child process, capture bytes, and decode for display. Do not write the password into a script or shell history.

```python
child = pexpect.spawn(
    'ssh',
    ['-o', 'StrictHostKeyChecking=accept-new', '-o', 'ConnectTimeout=10',
     'ubuntu@HOST', remote_command],
    encoding=None,
    timeout=60,
)
# expect password / EOF / TIMEOUT; send password only on password prompt
# decode child.before with .decode('utf-8', 'replace') for display
```

## Safe Python syntax probe

`python3 -m py_compile target.py` is not read-only because it may create `__pycache__`. Prefer:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('/absolute/target.py')
compile(p.read_text(encoding='utf-8'), str(p), 'exec')
print('syntax: PASS')
PY
```

## Evidence collection

- `stat -c '%n | %s bytes | %y | %A' target.py`
- `find "$(dirname "$p")" -maxdepth 1 -type f ...` for same-directory companions
- `grep -nE '^\s*(from|import) ' target.py` for imports
- targeted `grep` for local filenames and `Path`/subprocess references
- bounded `find` or a remote Python `os.walk` to verify exact referenced artifacts

When quoting predicates through SSH becomes fragile, use a small remote Python script or a simple filename search. Prefer a narrower trustworthy result to a broad command whose escaping is ambiguous.
