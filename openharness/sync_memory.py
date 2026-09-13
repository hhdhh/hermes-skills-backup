#!/usr/bin/env python3
"""Bidirectional memory sync between ohmo (~/.ohmo/memory → wiki/) and back.

- ohmo → wiki: writes new ohmo memory entries to wiki/openharness-memory/ (already via symlink)
- wiki → ohmo: watches wiki/openharness-memory/ for new/changed files
- Drift detection: lists entries that differ in both sides

Usage:
    python sync_memory.py sync          # one-shot sync
    python sync_memory.py watch         # continuous watch
    python sync_memory.py drift         # show divergence
"""
from __future__ import annotations
import os
import sys
import hashlib
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

OHMO_DIR = Path.home() / ".ohmo"
WIKI_DIR = Path.home() / ".openclaw/workspace/wiki"
MEMORY_DIR_NAME = "openharness-memory"

def ohmo_memory_dir() -> Path:
    """Return the .ohmo memory directory (resolves symlink)."""
    p = OHMO_DIR / "memory"
    return p.resolve()

def wiki_memory_dir() -> Path:
    return WIKI_DIR / MEMORY_DIR_NAME

def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()

def all_md_files(d: Path) -> dict[str, Path]:
    """Return {filename: path} for all .md files in d, excluding MEMORY.md."""
    return {f.name: f for f in d.glob("*.md") if f.name != "MEMORY.md"}

def sync_once(verbose: bool = True) -> dict:
    """Run one-way ohmo→wiki sync (since symlink, just verify + report)."""
    src = wiki_memory_dir()  # actually = ~/.ohmo/memory via symlink
    if not src.exists():
        return {"status": "no_source", "files": 0}
    files = all_md_files(src)
    return {"status": "ok", "files": len(files), "names": sorted(files.keys())}

def show_drift() -> dict:
    """Compare ohmo vs wiki memory files (only relevant if symlink missing)."""
    ohmo = ohmo_memory_dir()
    wiki = wiki_memory_dir()
    ohmo_files = {p.name: p for p in ohmo.glob("*.md")} if ohmo.exists() else {}
    wiki_files = {p.name: p for p in wiki.glob("*.md")} if wiki.exists() else {}
    only_ohmo = set(ohmo_files) - set(wiki_files)
    only_wiki = set(wiki_files) - set(ohmo_files)
    common = set(ohmo_files) & set(wiki_files)
    diverged = []
    for name in common:
        if md5(ohmo_files[name]) != md5(wiki_files[name]):
            diverged.append(name)
    return {"only_ohmo": sorted(only_ohmo), "only_wiki": sorted(only_wiki), "diverged": sorted(diverged)}

def watch_loop(interval: int = 60):
    """Poll wiki_memory_dir for new .md files and report."""
    import time
    target = wiki_memory_dir()
    target.mkdir(parents=True, exist_ok=True)
    seen = set(all_md_files(target).keys())
    print(f"Watching {target} every {interval}s (start: {len(seen)} files)")
    while True:
        time.sleep(interval)
        current = set(all_md_files(target).keys())
        new = current - seen
        if new:
            print(f"[{datetime.now().isoformat()}] New: {sorted(new)}")
            seen = current

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sync").add_argument("--quiet", action="store_true")
    sub.add_parser("drift")
    sub.add_parser("watch").add_argument("--interval", type=int, default=60)
    args = ap.parse_args()
    if args.cmd == "sync":
        r = sync_once(verbose=not args.quiet)
        if not args.quiet: print(f"sync: {r['status']}, {r['files']} files in wiki/openharness-memory/")
    elif args.cmd == "drift":
        r = show_drift()
        print(f"only in ohmo: {r['only_ohmo']}")
        print(f"only in wiki: {r['only_wiki']}")
        print(f"diverged: {r['diverged']}")
    elif args.cmd == "watch":
        watch_loop(args.interval)

if __name__ == "__main__":
    main()
