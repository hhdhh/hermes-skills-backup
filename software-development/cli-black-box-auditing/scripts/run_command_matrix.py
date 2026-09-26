#!/usr/bin/env python3
"""Run a JSON-defined CLI command matrix without shell expansion."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

CRASH_RE = re.compile(
    r"Traceback \(most recent call last\)|Segmentation fault|core dumped",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("matrix", type=Path, help="JSON matrix file")
    parser.add_argument("--output", type=Path, required=True, help="result JSON path")
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--default-timeout", type=float, default=30.0)
    parser.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="environment override; repeat as needed",
    )
    return parser.parse_args()


def load_matrix(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("matrix must be a JSON array")
    for index, row in enumerate(data, 1):
        if not isinstance(row, dict):
            raise SystemExit(f"row {index} must be an object")
        argv = row.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
            raise SystemExit(f"row {index}.argv must be a non-empty string array")
        expected = row.get("expected_exit")
        if isinstance(expected, int):
            row["expected_exits"] = [expected]
        elif isinstance(row.get("expected_exits"), list) and all(
            isinstance(x, int) for x in row["expected_exits"]
        ):
            pass
        else:
            raise SystemExit(f"row {index} needs expected_exit or expected_exits")
    return data


def main() -> int:
    args = parse_args()
    rows = load_matrix(args.matrix)
    env = os.environ.copy()
    for item in args.env:
        if "=" not in item:
            raise SystemExit(f"invalid --env value: {item!r}")
        key, value = item.split("=", 1)
        env[key] = value

    results: list[dict[str, Any]] = []
    for index, row in enumerate(rows, 1):
        argv = row["argv"]
        timeout = float(row.get("timeout", args.default_timeout))
        started = time.monotonic()
        timed_out = False
        try:
            completed = subprocess.run(
                argv,
                cwd=args.cwd,
                env=env,
                input="",
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
            exit_code = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = 124
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""

        combined = stdout + "\n" + stderr
        expected_exits = row["expected_exits"]
        results.append(
            {
                "id": row.get("id", index),
                "command": row.get("command", " ".join(argv)),
                "argv": argv,
                "category": row.get("category", "actual"),
                "expected_exits": expected_exits,
                "reason": row.get("reason", ""),
                "exit": exit_code,
                "is_expected_exit": exit_code in expected_exits,
                "duration_s": round(time.monotonic() - started, 3),
                "timed_out": timed_out,
                "crash_marker": bool(CRASH_RE.search(combined)),
                "stdout": stdout,
                "stderr": stderr,
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = {
        "total": len(results),
        "expected_exit": sum(item["is_expected_exit"] for item in results),
        "unexpected_exit": [
            {"command": item["command"], "exit": item["exit"], "reason": item["reason"]}
            for item in results
            if not item["is_expected_exit"]
        ],
        "timeouts": [item["command"] for item in results if item["timed_out"]],
        "crash_markers": [item["command"] for item in results if item["crash_marker"]],
        "output": str(args.output),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not summary["unexpected_exit"] and not summary["timeouts"] and not summary["crash_markers"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
