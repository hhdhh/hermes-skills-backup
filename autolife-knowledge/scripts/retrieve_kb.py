"""Query the Autolife knowledge base.

Usage:
    python retrieve_kb.py "your question" [--top-k 5] [--kb-name NAME]...
                         [--url http://...] [--max-chars N] [--max-per-doc N]
                         [--no-dedup] [--json]
"""

from __future__ import annotations

import argparse
import sys

from kb_client import (
    DEFAULT_KB_NAMES,
    Config,
    KbClient,
    KbError,
    PublicKbClient,
    format_results,
    load_dotenv,
    results_as_json,
    split_kb_names,
)
from netbird_preflight import ensure_netbird


def build_parser(config: Config) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query the Autolife knowledge base",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("query", help="自然语言问题")
    parser.add_argument("--top-k", type=int, default=config.top_k, help="返回片段数（默认 %(default)s）")
    parser.add_argument(
        "--kb-name",
        action="append",
        default=None,
        metavar="NAME",
        help=f"知识库名称，可重复指定（默认：{DEFAULT_KB_NAMES}）",
    )
    parser.add_argument("--url", default=config.base_url, help="覆盖 KB_BASE_URL")
    parser.add_argument(
        "--max-chars",
        type=int,
        default=config.max_chars,
        help="输出字符上限，0 表示不限制（默认 %(default)s）",
    )
    parser.add_argument(
        "--max-per-doc",
        type=int,
        default=config.max_per_doc,
        help="同一文档最多保留的片段数，0 表示不限制（默认 %(default)s）",
    )
    parser.add_argument("--no-dedup", action="store_true", help="关闭去重与同文档限流")
    parser.add_argument(
        "--expand",
        choices=("none", "window", "section"),
        default="section",
        help="命中后向前后补上下文：section 补到所在小节（默认），window 补 N 块，none 只用命中块",
    )
    parser.add_argument(
        "--expand-window",
        type=int,
        default=1,
        help="--expand window 时前后各取几块（默认 %(default)s）",
    )
    parser.add_argument(
        "--expand-max-chunks",
        type=int,
        default=8,
        help="单条命中最多合并多少块，防止一小节吞掉整篇（默认 %(default)s）",
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 输出，便于程序消费")
    parser.add_argument(
        "--public-url",
        default=config.public_url,
        help="覆盖 KB_PUBLIC_URL（默认 %(default)s）",
    )
    parser.add_argument(
        "--internal",
        action="store_true",
        help="强制走内网 AstrBot API（忽略 KB_API_TOKEN），需要 NetBird",
    )
    parser.add_argument("--skip-netbird-check", action="store_true", help=argparse.SUPPRESS)
    return parser


def run_public(config: Config, args) -> int:
    """Retrieve through the internet-facing gateway. No NetBird required."""
    client = PublicKbClient(Config(public_url=args.public_url))
    try:
        results = client.search(args.query, top_k=args.top_k)
    except KbError as exc:
        print(f"检索失败：{exc}", file=sys.stderr)
        return 1

    if not results:
        print("知识库没有返回相关内容。")
        return 0

    print(results_as_json(results) if args.json else format_results(results, args.max_chars))
    return 0


def run_internal(config: Config, args) -> int:
    """Retrieve through the AstrBot API over NetBird (the original path)."""
    try:
        ensure_netbird()
    except (OSError, RuntimeError) as exc:
        print(f"NetBird 预检失败：{exc}", file=sys.stderr)
        return 2

    names = split_kb_names(",".join(args.kb_name)) if args.kb_name else config.kb_names
    client = KbClient(Config(base_url=args.url, kb_names=names))

    try:
        resolved = client.resolve_kb_names(names)
        results = client.search(
            args.query,
            kb_names=resolved,
            top_k=args.top_k,
            max_per_doc=args.max_per_doc,
            dedupe=not args.no_dedup,
        )
        if args.expand != "none" and results:
            # Give every hit an equal share of the character budget so one long
            # section cannot crowd the others out of the output.
            per_hit = args.max_chars // len(results) if args.max_chars else 0
            results = client.expand_hits(
                results,
                mode=args.expand,
                window=args.expand_window,
                max_chunks=args.expand_max_chunks,
                per_hit_chars=per_hit,
            )
    except KbError as exc:
        print(f"检索失败：{exc}", file=sys.stderr)
        return 1

    if not results:
        print("知识库没有返回相关内容。")
        return 0

    print(results_as_json(results) if args.json else format_results(results, args.max_chars))
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    config = Config()
    args = build_parser(config).parse_args(argv)

    if config.mode == "public" and not args.internal:
        return run_public(config, args)
    return run_internal(config, args)


if __name__ == "__main__":
    raise SystemExit(main())
