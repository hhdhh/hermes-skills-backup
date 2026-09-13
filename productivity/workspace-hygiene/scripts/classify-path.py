#!/usr/bin/env python3
"""
classify-path.py — workspace-hygiene skill 的辅助脚本

对给定路径做"能清/不能清/需拍板"三档分类。
用法:
    python3 classify-path.py <PATH>
    python3 classify-path.py <PATH1> <PATH2> ...
    python3 classify-path.py --report <DIR>  # 扫描整个目录输出报告

判断规则:
- 灵魂三件: SOUL.md / CLAUDE.md / AGENTS.md → 🔴 绝对不动
- 主人 4 月起的 daily 笔记(.openclaw/workspace/memory/2026-04-*.md) → 🔴 不动
- 30 天没动 + size > 10M + 不在 git → 🟡 可清
- 名字带 .bak / .bak-pre-* / .trash / .archive-7days-ago / dreaming/ → 🟢 可清
- 名字带 venv / node_modules / .git/ → 🟡 需拍板
"""
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

HOME = Path.home()
SOUL_PATHS = [
    HOME / ".openclaw/workspace/SOUL.md",
    HOME / ".claude/CLAUDE.md",
    HOME / ".openclaw/workspace/AGENTS.md",
    HOME / ".openclaw/workspace/MEMORY.md",  # 主体长篇 curated
]


def is_in_git(path: Path) -> bool:
    """Check if path is tracked in any git repo."""
    try:
        result = subprocess.run(
            ["git", "ls-files", str(path)],
            capture_output=True, text=True, timeout=5,
            cwd=path.parent if path.is_dir() else path.parent.parent,
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def classify(path: str) -> dict:
    p = Path(path).expanduser()
    if not p.exists():
        return {"path": str(p), "exists": False}

    name = p.name
    stat = p.stat()
    age_days = (datetime.now() - datetime.fromtimestamp(stat.st_mtime)).days

    # Rule: soul core
    if p.resolve() in [s.resolve() for s in SOUL_PATHS]:
        return {
            "path": str(p), "tier": "🔴", "reason": "灵魂核心,绝对不动",
            "size_mb": round(stat.st_size / 1024 / 1024, 2), "age_days": age_days,
        }

    # Rule: owner daily notes (4 月起的)
    if ".openclaw/workspace/memory" in str(p) and "2026-04" in name:
        return {
            "path": str(p), "tier": "🔴", "reason": "主人 4 月真实日记",
            "size_mb": round(stat.st_size / 1024 / 1024, 2), "age_days": age_days,
        }

    # Rule: obvious trash
    if any(s in name for s in [".bak", ".trash", "dreaming/deep", "dreaming/light"]):
        return {
            "path": str(p), "tier": "🟢", "reason": f"名字带垃圾标识符",
            "size_mb": round(stat.st_size / 1024 / 1024, 2), "age_days": age_days,
        }

    # Rule: venv / node_modules / .git
    if name in ("venv", ".venv", "node_modules", ".git"):
        return {
            "path": str(p), "tier": "🟡", "reason": "依赖/版本控制目录,需确认是否在用",
            "size_mb": round(stat.st_size / 1024 / 1024, 2), "age_days": age_days,
        }

    # Rule: long-idle large files (>30d, >10M, not in git)
    in_git = is_in_git(p) if p.is_file() else False
    if age_days > 30 and stat.st_size > 10 * 1024 * 1024 and not in_git:
        return {
            "path": str(p), "tier": "🟡", "reason": f"长期未动且不在 git,确认用途后可清",
            "size_mb": round(stat.st_size / 1024 / 1024, 2), "age_days": age_days,
        }

    # Rule: recent small files
    if age_days < 7 and stat.st_size < 1024 * 1024:
        return {
            "path": str(p), "tier": "⚪", "reason": "近期活跃,不动",
            "size_mb": round(stat.st_size / 1024 / 1024, 2), "age_days": age_days,
        }

    return {
        "path": str(p), "tier": "🟡", "reason": "需人工判断",
        "size_mb": round(stat.st_size / 1024 / 1024, 2), "age_days": age_days,
    }


def report(directory: str) -> list[dict]:
    """Scan a directory and return tier-sorted classifications."""
    results = []
    d = Path(directory).expanduser()
    if not d.is_dir():
        return [{"error": f"{d} is not a directory"}]
    for item in sorted(d.iterdir(), key=lambda x: x.stat().st_size, reverse=True):
        if item.name.startswith("."):
            continue
        results.append(classify(str(item)))
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == "--report":
        for r in report(sys.argv[2]):
            print(f"{r.get('tier', '?')} {r.get('size_mb', '?'):>8} MB  {r.get('age_days', '?'):>4}d  {r.get('path', '?')}")
            print(f"   └─ {r.get('reason', '?')}")
    else:
        for arg in sys.argv[1:]:
            r = classify(arg)
            tier = r.get("tier", "?")
            size = r.get("size_mb", "?")
            age = r.get("age_days", "?")
            reason = r.get("reason", "?")
            print(f"{tier} {size:>8} MB  {age:>4}d  {arg}")
            print(f"   └─ {reason}")
