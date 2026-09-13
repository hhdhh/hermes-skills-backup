#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pypdf>=6,<7"]
# ///
"""Build and query a private local index of Autolife Feishu knowledge."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import time
from typing import Any, Iterable
import zipfile
import xml.etree.ElementTree as ET


DEFAULT_ARCHIVE = Path.home() / ".local" / "share" / "autolife-robot-knowledge" / "current"
TEXT_SUFFIXES = {".md", ".txt", ".json", ".base", ".xml", ".csv", ".yaml", ".yml"}
OFFICE_SUFFIXES = {".docx", ".pptx", ".xlsx"}
QUERY_SAFETY = {
    "evidence_class": "Feishu historical knowledge and conversation",
    "integrity_scope": "self-consistent local unsigned archive",
    "authoritative_for_live_robot_state": False,
    "authorizes_repair": False,
    "zero_results_prove_absence": False,
    "source_recheck_required": True,
}
QUERY_LIMIT = 12


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_private(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(body)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def verify_sidecar(root: Path, data_name: str, sidecar_name: str) -> bool:
    data = root / data_name
    sidecar = root / sidecar_name
    if data.is_symlink() or sidecar.is_symlink() or not data.is_file() or not sidecar.is_file():
        return False
    try:
        expected = sidecar.read_text().split()[0]
    except (OSError, IndexError):
        return False
    return sha256(data) == expected


def private_mode(path: Path, expected: int) -> bool:
    try:
        return (path.stat().st_mode & 0o777) == expected
    except OSError:
        return False


def query_integrity(root: Path, database: Path) -> dict[str, Any]:
    """Verify every artifact that authorizes historical-knowledge queries.

    The index is useful for forming hypotheses, so a corrupted or stale binding
    must fail before snippets are returned. Stable reason codes make the HOLD
    actionable without printing private archive contents.
    """

    errors: list[str] = []
    if not root.is_dir():
        errors.append("archive_root_missing")
    elif not private_mode(root, 0o700):
        errors.append("archive_root_permissions")

    sidecars = (
        ("manifest.json", "manifest.sha256", "document_manifest_integrity"),
        ("chat-manifest.json", "chat-manifest.sha256", "chat_manifest_integrity"),
        ("knowledge-manifest.json", "knowledge-manifest.sha256", "knowledge_manifest_integrity"),
        ("knowledge-index-manifest.json", "knowledge-index-manifest.sha256", "index_manifest_integrity"),
    )
    for data_name, sidecar_name, reason in sidecars:
        if not verify_sidecar(root, data_name, sidecar_name):
            errors.append(reason)
        for name in (data_name, sidecar_name):
            path = root / name
            if path.exists() and not private_mode(path, 0o600):
                errors.append(f"{reason}_permissions")

    database_hash = ""
    database_sidecar = database.with_suffix(database.suffix + ".sha256")
    database_regular = database.is_file() and not database.is_symlink()
    database_sidecar_regular = database_sidecar.is_file() and not database_sidecar.is_symlink()
    if not database_regular:
        errors.append("database_not_regular" if database.exists() or database.is_symlink() else "database_missing")
    else:
        if not private_mode(database, 0o600):
            errors.append("database_permissions")
        if not database_sidecar_regular or not private_mode(database_sidecar, 0o600):
            errors.append("database_sidecar_permissions")
        try:
            database_hash = sha256(database)
            if not database_sidecar_regular:
                raise OSError("database sidecar is missing or not a regular file")
            expected = database_sidecar.read_text().split()[0]
            if database_hash != expected:
                errors.append("database_integrity")
        except (OSError, IndexError):
            errors.append("database_integrity")

    document_hash = ""
    chat_hash = ""
    try:
        document_hash = sha256(root / "manifest.json")
        chat_hash = sha256(root / "chat-manifest.json")
        knowledge = read_json(root / "knowledge-manifest.json")
        if (knowledge.get("document_manifest") or {}).get("sha256") != document_hash:
            errors.append("knowledge_document_binding")
        if (knowledge.get("chat_manifest") or {}).get("sha256") != chat_hash:
            errors.append("knowledge_chat_binding")
    except (OSError, json.JSONDecodeError, AttributeError):
        errors.append("knowledge_manifest_binding")

    index_manifest: dict[str, Any] = {}
    try:
        index_manifest = read_json(root / "knowledge-index-manifest.json")
        if index_manifest.get("document_manifest_sha256") != document_hash:
            errors.append("index_document_binding")
        if index_manifest.get("chat_manifest_sha256") != chat_hash:
            errors.append("index_chat_binding")
        if index_manifest.get("database_sha256") != database_hash:
            errors.append("index_database_binding")
        if index_manifest.get("database") != database.name:
            errors.append("index_database_name_binding")
    except (OSError, json.JSONDecodeError, AttributeError):
        errors.append("index_manifest_binding")

    if database_regular and "database_integrity" not in errors:
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                errors.append("sqlite_integrity")
            source_count = int(connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0])
            fts_count = int(connection.execute("SELECT COUNT(*) FROM sources_fts").fetchone()[0])
            if source_count != index_manifest.get("source_count"):
                errors.append("sqlite_source_count")
            if fts_count != source_count:
                errors.append("sqlite_fts_count")
            counts = dict(connection.execute("SELECT kind, COUNT(*) FROM sources GROUP BY kind").fetchall())
            if counts != index_manifest.get("counts_by_kind"):
                errors.append("sqlite_kind_counts")
        except (OSError, sqlite3.Error, TypeError, ValueError):
            errors.append("sqlite_integrity")
        finally:
            if connection is not None:
                connection.close()

    return {
        "query_ready": not errors,
        "query_errors": sorted(set(errors)),
        "database_sha256": database_hash or None,
        "integrity_scope": "self-consistent local unsigned archive",
    }


def require_query_integrity(root: Path, database: Path) -> dict[str, Any]:
    integrity = query_integrity(root, database)
    if not integrity["query_ready"]:
        raise RuntimeError(
            "knowledge_integrity_hold: " + ",".join(integrity["query_errors"])
        )
    return integrity


def iter_xml_text(body: bytes) -> Iterable[str]:
    try:
        element = ET.fromstring(body)
    except ET.ParseError:
        return []
    return (text.strip() for text in element.itertext() if text and text.strip())


def extract_office(path: Path) -> str:
    parts: list[str] = []
    with zipfile.ZipFile(path) as archive:
        for name in sorted(archive.namelist()):
            include = False
            if path.suffix.lower() == ".docx":
                include = name.startswith("word/") and name.endswith(".xml") and not name.startswith("word/theme/")
            elif path.suffix.lower() == ".pptx":
                include = (name.startswith("ppt/slides/") or name.startswith("ppt/notesSlides/")) and name.endswith(".xml")
            elif path.suffix.lower() == ".xlsx":
                include = (name == "xl/sharedStrings.xml" or name.startswith("xl/worksheets/")) and name.endswith(".xml")
            if include:
                parts.extend(iter_xml_text(archive.read(name)))
    return "\n".join(parts)


def extract_text(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    with path.open("rb") as handle:
        magic = handle.read(8)
    if magic.startswith(b"%PDF-"):
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path), strict=False)
            parts = [(page.extract_text() or "") for page in reader.pages]
            text = "\n".join(part for part in parts if part.strip())
            return (text, "pdf:pypdf") if text else ("", "pdf_scan_metadata_only")
        except (ImportError, OSError, ValueError):
            return "", "pdf_metadata_only"
    if suffix in TEXT_SUFFIXES:
        return path.read_text(errors="replace"), "text"
    if suffix in OFFICE_SUFFIXES and zipfile.is_zipfile(path):
        return extract_office(path), f"office_xml:{suffix[1:]}"
    if zipfile.is_zipfile(path):
        return extract_office(path), "office_xml:zip"
    return "", "binary_metadata_only"


def extract_text_cached(root: Path, path: Path, content_hash: str) -> tuple[str, str]:
    cache_dir = root / ".knowledge-cache" / "extracted-documents"
    text_path = cache_dir / f"{content_hash}.txt"
    metadata_path = cache_dir / f"{content_hash}.json"
    if text_path.is_file() and metadata_path.is_file():
        metadata = read_json(metadata_path)
        return text_path.read_text(errors="replace"), str(metadata.get("mode") or "cache")
    text, mode = extract_text(path)
    write_private(text_path, text.encode(errors="replace"))
    write_private(metadata_path, (json.dumps({"mode": mode}, sort_keys=True) + "\n").encode())
    return text, mode


def flatten_message_content(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
        return flatten_message_content(decoded)
    if isinstance(value, dict):
        return "\n".join(flatten_message_content(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(flatten_message_content(item) for item in value)
    return str(value)


def normalize_index_text(value: str) -> str:
    """Remove control bytes that make FTS5 tokenization non-reproducible."""
    return "".join(" " if character == "\x00" or (ord(character) < 32 and character not in "\t\n\r") else character for character in value)


def chat_title(message: dict[str, Any], fallback: str) -> str:
    if message.get("chat_name"):
        return str(message["chat_name"])
    partner = message.get("chat_partner")
    if isinstance(partner, dict):
        return str(partner.get("name") or partner.get("display_name") or fallback)
    return fallback


def insert_source(
    connection: sqlite3.Connection,
    source_id: str,
    kind: str,
    source_ref: str,
    title: str,
    timestamp: str,
    content: str,
    content_hash: str,
    metadata: dict[str, Any],
) -> None:
    title = normalize_index_text(title)
    content = normalize_index_text(content)
    cursor = connection.execute(
        "INSERT OR IGNORE INTO sources(source_id,kind,source_ref,title,timestamp,content,content_sha256,metadata_json) VALUES(?,?,?,?,?,?,?,?)",
        (source_id, kind, source_ref, title, timestamp, content, content_hash, json.dumps(metadata, ensure_ascii=False, sort_keys=True)),
    )
    if cursor.rowcount:
        rowid = connection.execute("SELECT id FROM sources WHERE source_id=?", (source_id,)).fetchone()[0]
        connection.execute("INSERT INTO sources_fts(rowid,title,content) VALUES(?,?,?)", (rowid, title, content))


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open() as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    yield value


def build_index(root: Path, database: Path) -> dict[str, Any]:
    if not verify_sidecar(root, "manifest.json", "manifest.sha256"):
        raise RuntimeError("document manifest hash validation failed")
    if not verify_sidecar(root, "chat-manifest.json", "chat-manifest.sha256"):
        raise RuntimeError("chat manifest hash validation failed")
    if not verify_sidecar(root, "knowledge-manifest.json", "knowledge-manifest.sha256"):
        raise RuntimeError("unified knowledge manifest hash validation failed")

    documents = read_json(root / "manifest.json")
    chats = read_json(root / "chat-manifest.json")
    database.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(prefix="knowledge-", suffix=".sqlite3", dir=database.parent)
    os.close(file_descriptor)
    temporary = Path(temporary_name)
    os.chmod(temporary, 0o600)
    connection = sqlite3.connect(temporary)
    try:
        connection.executescript(
            """
            PRAGMA journal_mode=DELETE;
            PRAGMA synchronous=FULL;
            CREATE TABLE sources(
                id INTEGER PRIMARY KEY,
                source_id TEXT NOT NULL UNIQUE,
                kind TEXT NOT NULL,
                source_ref TEXT NOT NULL,
                title TEXT NOT NULL,
                timestamp TEXT,
                content TEXT NOT NULL,
                content_sha256 TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            );
            CREATE INDEX sources_kind_idx ON sources(kind);
            CREATE VIRTUAL TABLE sources_fts USING fts5(title, content, tokenize='trigram');
            """
        )
        modes: dict[str, int] = {}
        indexed_document_hashes: set[str] = set()
        for entry in documents.get("entries", []):
            if entry.get("status") != "archived" or not entry.get("content_path"):
                continue
            content_hash = str(entry.get("content_sha256") or "")
            if not content_hash or content_hash in indexed_document_hashes:
                continue
            indexed_document_hashes.add(content_hash)
            path = root / str(entry["content_path"])
            text, mode = extract_text_cached(root, path, content_hash)
            modes[mode] = modes.get(mode, 0) + 1
            title = str(entry.get("title") or path.name)
            if not text:
                text = " ".join([title, " ".join(entry.get("matched_queries") or [])])
            insert_source(
                connection,
                f"document:{content_hash}",
                "feishu_document",
                str(entry.get("canonical_url") or entry.get("original_url") or path),
                title,
                str(entry.get("update_time_iso") or entry.get("update_time") or ""),
                text,
                content_hash,
                {
                    "evidence_class": "Feishu knowledge",
                    "content_path": str(entry["content_path"]),
                    "extraction_mode": mode,
                    "matched_queries": entry.get("matched_queries") or [],
                },
            )

        group_paths: dict[str, str] = {}
        for group in chats.get("groups", []):
            info = group.get("content") or {}
            if info.get("path"):
                group_paths[str(info["path"])] = str(group.get("chat_name") or "Feishu group chat")
        chat_files: list[tuple[str, str]] = [(path, "feishu_group_message") for path in group_paths]
        private_path = (chats.get("private_content") or {}).get("path")
        if private_path:
            chat_files.append((str(private_path), "feishu_private_message"))
        indexed_message_ids: set[str] = set()
        for relative, kind in chat_files:
            path = root / relative
            for message in iter_jsonl(path):
                message_id = str(message.get("message_id") or "")
                if not message_id or message_id in indexed_message_ids:
                    continue
                indexed_message_ids.add(message_id)
                content = flatten_message_content(message.get("content"))
                title = chat_title(message, group_paths.get(relative, "Feishu private chat"))
                body_hash = hashlib.sha256(content.encode()).hexdigest()
                insert_source(
                    connection,
                    f"message:{message_id}",
                    kind,
                    str(message.get("message_app_link") or f"feishu-message:{message_id}"),
                    title,
                    str(message.get("update_time") or message.get("create_time") or ""),
                    content,
                    body_hash,
                    {
                        "evidence_class": "Feishu conversation",
                        "chat_id": message.get("chat_id"),
                        "message_id": message_id,
                        "msg_type": message.get("msg_type"),
                        "deleted": bool(message.get("deleted")),
                        "updated": bool(message.get("updated")),
                    },
                )
        connection.commit()
        counts = dict(connection.execute("SELECT kind, COUNT(*) FROM sources GROUP BY kind").fetchall())
        total = int(connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0])
    finally:
        connection.close()
    os.replace(temporary, database)
    os.chmod(database, 0o600)
    index_hash = sha256(database)
    write_private(database.with_suffix(database.suffix + ".sha256"), f"{index_hash}  {database.name}\n".encode())
    result = {
        "schema_version": 1,
        "built_at_unix": int(time.time()),
        "database": database.name,
        "database_sha256": index_hash,
        "document_manifest_sha256": sha256(root / "manifest.json"),
        "chat_manifest_sha256": sha256(root / "chat-manifest.json"),
        "source_count": total,
        "counts_by_kind": counts,
        "document_extraction_modes": modes,
        "safety": "Feishu sources are historical knowledge, not live robot or release evidence.",
    }
    write_private(root / "knowledge-index-manifest.json", (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())
    write_private(root / "knowledge-index-manifest.sha256", f"{sha256(root / 'knowledge-index-manifest.json')}  knowledge-index-manifest.json\n".encode())
    return result


def redact_excerpt(text: str) -> str:
    text = re.sub(r"-----BEGIN [^-]+ PRIVATE KEY-----.*?-----END [^-]+ PRIVATE KEY-----", "[REDACTED PRIVATE KEY]", text, flags=re.S)
    text = re.sub(r"(?i)\b(bearer|token|password|passwd|secret|api[_-]?key)\b\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]", text)
    text = re.sub(r"\b(gh[pousr]_[A-Za-z0-9_]{20,}|t-[A-Za-z0-9_-]{20,})\b", "[REDACTED TOKEN]", text)
    return " ".join(text.split())


def search_index(database: Path, query: str, limit: int, kinds: list[str]) -> list[dict[str, Any]]:
    if not database.is_file():
        raise RuntimeError(f"knowledge index not found: {database}")
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    where_kind = ""
    parameters: list[Any] = []
    if kinds:
        where_kind = f" AND s.kind IN ({','.join('?' for _ in kinds)})"
        parameters.extend(kinds)
    escaped = query.replace('"', '""')
    match = f'"{escaped}"'
    rows: list[sqlite3.Row] = []
    if len(query.strip()) >= 3:
        rows = connection.execute(
            "SELECT s.source_id,s.kind,s.source_ref,s.title,s.timestamp,s.metadata_json,"
            "snippet(sources_fts,1,'[[',']]',' … ',48) AS excerpt,bm25(sources_fts,8.0,1.0) AS rank "
            "FROM sources_fts JOIN sources s ON s.id=sources_fts.rowid WHERE sources_fts MATCH ?"
            + where_kind + " ORDER BY rank LIMIT ?",
            [match, *parameters, limit],
        ).fetchall()
    if not rows:
        rows = connection.execute(
            "SELECT s.source_id,s.kind,s.source_ref,s.title,s.timestamp,s.metadata_json,"
            "substr(s.content,max(1,instr(lower(s.content),lower(?))-120),360) AS excerpt,0.0 AS rank "
            "FROM sources s WHERE (instr(lower(s.title),lower(?))>0 OR instr(lower(s.content),lower(?))>0)"
            + where_kind + " LIMIT ?",
            [query, query, query, *parameters, limit],
        ).fetchall()
    connection.close()
    return [
        {
            "source_id": row["source_id"],
            "kind": row["kind"],
            "source_ref": row["source_ref"],
            "title": row["title"],
            "timestamp": row["timestamp"],
            "excerpt": redact_excerpt(row["excerpt"] or ""),
            "rank": row["rank"],
            "metadata": json.loads(row["metadata_json"]),
        }
        for row in rows
    ]


def status(root: Path, database: Path) -> dict[str, Any]:
    result = {
        "archive_root": str(root),
        "archive_root_mode": oct(root.stat().st_mode & 0o777) if root.exists() else None,
        "document_manifest_valid": verify_sidecar(root, "manifest.json", "manifest.sha256"),
        "chat_manifest_valid": verify_sidecar(root, "chat-manifest.json", "chat-manifest.sha256"),
        "knowledge_manifest_valid": verify_sidecar(root, "knowledge-manifest.json", "knowledge-manifest.sha256"),
        "index_present": database.is_file(),
        "index_mode": oct(database.stat().st_mode & 0o777) if database.is_file() else None,
        "index_hash_valid": database.is_file() and database.with_suffix(database.suffix + ".sha256").is_file() and sha256(database) == database.with_suffix(database.suffix + ".sha256").read_text().split()[0],
    }
    index_manifest = root / "knowledge-index-manifest.json"
    if index_manifest.is_file():
        try:
            result["index"] = read_json(index_manifest)
            result["index_manifest_readable"] = True
        except (OSError, json.JSONDecodeError):
            result["index"] = None
            result["index_manifest_readable"] = False
        result["index_manifest_valid"] = verify_sidecar(root, "knowledge-index-manifest.json", "knowledge-index-manifest.sha256")
    result.update(query_integrity(root, database))
    return result


def normalized_queries(values: list[str]) -> list[str]:
    queries: list[str] = []
    seen: set[str] = set()
    for value in values:
        query = " ".join(value.split())
        if not query:
            raise ValueError("query must not be empty")
        if len(query) > 200:
            raise ValueError("query must not exceed 200 characters")
        if "\x00" in query:
            raise ValueError("query must not contain NUL")
        if query not in seen:
            seen.add(query)
            queries.append(query)
    if len(queries) > QUERY_LIMIT:
        raise ValueError(f"at most {QUERY_LIMIT} distinct queries are allowed")
    return queries


def search_many(
    database: Path,
    queries: list[str],
    limit: int,
    kinds: list[str],
) -> dict[str, Any]:
    grouped: list[dict[str, Any]] = []
    distinct_sources: set[str] = set()
    zero_hit_queries: list[str] = []
    for query in queries:
        results = search_index(database, query, limit, kinds)
        if not results:
            zero_hit_queries.append(query)
        distinct_sources.update(str(result["source_id"]) for result in results)
        grouped.append({"query": query, "count": len(results), "results": results})
    return {
        "schema_version": 1,
        "query_count": len(queries),
        "distinct_source_count": len(distinct_sources),
        "zero_hit_queries": zero_hit_queries,
        "queries": grouped,
        "safety": QUERY_SAFETY,
    }


def print_text_results(grouped: list[dict[str, Any]]) -> None:
    print(
        "SAFETY integrity=self-consistent-local-unsigned source_recheck=true "
        "historical_only=true live_authority=false repair_authority=false zero_hits_are_not_absence=true"
    )
    for query_result in grouped:
        print(f"\nQUERY {query_result['query']} | {query_result['count']} hit(s)")
        for number, result in enumerate(query_result["results"], 1):
            print(f"[{number}] {result['kind']} | {result['title']} | {result['source_ref']}")
            print(f"    {result['excerpt']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", type=Path, default=Path(os.environ.get("AUTOLIFE_DOCTOR_KNOWLEDGE_ROOT", DEFAULT_ARCHIVE)))
    parser.add_argument("--database", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")
    subparsers.add_parser("build")
    search = subparsers.add_parser("search")
    search.add_argument("--query", required=True)
    search.add_argument("--limit", type=int, default=12)
    search.add_argument("--kind", action="append", default=[])
    search.add_argument("--json", action="store_true")
    search_many_parser = subparsers.add_parser(
        "search-many",
        help="run independent historical queries and keep zero-hit queries visible",
    )
    search_many_parser.add_argument("--query", action="append", required=True)
    search_many_parser.add_argument("--limit", type=int, default=6, help="maximum hits per query")
    search_many_parser.add_argument("--kind", action="append", default=[])
    search_many_parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = args.archive_root.expanduser().resolve()
    # Keep the final database path component unresolved.  query_integrity()
    # must be able to observe and reject a database symlink before SQLite opens
    # it; Path.resolve() here would erase that security-relevant fact.
    database = (args.database or (root / "knowledge.sqlite3")).expanduser().absolute()
    if args.command == "build":
        print(json.dumps(build_index(root, database), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command == "status":
        print(json.dumps(status(root, database), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    try:
        before = require_query_integrity(root, database)
        queries = normalized_queries(args.query if args.command == "search-many" else [args.query])
        result = search_many(database, queries, max(1, min(args.limit, 100)), args.kind)
        after = require_query_integrity(root, database)
        if before["database_sha256"] != after["database_sha256"]:
            raise RuntimeError("knowledge_integrity_hold: database_changed_during_query")
    except (RuntimeError, ValueError) as error:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "knowledge_integrity_hold",
                    "detail": str(error),
                    "safety": QUERY_SAFETY,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    if args.command == "search":
        single = result["queries"][0]
        result = {
            "query": single["query"],
            "count": single["count"],
            "results": single["results"],
            "safety": QUERY_SAFETY,
        }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "search":
        print_text_results([{"query": result["query"], "count": result["count"], "results": result["results"]}])
    else:
        print_text_results(result["queries"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
