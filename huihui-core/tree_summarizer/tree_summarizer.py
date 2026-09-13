#!/usr/bin/env python3
"""
Tree Summarizer — OpenHuman-inspired hierarchical memory summarization for Huihui

Core responsibilities:
1. Build multi-level summaries from memory chunks
2. Iterative compression: chunks → layer1 summaries → layer2 → ... → root
3. Each level is ~60% compression of the level below
4. Support for topic-specific trees
5. Query: can ask for "high level" or "detailed" summaries

Usage:
    python3 tree_summarizer.py build                    # build full tree from memory tree
    python3 tree_summarizer.py build --topic vault    # build for specific topic
    python3 tree_summarizer.py query "project status" # query with summarization
    python3 tree_summarizer.py export                  # export to markdown
"""

import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# ─── Configuration ────────────────────────────────────────────────────────────

MEMORY_TREE_DB = Path(os.path.expanduser("~/.openclaw/wiki/main/memory_tree.db"))
TREE_SUMMARIZER_DB = Path(os.path.expanduser("~/.openclaw/wiki/main/tree_summarizer.db"))

MAX_CHUNK_CHARS = 3000
SUMMARY_RATIO = 0.4  # each level is 40% of parent size
MAX_LEVELS = 4       # chunks → L1 → L2 → L3 → L4 (root)

# ─── Database Schema ─────────────────────────────────────────────────────────

