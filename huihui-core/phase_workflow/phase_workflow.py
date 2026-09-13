#!/usr/bin/env python3
"""
Phase Workflow — OpenHuman-inspired staged task execution framework for Huihui

Core responsibilities:
1. Decompose complex tasks into explicit phases with guard conditions
2. Each phase has: goal, completion criteria, rollback plan
3. No skipping phases — must meet completion criteria to advance
4. Surface blockers early rather than discovering them late
5. Human-in-the-loop for ambiguous decisions

Based on the PR Manager / Ship & Babysit patterns from OpenHuman's .agents/

Usage:
    python3 phase_workflow.py init "Build W1 controller" --phases 4
    python3 phase_workflow.py advance --phase 2
    python3 phase_workflow.py status
    python3 phase_workflow.py checkpoint "before refactor"
"""

import os
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, TypedDict

# ─── Configuration ───────────────────────────────────────────────────────────

WORKFLOW_DIR = Path(os.path.expanduser("~/.openclaw/workspace/.workflows"))
STATE_FILE = WORKFLOW_DIR / "active_workflow.json"
CHECKPOINT_DIR = WORKFLOW_DIR / "checkpoints"

# ─── Data Structures ─────────────────────────────────────────────────────────

class Phase(TypedDict):
    number: int
    name: str
    goal: str
    completion_criteria: list[str]   # Must ALL be true to advance
    blockers: list[str]             # Current blockers
    status: str                    # pending | in_progress | complete | blocked
    started_at: Optional[str]
    completed_at: Optional[str]
    notes: str                     # Current working notes for this phase

class Workflow(TypedDict):
    id: str
    name: str
    description: str
    created_at: str
    phases: list[Phase]
    current_phase: int            # 1-indexed
    status: str                   # planning | active | paused | complete | abandoned
    checkpoints: list[str]         # checkpoint IDs

# ─── State Management ─────────────────────────────────────────────────────────

