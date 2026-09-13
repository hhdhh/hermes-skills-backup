#!/usr/bin/env python3
"""
Subconscious Loop — OpenHuman-inspired proactive reasoning for Huihui

Core responsibilities:
1. Background scan of recent memories and conversations
2. Identify pending tasks, risks, gaps, and opportunities
3. Generate "subconscious insights" without user prompting
4. Surface insights during heartbeats or session transitions
5. No external APIs — pure pattern analysis on local data

Unlike auto_fetch (which pulls external data), subconscious processes
what we ALREADY have and draws connections the user hasn't asked about.

Usage:
    python3 subconscious.py scan              # full background scan
    python3 subconscious.py insights             # show current insights
    python3 subconscious.py digest              # generate and display digest
"""

import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, TypedDict

# ─── Configuration ────────────────────────────────────────────────────────────

MEMORY_DIR = Path(os.path.expanduser("~/.openclaw/workspace/memory"))
WIKI_DIR = Path(os.path.expanduser("~/.openclaw/wiki/main"))
SESSION_STATE = Path(os.path.expanduser("~/.openclaw/workspace/SESSION-STATE.md"))
SUB_STATE = Path(os.path.expanduser("~/.openclaw/workspace/.subconscious_state.json"))

SCAN_WINDOW_DAYS = 7  # How far back to scan for patterns
MAX_INSIGHTS = 10

# ─── Insight Types ────────────────────────────────────────────────────────────

class Insight(TypedDict):
    type: str           # pending_task | risk | gap | opportunity | pattern | reminder
    title: str
    body: str
    confidence: float   # 0-1
    source: str          # file or system
    created_at: str

# ─── Pattern Detectors ────────────────────────────────────────────────────────

def detect_pending_tasks() -> list[Insight]:
    """
    Scan memory files for tasks that were mentioned but not confirmed complete.
    Looks for: 'TODO', '待办', '[ ]', '下一步', '还没', '还没做', etc.
    """
    insights = []
    
    if not MEMORY_DIR.exists():
        return insights
    
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=SCAN_WINDOW_DAYS)
    
    pending_patterns = [
        r'(TODO|待办|TODO:)',
        r'\[ \]',          # unchecked checkbox
        r'下一步',
        r'还没',
        r'还没做',
        r'没完成',
        r'应该做',
        r'记得.*要',
        r'要.*记得',
    ]
    
    import re
    
    for day_offset in range(SCAN_WINDOW_DAYS):
        date = now - timedelta(days=day_offset)
        date_str = date.strftime('%Y-%m-%d')
        filepath = MEMORY_DIR / f"{date_str}.md"
        
        if not filepath.exists():
            continue
        
        content = filepath.read_text(encoding='utf-8')
        
        for pattern in pending_patterns:
            matches = list(re.finditer(pattern, content, re.IGNORECASE))
            for m in matches:
                # Get context around the match
                start = max(0, m.start() - 100)
                end = min(len(content), m.end() + 100)
                context = content[start:end].strip()
                
                insights.append(Insight(
                    type="pending_task",
                    title=f"潜在待办（{date_str}）",
                    body=context,
                    confidence=0.6,
                    source=f"memory/{date_str}.md",
                    created_at=now.isoformat()
                ))
    
    # Deduplicate by body content
    seen = set()
    deduped = []
    for ins in insights:
        key = ins['body'][:50]
        if key not in seen:
            seen.add(key)
            deduped.append(ins)
    
    return deduped[:MAX_INSIGHTS]

def detect_recurring_patterns() -> list[Insight]:
    """
    Find things that appear repeatedly across multiple days —
    indicates importance or ongoing concern.
    """
    insights = []
    
    if not MEMORY_DIR.exists():
        return insights
    
    now = datetime.now(timezone.utc)
    
    # Scan last 14 days for recurring mentions
    word_freq = {}
    
    import re
    
    for day_offset in range(14):
        date = now - timedelta(days=day_offset)
        filepath = MEMORY_DIR / f"{date.strftime('%Y-%m-%d')}.md"
        
        if not filepath.exists():
            continue
        
        content = filepath.read_text(encoding='utf-8')
        
        # Extract significant words (3+ chars, skip common words)
        words = re.findall(r'[\w]{3,}', content.lower())
        
        stopwords = {'the', 'and', 'for', 'that', 'this', 'with', '你是', '你的', '已经', '没有', 
                     '什么', '这个', '那个', '可以', '一个', '主人', '慧慧', '就是', '还是'}
        
        for word in words:
            if word not in stopwords and len(word) > 2:
                word_freq[word] = word_freq.get(word, 0) + 1
    
    # Find words mentioned on 3+ different days
    recurring = {k: v for k, v in word_freq.items() if v >= 3 and v >= 3}
    
    for word, count in sorted(recurring.items(), key=lambda x: -x[1])[:5]:
        insights.append(Insight(
            type="pattern",
            title=f"反复出现的主题",
            body=f"「{word}」在过去14天内出现了 {count} 次，可能值得关注。",
            confidence=min(0.5 + count * 0.05, 0.95),
            source="memory/ (跨日分析)",
            created_at=datetime.now(timezone.utc).isoformat()
        ))
    
    return insights

