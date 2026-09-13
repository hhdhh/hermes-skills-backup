#!/usr/bin/env python3
"""
Auto-Fetch — OpenHuman-inspired 20-minute automatic data polling for Huihui

Core responsibilities:
1. Poll configured data sources every 20 minutes
2. Detect new data and feed into memory pipeline
3. Send notifications via Feishu for significant changes
4. Track last-sync timestamps per source

Usage:
    python3 auto_fetch.py run          # Start polling loop
    python3 auto_fetch.py status       # Show sync status
    python3 auto_fetch.py add SOURCE   # Add a data source
    python3 auto_fetch.py sync SOURCE  # Force sync one source

Supported sources: gmail, calendar, github, notion, feishu, local_files
"""

import os
import json
import time
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, TypedDict

# ─── Configuration ────────────────────────────────────────────────────────────

CONFIG_DIR = Path(os.path.expanduser("~/.openclaw/workspace"))
STATE_FILE = CONFIG_DIR / "auto_fetch_state.json"
SYNC_DB = CONFIG_DIR / "auto_fetch.db"
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "")

POLL_INTERVAL_SECONDS = 20 * 60  # 20 minutes
DEFAULT_SOURCES = ["feishu", "local_files"]

# ─── State ─────────────────────────────────────────────────────────────────────

class SyncState:
    def __init__(self):
        self.state_file = STATE_FILE
        self.data = self._load()
    
    def _load(self) -> dict:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except:
                pass
        return {"sources": {}, "last_full_sync": None, "enabled": True}
    
    def save(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self.data, indent=2, ensure_ascii=False))
    
    def get_source(self, name: str) -> dict:
        return self.data.get("sources", {}).get(name, {
            "enabled": True,
            "last_sync": None,
            "last_success": None,
            "last_error": None,
            "config": {}
        })
    
    def update_source(self, name: str, updates: dict):
        if "sources" not in self.data:
            self.data["sources"] = {}
        if name not in self.data["sources"]:
            self.data["sources"][name] = {"enabled": True, "last_sync": None, 
                                          "last_success": None, "last_error": None, "config": {}}
        self.data["sources"][name].update(updates)
        self.save()
    
    def get_sources(self) -> list[str]:
        return list(self.data.get("sources", {}).keys())
    
    @property
    def enabled(self) -> bool:
        return self.data.get("enabled", True)
    
    @enabled.setter
    def enabled(self, value: bool):
        self.data["enabled"] = value
        self.save()

# ─── Source Adapters ──────────────────────────────────────────────────────────

class SourceAdapter:
    """Base class for data source adapters"""
    name: str = "base"
    
    def __init__(self, config: dict):
        self.config = config
    
    def fetch(self, since: Optional[str]) -> list[dict]:
        """
        Fetch new items since last sync.
        Returns list of {id, title, content, timestamp, metadata}
        """
        raise NotImplementedError
    
    def should_notify(self, item: dict) -> bool:
        """Determine if this item warrants a notification"""
        return False

class FeishuAdapter(SourceAdapter):
    """Feishu/Lark messages and updates"""
    name = "feishu"
    
    def fetch(self, since: Optional[str]) -> list[dict]:
        # Placeholder - in production, use feishu API
        # This would check for new messages in configured channels
        return []
    
    def should_notify(self, item: dict) -> bool:
        return item.get("priority") == "high"

