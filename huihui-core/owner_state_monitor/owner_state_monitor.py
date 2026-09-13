#!/usr/bin/env python3
"""
Owner State Monitor — Huihui's task context tracker

Core responsibilities:
1. Track what owner is currently working on (from SESSION-STATE)
2. Monitor progress across sessions (from daily memory)
3. Detect when tasks go stale (not updated in X hours)
4. Generate proactive reminders via Feishu
5. Surface context at session start

Usage:
    python3 owner_state_monitor.py check          # check for stale tasks
    python3 owner_state_monitor.py context       # get current context for session
    python3 owner_state_monitor.py update "task" # manually note a task
    python3 owner_state_monitor.py status        # show full state
"""

import os
import re
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, TypedDict

# ─── Configuration ──────────────────────────────────────────────────────────────

MEMORY_DIR = Path(os.path.expanduser("~/.openclaw/workspace/memory"))
SESSION_STATE = Path(os.path.expanduser("~/.openclaw/workspace/SESSION-STATE.md"))
STATE_FILE = Path(os.path.expanduser("~/.openclaw/workspace/.owner_state.json"))
WIKI_DIR = Path(os.path.expanduser("~/.openclaw/wiki/main"))
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "")

STALE_HOURS = 4          # Task considered stale after this many hours
WATCH_WINDOW_DAYS = 14    # Look back this many days for context
MAX_CONTEXT_LINES = 50    # Max lines to include in context summary

# ─── Data Types ─────────────────────────────────────────────────────────────────

class Task(TypedDict):
    id: str
    description: str
    created_at: str
    last_updated: str
    status: str           # active | paused | complete | abandoned
    urgency: str           # high | medium | low
    source: str            # session_state | owner_said | self_inferred
    stale_after_hours: int  # when to consider it stale

# ─── State Management ───────────────────────────────────────────────────────────

class OwnerState:
    def __init__(self):
        self.state_file = STATE_FILE
        self.data = self._load()
    
    def _load(self) -> dict:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except:
                pass
        return {
            "current_task": None,
            "recent_tasks": [],
            "context_summary": "",
            "last_check": None,
            "reminders_sent": {}  # task_id → last_reminder_time
        }
    
    def save(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self.data, indent=2, ensure_ascii=False))
    
    def set_current_task(self, description: str, source: str = "session_state"):
        """Set the active task"""
        now = datetime.now(timezone.utc)
        
        task = Task(
            id=f"task_{now.strftime('%Y%m%d%H%M')}",
            description=description,
            created_at=now.isoformat(),
            last_updated=now.isoformat(),
            status="active",
            urgency="medium",
            source=source,
            stale_after_hours=STALE_HOURS
        )
        
        # Archive previous current task to recent
        if self.data.get("current_task"):
            self.data.setdefault("recent_tasks", []).insert(0, self.data["current_task"])
            self.data["recent_tasks"] = self.data["recent_tasks"][:10]  # Keep last 10
        
        self.data["current_task"] = task
        self.data["last_check"] = now.isoformat()
        self.save()
    
    def update_task(self, description: Optional[str] = None, status: Optional[str] = None,
                    urgency: Optional[str] = None):
        """Update current task"""
        if not self.data.get("current_task"):
            return
        
        now = datetime.now(timezone.utc).isoformat()
        
        if description:
            self.data["current_task"]["description"] = description
        if status:
            self.data["current_task"]["status"] = status
        if urgency:
            self.data["current_task"]["urgency"] = urgency
        
        self.data["current_task"]["last_updated"] = now
        self.data["last_check"] = now
        self.save()
    
    def mark_complete(self):
        """Mark current task as complete"""
        if self.data.get("current_task"):
            self.data["current_task"]["status"] = "complete"
            self.data["current_task"]["last_updated"] = datetime.now(timezone.utc).isoformat()
            self.save()
    
    def get_stale_tasks(self) -> list[dict]:
        """Find tasks that haven't been updated in a while"""
        stale = []
        now = datetime.now(timezone.utc)
        
        if self.data.get("current_task"):
            task = self.data["current_task"]
            if task.get("status") == "active":
                last_updated = datetime.fromisoformat(task["last_updated"].replace('Z', '+00:00'))
                hours_since = (now - last_updated).total_seconds() / 3600
                
                if hours_since >= task.get("stale_after_hours", STALE_HOURS):
                    task["hours_since_update"] = round(hours_since, 1)
                    stale.append(task)
        
        return stale
    
    def should_remind(self, task_id: str) -> bool:
        """Check if we should send a reminder for this task (rate-limited)"""
        last_reminder = self.data.get("reminders_sent", {}).get(task_id)
        
        if not last_reminder:
            return True
        
        last = datetime.fromisoformat(last_reminder.replace('Z', '+00:00'))
        hours_since_reminder = (datetime.now(timezone.utc) - last).total_seconds() / 3600
        
        # Don't send more than 1 reminder per 2 hours per task
        return hours_since_reminder >= 2
    
    def mark_reminder_sent(self, task_id: str):
        self.data.setdefault("reminders_sent", {})[task_id] = datetime.now(timezone.utc).isoformat()
        self.save()

