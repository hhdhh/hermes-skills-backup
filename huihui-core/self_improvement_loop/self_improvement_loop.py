#!/usr/bin/env python3
"""
Self-Improvement Loop — Huihui's automatic lesson learning system

Core responsibilities:
1. Record every correction, mistake, and feedback from owner
2. Build a lessons database that persists across sessions
3. Pre-session injection: read relevant lessons before answering
4. Pattern detection: what types of mistakes recur most often

Usage (internal):
    from self_improvement_loop import record_lesson
    record_lesson("mistake", "混淆了 W1 和 X1 的坐标系统", "owner_correction")

Pre-session call:
    python3 self_improvement_loop.py pre_session
    python3 self_improvement_loop.py recent_lessons --limit 5
    python3 self_improvement_loop.py patterns

Record a lesson:
    python3 self_improvement_loop.py record --type mistake --content "..." --tag robot
"""

import os
import re
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, TypedDict

# ─── Configuration ────────────────────────────────────────────────────────────

LESSONS_FILE = Path(os.path.expanduser("~/.openclaw/workspace/memory/lessons.md"))
SELF_STATE = Path(os.path.expanduser("~/.openclaw/workspace/.self_improvement_state.json"))

MAX_LESSONS = 500  # Keep last 500 lessons
SIMILARITY_THRESHOLD = 0.7  # Don't record near-duplicate lessons

# ─── Data Types ────────────────────────────────────────────────────────────────

class Lesson(TypedDict):
    id: str
    type: str           # mistake | correction | insight | preference | decision
    content: str
    tags: list[str]
    source: str         # owner_correction | owner_preference | self_noticed | pattern_detected
    created_at: str
    recall_count: int   # how many times this was relevant
    last_recalled: Optional[str]

LESSON_TYPE_LABELS = {
    'mistake': '🔴 我的错误',
    'correction': '🔧 纠正记录',
    'insight': '💡 领悟',
    'preference': '❤️ 主人偏好',
    'decision': '📋 决策记录',
}

# ─── Lesson Storage ────────────────────────────────────────────────────────────