class LocalFilesAdapter(SourceAdapter):
    """Monitor local files for changes"""
    name = "local_files"
    
    def fetch(self, since: Optional[str]) -> list[dict]:
        items = []
        
        # Watch memory directory
        memory_dir = Path(os.path.expanduser("~/.openclaw/workspace/memory"))
        if not memory_dir.exists():
            return items
        
        since_dt = None
        if since:
            since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
        
        for filepath in memory_dir.glob("*.md"):
            mtime = datetime.fromtimestamp(filepath.stat().st_mtime, tz=timezone.utc)
            
            if since_dt and mtime <= since_dt:
                continue
            
            content = filepath.read_text(encoding='utf-8')
            items.append({
                "id": f"file:{filepath.name}",
                "title": filepath.name,
                "content": content[:500],  # First 500 chars as preview
                "timestamp": mtime.isoformat(),
                "metadata": {"path": str(filepath), "size": len(content)}
            })
        
        # Watch wiki sources
        wiki_dir = Path(os.path.expanduser("~/.openclaw/wiki/main/sources"))
        if wiki_dir.exists():
            for filepath in wiki_dir.glob("**/*.md"):
                mtime = datetime.fromtimestamp(filepath.stat().st_mtime, tz=timezone.utc)
                if since_dt and mtime <= since_dt:
                    continue
                
                content = filepath.read_text(encoding='utf-8')
                items.append({
                    "id": f"wiki:{filepath.name}",
                    "title": filepath.name,
                    "content": content[:500],
                    "timestamp": mtime.isoformat(),
                    "metadata": {"path": str(filepath)}
                })
        
        return items

class GitHubAdapter(SourceAdapter):
    """GitHub notifications and activity"""
    name = "github"
    
    def fetch(self, since: Optional[str]) -> list[dict]:
        # Placeholder - requires GITHUB_TOKEN env var
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            return []
        
        # Would use GitHub API here
        return []

class GmailAdapter(SourceAdapter):
    """Gmail/Google Workspace email polling"""
    name = "gmail"
    
    def fetch(self, since: Optional[str]) -> list[dict]:
        # Placeholder - requires OAuth2
        return []

# ─── Notification ─────────────────────────────────────────────────────────────

def send_feishu_notification(title: str, content: str, webhook: Optional[str] = None):
    """Send notification via Feishu webhook"""
    if not webhook:
        webhook = FEISHU_WEBHOOK
    
    if not webhook:
        print(f"[AutoFetch] Notification (no webhook): {title}")
        return
    
    try:
        import requests
        payload = {
            "msg_type": "text",
            "content": {"text": f"**{title}**\n{content}"}
        }
        resp = requests.post(webhook, json=payload, timeout=5)
        resp.raise_for_status()
        print(f"[AutoFetch] Notification sent: {title}")
    except Exception as e:
        print(f"[AutoFetch] Notification failed: {e}")

# ─── Core Polling Loop ─────────────────────────────────────────────────────────

def sync_source(source_name: str, adapter: SourceAdapter, state: SyncState) -> int:
    """Sync one source and return number of new items"""
    source_state = state.get_source(source_name)
    last_sync = source_state.get("last_sync")
    
    try:
        items = adapter.fetch(last_sync)
        
        if items:
            print(f"[AutoFetch] {source_name}: {len(items)} new items")
            
            # Feed to memory tree (if available)
            try:
                import sys
                sys.path.insert(0, str(Path(__file__).parent.parent / "memory_tree"))
                from memory_tree import add_memory, init_db
                conn = init_db()
                
                for item in items:
                    add_memory(
                        conn, 
                        content=f"## {item['title']}\n\n{item['content']}",
                        topic=source_name,
                        time_str=item.get("timestamp"),
                        embedding_id=item.get("id")
                    )
                conn.close()
            except Exception as e:
                print(f"[AutoFetch] Memory tree sync failed: {e}")
            
            # Send notifications for important items
            for item in items:
                if adapter.should_notify(item):
                    send_feishu_notification(
                        title=f"[{source_name}] {item['title']}",
                        content=item.get("content", "")[:200]
                    )
        
        state.update_source(source_name, {
            "last_sync": datetime.now(timezone.utc).isoformat(),
            "last_success": datetime.now(timezone.utc).isoformat(),
            "last_error": None
        })
        
        return len(items)
        
    except Exception as e:
        state.update_source(source_name, {
            "last_error": str(e),
            "last_error_time": datetime.now(timezone.utc).isoformat()
        })
        print(f"[AutoFetch] {source_name} failed: {e}")
        return 0

