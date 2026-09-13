#!/usr/bin/env python3
"""Archive Autolife Robot Doctor-relevant Feishu chats without printing content."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any


QUERIES = [
    "Autolife", "机器人", "robot", "Doctor", "故障", "运维", "装机",
    "Vision", "机械臂", "GV", "SDK", "Inspection", "OTA", "S2",
    "相机", "电机", "温度", "服务", "配置",
]

# These anchors are specific enough to establish that a chat belongs to the
# Robot Doctor knowledge domain. Secondary terms enrich already-relevant group
# chats but do not pull unrelated private conversations into the archive.
STRONG_QUERIES = {
    "Autolife", "机器人", "robot", "Doctor", "故障", "运维", "装机",
    "机械臂", "Inspection",
}


def safe_name(value: str) -> str:
    clean = "".join(c if c.isascii() and (c.isalnum() or c in "-_.") else "_" for c in value)
    clean = clean.strip("._") or "item"
    return f"{clean[:48]}-{hashlib.sha256(value.encode()).hexdigest()[:10]}"


def write_bytes(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(body)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def write_json(path: Path, payload: Any) -> None:
    write_bytes(path, (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    body = b"".join((json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode() for row in rows)
    write_bytes(path, body)
    return {
        "path": path.as_posix(),
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
        "count": len(rows),
    }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def diagnostic_text(completed: subprocess.CompletedProcess[str]) -> str:
    text = (completed.stderr or completed.stdout or "").strip()
    return f"exit={completed.returncode}; {text[:4000]}"


def run_lark(args: list[str], cwd: Path, timeout: int = 900) -> tuple[dict[str, Any] | None, str]:
    last = ""
    for attempt in range(6):
        try:
            completed = subprocess.run(
                ["lark-cli", *args], cwd=cwd, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired:
            last = f"timeout after {timeout}s"
            time.sleep(min(2 ** attempt, 30))
            continue
        last = diagnostic_text(completed)
        payload = None
        if completed.stdout.strip():
            try:
                payload = json.loads(completed.stdout)
            except json.JSONDecodeError:
                payload = None
        if completed.returncode == 0 and payload and payload.get("ok"):
            return payload, ""
        low = last.lower()
        retryable = any(term in low for term in ("rate limit", "too many requests", "429", "1254607", "server_error", "timeout"))
        if not retryable or attempt == 5:
            return payload, last
        time.sleep(min(2 ** attempt, 30))
    return None, last


def message_list(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    data = (payload or {}).get("data") or {}
    messages = data.get("messages") or data.get("items") or []
    return [item for item in messages if isinstance(item, dict)]


def discover_messages(root: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    raw_dir = root / "chats" / "raw" / "message-search"
    failures: list[dict[str, Any]] = []
    query_summaries: list[dict[str, Any]] = []

    def one(query: str) -> tuple[str, dict[str, Any] | None, str, Path]:
        path = raw_dir / f"{safe_name(query)}.json"
        if path.is_file():
            return query, load_json(path), "cache", path
        payload, error = run_lark([
            "im", "+messages-search", "--query", query,
            "--page-size", "50", "--page-all", "--page-limit", "40",
            "--no-reactions", "--format", "json",
        ], root)
        if payload:
            write_json(path, payload)
        return query, payload, error, path

    discovered: list[tuple[str, dict[str, Any] | None, str, Path]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(one, query) for query in QUERIES]
        for future in concurrent.futures.as_completed(futures):
            query, payload, error, path = future.result()
            discovered.append((query, payload, error, path))
            count = len(message_list(payload))
            print(f"message-search {safe_name(query)} count={count}", flush=True)

    merged: dict[str, dict[str, Any]] = {}
    for query, payload, error, path in sorted(discovered, key=lambda item: QUERIES.index(item[0])):
        if not payload or not payload.get("ok"):
            failures.append({"phase": "message_search", "query": query, "error": error})
            continue
        data = payload.get("data") or {}
        messages = message_list(payload)
        query_summaries.append({
            "query": query,
            "raw_path": str(path.relative_to(root)),
            "result_count": len(messages),
            "reported_total": data.get("total"),
            "residual_has_more": bool(data.get("has_more")),
        })
        for message in messages:
            message_id = str(message.get("message_id") or "")
            if not message_id:
                continue
            if message_id not in merged:
                merged[message_id] = dict(message)
                merged[message_id]["matched_queries"] = []
            queries = merged[message_id].setdefault("matched_queries", [])
            if query not in queries:
                queries.append(query)
    return merged, query_summaries, failures


def discover_named_chats(root: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    raw_dir = root / "chats" / "raw" / "chat-search"
    chats: dict[str, dict[str, Any]] = {}
    summaries: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    def one(query: str) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], str]:
        query_dir = raw_dir / safe_name(query)
        complete_path = query_dir / "complete.json"
        if complete_path.is_file():
            marker = load_json(complete_path)
            rows: list[dict[str, Any]] = []
            for rel in marker.get("page_paths", []):
                payload = load_json(root / rel)
                rows.extend(((payload.get("data") or {}).get("chats") or []))
            return query, rows, marker.get("page_records", []), ""
        rows: list[dict[str, Any]] = []
        page_records: list[dict[str, Any]] = []
        page_token = ""
        seen_tokens: set[str] = set()
        for number in range(1, 101):
            args = ["im", "+chat-search", "--query", query, "--page-size", "100", "--format", "json"]
            if page_token:
                args.extend(["--page-token", page_token])
            payload, error = run_lark(args, root)
            if not payload or not payload.get("ok"):
                return query, rows, page_records, error
            path = query_dir / f"page-{number:04d}.json"
            write_json(path, payload)
            data = payload.get("data") or {}
            batch = data.get("chats") or []
            rows.extend(item for item in batch if isinstance(item, dict))
            next_token = str(data.get("page_token") or "")
            has_more = bool(data.get("has_more"))
            page_records.append({"path": str(path.relative_to(root)), "count": len(batch), "has_more": has_more})
            if not has_more:
                marker = {"complete": True, "page_paths": [p["path"] for p in page_records], "page_records": page_records}
                write_json(complete_path, marker)
                return query, rows, page_records, ""
            if not next_token or next_token in seen_tokens:
                return query, rows, page_records, "pagination stopped with has_more=true and no fresh token"
            seen_tokens.add(next_token)
            page_token = next_token
        return query, rows, page_records, "page cap reached"

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(one, query) for query in STRONG_QUERIES]
        for future in concurrent.futures.as_completed(futures):
            query, rows, pages, error = future.result()
            print(f"chat-search {safe_name(query)} count={len(rows)}", flush=True)
            summaries.append({"query": query, "result_count": len(rows), "pages": len(pages)})
            if error:
                failures.append({"phase": "chat_search", "query": query, "error": error})
            for chat in rows:
                chat_id = str(chat.get("chat_id") or "")
                if chat_id:
                    chats.setdefault(chat_id, chat)
    return chats, sorted(summaries, key=lambda item: item["query"]), failures


def archive_group(root: Path, chat_id: str, metadata: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    group_dir = root / "chats" / "raw" / "groups" / safe_name(chat_id)
    summary_path = group_dir / "summary.json"
    if summary_path.is_file():
        summary = load_json(summary_path)
        if summary.get("complete"):
            return summary, summary.get("reply_roots", [])

    page_token = ""
    seen_tokens: set[str] = set()
    records: list[dict[str, Any]] = []
    messages_by_id: dict[str, dict[str, Any]] = {}
    failure = ""
    complete = False
    for number in range(1, 10001):
        args = [
            "im", "+chat-messages-list", "--chat-id", chat_id,
            "--page-size", "50", "--order", "asc", "--no-reactions", "--format", "json",
        ]
        if page_token:
            args.extend(["--page-token", page_token])
        payload, error = run_lark(args, root)
        if not payload or not payload.get("ok"):
            failure = error
            break
        path = group_dir / f"page-{number:05d}.json"
        write_json(path, payload)
        data = payload.get("data") or {}
        batch = message_list(payload)
        for message in batch:
            message_id = str(message.get("message_id") or "")
            if message_id:
                messages_by_id[message_id] = message
        has_more = bool(data.get("has_more"))
        next_token = str(data.get("page_token") or "")
        records.append({"path": str(path.relative_to(root)), "count": len(batch), "has_more": has_more})
        print(f"group-page chat={safe_name(chat_id)} page={number} count={len(batch)}", flush=True)
        if not has_more:
            complete = True
            break
        if not next_token or next_token in seen_tokens:
            failure = "pagination stopped with has_more=true and no fresh token"
            break
        seen_tokens.add(next_token)
        page_token = next_token
    else:
        failure = "page cap reached"

    rows = sorted(messages_by_id.values(), key=lambda item: (str(item.get("create_time") or ""), str(item.get("message_id") or "")))
    content_path = group_dir / "messages.jsonl"
    content_info = write_jsonl(content_path, rows)
    content_info["path"] = str(content_path.relative_to(root))
    reply_roots = sorted({str(item.get("reply_to")) for item in rows if item.get("reply_to")})
    summary = {
        "chat_id": chat_id,
        "chat_name": metadata.get("chat_name") or metadata.get("name"),
        "complete": complete,
        "failure": failure or None,
        "pages": records,
        "message_count": len(rows),
        "content": content_info,
        "reply_roots": reply_roots,
    }
    write_json(summary_path, summary)
    return summary, reply_roots


def archive_matched_details(root: Path, messages: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    ids = sorted(messages)
    raw_dir = root / "chats" / "raw" / "message-details"
    summaries: list[dict[str, Any]] = []
    for offset in range(0, len(ids), 50):
        batch = ids[offset:offset + 50]
        digest = hashlib.sha256(",".join(batch).encode()).hexdigest()[:16]
        path = raw_dir / f"batch-{offset // 50 + 1:05d}-{digest}.json"
        if path.is_file():
            payload = load_json(path)
            error = ""
        else:
            payload, error = run_lark([
                "im", "+messages-mget", "--message-ids", ",".join(batch),
                "--no-reactions", "--format", "json",
            ], root)
            if payload:
                write_json(path, payload)
        summaries.append({
            "path": str(path.relative_to(root)) if path.is_file() else None,
            "requested": len(batch),
            "received": len(message_list(payload)),
            "error": error or None,
        })
        print(f"message-details batch={offset // 50 + 1} requested={len(batch)}", flush=True)
    return summaries


def archive_thread(root: Path, root_message_id: str) -> dict[str, Any]:
    thread_dir = root / "chats" / "raw" / "threads" / safe_name(root_message_id)
    summary_path = thread_dir / "summary.json"
    if summary_path.is_file():
        return load_json(summary_path)
    page_token = ""
    seen_tokens: set[str] = set()
    messages_by_id: dict[str, dict[str, Any]] = {}
    pages: list[dict[str, Any]] = []
    status = "complete"
    failure = ""
    for number in range(1, 1001):
        args = [
            "im", "+threads-messages-list", "--thread", root_message_id,
            "--page-size", "500", "--order", "asc", "--no-reactions", "--format", "json",
        ]
        if page_token:
            args.extend(["--page-token", page_token])
        payload, error = run_lark(args, root)
        if not payload or not payload.get("ok"):
            if "thread id not found for this message" in error.lower():
                status = "not_thread"
            else:
                status = "failed"
                failure = error
            break
        path = thread_dir / f"page-{number:04d}.json"
        write_json(path, payload)
        batch = message_list(payload)
        for message in batch:
            message_id = str(message.get("message_id") or "")
            if message_id:
                messages_by_id[message_id] = message
        data = payload.get("data") or {}
        has_more = bool(data.get("has_more"))
        next_token = str(data.get("page_token") or "")
        pages.append({"path": str(path.relative_to(root)), "count": len(batch), "has_more": has_more})
        if not has_more:
            break
        if not next_token or next_token in seen_tokens:
            status = "incomplete"
            failure = "pagination stopped with has_more=true and no fresh token"
            break
        seen_tokens.add(next_token)
        page_token = next_token
    rows = sorted(messages_by_id.values(), key=lambda item: (str(item.get("create_time") or ""), str(item.get("message_id") or "")))
    content_info = None
    if rows:
        content_path = thread_dir / "messages.jsonl"
        content_info = write_jsonl(content_path, rows)
        content_info["path"] = str(content_path.relative_to(root))
    summary = {
        "root_message_id": root_message_id,
        "status": status,
        "failure": failure or None,
        "pages": pages,
        "message_count": len(rows),
        "content": content_info,
    }
    write_json(summary_path, summary)
    return summary


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    (root / "chats").mkdir(parents=True, exist_ok=True)
    started = int(time.time())

    matched, message_searches, failures = discover_messages(root)
    named_chats, chat_searches, chat_failures = discover_named_chats(root)
    failures.extend(chat_failures)

    # Establish relevant groups from strong-query message hits and strong-query
    # name matches. Private chat content is limited to strong-query hits.
    relevant_groups: dict[str, dict[str, Any]] = dict(named_chats)
    selected_private: dict[str, dict[str, Any]] = {}
    selected_matched: dict[str, dict[str, Any]] = {}
    for message_id, message in matched.items():
        queries = set(message.get("matched_queries") or [])
        if not (queries & STRONG_QUERIES):
            continue
        selected_matched[message_id] = message
        if message.get("chat_type") == "group" and message.get("chat_id"):
            relevant_groups.setdefault(str(message["chat_id"]), {
                "chat_id": message.get("chat_id"), "chat_name": message.get("chat_name"),
            })
        elif message.get("chat_type") == "p2p":
            selected_private[message_id] = message

    content_dir = root / "chats" / "content"
    matched_rows = sorted(selected_matched.values(), key=lambda item: (str(item.get("create_time") or ""), str(item.get("message_id") or "")))
    matched_info = write_jsonl(content_dir / "matched-messages.jsonl", matched_rows)
    matched_info["path"] = str((content_dir / "matched-messages.jsonl").relative_to(root))
    private_rows = sorted(selected_private.values(), key=lambda item: (str(item.get("create_time") or ""), str(item.get("message_id") or "")))
    private_info = write_jsonl(content_dir / "matched-private-messages.jsonl", private_rows)
    private_info["path"] = str((content_dir / "matched-private-messages.jsonl").relative_to(root))

    detail_batches = archive_matched_details(root, selected_matched)

    group_summaries: list[dict[str, Any]] = []
    reply_roots = {str(message.get("reply_to")) for message in selected_matched.values() if message.get("reply_to")}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(archive_group, root, chat_id, metadata): chat_id
            for chat_id, metadata in relevant_groups.items()
        }
        for future in concurrent.futures.as_completed(futures):
            summary, roots = future.result()
            group_summaries.append(summary)
            reply_roots.update(roots)
            print(f"group-complete chat={safe_name(futures[future])} messages={summary.get('message_count')} complete={summary.get('complete')}", flush=True)

    thread_summaries: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(archive_thread, root, message_id) for message_id in sorted(reply_roots)]
        for number, future in enumerate(concurrent.futures.as_completed(futures), 1):
            summary = future.result()
            thread_summaries.append(summary)
            print(f"thread-check {number}/{len(futures)} status={summary.get('status')} messages={summary.get('message_count')}", flush=True)

    group_summaries.sort(key=lambda item: str(item.get("chat_id") or ""))
    thread_summaries.sort(key=lambda item: str(item.get("root_message_id") or ""))
    for summary in group_summaries:
        summary.pop("reply_roots", None)

    incomplete_groups = [item for item in group_summaries if not item.get("complete")]
    failed_threads = [item for item in thread_summaries if item.get("status") in {"failed", "incomplete"}]
    residual_searches = [item for item in message_searches if item.get("residual_has_more")]
    failures.extend({"phase": "group_history", "chat_id": item.get("chat_id"), "error": item.get("failure")} for item in incomplete_groups)
    failures.extend({"phase": "thread", "root_message_id": item.get("root_message_id"), "error": item.get("failure")} for item in failed_threads)

    manifest = {
        "schema_version": 1,
        "created_at_unix": started,
        "completed_at_unix": int(time.time()),
        "scope": "Autolife Robot Doctor-relevant Feishu chats visible to the authorized user",
        "contract": "Full history for strong-query-relevant groups; strong-query hits only for P2P; secondary terms do not independently include private chats; resources are referenced but not downloaded.",
        "queries": QUERIES,
        "strong_queries": sorted(STRONG_QUERIES),
        "message_searches": message_searches,
        "chat_searches": chat_searches,
        "discovered_unique_messages": len(matched),
        "selected_matched_messages": len(selected_matched),
        "selected_private_messages": len(selected_private),
        "relevant_group_count": len(relevant_groups),
        "group_message_count": sum(int(item.get("message_count") or 0) for item in group_summaries),
        "thread_candidate_count": len(reply_roots),
        "archived_thread_count": sum(1 for item in thread_summaries if item.get("status") == "complete"),
        "thread_message_count": sum(int(item.get("message_count") or 0) for item in thread_summaries),
        "not_thread_count": sum(1 for item in thread_summaries if item.get("status") == "not_thread"),
        "residual_search_count": len(residual_searches),
        "matched_content": matched_info,
        "private_content": private_info,
        "message_detail_batches": detail_batches,
        "groups": group_summaries,
        "threads": thread_summaries,
        "failures": failures,
        "failure_count": len(failures),
    }
    manifest_path = root / "chat-manifest.json"
    write_json(manifest_path, manifest)
    digest = sha_file(manifest_path)
    write_bytes(root / "chat-manifest.sha256", f"{digest}  chat-manifest.json\n".encode())

    document_manifest = root / "manifest.json"
    unified = {
        "schema_version": 1,
        "created_at_unix": int(time.time()),
        "document_manifest": {
            "path": "manifest.json",
            "sha256": sha_file(document_manifest) if document_manifest.is_file() else None,
        },
        "chat_manifest": {"path": "chat-manifest.json", "sha256": digest},
        "archive_root_mode": oct(root.stat().st_mode & 0o777),
    }
    unified_path = root / "knowledge-manifest.json"
    write_json(unified_path, unified)
    write_bytes(root / "knowledge-manifest.sha256", f"{sha_file(unified_path)}  knowledge-manifest.json\n".encode())
    print(json.dumps({
        "discovered_unique_messages": len(matched),
        "selected_private_messages": len(selected_private),
        "relevant_group_count": len(relevant_groups),
        "group_message_count": manifest["group_message_count"],
        "archived_thread_count": manifest["archived_thread_count"],
        "failure_count": len(failures),
        "residual_search_count": len(residual_searches),
    }, ensure_ascii=False), flush=True)
    return 1 if failures or residual_searches else 0


if __name__ == "__main__":
    raise SystemExit(main())
