#!/usr/bin/env python3
"""Archive Autolife robot knowledge from Feishu without printing document bodies."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


DOCUMENT_QUERIES = (
    "Autolife",
    "机器人",
    "robot",
    "Doctor",
    "故障",
    "运维",
    "装机",
    "Vision",
    "机械臂",
    "GV",
    "SDK",
    "Inspection",
    "OTA",
    "S2",
    "相机",
    "电机",
    "温度",
    "服务",
    "配置",
)


def safe_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    if name:
        return name[:96]
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"item-{digest}"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def run_lark(args: list[str], cwd: Path, timeout: int = 180) -> tuple[dict[str, Any] | None, str]:
    environment = os.environ.copy()
    environment["LARKSUITE_CLI_NO_UPDATE_NOTIFIER"] = "1"
    environment["LARKSUITE_CLI_NO_SKILLS_NOTIFIER"] = "1"
    for attempt in range(6):
        completed = subprocess.run(
            ["lark-cli", *args],
            cwd=cwd,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        stderr = completed.stderr.strip()
        try:
            payload = json.loads(completed.stdout) if completed.stdout.strip() else None
        except json.JSONDecodeError:
            payload = None
        combined = f"{completed.stdout}\n{stderr}".lower()
        if completed.returncode == 0 and payload and payload.get("ok"):
            return payload, stderr
        if "rate_limit" in combined or "rate limit" in combined or "429" in combined:
            if attempt < 5:
                time.sleep(2**attempt)
                continue
        if completed.stdout.strip() and payload is None:
            return None, f"exit={completed.returncode}; invalid JSON response; stderr={stderr[:500]}"
        error = payload.get("error") if isinstance(payload, dict) else None
        return payload, f"exit={completed.returncode}; error={error}; stderr={stderr[:500]}"
    return None, "rate limit retry budget exhausted"


def discover_documents(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    discovery = root / "discovery" / "documents"
    deduplicated = discovery / "deduplicated.json"
    if deduplicated.is_file():
        cached = json.loads(deduplicated.read_text(encoding="utf-8"))
        return cached.get("results") or [], []

    def discover_query(query: str) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
        found: list[dict[str, Any]] = []
        query_failures: list[dict[str, Any]] = []
        query_dir = discovery / safe_name(query)
        page_token = ""
        page = 1
        while True:
            args = [
                "drive",
                "+search",
                "--query",
                query,
                "--page-size",
                "20",
                "--format",
                "json",
            ]
            if page_token:
                args.extend(["--page-token", page_token])
            payload, diagnostic = run_lark(args, root)
            if not payload or not payload.get("ok"):
                query_failures.append({"phase": "document_search", "query": query, "page": page, "error": diagnostic})
                break
            write_json(query_dir / f"page-{page:04d}.json", payload)
            data = payload.get("data") or {}
            for result in data.get("results") or []:
                found.append(result)
            if not data.get("has_more"):
                break
            next_token = data.get("page_token") or ""
            if not next_token or next_token == page_token:
                query_failures.append({"phase": "document_search", "query": query, "page": page, "error": "pagination token missing or repeated"})
                break
            page_token = next_token
            page += 1
            if page > 200:
                query_failures.append({"phase": "document_search", "query": query, "error": "pagination safety limit reached"})
                break
        return query, found, query_failures

    by_url: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(discover_query, query) for query in DOCUMENT_QUERIES]
        for future in concurrent.futures.as_completed(futures):
            query, found, query_failures = future.result()
            failures.extend(query_failures)
            for result in found:
                meta = result.get("result_meta") or {}
                url = meta.get("url") or ""
                if not url:
                    continue
                current = by_url.setdefault(url, result)
                current.setdefault("matched_queries", [])
                if query not in current["matched_queries"]:
                    current["matched_queries"].append(query)
    results = sorted(by_url.values(), key=lambda item: ((item.get("result_meta") or {}).get("url") or ""))
    write_json(deduplicated, {"queries": DOCUMENT_QUERIES, "count": len(results), "results": results})
    return results, failures


def inspect_document(root: Path, url: str) -> tuple[dict[str, Any] | None, str]:
    cache = root / "discovery" / "inspected" / f"{hashlib.sha256(url.encode('utf-8')).hexdigest()}.json"
    if cache.is_file():
        cached = json.loads(cache.read_text(encoding="utf-8"))
        return cached, "cache"
    payload, diagnostic = run_lark(["drive", "+inspect", "--url", url, "--format", "json"], root)
    if not payload or not payload.get("ok"):
        return None, diagnostic
    inspected = payload.get("data") or {}
    write_json(cache, inspected)
    return inspected, diagnostic


def archive_docx(root: Path, original_url: str, token: str) -> tuple[dict[str, Any] | None, str]:
    raw_path = root / "documents" / "raw" / f"{safe_name(token)}.json"
    content_path = root / "documents" / "content" / f"{safe_name(token)}.md"
    if raw_path.is_file() and content_path.is_file():
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
        document = ((payload.get("data") or {}).get("document") or {})
        content = content_path.read_text(encoding="utf-8")
        return {
            "revision_id": document.get("revision_id"),
            "document_id": document.get("document_id"),
            "content_path": str(content_path.relative_to(root)),
            "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "content_bytes": len(content.encode("utf-8")),
        }, "cache"
    payload, diagnostic = run_lark(
        ["docs", "+fetch", "--doc", original_url, "--doc-format", "markdown", "--detail", "simple"],
        root,
        timeout=300,
    )
    if not payload or not payload.get("ok"):
        return None, diagnostic
    write_json(raw_path, payload)
    document = ((payload.get("data") or {}).get("document") or {})
    content = document.get("content") or ""
    write_text(content_path, content)
    return {
        "revision_id": document.get("revision_id"),
        "document_id": document.get("document_id"),
        "content_path": f"documents/content/{safe_name(token)}.md",
        "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "content_bytes": len(content.encode("utf-8")),
    }, diagnostic


def archive_file(root: Path, token: str, extension: str) -> tuple[dict[str, Any] | None, str]:
    extension = safe_name(extension.lower()) or "bin"
    relative = Path("files") / f"{safe_name(token)}.{extension}"
    (root / relative.parent).mkdir(parents=True, exist_ok=True)
    path = root / relative
    if path.is_file():
        body = path.read_bytes()
        return {"content_path": relative.as_posix(), "content_sha256": hashlib.sha256(body).hexdigest(), "content_bytes": len(body)}, "cache"
    payload, diagnostic = run_lark(
        ["drive", "+download", "--file-token", token, "--output", f"./{relative.as_posix()}"],
        root,
        timeout=600,
    )
    if not payload or not payload.get("ok") or not path.is_file():
        return None, diagnostic or "download did not create a file"
    os.chmod(path, 0o600)
    body = path.read_bytes()
    return {"content_path": relative.as_posix(), "content_sha256": hashlib.sha256(body).hexdigest(), "content_bytes": len(body)}, diagnostic


def archive_export(root: Path, token: str, doc_type: str) -> tuple[dict[str, Any] | None, str]:
    extension_for = {"doc": "docx", "sheet": "xlsx", "bitable": "base", "slides": "pptx"}
    extension = extension_for[doc_type]
    relative_dir = Path("exports") / doc_type
    (root / relative_dir).mkdir(parents=True, exist_ok=True)
    # Native .base export occasionally fails server-side for some bitables even
    # though the same source exports successfully as XLSX. Preserve .base when
    # available, then fall back to XLSX so a transient format failure does not
    # leave the knowledge archive without table content.
    extensions = [extension, "xlsx"] if doc_type == "bitable" else [extension]
    diagnostics: list[str] = []
    for candidate_extension in extensions:
        file_name = f"{safe_name(token)}.{candidate_extension}"
        path = root / relative_dir / file_name
        if path.is_file():
            body = path.read_bytes()
            return {"content_path": str(path.relative_to(root)), "content_sha256": hashlib.sha256(body).hexdigest(), "content_bytes": len(body)}, "cache"
        args = [
            "drive",
            "+export",
            "--token",
            token,
            "--doc-type",
            doc_type,
            "--file-extension",
            candidate_extension,
            "--file-name",
            file_name,
            "--output-dir",
            f"./{relative_dir.as_posix()}",
        ]
        payload, diagnostic = run_lark(args, root, timeout=180)
        diagnostics.append(f"{candidate_extension}: {diagnostic}")
        receipt_path = root / "documents" / "export-receipts" / f"{safe_name(token)}-{candidate_extension}.json"
        if payload:
            write_json(receipt_path, payload)
        if not payload or not payload.get("ok"):
            continue
        if not path.is_file():
            data = payload.get("data") or {}
            return {
                "export_pending": True,
                "ticket": data.get("ticket"),
                "next_command": data.get("next_command"),
                "receipt_path": str(receipt_path.relative_to(root)),
            }, diagnostic
        os.chmod(path, 0o600)
        body = path.read_bytes()
        return {"content_path": str(path.relative_to(root)), "content_sha256": hashlib.sha256(body).hexdigest(), "content_bytes": len(body)}, diagnostic
    return None, " | ".join(diagnostics)


def archive_documents(root: Path, results: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    entries: list[dict[str, Any] | None] = [None] * len(results)
    failures: list[dict[str, Any]] = []

    def inspect_one(number: int, result: dict[str, Any]) -> tuple[int, dict[str, Any], dict[str, Any]]:
        meta = result.get("result_meta") or {}
        original_url = meta.get("url") or ""
        original_token = meta.get("token") or ""
        entry: dict[str, Any] = {
            "original_url": original_url,
            "original_token": original_token,
            "search_doc_types": meta.get("doc_types"),
            "title_highlighted": result.get("title_highlighted"),
            "owner_name": meta.get("owner_name"),
            "update_time": meta.get("update_time"),
            "update_time_iso": meta.get("update_time_iso"),
            "matched_queries": result.get("matched_queries") or [],
        }
        inspected, diagnostic = inspect_document(root, original_url)
        if not inspected:
            entry["status"] = "inspect_failed"
            entry["error"] = diagnostic
            return number, entry, meta
        entry.update(
            {
                "title": inspected.get("title"),
                "canonical_url": inspected.get("url"),
                "canonical_token": inspected.get("token"),
                "canonical_type": inspected.get("type"),
                "wiki_node": inspected.get("wiki_node"),
            }
        )
        return number, entry, meta

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(inspect_one, number, result) for number, result in enumerate(results)]
        for future in concurrent.futures.as_completed(futures):
            number, entry, _ = future.result()
            entries[number] = entry
            if entry.get("status") == "inspect_failed":
                failures.append({"phase": "inspect", "url": entry.get("original_url"), "error": entry.get("error")})

    groups: dict[tuple[str, str], list[int]] = {}
    for number, entry in enumerate(entries):
        assert entry is not None
        if entry.get("status") == "inspect_failed":
            continue
        key = ((entry.get("canonical_type") or "").lower(), entry.get("canonical_token") or entry.get("original_token") or "")
        groups.setdefault(key, []).append(number)

    def archive_group(key: tuple[str, str], indexes: list[int]) -> tuple[tuple[str, str], list[int], dict[str, Any] | None, str, str | None, str | None]:
        doc_type, token = key
        first = entries[indexes[0]]
        assert first is not None
        archived: dict[str, Any] | None = None
        error = ""
        if doc_type == "docx":
            archived, error = archive_docx(root, first.get("original_url") or first.get("canonical_url") or "", token)
        elif doc_type == "file":
            search_result = results[indexes[0]]
            archived, error = archive_file(root, token, (search_result.get("result_meta") or {}).get("file_type") or "bin")
        elif doc_type in {"doc", "sheet", "bitable", "slides"}:
            archived, error = archive_export(root, token, doc_type)
        elif doc_type in {"folder", "catalog", "shortcut", "mindnote"}:
            return key, indexes, None, "", "indexed_only", f"content extraction not selected for {doc_type}"
        else:
            return key, indexes, None, "", "unsupported", f"unsupported canonical type: {doc_type}"
        return key, indexes, archived, error, None, None

    completed_groups = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(archive_group, key, indexes) for key, indexes in groups.items()]
        for future in concurrent.futures.as_completed(futures):
            key, indexes, archived, error, fixed_status, reason = future.result()
            doc_type, token = key
            completed_groups += 1
            print(f"[{completed_groups}/{len(groups)}] {doc_type or 'unknown'} {token}", flush=True)
            for number in indexes:
                entry = entries[number]
                assert entry is not None
                if fixed_status:
                    entry["status"] = fixed_status
                    entry["reason"] = reason
                elif archived is not None:
                    entry.update(archived)
                    entry["status"] = "pending" if archived.get("export_pending") else "archived"
                else:
                    entry["status"] = "archive_failed"
                    entry["error"] = error
            if archived is None and not fixed_status:
                failures.append({"phase": "archive", "token": token, "type": doc_type, "error": error})
            if completed_groups % 10 == 0 or completed_groups == len(groups):
                write_json(root / "manifest.partial.json", {"entries": entries, "failures": failures})
    return [entry for entry in entries if entry is not None], failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    root = args.output.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    started = time.time()
    results, search_failures = discover_documents(root)
    entries, archive_failures = archive_documents(root, results)
    manifest = {
        "contract": "autolife.robot-knowledge-archive",
        "schema_version": 1,
        "created_at_unix": int(started),
        "completed_at_unix": int(time.time()),
        "scope": "Autolife robot and Doctor related resources discoverable by configured queries",
        "queries": DOCUMENT_QUERIES,
        "document_count": len(entries),
        "archived_count": sum(entry.get("status") == "archived" for entry in entries),
        "pending_count": sum(entry.get("status") == "pending" for entry in entries),
        "indexed_only_count": sum(entry.get("status") == "indexed_only" for entry in entries),
        "failure_count": len(search_failures) + len(archive_failures),
        "entries": entries,
        "failures": search_failures + archive_failures,
    }
    write_json(root / "manifest.json", manifest)
    digest = hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest()
    write_text(root / "manifest.sha256", f"{digest}  manifest.json\n")
    print(json.dumps({key: manifest[key] for key in ("document_count", "archived_count", "pending_count", "indexed_only_count", "failure_count")}, ensure_ascii=False))
    return 0 if not manifest["failure_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
