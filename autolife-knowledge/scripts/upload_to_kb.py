"""Upload a Markdown document to the Autolife knowledge base.

Usage:
    python upload_to_kb.py "path/to/document.md" [--kb-name NAME]
                           [--title "标题"] [--no-wait] [--timeout SECONDS]
    cat summary.md | python upload_to_kb.py - --title "Fix: 电池显示 100%"
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time

from kb_client import Config, KbClient, KbError, load_dotenv
from netbird_preflight import ensure_netbird


def build_parser(config: Config) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Upload a document to the Autolife knowledge base",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("file", help="待上传文件路径，- 表示从标准输入读取")
    parser.add_argument(
        "--kb-name",
        default=os.environ.get("KB_NAMES", "").split(",")[0].strip() or None,
        help="目标知识库名称",
    )
    parser.add_argument("--title", default=None, help="文档标题（默认取文件名）")
    parser.add_argument("--no-wait", action="store_true", help="只创建任务，不等待分块与向量化完成")
    parser.add_argument(
        "--timeout",
        type=int,
        default=config.upload_timeout,
        help="等待后台处理的最长秒数（默认 %(default)s）",
    )
    parser.add_argument("--skip-netbird-check", action="store_true", help=argparse.SUPPRESS)
    return parser


def _progress(status, payload, elapsed):
    if status in {"pending", "running", "processing"} or elapsed < 5:
        print(f"[kb] 处理中… 状态={status or 'unknown'} 已等待 {elapsed:.0f}s", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    config = Config()
    args = build_parser(config).parse_args(argv)

    if not args.skip_netbird_check:
        try:
            ensure_netbird()
        except (OSError, RuntimeError) as exc:
            print(f"NetBird 预检失败：{exc}", file=sys.stderr)
            return 2

    if not config.username or not config.password:
        print("请设置 KB_USERNAME 和 KB_PASSWORD", file=sys.stderr)
        return 2

    temp_path = None
    try:
        if args.file == "-":
            content = sys.stdin.read()
            if not content.strip():
                print("标准输入为空，未上传任何内容。", file=sys.stderr)
                return 2
            handle = tempfile.NamedTemporaryFile(
                mode="w", suffix=".md", delete=False, encoding="utf-8"
            )
            try:
                handle.write(content)
            finally:
                handle.close()
            temp_path = handle.name
            file_path = temp_path
            if not args.title:
                args.title = "Untitled KB Entry.md"
        else:
            file_path = args.file
            if not os.path.exists(file_path):
                print(f"文件不存在：{file_path}", file=sys.stderr)
                return 1

        client = KbClient(config)
        kb_name = args.kb_name or client.resolve_kb_names()[0]

        task_id = client.upload_document(file_path, kb_name, args.title)
        display = args.title or os.path.basename(file_path)
        print(f"[kb] 已提交：{display} -> {kb_name}（task_id={task_id}）")

        if args.no_wait:
            print("[kb] 已跳过等待；后台仍会继续分块与向量化。")
            return 0

        started = time.time()
        outcome = client.wait_for_upload(
            task_id, timeout_seconds=args.timeout, on_progress=_progress
        )
        print(f"[kb] 处理完成，耗时 {time.time() - started:.0f}s")
        print(f"[kb] 结果：{outcome}")
        return 0

    except KbError as exc:
        print(f"上传失败：{exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n[kb] 已中断；后台任务可能仍在继续。", file=sys.stderr)
        return 130
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