def check_overdue_reminders() -> list[Insight]:
    """
    Check SESSION-STATE for pending actions that might be overdue.
    """
    insights = []
    
    if not SESSION_STATE.exists():
        return insights
    
    content = SESSION_STATE.read_text(encoding='utf-8')
    now = datetime.now(timezone.utc)
    
    import re
    
    # Look for dated items
    date_patterns = [
        r'(\d{4}-\d{2}-\d{2})[^\n]*',  # YYYY-MM-DD
        r'(今天|明天|本周|下周)[^\n]*',
    ]
    
    for pattern in date_patterns:
        matches = re.findall(pattern, content)
        for match in matches:
            # Check if it's in the past
            date_str = str(match)
            
            if '今天' in date_str:
                # Check if we've passed noon — today is half-gone
                if now.hour >= 14:
                    insights.append(Insight(
                        type="reminder",
                        title="今日事项提醒",
                        body=f"「{date_str}」相关条目在 SESSION-STATE 中，请确认是否已完成。",
                        confidence=0.7,
                        source="SESSION-STATE.md",
                        created_at=now.isoformat()
                    ))
    
    # Look for pending actions without completion
    pending_section = re.search(r'## Pending Actions\n(.*?)(?:\n##|\n---)', content, re.DOTALL)
    if pending_section:
        pending_text = pending_section.group(1)
        unchecked = re.findall(r'- \[ \] (.+)', pending_text)
        
        for item in unchecked[:3]:
            insights.append(Insight(
                type="pending_task",
                title="未完成的待办",
                body=item.strip(),
                confidence=0.8,
                source="SESSION-STATE.md",
                created_at=now.isoformat()
            ))
    
    return insights

def detect_memory_gaps() -> list[Insight]:
    """
    Identify topics the owner mentioned but we haven't followed up on.
    Eg: owner said "I want to learn X" but no memory of learning X happened.
    """
    insights = []
    now = datetime.now(timezone.utc)
    
    if not MEMORY_DIR.exists():
        return insights
    
    # Check recent memories for expressed interests without follow-up
    recent_files = sorted(MEMORY_DIR.glob("2026-*.md"), 
                          key=lambda p: p.stat().st_mtime, 
                          reverse=True)[:5]
    
    topics_mentioned = set()
    topics_followed_up = set()
    
    import re
    
    for filepath in recent_files:
        content = filepath.read_text(encoding='utf-8')
        
        # Topics mentioned
        topic_patterns = [
            r'(?:想学|想了解|对.*感兴趣|打算学|准备学)\s*(.{2,20})',
            r'(?:ROS2?|YOLO|SLAM|Navigation)[^\n]{0,50}',
        ]
        
        for pattern in topic_patterns:
            matches = re.findall(pattern, content)
            for m in matches:
                if isinstance(m, str):
                    topics_mentioned.add(m.strip()[:30])
        
        # Topics with follow-up (mentioned with progress/learning)
        follow_up_patterns = [r'学会了', r'已学', r'完成了', r'部署了', r'安装好']
        for pattern in follow_up_patterns:
            if re.search(pattern, content):
                # Extract what was learned
                for topic in topics_mentioned:
                    topics_followed_up.add(topic)
    
    # Topics mentioned but not followed up
    unfollowed = topics_mentioned - topics_followed_up
    
    for topic in list(unfollowed)[:3]:
        insights.append(Insight(
            type="gap",
            title="有提及未跟进",
            body=f"主人之前提到想了解「{topic}」，但还没有后续记录。",
            confidence=0.5,
            source="memory/ (gap analysis)",
            created_at=now.isoformat()
        ))
    
    return insights

# ─── State Management ────────────────────────────────────────────────────────

class SubconsciousState:
    def __init__(self):
        self.state_file = SUB_STATE
        self.data = self._load()
    
    def _load(self) -> dict:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except:
                pass
        return {
            "last_scan": None,
            "insights": [],
            "dismissed": []  # dismissed insight hashes
        }
    
    def save(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self.data, indent=2, ensure_ascii=False))
    
    def add_insight(self, insight: Insight):
        # Check if already dismissed
        key = hash(insight['body'][:50])
        if key in self.data.get('dismissed', []):
            return
        
        self.data.setdefault('insights', []).insert(0, insight)
        # Keep only last 20 insights
        self.data['insights'] = self.data['insights'][:20]
        self.save()
    
    def dismiss_insight(self, idx: int):
        if 0 <= idx < len(self.data.get('insights', [])):
            insight = self.data['insights'].pop(idx)
            self.data.setdefault('dismissed', []).append(hash(insight['body'][:50]))
            self.save()
    
    def clear_insights(self):
        self.data['insights'] = []
        self.save()