def run_poll_loop(state: SyncState, sources: dict[str, SourceAdapter]):
    """Main polling loop"""
    print(f"[AutoFetch] Starting 20-minute polling loop...")
    print(f"[AutoFetch] Monitoring {len(sources)} sources: {', '.join(sources.keys())}")
    
    while state.enabled:
        for source_name, adapter in sources.items():
            source_state = state.get_source(source_name)
            if not source_state.get("enabled", True):
                continue
            
            sync_source(source_name, adapter, state)
        
        print(f"[AutoFetch] Cycle complete. Sleeping {POLL_INTERVAL_SECONDS}s...")
        time.sleep(POLL_INTERVAL_SECONDS)

# ─── CLI Interface ────────────────────────────────────────────────────────────

def cmd_run(args):
    state = SyncState()
    
    sources = {
        "local_files": LocalFilesAdapter(state.get_source("local_files").get("config", {}))
    }
    
    # Load additional source adapters based on config
    if os.environ.get("GITHUB_TOKEN"):
        sources["github"] = GitHubAdapter(state.get_source("github").get("config", {}))
    
    if state.enabled:
        run_poll_loop(state, sources)
    else:
        print("[AutoFetch] Disabled in state file. Enable with: auto_fetch.py enable")

def cmd_status(args):
    state = SyncState()
    print("=== Auto-Fetch Status ===")
    print(f"Enabled: {state.enabled}")
    print(f"Sources: {', '.join(state.get_sources()) or '(none)'}")
    print()
    
    for source_name in state.get_sources():
        info = state.get_source(source_name)
        print(f"{source_name}:")
        print(f"  Enabled: {info.get('enabled', True)}")
        print(f"  Last sync: {info.get('last_sync', 'never')}")
        print(f"  Last success: {info.get('last_success', 'never')}")
        if info.get('last_error'):
            print(f"  Last error: {info['last_error']} ({info.get('last_error_time', '')})")
        print()

def cmd_add(args):
    source = args.source
    state = SyncState()
    
    if source not in ["feishu", "gmail", "github", "notion", "local_files"]:
        print(f"Unknown source: {source}")
        print("Supported: feishu, gmail, github, notion, local_files")
        return
    
    state.update_source(source, {"enabled": True})
    print(f"Added source: {source}")
    
    # Initialize adapter
    adapter_map = {
        "local_files": LocalFilesAdapter,
        "feishu": FeishuAdapter,
        "github": GitHubAdapter,
        "gmail": GmailAdapter
    }
    
    if source in adapter_map:
        adapter = adapter_map[source]({})
        # Do initial sync
        sync_source(source, adapter, state)

def cmd_sync(args):
    source = args.source
    state = SyncState()
    
    adapter_map = {
        "local_files": LocalFilesAdapter,
        "feishu": FeishuAdapter,
        "github": GitHubAdapter,
        "gmail": GmailAdapter
    }
    
    if source not in adapter_map:
        print(f"Unknown source: {source}")
        return
    
    adapter = adapter_map[source](state.get_source(source).get("config", {}))
    count = sync_source(source, adapter, state)
    print(f"Synced {count} items from {source}")

def cmd_enable(args):
    state = SyncState()
    state.enabled = True
    print("Auto-fetch enabled")

def cmd_disable(args):
    state = SyncState()
    state.enabled = False
    print("Auto-fetch disabled (polling loop will stop on next cycle)")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Auto-Fetch — 20-minute data polling for Huihui')
    subparsers = parser.add_subparsers(dest='command')
    
    subparsers.add_parser('run', help='Start polling loop')
    subparsers.add_parser('status', help='Show sync status')
    
    add_parser = subparsers.add_parser('add', help='Add a data source')
    add_parser.add_argument('source', help='Source name: feishu, gmail, github, notion, local_files')
    
    sync_parser = subparsers.add_parser('sync', help='Force sync one source')
    sync_parser.add_argument('source', help='Source name')
    
    subparsers.add_parser('enable', help='Enable auto-fetch')
    subparsers.add_parser('disable', help='Disable auto-fetch')
    
    args = parser.parse_args()
    
    if args.command == 'run':
        cmd_run(args)
    elif args.command == 'status':
        cmd_status(args)
    elif args.command == 'add':
        cmd_add(args)
    elif args.command == 'sync':
        cmd_sync(args)
    elif args.command == 'enable':
        cmd_enable(args)
    elif args.command == 'disable':
        cmd_disable(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()