# ─── Context Extraction ─────────────────────────────────────────────────────────

def extract_task_from_session_state() -> Optional[str]:
    """Read SESSION-STATE.md to find current task"""
    if not SESSION_STATE.exists():
        return None
    
    content = SESSION_STATE.read_text(encoding='utf-8')
    
    # Look for "Current Task" section
    match = re.search(r'## Current Task\s*\n(.*?)(?:\n##|\n---)', content, re.DOTALL)
    if match:
        task_text = match.group(1).strip()
        # Remove markdown artifacts
        task_text = re.sub(r'\[.*?\]\(.*?\)', '', task_text)
        task_text = re.sub(r'[-*]', '', task_text).strip()
        return task_text[:200] if task_text else None
    
    return None

def extract_task_from_daily_memory() -> list[dict]:
    """Scan recent daily memory for task mentions"""
    tasks = []
    now = datetime.now(timezone.utc)
    
    for day_offset in range(WATCH_WINDOW_DAYS):
        date = now - timedelta(days=day_offset)
        filepath = MEMORY_DIR / f"{date.strftime('%Y-%m-%d')}.md"
        
        if not filepath.exists():
            continue
        
        content = filepath.read_text(encoding='utf-8')
        
        # Look for task-like patterns
        patterns = [
            r'(?:正在做|在做|做.*?任务)[：:]\s*(.{5,80})',
            r'(?:下一步|接下来)[：:]\s*(.{5,80})',
            r'(?:TODO|FIXME|待办)[：:]\s*(.{5,80})',
            r'(?:W1|X1|机器人)[^\n]{0,30}(?:开发|代码|测试)[^\n]{0,30}',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for m in matches:
                if isinstance(m, str) and len(m) > 10:
                    tasks.append({
                        "text": m.strip()[:100],
                        "date": date.strftime('%Y-%m-%d'),
                        "source": "daily_memory"
                    })
    
    return tasks

def build_context_summary() -> str:
    """Build a compact context summary for session startup"""
    parts = []
    
    # Current task from session state
    current = extract_task_from_session_state()
    if current:
        parts.append(f"📌 当前任务：{current[:100]}")
    
    # Recent task mentions from daily memory
    recent_tasks = extract_task_from_daily_memory()[:5]
    if recent_tasks:
        parts.append("\n📋 最近任务相关：")
        seen = set()
        for t in recent_tasks:
            if t['text'][:50] not in seen:
                seen.add(t['text'][:50])
                parts.append(f"  • {t['text'][:80]}（{t['date']}）")
    
    # Recent lessons (top 3)
    try:
        import subprocess
        result = subprocess.run(
            ['python3', str(Path(__file__).parent.parent / 'self_improvement_loop' / 'self_improvement_loop.py'), 'recent', '--limit', '3'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            parts.append("\n🔴 最近教训：")
            for line in result.stdout.strip().split('\n'):
                if line.strip() and not line.startswith('===') and not line.startswith('Found'):
                    parts.append(f"  {line[:100]}")
    except:
        pass
    
    return '\n'.join(parts) if parts else ""

# ─── Notification ───────────────────────────────────────────────────────────────

def send_feishu_reminder(title: str, body: str):
    """Send a reminder via Feishu webhook"""
    if not FEISHU_WEBHOOK:
        print(f"[OwnerStateMonitor] Reminder (no webhook): {title}")
        print(f"  {body[:100]}")
        return
    
    try:
        import requests
        payload = {
            "msg_type": "text",
            "content": {"text": f"**{title}**\n{body}"}
        }
        resp = requests.post(FEISHU_WEBHOOK, json=payload, timeout=5)
        resp.raise_for_status()
        print(f"[OwnerStateMonitor] Reminder sent: {title}")
    except Exception as e:
        print(f"[OwnerStateMonitor] Feishu notification failed: {e}")

# ─── Main Check Loop ───────────────────────────────────────────────────────────

def run_check() -> list[dict]:
    """
    Run a periodic check for stale tasks.
    Called from heartbeat.
    Returns list of reminders that were sent.
    """
    state = OwnerState()
    
    # Update current task from session state
    session_task = extract_task_from_session_state()
    current_task = state.data.get("current_task") or {}
    if session_task and session_task != current_task.get("description"):
        state.set_current_task(session_task, source="session_state")
    
    # Check for stale tasks
    stale_tasks = state.get_stale_tasks()
    reminders_sent = []
    
    for task in stale_tasks:
        if state.should_remind(task["id"]):
            hours = task.get("hours_since_update", STALE_HOURS)
            
            reminder_body = (
                f"任务「{task['description'][:50]}...」已经 {hours} 小时没有更新了。\n"
                f"需要我帮你继续处理吗？还是已经完成了？"
            )
            
            send_feishu_reminder(
                title=f"⏰ 任务提醒（{hours}h 未更新）",
                body=reminder_body
            )
            
            state.mark_reminder_sent(task["id"])
            reminders_sent.append(task)
    
    return reminders_sent

# ─── CLI Interface ─────────────────────────────────────────────────────────────

def cmd_check(args):
    """Check for stale tasks and send reminders"""
    reminders = run_check()
    
    if not reminders:
        print("No stale tasks. Everything is fresh.")
    else:
        print(f"Sent reminders for {len(reminders)} stale task(s)")

def cmd_context(args):
    """Get context summary for session startup"""
    summary = build_context_summary()
    
    if not summary:
        print("No context available yet. Start working on something! 😄")
        return
    
    print("\n" + "="*60)
    print("📋 SESSION START — 上下文概要")
    print("="*60)
    print(summary)

def cmd_update(args):
    """Manually update current task"""
    state = OwnerState()
    state.set_current_task(args.task, source="manual")
    print(f"Updated current task: {args.task[:80]}")

def cmd_status(args):
    """Show full owner state"""
    state = OwnerState()
    
    print("\n=== Owner State Monitor ===\n")
    print(f"Last check: {state.data.get('last_check', 'never')}")
    
    current = state.data.get("current_task")
    if current:
        print(f"\n📌 Current Task: {current.get('description', 'N/A')}")
        print(f"   Status: {current.get('status', 'unknown')}")
        print(f"   Created: {current.get('created_at', 'N/A')}")
        print(f"   Last updated: {current.get('last_updated', 'N/A')}")
        print(f"   Source: {current.get('source', 'unknown')}")
        
        hours_since = (datetime.now(timezone.utc) - datetime.fromisoformat(current["last_updated"].replace('Z', '+00:00'))).total_seconds() / 3600
        print(f"   Hours since update: {hours_since:.1f}")
        
        if hours_since >= STALE_HOURS:
            print(f"   ⚠️  STALE — needs attention")
    else:
        print("\n📌 No current task set.")
    
    recent = state.data.get("recent_tasks", [])
    if recent:
        print(f"\n📋 Recent Tasks ({len(recent)}):")
        for t in recent[:5]:
            print(f"  • {t.get('description', 'N/A')[:70]} [{t.get('status')}]")
    
    reminders = state.data.get("reminders_sent", {})
    if reminders:
        print(f"\n📬 Reminders sent: {len(reminders)}")
        for tid, ts in list(reminders.items())[:5]:
            print(f"  {tid}: {ts[:16]}")

def cmd_complete(args):
    """Mark current task as complete"""
    state = OwnerState()
    state.mark_complete()
    print("Current task marked as complete.")

def cmd_clear(args):
    """Clear current task"""
    state = OwnerState()
    if state.data.get("current_task"):
        task = state.data.pop("current_task")
        state.data.setdefault("recent_tasks", []).insert(0, task)
        state.save()
        print("Cleared current task.")
    else:
        print("No current task to clear.")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Owner State Monitor — Task context tracker')
    subparsers = parser.add_subparsers(dest='command')
    
    subparsers.add_parser('check', help='Check for stale tasks and send reminders')
    subparsers.add_parser('context', help='Get context summary for session start')
    
    update_parser = subparsers.add_parser('update', help='Update current task')
    update_parser.add_argument('task', help='Task description')
    
    subparsers.add_parser('status', help='Show full owner state')
    subparsers.add_parser('complete', help='Mark current task as complete')
    subparsers.add_parser('clear', help='Clear current task')
    
    args = parser.parse_args()
    
    if args.command == 'check':
        cmd_check(args)
    elif args.command == 'context':
        cmd_context(args)
    elif args.command == 'update':
        cmd_update(args)
    elif args.command == 'status':
        cmd_status(args)
    elif args.command == 'complete':
        cmd_complete(args)
    elif args.command == 'clear':
        cmd_clear(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()