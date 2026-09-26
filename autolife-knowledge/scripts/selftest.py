"""Smoke tests for the Autolife knowledge-base skill.

Offline unit checks always run. Network checks run only when NetBird is up and
`--online` is passed, so this stays safe to run anywhere.

Usage:
    python selftest.py            # 离线单元检查
    python selftest.py --online   # 额外跑 NetBird / 登录 / 列表 / 检索
"""

from __future__ import annotations

import argparse
import os
import sys

from kb_client import (
    DEFAULT_KB_NAMES,
    HIT_CLOSE,
    HIT_OPEN,
    Config,
    KbClient,
    KbError,
    _assemble_hit,
    _build_multipart,
    _center_crop,
    _locate_chunk,
    _section_bounds,
    _trim_around_hit,
    dedupe_results,
    format_results,
    jwt_expiry,
    looks_like_heading,
    normalize_doc_name,
    split_kb_names,
)

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(name)
        print(f"  PASS  {name}")
    else:
        FAILED.append(f"{name} {detail}".strip())
        print(f"  FAIL  {name} {detail}".rstrip())


def unit_checks() -> None:
    print("离线单元检查")

    check("split_kb_names 去重保序", split_kb_names(" a , b ,a, ") == ["a", "b"])
    check("split_kb_names 空串回落默认", split_kb_names("") == split_kb_names(DEFAULT_KB_NAMES))

    check("normalize 副本", normalize_doc_name("Autolife 配置流程 副本.txt") == "autolife配置流程")
    check("normalize (1)", normalize_doc_name("Autolife-S2 使用手册 (1).txt") == "autolifes2使用手册")
    check("normalize 已规范名不变", normalize_doc_name("手册.txt") == "手册")
    check(
        "normalize 折叠全角括号与下划线",
        normalize_doc_name("手册_EN（多图需修）.txt") == normalize_doc_name("手册_EN_多图需修_.txt"),
    )
    check(
        "normalize 折叠 & 与 _",
        normalize_doc_name("AI语音&导航.txt") == normalize_doc_name("AI语音_导航.txt"),
    )
    check(
        "normalize 折叠 emoji 与前后缀下划线",
        normalize_doc_name("🚀 FAE新人顺序（按优先级）.txt")
        == normalize_doc_name("_ FAE新人顺序_按优先级_.txt"),
    )
    check(
        "normalize 不合并中英文版",
        normalize_doc_name("运维手册.txt") != normalize_doc_name("运维手册_EN.txt"),
    )
    check(
        "normalize 把 (N) 视为副本后缀",
        normalize_doc_name("手册 (1).txt") == normalize_doc_name("手册 (2).txt") == "手册",
    )

    items = [
        {"doc_name": "A 副本.txt", "content": "x", "score": 0.5},
        {"doc_name": "A.txt", "content": "x", "score": 0.9},
        {"doc_name": "A.txt", "content": "y", "score": 0.8},
        {"doc_name": "A.txt", "content": "z", "score": 0.7},
        {"doc_name": "B.txt", "content": "w", "score": 0.6},
    ]
    kept = dedupe_results(items, max_per_doc=2)
    check("dedupe 按分数降序", [i["score"] for i in kept] == [0.9, 0.8, 0.6])
    check("dedupe 合并副本名", len(kept) == 3, f"实际 {len(kept)}")
    check("dedupe 内容完全相同时去重", dedupe_results(items, max_per_doc=0)[0]["score"] == 0.9)
    check("dedupe max_per_doc=0 不限流", len(dedupe_results(items, max_per_doc=0)) == 4)

    # The remote corpus stores ~45 near-identical copies of each document, so the
    # same logical chunk comes back several times with slightly different bytes.
    slot_items = [
        {"doc_name": "M 副本.txt", "content": "copy-a", "score": 0.9, "chunk_index": 15},
        {"doc_name": "M.txt", "content": "copy-b", "score": 0.8, "chunk_index": 15},
        {"doc_name": "M.txt", "content": "other", "score": 0.7, "chunk_index": 29},
    ]
    slot_kept = dedupe_results(slot_items, max_per_doc=2)
    check(
        "dedupe 折叠同文档同块号",
        [i["content"] for i in slot_kept] == ["copy-a", "other"],
        str([i["content"] for i in slot_kept]),
    )

    text = format_results([{"doc_name": "D.txt", "kb_name": "kb1", "content": "hello", "score": 0.86523939}])
    check("score 四舍五入到 3 位", "score: 0.865" in text, text.splitlines()[0])
    check("输出含来源文档名", "D.txt" in text)
    check("输出含 kb 名", "kb1" in text)

    truncated = format_results([{"doc_name": "D.txt", "content": "a" * 500, "score": 1.0}], max_chars=100)
    check("max_chars 触发截断", "已截断" in truncated and len(truncated) < 300)

    body = _build_multipart("BOUNDARY", "kb-id-1", '中文 标题.md', b"data")
    check("multipart 含随机 boundary", b"--BOUNDARY\r\n" in body)
    check("multipart 含 filename*", b"filename*=UTF-8''%E4%B8%AD%E6%96%87" in body)
    check("multipart 含原始数据", body.endswith(b"--\r\n"))
    check("multipart 不含裸换行注入", b'filename="\r' not in body)

    check("jwt_expiry 解析合法 token", jwt_expiry("a.eyJleHAiOjE3MDAwMDAwMDB9.c") == 1700000000)
    check("jwt_expiry 非法 token 返回 None", jwt_expiry("not-a-jwt") is None)

    os.environ["KB_TOP_K"] = "abc"
    check("KB_TOP_K 非法值回落默认", Config().top_k == 5)
    os.environ["KB_TOP_K"] = "9999"
    check("KB_TOP_K 超上限被截断", Config().top_k == 50)
    os.environ.pop("KB_TOP_K", None)

    # 上下文扩展：固定切片会切断 91% 的块，需要按小节补回上下文
    check("标题识别 markdown", looks_like_heading("## 网络配置\n后续内容"))
    check("标题识别 中文序号", looks_like_heading("三、根因分析"))
    check("标题识别 数字序号", looks_like_heading("1.2 部署步骤"))
    check("标题识别 方括号", looks_like_heading("【注意事项】"))
    check("标题识别 普通正文为否", not looks_like_heading("如果仍然无法显示视频，尝试重启机器人。"))

    sample = [
        {"chunk_index": 0, "content": "## 一、网络问题\n步骤一"},
        {"chunk_index": 1, "content": "步骤二，继续"},
        {"chunk_index": 2, "content": "步骤三，结尾"},
        {"chunk_index": 3, "content": "## 二、视觉问题\n步骤一"},
        {"chunk_index": 4, "content": "步骤二"},
    ]
    low, high = _section_bounds(sample, 1, max_chunks=8)
    check("小节边界向左找到标题", (low, high) == (0, 2), f"得到 {(low, high)}")
    low, high = _section_bounds(sample, 4, max_chunks=8)
    check("小节边界向右到下一标题前", (low, high) == (3, 4), f"得到 {(low, high)}")

    no_headings = [{"chunk_index": i, "content": f"正文片段{i}"} for i in range(20)]
    low, high = _section_bounds(no_headings, 10, max_chunks=6)
    check("无标题时回落为对称窗口", (low, high) == (7, 12), f"得到 {(low, high)}")
    check("窗口不越界", high - low + 1 == 6)

    check("locate 按 chunk_id", _locate_chunk({"chunk_id": "c"}, [{"chunk_id": "a"}, {"chunk_id": "c"}]) == 1)
    check("locate 按 chunk_index", _locate_chunk({"chunk_index": 4}, sample) == 4)
    check("locate 找不到返回 None", _locate_chunk({"content": "zzz"}, sample) is None)

    cropped = _center_crop("A" * 300 + "B" * 300, 200)
    check("center_crop 保留首尾", cropped.startswith("A") and cropped.endswith("B"))
    check("center_crop 标注省略", "中间省略" in cropped)
    check("center_crop 不超长太多", len(cropped) < 260, str(len(cropped)))
    check("center_crop 短文本原样返回", _center_crop("short", 100) == "short")

    # 对称窗口会把命中块埋在中段，裁剪时必须保住命中块本体
    before, hit, after = _trim_around_hit("B" * 400, "H" * 100, "A" * 400, 300)
    check("裁剪后命中块完整保留", hit == "H" * 100)
    check("裁剪保留靠近命中的前文", before.endswith("B"))
    check("裁剪保留靠近命中的后文", after.startswith("A"))
    check("裁剪总长受控", len(before) + len(hit) + len(after) <= 320,
          str(len(before) + len(hit) + len(after)))
    check("裁剪标记省略号", before.startswith("…") and after.endswith("…"))
    check("命中块超预算时不裁剪命中", _trim_around_hit("b", "H" * 500, "a", 100)[1] == "H" * 500)
    check("未超预算时原样返回", _trim_around_hit("b", "h", "a", 999) == ("b", "h", "a"))

    marked = _assemble_hit("前文", "命中", "后文")
    check("拼接标注命中起点", HIT_OPEN in marked and marked.index(HIT_OPEN) < marked.index("命中"))
    check("拼接标注命中终点", HIT_CLOSE in marked and marked.index("命中") < marked.index(HIT_CLOSE))
    check("无上下文时不加标记", _assemble_hit("", "命中", "") == "命中")


