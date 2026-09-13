"""ljg-zotero — Zotero library 读取器 (0 依赖)。

来源: 简化适配 Zotero SQLite schema。
不调 Zotero API / Web API,只读本地 DB (sqlite3 stdlib)。
找不到 DB 时用 sample data (5 条 + 3 collection)。

用法:
  from ljg_zotero import Library
  lib = Library.discover()  # 自动找 DB,找不到用 sample
  items = lib.search("transformer")
  for it in items:
      print(it.cite_key(), it.title)
  lib.export_bibtex("/tmp/refs.bib")
  lib.export_json("/tmp/library.json")
  entries = lib.export_for_paper("AI Reading List")
"""

from __future__ import annotations

from .db import (
    Item, Collection, Library,
    find_zotero_db, DEFAULT_PATHS,
)

__version__ = "0.1.0"
__all__ = [
    "Item", "Collection", "Library",
    "find_zotero_db", "DEFAULT_PATHS",
]
