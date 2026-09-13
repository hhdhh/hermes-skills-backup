#!/usr/bin/env python3
"""
Memory Tree — OpenHuman-inspired structured memory storage for Huihui

Core responsibilities:
1. Store memory chunks with topic + time scoring
2. Build hierarchical tree structure (topic × time)
3. Auto-generate summary nodes
4. Export to Obsidian-compatible Markdown
5. Support semantic retrieval

Usage:
    python3 memory_tree.py add --content "..." --topic "preference" --time "2026-05-20"
    python3 memory_tree.py query --topic "preference" --limit 5
    python3 memory_tree.py build_tree  # rebuild summary tree
    python3 memory_tree.py export     # export to Obsidian format
"""

import os
import json
import sqlite3
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, TypedDict

# ─── Configuration ────────────────────────────────────────────────────────────

WIKI_DIR = Path(os.path.expanduser("~/.openclaw/wiki/main"))
TREE_DB = WIKI_DIR / "memory_tree.db"
MEMORY_DIR = Path(os.path.expanduser("~/.openclaw/workspace/memory"))

# ─── Schema ───────────────────────────────────────────────────────────────────

class MemoryEntry(TypedDict):
    id: str
    content: str
    topic: str
    time_str: str  # ISO format
    topic_score: float  # 0-1, how strongly it matches topic
    recency_score: float  # 0-1, time decay
    combined_score: float  # weighted sum
    chunk_index: int  # which chunk this belongs to
    created_at: str

def init_db():
    """Initialize SQLite database with memory tree schema"""
    TREE_DB.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(TREE_DB))
    conn.execute('''
        CREATE TABLE IF NOT EXISTS memory_tree (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            topic TEXT NOT NULL,
            time_str TEXT NOT NULL,
            topic_score REAL DEFAULT 0.5,
            recency_score REAL DEFAULT 0.5,
            combined_score REAL DEFAULT 0.5,
            chunk_index INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            embedding_id TEXT  -- for vector search integration
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS summary_nodes (
            topic TEXT PRIMARY KEY,
            summary TEXT NOT NULL,
            last_updated TEXT NOT NULL,
            child_ids TEXT  -- JSON array of child memory IDs
        )
    ''')
    
    conn.execute('CREATE INDEX IF NOT EXISTS idx_topic ON memory_tree(topic)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_combined ON memory_tree(combined_score DESC)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_time ON memory_tree(time_str DESC)')
    
    conn.commit()
    return conn

def compute_recency_score(time_str: str) -> float:
    """
    Exponential decay based on age.
    Score = e^(-λ * days_since)
    Half-life of 30 days: λ = ln(2)/30 ≈ 0.023
    """
    try:
        dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
    except:
        dt = datetime.now(timezone.utc)
    
    now = datetime.now(timezone.utc)
    days_since = (now - dt).total_seconds() / 86400
    
    half_life_days = 30
    return 2 ** (-days_since / half_life_days)

def compute_topic_score(content: str, topic: str) -> float:
    """
    Simple keyword matching for topic scoring.
    In production, use embeddings cosine similarity.
    """
    content_lower = content.lower()
    topic_lower = topic.lower()
    
    # Direct keyword matches
    words = topic_lower.replace('_', ' ').split()
    matches = sum(1 for w in words if w in content_lower)
    
    if not words:
        return 0.5
    
    base_score = matches / len(words)
    
    # Bonus for topic keyword appearing near start
    first_200 = content_lower[:200]
    early_bonus = 0.1 if any(w in first_200 for w in words if len(w) > 3) else 0
    
    return min(1.0, base_score + early_bonus)

# ─── Memory Operations ────────────────────────────────────────────────────────