def online_checks() -> None:
    print("\n在线检查（需要 NetBird 已连接）")

    from netbird_preflight import ensure_netbird

    try:
        report = ensure_netbird()
    except (OSError, RuntimeError) as exc:
        check("NetBird 预检", False, str(exc))
        return
    check("NetBird 预检", report.get("ok") is True)
    check("NetBird 使用自托管服务器", report.get("management_url") == report.get("expected_management_url"))

    client = KbClient(Config())
    try:
        token = client.login()
    except KbError as exc:
        check("登录获取 JWT", False, str(exc))
        return
    check("登录获取 JWT", bool(token))
    check("JWT 含 exp 声明", jwt_expiry(token) is not None)

    try:
        kbs = client.list_kbs()
    except KbError as exc:
        check("列出知识库", False, str(exc))
        return
    names = [str(k.get("kb_name")) for k in kbs]
    check("列出知识库", len(kbs) > 0, f"共 {len(kbs)} 个")
    print(f"        可用知识库：{names}")

    missing = [n for n in split_kb_names(DEFAULT_KB_NAMES) if n not in names]
    check("默认知识库均存在", not missing, f"缺失 {missing}")

    try:
        client.resolve_kb_names(["__definitely_not_a_kb__"])
    except KbError:
        check("全部名称无效时明确报错", True)
    else:
        check("全部名称无效时明确报错", False, "未抛出 KbError")

    try:
        results = client.search("太空舱", top_k=5)
    except KbError as exc:
        check("检索返回结果", False, str(exc))
        return
    check("检索返回结果", len(results) > 0, f"共 {len(results)} 条")
    if results:
        top = results[0]
        check("结果含来源文档名", bool(top.get("doc_name")))
        check("结果含内容", bool(str(top.get("content") or "").strip()))
        check("同文档不超过 max_per_doc", len(results) <= 5)
        print(f"        首条：{top.get('doc_name')} score={float(top.get('score') or 0):.3f}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Autolife KB skill smoke tests")
    parser.add_argument("--online", action="store_true", help="额外执行需要网络与 NetBird 的检查")
    args = parser.parse_args()

    unit_checks()
    if args.online:
        online_checks()

    print(f"\n通过 {len(PASSED)} 项，失败 {len(FAILED)} 项")
    for item in FAILED:
        print(f"  - {item}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
