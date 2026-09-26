#!/usr/bin/env python3
"""Batch-approve pending skills + memory writes via the OFFICIAL approval path
(same functions as `/skills approve all` and `/memory approve all`).

Usage:
  /home/kk/.hermes/hermes-agent/.venv/bin/python batch_approve_official.py

Applies in created_at order (oldest first) so chained patches replay in order.
Only discards from the queue on success; failures are kept pending — classify
them against the SKILL.md failure table and repair before re-running.
"""
import json
import sys

sys.path.insert(0, "/home/kk/.hermes/hermes-agent")

from tools import write_approval as wa                      # noqa: E402
from tools.memory_tool import (                              # noqa: E402
    load_on_disk_store, apply_memory_pending)
from tools.skill_manager_tool import apply_skill_pending     # noqa: E402

REPORT = "pending-approve-report.json"
report = {"skills": {"applied": [], "failed": []},
          "memory": {"applied": [], "failed": []}}

store = load_on_disk_store()

for subsystem in ("skills", "memory"):
    records = wa.list_pending(subsystem)  # sorted by created_at, oldest first
    print(f"[{subsystem}] pending={len(records)}")
    for rec in records:
        rid = rec["id"]
        payload = rec.get("payload", {})
        try:
            if subsystem == "memory":
                store.reset_consolidation_failures()  # avoid breaker cascade
                result = apply_memory_pending(payload, store)
            else:
                result = json.loads(apply_skill_pending(payload))
            if result.get("success"):
                wa.discard_pending(subsystem, rid)
                report[subsystem]["applied"].append(rid)
            else:
                err = str(result.get("error", ""))[:200]
                report[subsystem]["failed"].append(
                    {"id": rid, "error": err,
                     "summary": rec.get("summary", "")[:120]})
                print(f"  FAIL {rid}: {err}")
        except Exception as e:  # noqa: BLE001
            report[subsystem]["failed"].append(
                {"id": rid,
                 "error": f"{type(e).__name__}: {e}"[:200],
                 "summary": rec.get("summary", "")[:120]})
            print(f"  ERR  {rid}: {type(e).__name__}")
    print(f"[{subsystem}] applied={len(report[subsystem]['applied'])} "
          f"failed={len(report[subsystem]['failed'])}")

with open(REPORT, "w") as f:
    json.dump(report, f, ensure_ascii=False, indent=1)
print(f"\nreport -> {REPORT}")
print("remaining:", len(wa.list_pending("skills")), "skills /",
      len(wa.list_pending("memory")), "memory")