def add_memory(conn: sqlite3.Connection, content: str, topic: str, time_str: Optional[str] = None,
               chunk_index: int = 0, embedding_id: Optional[str] = None) -> str:
    """Add a new memory entry to the tree"""
    
    if time_str is None:
        time_str = datetime.now(timezone.utc).isoformat()
    
    memory_id = hashlib.sha256(f"{content[:100]}{time_str}".encode()).hexdigest()[:16]
    
    topic_score = compute_topic_score(content, topic)
    recency_score = compute_recency_score(time_str)
    combined_score = 0.6 * topic_score + 0.4 * recency_score  # topic-weighted
    
    conn.execute('''
        INSERT OR REPLACE INTO memory_tree 
        (id, content, topic, time_str, topic_score, recency_score, combined_score, chunk_index, created_at, embedding_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (memory_id, content, topic, time_str, topic_score, recency_score, 
          combined_score, chunk_index, datetime.now(timezone.utc).isoformat(), embedding_id))
    
    conn.commit()
    return memory_id

def query_memories(conn: sqlite3.Connection, topic: Optional[str] = None, 
                   limit: int = 10, min_score: float = 0.3) -> list[MemoryEntry]:
    """Query memories by topic (or all), ordered by combined score"""
    
    if topic:
        sql = '''
            SELECT * FROM memory_tree 
            WHERE combined_score >= ? AND topic = ?
            ORDER BY combined_score DESC LIMIT ?
        '''
        rows = conn.execute(sql, (min_score, topic, limit)).fetchall()
    else:
        sql = '''
            SELECT * FROM memory_tree 
            WHERE combined_score >= ?
            ORDER BY combined_score DESC LIMIT ?
        '''
        rows = conn.execute(sql, (min_score, limit)).fetchall()
    
    return [MemoryEntry(
        id=row[0], content=row[1], topic=row[2], time_str=row[3],
        topic_score=row[4], recency_score=row[5], combined_score=row[6],
        chunk_index=row[7], created_at=row[8]
    ) for row in rows]

def build_tree(conn: sqlite3.Connection) -> dict:
    """
    Build summary tree from memories grouped by topic.
    Returns tree structure with summaries.
    """
    topics = conn.execute('SELECT DISTINCT topic FROM memory_tree').fetchall()
    topics = [t[0] for t in topics]
    
    tree = {}
    for topic in topics:
        # Get all memories for this topic, sorted by time
        memories = conn.execute('''
            SELECT content, time_str, combined_score 
            FROM memory_tree 
            WHERE topic = ?
            ORDER BY time_str DESC
        ''', (topic,)).fetchall()
        
        if not memories:
            continue
        
        # Generate summary (simple: concatenate first sentences up to limit)
        summary_parts = []
        total_len = 0
        for mem in memories:
            content = mem[0]
            # Take first 100 chars of each memory for summary
            excerpt = content[:100].strip()
            if excerpt:
                summary_parts.append(excerpt)
                total_len += len(excerpt)
                if total_len > 500:
                    break
        
        summary = ' | '.join(summary_parts) if summary_parts else '(no memories)'
        
        # Update summary node
        child_ids = [hashlib.sha256(m[0].encode()).hexdigest()[:16] for m in memories[:10]]
        
        conn.execute('''
            INSERT OR REPLACE INTO summary_nodes (topic, summary, last_updated, child_ids)
            VALUES (?, ?, ?, ?)
        ''', (topic, summary, datetime.now(timezone.utc).isoformat(), json.dumps(child_ids)))
        
        tree[topic] = {
            "summary": summary,
            "count": len(memories),
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
    
    conn.commit()
    return tree

# ─── Obsidian Export ───────────────────────────────────────────────────────────

def export_to_obsidian(conn: sqlite3.Connection, output_dir: Optional[Path] = None):
    """
    Export memories as Obsidian-compatible Markdown files.
    Creates topic folders with memory notes.
    """
    if output_dir is None:
        output_dir = WIKI_DIR / "memories"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    topics = conn.execute('SELECT DISTINCT topic FROM memory_tree').fetchall()
    
    for (topic,) in topics:
        topic_dir = output_dir / topic.replace('_', '-')
        topic_dir.mkdir(exist_ok=True)
        
        memories = conn.execute('''
            SELECT content, time_str, combined_score 
            FROM memory_tree 
            WHERE topic = ?
            ORDER BY time_str DESC
        ''', (topic,)).fetchall()
        
        # Create index file for this topic
        index_content = f"# {topic.replace('_', ' ').title()}\n\n"
        index_content += f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        index_content += f"Total memories: {len(memories)}\n\n"
        
        for i, mem in enumerate(memories):
            filename = f"{mem[1][:10]}_{i+1}.md"
            filepath = topic_dir / filename
            
            mem_content = f"""---
date: {mem[1]}
score: {mem[2]:.3f}
topic: {topic}
---

{mem[0]}

---
*Auto-generated by Huihui Memory Tree*
"""
            filepath.write_text(mem_content, encoding='utf-8')
            index_content += f"- [[{topic.replace('_', '-')}/{filename[:-3]}]] ({mem[1][:10]})\n"
        
        (topic_dir / "index.md").write_text(index_content, encoding='utf-8')
    
    # Create root index
    root_index = "# Memory Tree\n\n"
    root_index += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    
    for (topic,) in topics:
        count = conn.execute('SELECT COUNT(*) FROM memory_tree WHERE topic = ?', (topic,)).fetchone()[0]
        root_index += f"- [[{topic.replace('_', '-')}/]] ({count} memories)\n"
    
    (output_dir / "index.md").write_text(root_index, encoding='utf-8')
    
    return output_dir

# ─── CLI Interface ────────────────────────────────────────────────────────────

def cmd_add(args):
    conn = init_db()
    memory_id = add_memory(conn, args.content, args.topic, args.time, args.chunk)
    print(f"Added memory: {memory_id}")
    conn.close()

def cmd_query(args):
    conn = init_db()
    memories = query_memories(conn, args.topic, args.limit, args.min_score)
    
    if not memories:
        print("No memories found.")
        return
    
    for mem in memories:
        print(f"\n[{mem['topic']}] {mem['time_str'][:10]} (score: {mem['combined_score']:.3f})")
        print(f"  {mem['content'][:200]}...")
    conn.close()

def cmd_build(args):
    conn = init_db()
    tree = build_tree(conn)
    print(f"Built tree with {len(tree)} topics:")
    for topic, info in tree.items():
        print(f"  {topic}: {info['count']} memories")
    conn.close()

def cmd_export(args):
    conn = init_db()
    output_dir = Path(args.output) if args.output else None
    out = export_to_obsidian(conn, output_dir)
    print(f"Exported to {out}")
    conn.close()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Memory Tree — Structured memory storage for Huihui')
    subparsers = parser.add_subparsers(dest='command')
    
    # Add memory
    add_parser = subparsers.add_parser('add', help='Add a new memory')
    add_parser.add_argument('--content', '-c', required=True, help='Memory content')
    add_parser.add_argument('--topic', '-t', required=True, help='Topic category')
    add_parser.add_argument('--time', help='ISO timestamp (default: now)')
    add_parser.add_argument('--chunk', type=int, default=0, help='Chunk index')
    
    # Query memories
    query_parser = subparsers.add_parser('query', help='Query memories')
    query_parser.add_argument('--topic', help='Filter by topic')
    query_parser.add_argument('--limit', type=int, default=10, help='Max results')
    query_parser.add_argument('--min-score', type=float, default=0.3, help='Min combined score')
    
    # Build tree
    subparsers.add_parser('build', help='Build summary tree from all memories')
    
    # Export
    export_parser = subparsers.add_parser('export', help='Export to Obsidian format')
    export_parser.add_argument('--output', '-o', help='Output directory')
    
    args = parser.parse_args()
    
    if args.command == 'add':
        cmd_add(args)
    elif args.command == 'query':
        cmd_query(args)
    elif args.command == 'build':
        cmd_build(args)
    elif args.command == 'export':
        cmd_export(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()