# ─── Main Scan ────────────────────────────────────────────────────────────────

def run_scan() -> list[Insight]:
    """Run all detectors and return consolidated insights"""
    print("[Subconscious] Running background scan...")
    
    all_insights = []
    
    print("[Subconscious]   Checking pending tasks...")
    all_insights.extend(detect_pending_tasks())
    
    print("[Subconscious]   Analyzing recurring patterns...")
    all_insights.extend(detect_recurring_patterns())
    
    print("[Subconscious]   Checking overdue reminders...")
    all_insights.extend(check_overdue_reminders())
    
    print("[Subconscious]   Detecting memory gaps...")
    all_insights.extend(detect_memory_gaps())
    
    # Sort by confidence
    all_insights.sort(key=lambda x: -x['confidence'])
    
    print(f"[Subconscious]   Found {len(all_insights)} insights")
    
    return all_insights

def generate_digest(insights: list[Insight]) -> str:
    """Generate a human-readable digest from insights"""
    if not insights:
        return "没有发现需要关注的事项。"
    
    digest = f"## 🧠 潜意识分析报告\n"
    digest += f"*{datetime.now().strftime('%Y-%m-%d %H:%M')} · {len(insights)} 项发现*\n\n"
    
    # Group by type
    by_type = {}
    for ins in insights:
        by_type.setdefault(ins['type'], []).append(ins)
    
    for ins_type, type_insights in by_type.items():
        labels = {
            'pending_task': '📋 待办事项',
            'risk': '⚠️ 风险提示',
            'gap': '🔍 认知缺口',
            'opportunity': '💡 机会发现',
            'pattern': '🔁 反复主题',
            'reminder': '⏰ 时间提醒',
        }
        digest += f"\n### {labels.get(ins_type, ins_type)}\n\n"
        
        for ins in type_insights[:3]:  # max 3 per type
            digest += f"- **{ins['title']}**\n"
            digest += f"  {ins['body'][:100]}{'...' if len(ins['body']) > 100 else ''}\n"
            digest += f"  _{ins['source']} · 置信度 {ins['confidence']:.0%}_\n\n"
    
    return digest

# ─── CLI Interface ───────────────────────────────────────────────────────────

def cmd_scan(args):
    state = SubconsciousState()
    
    insights = run_scan()
    
    # Store new insights
    for ins in insights:
        state.add_insight(ins)
    
    state.data['last_scan'] = datetime.now(timezone.utc).isoformat()
    state.save()
    
    if args.digest or args.verbose:
        digest = generate_digest(insights)
        print("\n" + digest)

def cmd_insights(args):
    state = SubconsciousState()
    insights = state.data.get('insights', [])
    
    if not insights:
        print("No insights yet. Run: subconscious.py scan")
        return
    
    print(f"=== Subconscious Insights ({len(insights)}) ===\n")
    print(f"Last scan: {state.data.get('last_scan', 'unknown')}\n")
    
    for i, ins in enumerate(insights):
        print(f"{i+1}. [{ins['type']}] {ins['title']}")
        print(f"   {ins['body'][:150]}{'...' if len(ins['body']) > 150 else ''}")
        print(f"   → {ins['source']} ({ins['confidence']:.0%})")
        print()

def cmd_digest(args):
    state = SubconsciousState()
    insights = state.data.get('insights', [])
    
    if not insights:
        # Run a fresh scan
        insights = run_scan()
        for ins in insights:
            state.add_insight(ins)
    
    print(generate_digest(insights))

def cmd_clear(args):
    state = SubconsciousState()
    state.clear_insights()
    print("Cleared all insights.")

def cmd_dismiss(args):
    state = SubconsciousState()
    state.dismiss_insight(args.index - 1)
    print(f"Dismissed insight #{args.index}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Subconscious Loop — Proactive reasoning for Huihui')
    subparsers = parser.add_subparsers(dest='command')
    
    scan_parser = subparsers.add_parser('scan', help='Run background scan for insights')
    scan_parser.add_argument('--digest', '-d', action='store_true', help='Show digest after scan')
    scan_parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    subparsers.add_parser('insights', help='Show current insights')
    subparsers.add_parser('digest', help='Generate digest from current insights')
    subparsers.add_parser('clear', help='Clear all insights')
    
    dismiss_parser = subparsers.add_parser('dismiss', help='Dismiss an insight by index')
    dismiss_parser.add_argument('index', type=int, help='Insight number to dismiss')
    
    args = parser.parse_args()
    
    if args.command == 'scan':
        cmd_scan(args)
    elif args.command == 'insights':
        cmd_insights(args)
    elif args.command == 'digest':
        cmd_digest(args)
    elif args.command == 'clear':
        cmd_clear(args)
    elif args.command == 'dismiss':
        cmd_dismiss(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