class LessonsDatabase:
    """Append-only lessons database stored as Markdown"""
    
    def __init__(self):
        self.lessons_file = LESSONS_FILE
        self.state_file = SELF_STATE
        self.state = self._load_state()
    
    def _load_state(self) -> dict:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except:
                pass
        return {"lesson_ids": [], "by_tag": {}, "by_type": {}}
    
    def _save_state(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self.state, indent=2))
    
    def _generate_id(self) -> str:
        """Generate short unique ID from timestamp"""
        ts = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
        return f"les_{ts}"
    
    def _compute_similarity(self, content1: str, content2: str) -> float:
        """Simple similarity based on word overlap"""
        words1 = set(re.findall(r'\w{3,}', content1.lower()))
        words2 = set(re.findall(r'\w{3,}', content2.lower()))
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)
    
    def _append_to_file(self, lesson: Lesson):
        """Append lesson to Markdown file with proper formatting"""
        self.lessons_file.parent.mkdir(parents=True, exist_ok=True)
        
        entry = f"""

### {lesson['id']} · {LESSON_TYPE_LABELS.get(lesson['type'], lesson['type'])} · {lesson['created_at'][:10]}

**标签:** {', '.join(lesson['tags']) if lesson['tags'] else '无'}
**来源:** {lesson['source']}

{lesson['content']}

---
"""
        
        if not self.lessons_file.exists():
            header = f"""# 慧慧的教训记录

> 自动记录主人每一次纠正和反馈
> 每次新会话开始前读取，避免重复犯错
> 上次更新：{datetime.now().strftime('%Y-%m-%d %H:%M')}

"""
            self.lessons_file.write_text(header + entry, encoding='utf-8')
        else:
            existing = self.lessons_file.read_text(encoding='utf-8')
            self.lessons_file.write_text(existing + entry, encoding='utf-8')
    
    def record(self, content: str, lesson_type: str = 'mistake',
               tags: Optional[list[str]] = None,
               source: str = 'owner_correction',
               auto_tag: bool = True) -> tuple[bool, str]:
        """
        Record a new lesson.
        Returns (is_new, message).
        """
        content = content.strip()
        if len(content) < 5:
            return False, "Content too short to record"
        
        # Check for near-duplicate against recent lessons
        recent_ids = self.state.get("lesson_ids", [])[-20:]
        for lid in reversed(recent_ids):
            # Read from file to check similarity
            if self.lessons_file.exists():
                content_of_file = self.lessons_file.read_text(encoding='utf-8')
                # Find the lesson content in file
                if lid in content_of_file:
                    # Extract surrounding context (rough)
                    idx = content_of_file.find(lid)
                    if idx >= 0:
                        snippet = content_of_file[idx:idx+500]
                        if self._compute_similarity(content, snippet) > SIMILARITY_THRESHOLD:
                            return False, f"Near-duplicate of recent lesson, skipping"
        
        # Generate ID and create lesson
        lesson_id = self._generate_id()
        lesson = Lesson(
            id=lesson_id,
            type=lesson_type,
            content=content,
            tags=tags or [],
            source=source,
            created_at=datetime.now(timezone.utc).isoformat(),
            recall_count=0,
            last_recalled=None
        )
        
        # Auto-tag based on content patterns
        if auto_tag and not tags:
            auto_tags = []
            
            # Detect topic
            topic_patterns = {
                'w1': ['W1', '机器人', 'Dexforce', '二次开发'],
                'ros': ['ROS', 'ROS2', '导航', 'SLAM'],
                'code': ['代码', '编程', 'Python', '错误', 'bug'],
                'memory': ['记忆', 'wiki', 'MEMORY', '忘记'],
                'mail': ['邮件', '飞书', '邮件'],
                'preference': ['喜欢', '偏好', '不要', '不要做'],
            }
            
            for tag, keywords in topic_patterns.items():
                if any(kw in content for kw in keywords):
                    auto_tags.append(tag)
            
            lesson['tags'] = auto_tags or ['general']
        
        # Append to file
        self._append_to_file(lesson)
        
        # ─── 进化引擎 Hook (2026-06-18 主人授权自主维护) ─────────
        # 把 lesson 同步为 fitness signal，让达尔文式进化有数据
        try:
            import sys
            from pathlib import Path
            _workspace = Path.home() / '.openclaw' / 'workspace'
            if str(_workspace) not in sys.path:
                sys.path.insert(0, str(_workspace))
            from evolution.bridge import on_lesson_recorded
            on_lesson_recorded(
                lesson_type=lesson_type,
                content=content,
                tags=lesson.get('tags', []),
            )
        except Exception as _e:
            # 进化引擎 hook 失败不能阻止 lesson 记录
            pass
        
        # Update state
        self.state.setdefault("lesson_ids", []).append(lesson_id)
        
        # Trim old lessons from state
        if len(self.state["lesson_ids"]) > MAX_LESSONS:
            self.state["lesson_ids"] = self.state["lesson_ids"][-MAX_LESSONS:]
        
        # Update tag index
        for tag in lesson['tags']:
            self.state.setdefault("by_tag", {}).setdefault(tag, []).append(lesson_id)
        
        self.state.setdefault("by_type", {}).setdefault(lesson_type, []).append(lesson_id)
        
        self._save_state()
        
        return True, f"Recorded: {lesson_id}"
    
    def get_recent_lessons(self, limit: int = 5, lesson_type: Optional[str] = None,
                           tag: Optional[str] = None) -> list[Lesson]:
        """Get recent lessons, optionally filtered"""
        if not self.lessons_file.exists():
            return []
        
        content = self.lessons_file.read_text(encoding='utf-8')
        
        # Parse from file (reverse order = newest first)
        lessons = []
        
        # Find all lesson blocks (### les_...)
        blocks = re.split(r'\n### les_', content)
        
        for block in reversed(blocks[1:]):  # skip header
            try:
                parts = block.split('\n', 1)
                if len(parts) < 2:
                    continue
                
                id_part = parts[0].split(' · ')[0]
                rest = parts[1]
                
                # Extract metadata line
                meta_match = re.match(r'([^·]+) · ([^·]+) · (\d{4}-\d{2}-\d{2})', rest)
                if meta_match:
                    lt_label = meta_match.group(1).strip()
                    source = meta_match.group(2).strip()
                    date = meta_match.group(3)
                    
                    # Map label back to type
                    type_from_label = {v: k for k, v in LESSON_TYPE_LABELS.items()}.get(lt_label, 'mistake')
                    
                    # Extract content between metadata and ---
                    content_match = re.search(r'\n---\n(.*?)(?:\n---|\Z)', rest, re.DOTALL)
                    body_content = content_match.group(1).strip() if content_match else rest[:300]
                    
                    # Extract tags
                    tags_match = re.search(r'\*\*标签:\*\* (.+)', rest)
                    lesson_tags = []
                    if tags_match:
                        tag_str = tags_match.group(1).replace('无', '').strip()
                        if tag_str:
                            lesson_tags = [t.strip() for t in tag_str.split(',')]
                    
                    # Apply filters
                    if tag and tag not in lesson_tags:
                        continue
                    if lesson_type and type_from_label != lesson_type:
                        continue
                    
                    lessons.append(Lesson(
                        id=f"les_{id_part}",
                        type=type_from_label,
                        content=body_content[:500],
                        tags=lesson_tags,
                        source=source,
                        created_at=date,
                        recall_count=0,
                        last_recalled=None
                    ))
                
                if len(lessons) >= limit:
                    break
            except:
                continue
        
        return lessons[:limit]
    
    def mark_recalled(self, lesson_id: str):
        """Record that a lesson was used in a session"""
        if lesson_id in self.state.get("lesson_ids", []):
            # We don't track recall counts in state for simplicity
            # Just update last_recalled in file if needed
            pass

    def get_patterns(self) -> dict:
        """Analyze lesson patterns"""
        if not self.lessons_file.exists():
            return {"top_tags": [], "top_types": [], "total": 0}
        
        lessons = self.get_recent_lessons(limit=100)
        
        if not lessons:
            return {"top_tags": [], "top_types": [], "total": 0}
        
        # Count tags
        tag_counts = {}
        type_counts = {}
        
        for lesson in lessons:
            for tag in lesson.get('tags', []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
            lt = lesson.get('type', 'unknown')
            type_counts[lt] = type_counts.get(lt, 0) + 1
        
        return {
            "top_tags": sorted(tag_counts.items(), key=lambda x: -x[1])[:10],
            "top_types": sorted(type_counts.items(), key=lambda x: -x[1]),
            "total": len(lessons)
        }

# ─── Convenience Functions ────────────────────────────────────────────────────

_db = None

def record_lesson(content: str, lesson_type: str = 'mistake',
                  tags: Optional[list[str]] = None,
                  source: str = 'owner_correction') -> tuple[bool, str]:
    """
    Record a lesson. Call this from anywhere in Huihui's code.
    
    Triggers:
    - Owner says "不对"、"不是这样"、"错了"
    - Owner corrects something I did
    - I notice a recurring mistake
    
    Usage in code:
        from self_improvement_loop import record_lesson
        record_lesson("我把 W1 的坐标系搞反了", "mistake", tags=["w1"])
    """
    global _db
    if _db is None:
        _db = LessonsDatabase()
    return _db.record(content, lesson_type, tags, source)

# ─── CLI Interface ────────────────────────────────────────────────────────────

def cmd_record(args):
    db = LessonsDatabase()
    is_new, msg = db.record(
        content=args.content,
        lesson_type=args.type or 'mistake',
        tags=args.tags.split(',') if args.tags else None,
        source=args.source or 'manual'
    )
    print(msg)

def cmd_pre_session(args):
    """Called at session start — output relevant lessons for current context"""
    db = LessonsDatabase()
    
    limit = args.limit or 5
    lessons = db.get_recent_lessons(limit=limit)
    
    if not lessons:
        print("No lessons recorded yet.")
        return
    
    print(f"\n📖 教训记录（最近 {len(lessons)} 条，上次更新前必读）\n")
    
    for lesson in lessons:
        type_label = LESSON_TYPE_LABELS.get(lesson['type'], lesson['type'])
        print(f"  [{type_label}] {lesson['content'][:120]}")
        if lesson.get('tags'):
            print(f"    标签: {', '.join(lesson['tags'])}")
        print()

def cmd_recent(args):
    db = LessonsDatabase()
    lessons = db.get_recent_lessons(limit=args.limit or 10, 
                                      lesson_type=args.type,
                                      tag=args.tag)
    
    if not lessons:
        print("No lessons found.")
        return
    
    print(f"=== Recent Lessons ({len(lessons)}) ===\n")
    for lesson in lessons:
        print(f"{lesson['id']} | {lesson['type']} | {lesson['created_at'][:10]}")
        print(f"  {lesson['content'][:150]}")
        if lesson.get('tags'):
            print(f"  Tags: {', '.join(lesson['tags'])}")
        print()

def cmd_patterns(args):
    db = LessonsDatabase()
    patterns = db.get_patterns()
    
    if patterns['total'] == 0:
        print("No lessons recorded yet.")
        return
    
    print(f"=== Lesson Patterns ({patterns['total']} lessons analyzed) ===\n")
    
    print("Top Tags:")
    for tag, count in patterns['top_tags'][:8]:
        print(f"  {tag}: {count}")
    
    print("\nBy Type:")
    for lt, count in patterns['top_types']:
        label = LESSON_TYPE_LABELS.get(lt, lt)
        print(f"  {label}: {count}")

def cmd_grep(args):
    """Search lessons by keyword"""
    db = LessonsDatabase()
    lessons = db.get_recent_lessons(limit=100)
    
    matched = [l for l in lessons if args.keyword.lower() in l['content'].lower()]
    
    if not matched:
        print(f"No lessons matching: {args.keyword}")
        return
    
    print(f"Found {len(matched)} lessons:\n")
    for lesson in matched[:args.limit or 10]:
        print(f"[{lesson['type']}] {lesson['content'][:150]}")
        print()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Self-Improvement Loop — Automatic lesson learning')
    subparsers = parser.add_subparsers(dest='command')
    
    record_parser = subparsers.add_parser('record', help='Record a new lesson')
    record_parser.add_argument('--content', '-c', required=True, help='Lesson content')
    record_parser.add_argument('--type', '-t', choices=['mistake', 'correction', 'insight', 'preference', 'decision'], help='Lesson type')
    record_parser.add_argument('--tags', help='Comma-separated tags')
    record_parser.add_argument('--source', '-s', help='Source: owner_correction, owner_preference, self_noticed, pattern_detected, manual')
    
    pre_session_parser = subparsers.add_parser('pre_session', help='Output lessons for session startup')
    pre_session_parser.add_argument('--limit', '-n', type=int, default=5, help='Number of lessons')
    pre_session_parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    subparsers.add_parser('patterns', help='Show lesson patterns')
    
    recent_parser = subparsers.add_parser('recent', help='Show recent lessons')
    recent_parser.add_argument('--limit', '-n', type=int, default=10, help='Number of lessons')
    recent_parser.add_argument('--type', '-t', help='Filter by type')
    recent_parser.add_argument('--tag', help='Filter by tag')
    
    grep_parser = subparsers.add_parser('grep', help='Search lessons by keyword')
    grep_parser.add_argument('keyword', help='Search keyword')
    grep_parser.add_argument('--limit', '-n', type=int, default=10, help='Max results')
    
    args = parser.parse_args()
    
    if args.command == 'record':
        cmd_record(args)
    elif args.command == 'pre_session':
        cmd_pre_session(args)
    elif args.command == 'recent':
        cmd_recent(args)
    elif args.command == 'patterns':
        cmd_patterns(args)
    elif args.command == 'grep':
        cmd_grep(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()