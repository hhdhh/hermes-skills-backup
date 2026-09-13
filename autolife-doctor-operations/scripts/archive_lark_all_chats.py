#!/usr/bin/env python3
"""Archive the FULL history of every visible Feishu chat (group + p2p) without printing content.

Reuses archive_lark_chats.py primitives; writes a chat-manifest.json compatible
with skills/autolife-doctor-operations/scripts/private_knowledge.py.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from archive_lark_chats import (  # noqa: E402
    archive_group,
    archive_thread,
    run_lark,
    safe_name,
    sha_file,
    write_bytes,
    write_json,
    write_jsonl,
)


def list_all_chats(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    items: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    token = ""
    seen: set[str] = set()
    for _ in range(200):
        args = ["im", "+chat-list", "--types=p2p,group", "--page-size", "100", "--format", "json"]
        if token:
            args.extend(["--page-token", token])
        payload, error = run_lark(args, root)
        if not payload or not payload.get("ok"):
            failures.append({"phase": "chat_list", "error": error})
            break
        data = payload.get("data") or {}
        items.extend(item for item in (data.get("items") or data.get("chats") or []) if isinstance(item, dict))
        if not data.get("has_more"):
            break
        token = str(data.get("page_token") or "")
        if not token or token in seen:
            failures.append({"phase": "chat_list", "error": "pagination stopped with has_more=true and no fresh token"})
            break
        seen.add(token)
    unique: dict[str, dict[str, Any]] = {}
    for item in items:
        chat_id = str(item.get("chat_id") or "")
        if chat_id:
            unique.setdefault(chat_id, item)
    return list(unique.values()), failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    root = args.output.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    started = int(time.time())

    # Preserve the prior manifest for audit before overwriting.
    previous = root / "chat-manifest.json"
    if previous.is_file() and not (root / "chat-manifest.previous.json").is_file():
        write_bytes(root / "chat-manifest.previous.json", previous.read_bytes())

    chats, failures = list_all_chats(root)
    groups = [chat for chat in chats if (chat.get("chat_mode") or chat.get("chat_type")) == "group"]
    p2ps = [chat for chat in chats if (chat.get("chat_mode") or chat.get("chat_type")) == "p2p"]
    print(f"chat-list total={len(chats)} groups={len(groups)} p2p={len(p2ps)}", flush=True)

    chat_names = {str(chat.get("chat_id")): str(chat.get("name") or "") for chat in chats}

    summaries: dict[str, dict[str, Any]] = {}
    reply_roots: set[str] = set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(archive_group, root, str(chat["chat_id"]), {"chat_name": chat.get("name")}): str(chat["chat_id"])
            for chat in chats
        }
        for future in concurrent.futures.as_completed(futures):
            chat_id = futures[future]
            summary, roots = future.result()
            summary["chat_name"] = summary.get("chat_name") or chat_names.get(chat_id) or None
            summaries[chat_id] = summary
            reply_roots.update(roots)
            print(f"chat-complete chat={safe_name(chat_id)} name={summary.get('chat_name')} messages={summary.get('message_count')} complete={summary.get('complete')}", flush=True)

    thread_summaries: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures2 = [executor.submit(archive_thread, root, message_id) for message_id in sorted(reply_roots)]
        for number, future in enumerate(concurrent.futures.as_completed(futures2), 1):
            summary = future.result()
            thread_summaries.append(summary)
            print(f"thread-check {number}/{len(futures2)} status={summary.get('status')} messages={summary.get('message_count')}", flush=True)
    thread_summaries.sort(key=lambda item: str(item.get("root_message_id") or ""))

    # Group entries: real groups, plus completed threads as pseudo-groups so the
    # indexer picks up thread replies that chat history pagination omits.
    group_entries: list[dict[str, Any]] = []
    for chat in sorted(groups, key=lambda item: str(item.get("chat_id"))):
        chat_id = str(chat["chat_id"])
        summary = summaries.get(chat_id) or {}
        group_entries.append(summary)
    for summary in thread_summaries:
        if summary.get("status") == "complete" and summary.get("content"):
            group_entries.append({
                "chat_id": f"thread:{summary['root_message_id']}",
                "chat_name": f"Thread {summary['root_message_id']}",
                "complete": True,
                "content": summary["content"],
                "message_count": summary.get("message_count"),
            })

    # P2P: merge every private chat's history into one jsonl, injecting the
    # partner name as chat_name so search results stay attributable.
    private_rows: list[dict[str, Any]] = []
    seen_private: set[str] = set()
    for chat in p2ps:
        chat_id = str(chat["chat_id"])
        summary = summaries.get(chat_id) or {}
        content = summary.get("content") or {}
        path = root / str(content.get("path") or "")
        if not content.get("path") or not path.is_file():
            continue
        with path.open() as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                message_id = str(row.get("message_id") or "")
                if not message_id or message_id in seen_private:
                    continue
                seen_private.add(message_id)
                row.setdefault("chat_name", chat_names.get(chat_id) or "Feishu private chat")
                private_rows.append(row)
    private_rows.sort(key=lambda item: (str(item.get("create_time") or ""), str(item.get("message_id") or "")))
    private_path = root / "chats" / "content" / "all-private-messages.jsonl"
    private_info = write_jsonl(private_path, private_rows)
    private_info["path"] = str(private_path.relative_to(root))

    incomplete = [item for item in summaries.values() if not item.get("complete")]
    failures.extend({"phase": "chat_history", "chat_id": item.get("chat_id"), "error": item.get("failure")} for item in incomplete)
    failed_threads = [item for item in thread_summaries if item.get("status") in {"failed", "incomplete"}]
    failures.extend({"phase": "thread", "root_message_id": item.get("root_message_id"), "error": item.get("failure")} for item in failed_threads)

    manifest = {
        "schema_version": 2,
        "created_at_unix": started,
        "completed_at_unix": int(time.time()),
        "scope": "Full history of every Feishu chat (group and p2p) visible to the authorized user",
        "contract": "Complete visible history for all group and p2p chats; thread replies archived for every reply root; resources are referenced but not downloaded.",
        "chat_count": len(chats),
        "group_count": len(groups),
        "p2p_count": len(p2ps),
        "group_message_count": sum(int((summaries.get(str(chat.get("chat_id"))) or {}).get("message_count") or 0) for chat in groups),
        "private_message_count": len(private_rows),
        "thread_candidate_count": len(reply_roots),
        "archived_thread_count": sum(1 for item in thread_summaries if item.get("status") == "complete"),
        "thread_message_count": sum(int(item.get("message_count") or 0) for item in thread_summaries),
        "not_thread_count": sum(1 for item in thread_summaries if item.get("status") == "not_thread"),
        "groups": group_entries,
        "private_content": private_info,
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
        "chat_count": len(chats),
        "group_message_count": manifest["group_message_count"],
        "private_message_count": len(private_rows),
        "archived_thread_count": manifest["archived_thread_count"],
        "failure_count": len(failures),
    }, ensure_ascii=False), flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
