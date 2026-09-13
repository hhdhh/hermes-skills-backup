#!/usr/bin/env python3
"""OpenHarness heartbeat - run periodically to keep state in sync.

Tasks performed every heartbeat:
1. Sync ohmo memory ↔ wiki (via symlink, just verify)
2. Run `oh --dry-run` on a sample task to verify readiness
3. Check if any new skills have been added since last run
4. Report stats to SESSION-STATE.md

Usage:
    python heartbeat.py run             # do one heartbeat tick
    python heartbeat.py stats            # show last known stats
    python heartbeat.py reset            # reset state
"""
from __future__ import annotations
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime

WORKSPACE = Path.home() / ".openclaw/workspace"
SKILLS_DIR = WORKSPACE / "skills"
SESSION_STATE = WORKSPACE / "SESSION-STATE.md"
HEARTBEAT_STATE = Path.home() / ".ohmo" / "heartbeat-state.json"

def load_state() -> dict:
    if HEARTBEAT_STATE.exists():
        try: return json.loads(HEARTBEAT_STATE.read_text())
        except: pass
    return {"last_run": None, "last_skill_count": 0, "last_dry_run_status": None, "tick_count": 0}

def save_state(state: dict):
    HEARTBEAT_STATE.parent.mkdir(parents=True, exist_ok=True)
    HEARTBEAT_STATE.write_text(json.dumps(state, indent=2))

def discover_skill_dirs() -> list[str]:
    """Return list of skill dir names under ~/.openclaw/workspace/skills/."""
    return sorted([d.name for d in SKILLS_DIR.iterdir() if d.is_dir() and not d.name.startswith(('.', '_'))])

def run_dry_run() -> dict:
    """Run a sample dry-run to verify OpenHarness is healthy."""
    sys.path.insert(0, str(Path(__file__).parent))
    from wrapper import oh_dry_run
    return oh_dry_run("scan for new skills and tell me what's available")

def append_to_session_state(message: str):
    """Append a line to SESSION-STATE.md (WAL Protocol)."""
    if not SESSION_STATE.exists():
        return
    timestamp = datetime.now().isoformat(timespec="seconds")
    with SESSION_STATE.open("a") as f:
        f.write(f"\n[{timestamp}] 🦀 OpenHarness heartbeat: {message}\n")

def run_once(verbose: bool = True) -> dict:
    state = load_state()
    state["tick_count"] = state.get("tick_count", 0) + 1
    state["last_run"] = datetime.now().isoformat()
    
    # 1. Skill discovery
    skills = discover_skill_dirs()
    new_count = len(skills)
    delta = new_count - state.get("last_skill_count", 0)
    
    # 2. Dry-run check
    try:
        preview = run_dry_run()
        dry_status = preview.get("readiness", "unknown")
        dry_model = preview.get("model")
        dry_skills = preview.get("skills_count", 0)
    except Exception as e:
        dry_status = f"error: {e}"
        dry_model = None
        dry_skills = None
    state["last_dry_run_status"] = dry_status
    
    # 3. Report
    summary = {
        "tick": state["tick_count"],
        "skills_local": new_count,
        "skills_delta": delta,
        "openharness_skills": dry_skills,
        "dry_run_status": dry_status,
        "model": dry_model,
    }
    state["last_summary"] = summary
    save_state(state)
    
    if verbose:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    
    # 4. Log to SESSION-STATE.md if anything notable
    if dry_status != "ready":
        append_to_session_state(f"dry-run status: {dry_status}")
    elif delta != 0:
        append_to_session_state(f"skills changed: {state['last_skill_count']} → {new_count} (Δ{delta:+d})")
    
    state["last_skill_count"] = new_count
    save_state(state)
    return summary

def show_stats():
    state = load_state()
    print(json.dumps(state, indent=2, ensure_ascii=False))

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run").add_argument("--quiet", action="store_true")
    sub.add_parser("stats")
    sub.add_parser("reset")
    args = ap.parse_args()
    if args.cmd == "run":
        run_once(verbose=not args.quiet)
    elif args.cmd == "stats":
        show_stats()
    elif args.cmd == "reset":
        if HEARTBEAT_STATE.exists():
            HEARTBEAT_STATE.unlink()
        print("heartbeat state reset")

if __name__ == "__main__":
    main()