class WorkflowState:
    def __init__(self):
        self.state_file = STATE_FILE
        self.checkpoint_dir = CHECKPOINT_DIR
        self.data = self._load()
    
    def _load(self) -> dict:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except:
                pass
        return {"active_workflow": None, "history": []}
    
    def save(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self.data, indent=2, ensure_ascii=False))
    
    def create_workflow(self, name: str, description: str, num_phases: int) -> Workflow:
        """Create a new workflow with specified number of phases"""
        
        # Default phase templates
        phase_templates = [
            {"name": "理解目标", "goal": "彻底理解任务需求，识别所有约束条件", "criteria": ["grill-me 已追问完毕", "需求文档化", "没有歧义项"]},
            {"name": "制定计划", "goal": "制定分步骤实施计划，识别依赖和技术风险", "criteria": ["计划文档化", "风险已识别", "技术方案确定"]},
            {"name": "执行", "goal": "按计划实施，完成每个子步骤", "criteria": ["核心代码完成", "自测通过", "无紧急blocker"]},
            {"name": "验证", "goal": "验证结果满足原始需求，清理收尾", "criteria": ["功能验证完成", "文档已更新", "无遗留问题"]},
        ]
        
        phases = []
        for i in range(num_phases):
            if i < len(phase_templates):
                t = phase_templates[i]
                phase = Phase(
                    number=i + 1,
                    name=t["name"],
                    goal=t["goal"],
                    completion_criteria=t["criteria"],
                    blockers=[],
                    status="pending",
                    started_at=None,
                    completed_at=None,
                    notes=""
                )
            else:
                phase = Phase(
                    number=i + 1,
                    name=f"Phase {i+1}",
                    goal="",
                    completion_criteria=[],
                    blockers=[],
                    status="pending",
                    started_at=None,
                    completed_at=None,
                    notes=""
                )
            phases.append(phase)
        
        import uuid
        wf = Workflow(
            id=str(uuid.uuid4())[:8],
            name=name,
            description=description,
            created_at=datetime.now(timezone.utc).isoformat(),
            phases=phases,
            current_phase=1,
            status="active",
            checkpoints=[]
        )
        
        wf["phases"][0]["status"] = "in_progress"
        wf["phases"][0]["started_at"] = datetime.now(timezone.utc).isoformat()
        
        self.data["active_workflow"] = wf
        self.save()
        
        return wf
    
    def get_workflow(self) -> Optional[Workflow]:
        return self.data.get("active_workflow")
    
    def update_phase(self, phase_num: int, updates: dict):
        wf = self.get_workflow()
        if not wf:
            return
        
        for phase in wf["phases"]:
            if phase["number"] == phase_num:
                phase.update(updates)
                break
        
        self.save()
    
    def advance_phase(self) -> tuple[bool, str]:
        """
        Attempt to advance to next phase.
        Returns (success, message).
        Checks completion criteria for current phase.
        """
        wf = self.get_workflow()
        if not wf:
            return False, "No active workflow"
        
        current_idx = wf["current_phase"] - 1
        current = wf["phases"][current_idx]
        
        if current["status"] == "blocked":
            return False, f"Phase {phase_num} is blocked. Resolve blockers first."
        
        # Check completion criteria
        if current["completion_criteria"]:
            unmet = [c for c in current["completion_criteria"] if not c.endswith("(done)")]
            if unmet:
                return False, f"Phase {wf['current_phase']} not ready to advance. Unmet criteria:\n  - " + "\n  - ".join(unmet)
        
        # Complete current phase
        current["status"] = "complete"
        current["completed_at"] = datetime.now(timezone.utc).isoformat()
        
        # Move to next phase
        if wf["current_phase"] < len(wf["phases"]):
            wf["current_phase"] += 1
            next_phase = wf["phases"][wf["current_phase"] - 1]
            next_phase["status"] = "in_progress"
            next_phase["started_at"] = datetime.now(timezone.utc).isoformat()
            self.save()
            return True, f"Advanced to Phase {wf['current_phase']}: {next_phase['name']}"
        else:
            wf["status"] = "complete"
            self.save()
            return True, "Workflow complete! All phases finished."
    
    def add_blocker(self, phase_num: int, blocker: str):
        wf = self.get_workflow()
        if not wf:
            return
        
        for phase in wf["phases"]:
            if phase["number"] == phase_num:
                phase["blockers"].append(blocker)
                if phase["status"] == "in_progress":
                    phase["status"] = "blocked"
                break
        
        self.save()
    
    def resolve_blocker(self, phase_num: int, blocker: str):
        wf = self.get_workflow()
        if not wf:
            return
        
        for phase in wf["phases"]:
            if phase["number"] == phase_num:
                if blocker in phase["blockers"]:
                    phase["blockers"].remove(blocker)
                if not phase["blockers"] and phase["status"] == "blocked":
                    phase["status"] = "in_progress"
                break
        
        self.save()
    
    def create_checkpoint(self, name: str) -> str:
        """Snapshot current workflow state"""
        wf = self.get_workflow()
        if not wf:
            raise ValueError("No active workflow")
        
        import uuid
        ckpt_id = str(uuid.uuid4())[:8]
        ckpt = {
            "id": ckpt_id,
            "name": name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "workflow_snapshot": dict(wf)
        }
        
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        (self.checkpoint_dir / f"{ckpt_id}.json").write_text(
            json.dumps(ckpt, indent=2, ensure_ascii=False)
        )
        
        wf["checkpoints"].append(ckpt_id)
        self.save()
        
        return ckpt_id
    
    def list_checkpoints(self) -> list[dict]:
        if not self.checkpoint_dir.exists():
            return []
        
        checkpoints = []
        for f in sorted(self.checkpoint_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(f.read_text())
                checkpoints.append({
                    "id": data["id"],
                    "name": data["name"],
                    "created_at": data["created_at"],
                    "workflow_name": data["workflow_snapshot"]["name"],
                    "phase": data["workflow_snapshot"]["current_phase"]
                })
            except:
                pass
        
        return checkpoints

# ─── CLI Interface ───────────────────────────────────────────────────────────

def cmd_init(args):
    state = WorkflowState()
    
    if state.get_workflow():
        print("⚠️  Active workflow exists. Complete or abandon it first.")
        print(f"   Current: {state.get_workflow()['name']} (Phase {state.get_workflow()['current_phase']})")
        response = input("Abandon and start new? [y/N] ")
        if response.lower() != 'y':
            return
    
    wf = state.create_workflow(args.name, args.description or "", args.phases)
    
    print(f"\n✅ Workflow created: {wf['name']} ({wf['id']})")
    print(f"   {len(wf['phases'])} phases\n")
    
    for phase in wf["phases"]:
        marker = "👉" if phase["status"] == "in_progress" else "  "
        print(f"{marker} Phase {phase['number']}: {phase['name']}")
        print(f"    Goal: {phase['goal']}")
        if phase["completion_criteria"]:
            print(f"    Criteria:")
            for c in phase["completion_criteria"]:
                print(f"      □ {c}")
        print()

def cmd_status(args):
    state = WorkflowState()
    wf = state.get_workflow()
    
    if not wf:
        print("No active workflow. Create one: phase_workflow.py init <name>")
        return
    
    print(f"\n{'='*60}")
    print(f"Workflow: {wf['name']} [{wf['id']}]")
    print(f"Status: {wf['status']} | Current: Phase {wf['current_phase']}/{len(wf['phases'])}")
    print(f"{'='*60}\n")
    
    for phase in wf["phases"]:
        if phase["status"] == "in_progress":
            marker = "👉"
        elif phase["status"] == "complete":
            marker = "✅"
        elif phase["status"] == "blocked":
            marker = "🚫"
        else:
            marker = "  "
        
        print(f"{marker} Phase {phase['number']}: {phase['name']} [{phase['status']}]")
        
        if phase["status"] == "in_progress":
            print(f"    Goal: {phase['goal']}")
            if phase["completion_criteria"]:
                print(f"    Completion criteria:")
                for c in phase["completion_criteria"]:
                    done = "□" if c.endswith("(done)") else "□"
                    print(f"      {done} {c}")
            if phase["blockers"]:
                print(f"    ⚠️  Blockers:")
                for b in phase["blockers"]:
                    print(f"      - {b}")
            if phase["notes"]:
                print(f"    Notes: {phase['notes'][:100]}")
        
        print()
    
    if wf["checkpoints"]:
        print(f"Checkpoints: {', '.join(wf['checkpoints'])}")

def cmd_advance(args):
    state = WorkflowState()
    success, msg = state.advance_phase()
    
    if success:
        print(f"✅ {msg}")
    else:
        print(f"❌ {msg}")

def cmd_block(args):
    state = WorkflowState()
    wf = state.get_workflow()
    
    if not wf:
        print("No active workflow.")
        return
    
    state.add_blocker(wf["current_phase"], args.blocker)
    print(f"Added blocker to Phase {wf['current_phase']}: {args.blocker}")

def cmd_resolve(args):
    state = WorkflowState()
    wf = state.get_workflow()
    
    if not wf:
        print("No active workflow.")
        return
    
    state.resolve_blocker(wf["current_phase"], args.blocker)
    print(f"Resolved blocker: {args.blocker}")

def cmd_note(args):
    state = WorkflowState()
    wf = state.get_workflow()
    
    if not wf:
        print("No active workflow.")
        return
    
    phase_num = args.phase or wf["current_phase"]
    state.update_phase(phase_num, {"notes": args.text})
    print(f"Note saved for Phase {phase_num}")

def cmd_checkpoint(args):
    state = WorkflowState()
    
    ckpt_id = state.create_checkpoint(args.name)
    print(f"✅ Checkpoint created: {ckpt_id} - {args.name}")
    
    if args.restore:
        # Load and apply checkpoint
        ckpt_file = state.checkpoint_dir / f"{ckpt_id}.json"
        if ckpt_file.exists():
            ckpt = json.loads(ckpt_file.read_text())
            # For now just report — full restore needs careful thought
            print(f"   (restore not yet implemented — checkpoint is saved)")

def cmd_list_checkpoints(args):
    state = WorkflowState()
    checkpoints = state.list_checkpoints()
    
    if not checkpoints:
        print("No checkpoints yet.")
        return
    
    print("=== Checkpoints ===\n")
    for ckpt in checkpoints:
        print(f"{ckpt['id']} | {ckpt['name']}")
        print(f"    {ckpt['workflow_name']} · Phase {ckpt['phase']} · {ckpt['created_at']}")
        print()

def cmd_abandon(args):
    state = WorkflowState()
    wf = state.get_workflow()
    
    if not wf:
        print("No active workflow.")
        return
    
    state.data["history"].append(dict(wf))
    state.data["active_workflow"] = None
    state.save()
    
    print(f"Abandoned workflow: {wf['name']}")

def cmd_complete(args):
    state = WorkflowState()
    wf = state.get_workflow()
    
    if not wf:
        print("No active workflow.")
        return
    
    wf["status"] = "complete"
    state.save()
    
    print(f"Marked complete: {wf['name']}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Phase Workflow — Staged task execution framework')
    subparsers = parser.add_subparsers(dest='command')
    
    init_parser = subparsers.add_parser('init', help='Initialize a new workflow')
    init_parser.add_argument('name', help='Workflow name')
    init_parser.add_argument('--description', '-d', help='Workflow description')
    init_parser.add_argument('--phases', '-n', type=int, default=4, help='Number of phases')
    
    subparsers.add_parser('status', help='Show current workflow status')
    subparsers.add_parser('advance', help='Advance to next phase (checks criteria)')
    
    block_parser = subparsers.add_parser('block', help='Add a blocker to current phase')
    block_parser.add_argument('blocker', help='Blocker description')
    
    resolve_parser = subparsers.add_parser('resolve', help='Resolve a blocker')
    resolve_parser.add_argument('blocker', help='Blocker to resolve')
    
    note_parser = subparsers.add_parser('note', help='Add note to current phase')
    note_parser.add_argument('text', help='Note text')
    note_parser.add_argument('--phase', '-p', type=int, help='Phase number')
    
    ckpt_parser = subparsers.add_parser('checkpoint', help='Create a checkpoint')
    ckpt_parser.add_argument('name', help='Checkpoint name')
    ckpt_parser.add_argument('--restore', '-r', action='store_true', help='Also restore this checkpoint')
    
    subparsers.add_parser('list-checkpoints', help='List all checkpoints')
    subparsers.add_parser('abandon', help='Abandon current workflow')
    subparsers.add_parser('complete', help='Mark workflow as complete')
    
    args = parser.parse_args()
    
    if args.command == 'init':
        cmd_init(args)
    elif args.command == 'status':
        cmd_status(args)
    elif args.command == 'advance':
        cmd_advance(args)
    elif args.command == 'block':
        cmd_block(args)
    elif args.command == 'resolve':
        cmd_resolve(args)
    elif args.command == 'note':
        cmd_note(args)
    elif args.command == 'checkpoint':
        cmd_checkpoint(args)
    elif args.command == 'list-checkpoints':
        cmd_list_checkpoints(args)
    elif args.command == 'abandon':
        cmd_abandon(args)
    elif args.command == 'complete':
        cmd_complete(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