def init_db():
    """Initialize tree summarizer database"""
    TREE_SUMMARIZER_DB.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(TREE_SUMMARIZER_DB))
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tree_nodes (
            id TEXT PRIMARY KEY,
            topic TEXT NOT NULL,
            level INTEGER NOT NULL,  -- 0=chunk, 1+=summary levels
            parent_id TEXT,
            content TEXT NOT NULL,
            num_children INTEGER DEFAULT 0,
            char_count INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (parent_id) REFERENCES tree_nodes(id)
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS build_log (
            topic TEXT,
            level INTEGER,
            built_at TEXT,
            nodes_created INTEGER,
            PRIMARY KEY (topic, level)
        )
    ''')
    
    conn.execute('CREATE INDEX IF NOT EXISTS idx_topic_level ON tree_nodes(topic, level)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_parent ON tree_nodes(parent_id)')
    
    conn.commit()
    return conn

# ─── Core Summarization ───────────────────────────────────────────────────────

def summarize_text(text: str, ratio: float = SUMMARY_RATIO) -> str:
    """
    Simple extractive summarization.
    Takes first sentences until we reach target ratio of original length.
    For production, could integrate with LLM API for abstractive summaries.
    """
    if not text or len(text) < 50:
        return text
    
    target_len = int(len(text) * ratio)
    
    # Split into sentences (CJK and English aware)
    import re
    
    # Try to split on sentence boundaries
    sentences = re.split(r'(?<=[。！？.!?])\s*', text)
    if len(sentences) <= 2:
        # Not enough sentences, use paragraph-based
        paragraphs = text.split('\n\n')
        result = []
        current_len = 0
        for para in paragraphs:
            if current_len + len(para) > target_len and result:
                break
            result.append(para)
            current_len += len(para)
        return '\n\n'.join(result)
    
    result = []
    current_len = 0
    for sentence in sentences:
        if current_len + len(sentence) > target_len and result:
            break
        result.append(sentence)
        current_len += len(sentence)
    
    return ''.join(result)

def build_tree_from_memory(topic: Optional[str] = None) -> dict:
    """
    Build or rebuild the summary tree from memory_tree.db.
    """
    if not MEMORY_TREE_DB.exists():
        raise FileNotFoundError(f"Memory tree DB not found: {MEMORY_TREE_DB}")
    
    mem_conn = sqlite3.connect(str(MEMORY_TREE_DB))
    tree_conn = init_db()
    
    # Get all memories for this topic (or all topics)
    if topic:
        rows = mem_conn.execute('''
            SELECT id, content, topic, time_str, combined_score
            FROM memory_tree
            WHERE topic = ?
            ORDER BY time_str DESC
        ''', (topic,)).fetchall()
        topics = [topic]
    else:
        rows = mem_conn.execute('''
            SELECT id, content, topic, time_str, combined_score
            FROM memory_tree
            ORDER BY topic, time_str DESC
        ''').fetchall()
        topics = [r[2] for r in rows]
        topics = list(dict.fromkeys(topics))  # preserve order, unique
    
    mem_conn.close()
    
    results = {}
    
    for t in topics:
        topic_rows = [r for r in rows if r[2] == t]
        if not topic_rows:
            continue
        
        print(f"Building tree for topic: {t} ({len(topic_rows)} chunks)")
        
        # Clear existing tree for this topic
        tree_conn.execute('DELETE FROM tree_nodes WHERE topic = ?', (t,))
        tree_conn.execute('DELETE FROM build_log WHERE topic = ?', (t,))
        
        # Level 0: original chunks
        chunk_ids = []
        for row in topic_rows:
            node_id = f"chunk_{row[0]}"
            tree_conn.execute('''
                INSERT INTO tree_nodes (id, topic, level, parent_id, content, num_children, char_count, created_at)
                VALUES (?, ?, 0, NULL, ?, 0, ?, ?)
            ''', (node_id, t, row[1][:5000], len(row[1]), datetime.now(timezone.utc).isoformat()))
            chunk_ids.append(node_id)
        
        # Build summary levels iteratively
        current_level_ids = chunk_ids
        level = 1
        
        while len(current_level_ids) > 1 and level < MAX_LEVELS:
            # Group chunks into groups of ~5 for summarization
            group_size = 5
            groups = [current_level_ids[i:i+group_size] for i in range(0, len(current_level_ids), group_size)]
            
            next_level_ids = []
            
            for group in groups:
                if len(group) < 2:
                    if group:
                        next_level_ids.append(group[0])
                    continue
                
                # Fetch content from all nodes in group
                placeholders = ','.join('?' * len(group))
                rows_in_group = tree_conn.execute(
                    f'SELECT content, char_count FROM tree_nodes WHERE id IN ({placeholders})',
                    group
                ).fetchall()
                
                # Concatenate content
                combined = '\n\n'.join(r[0] for r in rows_in_group)
                
                # Summarize
                summary = summarize_text(combined)
                
                # Create summary node
                node_id = f"l{level}_{group[0].split('_', 1)[1]}"
                parent_id = group[0] if len(group) == 1 else None
                
                tree_conn.execute('''
                    INSERT INTO tree_nodes (id, topic, level, parent_id, content, num_children, char_count, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (node_id, t, level, parent_id, summary, len(group), len(summary),
                      datetime.now(timezone.utc).isoformat()))
                
                # Update children's parent_id
                for child_id in group:
                    tree_conn.execute('''
                        UPDATE tree_nodes SET parent_id = ? WHERE id = ?
                    ''', (node_id, child_id))
                
                next_level_ids.append(node_id)
            
            current_level_ids = next_level_ids
            print(f"  Level {level}: {len(current_level_ids)} nodes")
            level += 1
        
        # Log build
        total_nodes = tree_conn.execute(
            'SELECT COUNT(*) FROM tree_nodes WHERE topic = ?', (t,)
        ).fetchone()[0]
        
        tree_conn.execute('''
            INSERT OR REPLACE INTO build_log (topic, level, built_at, nodes_created)
            VALUES (?, ?, ?, ?)
        ''', (t, level - 1, datetime.now(timezone.utc).isoformat(), total_nodes))
        
        tree_conn.commit()
        
        results[t] = {
            "levels": level - 1,
            "total_nodes": total_nodes
        }
    
    tree_conn.close()
    
    return results

def query_tree(topic: str, level: Optional[int] = None, max_chars: int = 3000) -> str:
    """
    Query the tree for a topic.
    If level is None, returns the highest-level (most summarized) node.
    If level is specified, returns that level's summaries.
    """
    if not TREE_SUMMARIZER_DB.exists():
        raise FileNotFoundError(f"Tree summarizer DB not found. Run: tree_summarizer.py build")
    
    conn = sqlite3.connect(str(TREE_SUMMARIZER_DB))
    
    if level is not None:
        rows = conn.execute('''
            SELECT content, char_count FROM tree_nodes
            WHERE topic = ? AND level = ?
            ORDER BY id
        ''', (topic, level)).fetchall()
        
        if not rows:
            print(f"No nodes at level {level} for topic '{topic}'")
            conn.close()
            return ""
        
        result = '\n\n---\n\n'.join(r[0] for r in rows if r[0])
        conn.close()
        return result[:max_chars]
    
    # Get highest level node (root summary)
    max_level_row = conn.execute('''
        SELECT MAX(level) FROM tree_nodes WHERE topic = ?
    ''', (topic,)).fetchone()
    
    if not max_level_row or max_level_row[0] is None:
        print(f"No tree found for topic '{topic}'")
        conn.close()
        return ""
    
    max_level = max_level_row[0]
    
    if max_level == 0:
        # No summarization happened, just return chunks
        rows = conn.execute('''
            SELECT content FROM tree_nodes
            WHERE topic = ? AND level = 0
            ORDER BY id
        ''', (topic,)).fetchall()
        result = '\n\n'.join(r[0] for r in rows if r[0])
    else:
        # Get root nodes (level = max_level, no parent)
        rows = conn.execute('''
            SELECT content FROM tree_nodes
            WHERE topic = ? AND level = ?
            ORDER BY id
        ''', (topic, max_level)).fetchall()
        
        if not rows:
            # Fall back to max_level - 1
            rows = conn.execute('''
                SELECT content FROM tree_nodes
                WHERE topic = ? AND level = ?
                ORDER BY id
            ''', (topic, max_level - 1)).fetchall()
        
        result = '\n\n'.join(r[0] for r in rows if r[0])
    
    conn.close()
    return result[:max_chars]

def export_to_markdown(output_dir: Optional[Path] = None) -> Path:
    """Export all topic trees as markdown files"""
    if output_dir is None:
        output_dir = Path(os.path.expanduser("~/.openclaw/wiki/main/summaries"))
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not TREE_SUMMARIZER_DB.exists():
        raise FileNotFoundError("Tree summarizer DB not found")
    
    conn = sqlite3.connect(str(TREE_SUMMARIZER_DB))
    
    topics = conn.execute('SELECT DISTINCT topic FROM tree_nodes').fetchall()
    
    for (topic,) in topics:
        topic_file = output_dir / f"{topic.replace(':', '_')}.md"
        
        max_level = conn.execute('SELECT MAX(level) FROM tree_nodes WHERE topic = ?', (topic,)).fetchone()[0]
        
        content = f"# {topic}\n\n"
        content += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        content += f"Max depth: {max_level}\n\n"
        
        for lvl in range(max_level + 1):
            rows = conn.execute('''
                SELECT content, num_children FROM tree_nodes
                WHERE topic = ? AND level = ?
                ORDER BY id
            ''', (topic, lvl)).fetchall()
            
            if not rows:
                continue
            
            content += f"\n## Level {lvl}"
            content += f" {'(Root summaries)' if lvl == max_level else '(Chunks)' if lvl == 0 else '(Summaries)'}\n\n"
            
            for i, (text, num_children) in enumerate(rows):
                if lvl > 0:
                    content += f"### Summary {i+1} ({num_children} children)\n\n"
                content += text + "\n\n"
        
        topic_file.write_text(content, encoding='utf-8')
    
    conn.close()
    
    # Write index
    index_content = "# Tree Summaries\n\n"
    index_content += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    
    for (topic,) in topics:
        max_level = conn.execute('SELECT MAX(level) FROM tree_nodes WHERE topic = ?', (topic,)).fetchone()[0]
        count = conn.execute('SELECT COUNT(*) FROM tree_nodes WHERE topic = ?', (topic,)).fetchone()[0]
        index_content += f"- [[{topic.replace(':', '_')}.md|{topic}]] (L{max_level}, {count} nodes)\n"
    
    (output_dir / "index.md").write_text(index_content, encoding='utf-8')
    
    return output_dir

# ─── CLI Interface ────────────────────────────────────────────────────────────

def cmd_build(args):
    if args.topic:
        print(f"Building tree for topic: {args.topic}")
        results = build_tree_from_memory(args.topic)
    else:
        print("Building full tree from all memory...")
        results = build_tree_from_memory()
    
    print("\n✅ Tree build complete:")
    for topic, info in results.items():
        print(f"  {topic}: {info['levels']} levels, {info['total_nodes']} nodes")

def cmd_query(args):
    level = None
    if args.level is not None:
        level = int(args.level)
    
    result = query_tree(args.topic, level=level, max_chars=args.max_chars)
    
    if not result:
        print(f"No result for topic '{args.topic}' at level {level or 'root'}")
        return
    
    print(f"\n{'='*60}")
    print(f"Topic: {args.topic}" + (f" | Level: {level}" if level else " | Root summary"))
    print(f"{'='*60}\n")
    print(result)

def cmd_export(args):
    output_dir = Path(args.output) if args.output else None
    out = export_to_markdown(output_dir)
    print(f"Exported summaries to: {out}")

def cmd_status(args):
    if not TREE_SUMMARIZER_DB.exists():
        print("Tree summarizer DB not found. Run: tree_summarizer.py build")
        return
    
    conn = sqlite3.connect(str(TREE_SUMMARIZER_DB))
    
    topics = conn.execute('SELECT DISTINCT topic FROM tree_nodes').fetchall()
    
    if not topics:
        print("No trees built yet. Run: tree_summarizer.py build")
        conn.close()
        return
    
    print("=== Tree Summarizer Status ===\n")
    
    for (topic,) in topics:
        max_level = conn.execute('SELECT MAX(level) FROM tree_nodes WHERE topic = ?', (topic,)).fetchone()[0]
        count = conn.execute('SELECT COUNT(*) FROM tree_nodes WHERE topic = ?', (topic,)).fetchone()[0]
        
        build_info = conn.execute('SELECT level, built_at, nodes_created FROM build_log WHERE topic = ?', (topic,)).fetchone()
        
        print(f"{topic}:")
        print(f"  Depth: {max_level} | Nodes: {count}")
        if build_info:
            print(f"  Last built: {build_info[1]} ({build_info[2]} nodes created)")
        print()
    
    conn.close()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Tree Summarizer — Hierarchical memory summarization')
    subparsers = parser.add_subparsers(dest='command')
    
    build_parser = subparsers.add_parser('build', help='Build summary tree from memory')
    build_parser.add_argument('--topic', help='Build for specific topic only')
    
    query_parser = subparsers.add_parser('query', help='Query a topic summary')
    query_parser.add_argument('topic', help='Topic name')
    query_parser.add_argument('--level', '-l', help='Specific level (0=chunks, 1+=summaries)')
    query_parser.add_argument('--max-chars', '-m', type=int, default=3000, help='Max chars to return')
    
    export_parser = subparsers.add_parser('export', help='Export trees to markdown')
    export_parser.add_argument('--output', '-o', help='Output directory')
    
    subparsers.add_parser('status', help='Show tree status')
    
    args = parser.parse_args()
    
    if args.command == 'build':
        cmd_build(args)
    elif args.command == 'query':
        cmd_query(args)
    elif args.command == 'export':
        cmd_export(args)
    elif args.command == 'status':
        cmd_status(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
