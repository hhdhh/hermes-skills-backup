"""Zotero library 读取器 (0 依赖,纯 sqlite3 + dataclass)。

Zotero SQLite DB 位置:
  - macOS: ~/Zotero/zotero.sqlite
  - Linux: ~/.zotero/zotero.sqlite (官方 Linux 版少见,通常用 flatpak 装在 ~/.var/app/org.zotero.Zotero/data/Zotero/zotero.sqlite)
  - Windows: %USERPROFILE%/Zotero/zotero.sqlite
  - 自定义: ~/.zotero_profiles/.../zotero.sqlite (多 profile 时)

如果找不到 DB,本 skill 用内置 sample data 跑 (让 agent 看到 schema)。

用法:
  from ljg_zotero import Library
  lib = Library.discover()  # 自动找 DB
  items = lib.search("机器学习", field="title")
  lib.export_json("/tmp/zotero.json")
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any


# ── Zotero DB 默认路径 ────────────────────────────────────
DEFAULT_PATHS = [
    Path.home() / "Zotero" / "zotero.sqlite",
    Path.home() / ".zotero" / "zotero.sqlite",
    Path.home() / ".var" / "app" / "org.zotero.Zotero" / "data" / "Zotero" / "zotero.sqlite",
    Path.home() / "Zotero" / "zotero-prod.sqlite",  # 旧版 mac
]


def find_zotero_db() -> Optional[Path]:
    """自动找 Zotero DB。"""
    for p in DEFAULT_PATHS:
        if p.exists():
            return p
    # 广搜:只搜 home 下 3 层以内,跳过 CloudStorage (慢)
    home = Path.home()
    skip_dirs = {"CloudStorage", "Library/Caches", ".Trash", "node_modules"}
    candidates = []
    for path in [home, home / "Documents", home / "Desktop", home / "Downloads"]:
        if not path.exists():
            continue
        try:
            for p in path.glob("zotero.sqlite"):
                candidates.append(p)
            for p in path.glob("Zotero/zotero.sqlite"):
                candidates.append(p)
            for p in path.glob(".zotero/zotero.sqlite"):
                candidates.append(p)
        except (PermissionError, OSError):
            continue
    return candidates[0] if candidates else None


# ── 数据类 ──────────────────────────────────────────────
@dataclass
class Item:
    """Zotero 一条文献。"""
    item_id: int
    key: str
    item_type: str                    # book / journalArticle / webpage / ...
    title: str = ""
    creators: List[str] = field(default_factory=list)    # ["Einstein, Albert", "Born, Max"]
    date: str = ""
    abstract: str = ""
    publication: str = ""              # 期刊名 / 出版社
    doi: str = ""
    url: str = ""
    tags: List[str] = field(default_factory=list)
    collections: List[str] = field(default_factory=list)
    date_added: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def cite_key(self) -> str:
        """生成引用 key (Einstein1925 风格)。"""
        first = self.creators[0].split(",")[0].strip() if self.creators else "Anon"
        year = self.date[:4] if self.date else "n.d."
        return f"{first}{year}"


@dataclass
class Collection:
    """Zotero 一个 collection (目录)。"""
    collection_id: int
    name: str
    key: str = ""
    parent_id: Optional[int] = None


# ── Library (主类) ──────────────────────────────────────
class Library:
    """Zotero library 包装。"""

    def __init__(self, db_path: Optional[Path] = None, sample: bool = False):
        """db_path: Zotero DB 路径;sample=True 用 sample data。"""
        self.db_path = db_path
        self._sample_mode = sample
        self._conn: Optional[sqlite3.Connection] = None
        self._items: List[Item] = []
        self._collections: List[Collection] = []
        self._item_type_map: Dict[int, str] = {}
        self._loaded = False

    @classmethod
    def discover(cls) -> "Library":
        """自动发现 Zotero DB;找不到就用 sample。"""
        path = find_zotero_db()
        if path:
            return cls(db_path=path)
        print("[ljg-zotero] Zotero DB not found, using sample data", file=sys.stderr)
        return cls(sample=True)

    # ── 加载 ──────────────────────────────────────────
    def _connect(self):
        if self._sample_mode:
            return
        if self._conn is None:
            # readonly,避免锁住 Zotero
            uri = f"file:{self.db_path}?mode=ro"
            self._conn = sqlite3.connect(uri, uri=True)
            self._conn.row_factory = sqlite3.Row

    def _ensure_loaded(self):
        if self._loaded:
            return
        if self._sample_mode:
            self._load_sample()
        else:
            self._load_db()
        self._loaded = True

    def _load_db(self):
        self._connect()
        c = self._conn.cursor()
        # item types map
        for row in c.execute("SELECT itemTypeID, typeName FROM itemTypes"):
            self._item_type_map[row[0]] = row[1]

        # items + creators + tags + collections
        for row in c.execute("""
            SELECT i.itemID, i.itemTypeID, i.key, i.dateAdded,
                   (SELECT value FROM itemData d
                    JOIN itemDataValues v ON d.valueID = v.valueID
                    JOIN fields f ON d.fieldID = f.fieldID
                    WHERE d.itemID = i.itemID AND f.fieldName = 'title') as title,
                   (SELECT value FROM itemData d
                    JOIN itemDataValues v ON d.valueID = v.valueID
                    JOIN fields f ON d.fieldID = f.fieldID
                    WHERE d.itemID = i.itemID AND f.fieldName = 'date') as pubdate,
                   (SELECT value FROM itemData d
                    JOIN itemDataValues v ON d.valueID = v.valueID
                    JOIN fields f ON d.fieldID = f.fieldID
                    WHERE d.itemID = i.itemID AND f.fieldName = 'abstractNote') as abstract,
                   (SELECT value FROM itemData d
                    JOIN itemDataValues v ON d.valueID = v.valueID
                    JOIN fields f ON d.fieldID = f.fieldID
                    WHERE d.itemID = i.itemID AND f.fieldName = 'DOI') as doi,
                   (SELECT value FROM itemData d
                    JOIN itemDataValues v ON d.valueID = v.valueID
                    JOIN fields f ON d.fieldID = f.fieldID
                    WHERE d.itemID = i.itemID AND f.fieldName = 'url') as url,
                   (SELECT value FROM itemData d
                    JOIN itemDataValues v ON d.valueID = v.valueID
                    JOIN fields f ON d.fieldID = f.fieldID
                    WHERE d.itemID = i.itemID AND f.fieldName = 'publicationTitle') as pub
            FROM items i
            WHERE i.itemTypeID NOT IN (1, 14)  -- exclude note/attachment
        """):
            creators = self._get_creators(row[0])
            tags = self._get_tags(row[0])
            colls = self._get_collections(row[0])
            self._items.append(Item(
                item_id=row[0],
                key=row[2] or "",
                item_type=self._item_type_map.get(row[1], "unknown"),
                title=row[3] or "",
                date=row[4] or "",
                abstract=row[5] or "",
                doi=row[6] or "",
                url=row[7] or "",
                publication=row[8] or "",
                creators=creators, tags=tags, collections=colls,
                date_added=row[3] or "",
            ))
        for row in c.execute("SELECT collectionID, collectionName, key, parentCollectionID FROM collections"):
            self._collections.append(Collection(
                collection_id=row[0], name=row[1], key=row[2] or "", parent_id=row[3],
            ))

    def _get_creators(self, item_id: int) -> List[str]:
        if self._sample_mode or self._conn is None:
            return []
        c = self._conn.cursor()
        out = []
        for row in c.execute("""
            SELECT c.firstName, c.lastName
            FROM creators c
            JOIN itemCreators ic ON c.creatorID = ic.creatorID
            WHERE ic.itemID = ?
            ORDER BY ic.orderIndex
        """, (item_id,)):
            first, last = row[0] or "", row[1] or ""
            full = f"{last}, {first}".strip(", ") if (first or last) else "Anonymous"
            out.append(full)
        return out

    def _get_tags(self, item_id: int) -> List[str]:
        if self._sample_mode or self._conn is None:
            return []
        c = self._conn.cursor()
        return [r[0] for r in c.execute("""
            SELECT t.name FROM tags t
            JOIN itemTags it ON t.tagID = it.tagID
            WHERE it.itemID = ?
        """, (item_id,))]

    def _get_collections(self, item_id: int) -> List[str]:
        if self._sample_mode or self._conn is None:
            return []
        c = self._conn.cursor()
        return [r[0] for r in c.execute("""
            SELECT c.collectionName FROM collections c
            JOIN collectionItems ci ON c.collectionID = ci.collectionID
            WHERE ci.itemID = ?
        """, (item_id,))]

    def _load_sample(self):
        """当 Zotero DB 不存在时,加载示例数据让 agent 看到 schema。"""
        self._items = [
            Item(item_id=1, key="ABCD1234", item_type="book",
                 title="Deep Learning", creators=["Goodfellow, Ian", "Bengio, Yoshua"],
                 date="2016", publication="MIT Press",
                 abstract="The deep learning textbook.",
                 tags=["machine-learning", "neural-networks"],
                 collections=["AI Reading List"], date_added="2024-01-15"),
            Item(item_id=2, key="EFGH5678", item_type="journalArticle",
                 title="Attention Is All You Need",
                 creators=["Vaswani, Ashish", "Shazeer, Noam"],
                 date="2017", publication="NeurIPS",
                 doi="10.48550/arXiv.1706.03762",
                 abstract="Introduces the Transformer architecture.",
                 tags=["transformer", "nlp"],
                 collections=["AI Reading List", "Foundational"], date_added="2024-02-01"),
            Item(item_id=3, key="IJKL9012", item_type="journalArticle",
                 title="Stable Diffusion: Latent Diffusion Models",
                 creators=["Rombach, Robin", "Blattmann, Andreas"],
                 date="2022", publication="CVPR",
                 doi="10.1109/CVPR52688.2022.01042",
                 abstract="High-resolution image synthesis with latent diffusion models.",
                 tags=["diffusion", "image-generation"],
                 collections=["AI Reading List"], date_added="2024-03-10"),
            Item(item_id=4, key="MNOP3456", item_type="book",
                 title="Robot Operating System (ROS)",
                 creators=["Quigley, Morgan"],
                 date="2009", publication="Springer",
                 abstract="The ROS textbook for robotics.",
                 tags=["robotics", "ros"],
                 collections=["Robotics Reading List"], date_added="2024-04-05"),
            Item(item_id=5, key="QRST7890", item_type="webpage",
                 title="ROS 2 Documentation",
                 creators=["Open Source Robotics Foundation"],
                 date="2024", url="https://docs.ros.org/",
                 abstract="Official ROS 2 documentation.",
                 tags=["robotics", "ros2"],
                 collections=["Robotics Reading List"], date_added="2024-05-20"),
        ]
        self._collections = [
            Collection(collection_id=1, name="AI Reading List"),
            Collection(collection_id=2, name="Robotics Reading List"),
            Collection(collection_id=3, name="Foundational"),
        ]

    # ── 查询 ──────────────────────────────────────────
    def all_items(self) -> List[Item]:
        self._ensure_loaded()
        return list(self._items)

    def all_collections(self) -> List[Collection]:
        self._ensure_loaded()
        return list(self._collections)

    def search(self, query: str, field: str = "title", limit: int = 50) -> List[Item]:
        """简单子串搜索。"""
        self._ensure_loaded()
        q = query.lower()
        out = []
        for it in self._items:
            haystack = {
                "title": it.title.lower(),
                "creator": " ".join(it.creators).lower(),
                "tag": " ".join(it.tags).lower(),
                "abstract": it.abstract.lower(),
                "publication": it.publication.lower(),
            }.get(field, it.title.lower())
            if q in haystack:
                out.append(it)
                if len(out) >= limit:
                    break
        return out

    def by_collection(self, name: str) -> List[Item]:
        self._ensure_loaded()
        return [it for it in self._items if name in it.collections]

    def by_tag(self, tag: str) -> List[Item]:
        self._ensure_loaded()
        return [it for it in self._items if tag in it.tags]

    def by_year(self, year: int) -> List[Item]:
        self._ensure_loaded()
        return [it for it in self._items if it.date.startswith(str(year))]

    # ── 导出 ──────────────────────────────────────────
    def export_json(self, path: str) -> str:
        """导整个 library 到 JSON。"""
        self._ensure_loaded()
        data = {
            "source_db": str(self.db_path) if self.db_path else "sample",
            "item_count": len(self._items),
            "collection_count": len(self._collections),
            "items": [it.to_dict() for it in self._items],
            "collections": [asdict(c) for c in self._collections],
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def export_bibtex(self, path: str) -> str:
        """导 BibTeX 引用格式。"""
        self._ensure_loaded()
        lines = []
        for it in self._items:
            key = it.cite_key()
            typ = {"book": "book", "journalArticle": "article", "webpage": "misc"}.get(it.item_type, "misc")
            lines.append(f"@{typ}{{{key},")
            lines.append(f"  title = {{{it.title}}},")
            if it.creators:
                lines.append(f"  author = {{{' and '.join(it.creators)}}},")
            if it.date:
                lines.append(f"  year = {{{it.date[:4]}}},")
            if it.publication:
                field = "journal" if it.item_type == "journalArticle" else "publisher"
                lines.append(f"  {field} = {{{it.publication}}},")
            if it.doi:
                lines.append(f"  doi = {{{it.doi}}},")
            if it.url:
                lines.append(f"  url = {{{it.url}}},")
            lines.append("}")
            lines.append("")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text("\n".join(lines), encoding="utf-8")
        return path

    def export_for_paper(self, collection: str) -> List[Dict[str, str]]:
        """导一个 collection 的引用 entry (给 ljg-paper-flow 用)。"""
        items = self.by_collection(collection)
        return [
            {
                "key": it.cite_key(),
                "title": it.title,
                "authors": it.creators,
                "year": it.date[:4] if it.date else "",
                "venue": it.publication,
                "doi": it.doi,
            }
            for it in items
        ]

    # ── 统计 ──────────────────────────────────────────
    def stats(self) -> dict:
        self._ensure_loaded()
        types: Dict[str, int] = {}
        for it in self._items:
            types[it.item_type] = types.get(it.item_type, 0) + 1
        years: Dict[str, int] = {}
        for it in self._items:
            y = it.date[:4] if it.date else "unknown"
            years[y] = years.get(y, 0) + 1
        return {
            "total_items": len(self._items),
            "total_collections": len(self._collections),
            "by_type": types,
            "by_year": years,
            "tags": sorted({t for it in self._items for t in it.tags}),
        }
