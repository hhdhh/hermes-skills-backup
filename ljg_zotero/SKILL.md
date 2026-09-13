---
name: ljg-zotero
version: 0.1.0
description: "Zotero library 读取器 (0 依赖,纯 sqlite3)。读 Zotero SQLite DB (~/.zotero/zotero.sqlite 或 ~/Zotero/zotero.sqlite),导 JSON / BibTeX / 论文引用列表。找不到 DB 时用内置 sample (5 条文献 + 3 collection)。配合 ljg-paper-flow 自动喂参考文献。"
metadata:
  requires:
    bins: ["python3"]
    python: ">=3.9"
  cliHelp: "python3 -c 'from ljg_zotero import Library; l = Library.discover(); print(l.stats())'"
---

# ljg-zotero

Zotero library 读取器。lifestyle for AI agents to read user's local Zotero library without Zotero running.

## 何时调我

| 用户说 | 调什么 |
|---|---|
| "我 Zotero 里有什么" / "我引过什么" | `Library.discover()` + `all_items()` |
| "找 X 主题的文献" | `lib.search("X")` |
| "导 Zotero 引用" | `lib.export_bibtex("refs.bib")` |
| "导 JSON 给 ljg-paper-flow" | `lib.export_for_paper(collection_name)` |
| "Zotero 库统计" | `lib.stats()` |

## 何时不调我

- 用户要"全功能 Zotero 控制" (添加/编辑/同步) — 用 `cli-anything-zotero` (HKUDS 原版)
- 用户要"Zotero Web API" — 装 pyzotero 走网络
- 主人没装 Zotero — 走 sample data 也能 demo

## 找不到 DB?

`Library.discover()` 自动找:
- `~/Zotero/zotero.sqlite` (macOS 标准)
- `~/.zotero/zotero.sqlite`
- `~/.var/app/org.zotero.Zotero/data/Zotero/zotero.sqlite` (Linux flatpak)
- 全 `~/**/zotero.sqlite` 广搜

**找不到** → 自动用 sample (5 条文献 + 3 collection),让 agent 看 schema。

## 5 条 sample (找不到 DB 时用)

- Deep Learning (Goodfellow, 2016) — book
- Attention Is All You Need (Vaswani, 2017) — article
- Stable Diffusion (Rombach, 2022) — article
- ROS (Quigley, 2009) — book
- ROS 2 Documentation (OSRF, 2024) — webpage

3 collection: AI Reading List / Robotics Reading List / Foundational

## 快速使用

```python
from ljg_zotero import Library

# 1. 自动发现
lib = Library.discover()  # 找到 DB 用真,找不到用 sample
print(lib.stats())
# {total_items: 5, by_type: {book: 2, article: 2, webpage: 1}, ...}

# 2. 搜索
items = lib.search("transformer", field="title")
for it in items:
    print(it.cite_key(), "—", it.title)
# Vaswani2017 — Attention Is All You Need

# 3. 导 BibTeX (给 LaTeX / Pandoc 用)
lib.export_bibtex("/tmp/refs.bib")

# 4. 导 JSON (给 ljg-paper-flow)
lib.export_json("/tmp/library.json")

# 5. 给某 collection 出引用列表 (paper-flow 直接消费)
entries = lib.export_for_paper("AI Reading List")
# [{key: "Goodfellow2016", title: "Deep Learning", ...}, ...]

# 6. 按 collection / tag / year 筛
ai_books = lib.by_collection("AI Reading List")
recent = lib.by_year(2022)
ros_refs = lib.by_tag("robotics")
```

## 数据契约

`Item` 字段:
- `item_id, key, item_type` (book / journalArticle / webpage / ...)
- `title, creators, date, publication, doi, url`
- `abstract, tags, collections, date_added`
- `.cite_key()` → "Einstein1925" 风格

`Library` 字段:
- `all_items() / all_collections()`
- `search(query, field="title")` (title/creator/tag/abstract/publication)
- `by_collection(name) / by_tag(tag) / by_year(year)`
- `export_json(path) / export_bibtex(path) / export_for_paper(name)`

## 跟 ljg-paper-flow 整合

```python
from ljg_zotero import Library
lib = Library.discover()
refs = lib.export_for_paper("My Paper References")
# refs = [{key, title, authors, year, venue, doi}, ...]
# 把 refs 喂给 ljg-paper-flow:
#   from ljg_paper_flow import ...
#   paper.use_references(refs)
```

## 跟 ljg-ppt-design 整合

`stats()` 输出可以直接进 ljg-ppt-design 的 `stats` 页:
```python
from ljg_zotero import Library
from ljg_ppt_design import render_deck

lib = Library.discover()
s = lib.stats()
deck = render_deck("academic", "business", {
    "cover": {"title": "My Reading", "subtitle": str(s["total_items"]) + " papers"},
    "stats": {"title": "Reading Stats", "items": [
        {"num": str(s["total_items"]), "label": "Total"},
        {"num": str(len(s["by_type"])), "label": "Types"},
        {"num": str(len(s["tags"])), "label": "Tags"},
    ], "summary": "Read 5 books, 2 articles, 1 webpage"},
    ...
})
```

## 已知限制

- 只读不写 (本 skill 不修改 Zotero DB,只读 readonly 模式)
- 不调 Zotero Web API
- 不处理 PDF 附件
- sample data 5 条 = 演示用,生产用必须装 Zotero

---

_ljg-zotero · 0 依赖 Zotero library 读取器_
_2026-06-18 · 慧慧_
