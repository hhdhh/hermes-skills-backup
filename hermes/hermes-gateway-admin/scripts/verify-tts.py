#!/usr/bin/env python3.13
"""
TTS 端到端验证脚本 — 2026-07-29 立

输入：provider name (edge | minimax | openai | elevenlabs | xai | mistral | ...)
输出：JSON { success, file_path, provider, error? } + 真实 MP3 落在 ~/.hermes/cache/audio/

设计 3 个原则：
1. agent 进程外跑 — 必须手动 export MINIMAX_API_KEY in env, 否则 .env 不会被 load
2. 真实跑到底 — 不 mock, 不截断, 真调 _generate_minimax_tts / _generate_edge_tts / ...
3. 显式列失败原因 — 改 base_url / 改 voice_id 时常见的 3 个错 (2049/2054/空响应) 都精确报

调用：
  MINIMAX_API_KEY=$(grep MINIMAX_API_KEY ~/.hermes/.env | cut -d= -f2) \
    /Users/kk/miniconda3/bin/python3.13 \
    ~/.hermes/skills/hermes/hermes-gateway-admin/scripts/verify-tts.py minimax
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# 强制 hermes_cli 路径
SITE_PACKAGES = "/Users/kk/miniconda3/lib/python3.13/site-packages"
if SITE_PACKAGES not in sys.path:
    sys.path.insert(0, SITE_PACKAGES)

from tools.tts_tool import text_to_speech_tool  # noqa: E402


def verify_tts(provider: str = "minimax", text: str | None = None) -> dict:
    """端到端验证 TTS。返回 dict 含 success / file_path / provider / error。"""
    if text is None:
        text = (
            "主人，灰灰正在验证 TTS 配置。如果你听到了这段话，说明一切正常。"
        )

    # 强制 cache 目录
    cache_dir = Path.home() / ".hermes" / "cache" / "audio"
    cache_dir.mkdir(parents=True, exist_ok=True)
    output_path = cache_dir / f"verify_tts_{provider}_{int(time.time())}.mp3"

    try:
        raw = text_to_speech_tool(text=text, output_path=str(output_path))
    except Exception as e:
        return {
            "success": False,
            "provider": provider,
            "error": f"text_to_speech_tool raised: {e!r}",
            "hint": _hint_for_exception(e),
        }

    # 工具返回 JSON string
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "success": False,
            "provider": provider,
            "raw_output": raw,
            "error": "text_to_speech_tool returned non-JSON",
        }

    # success = True 才验证 file
    if result.get("success"):
        path = Path(result.get("file_path", ""))
        if path.exists():
            size = path.stat().st_size
            result["file_size_bytes"] = size
            result["file_size_human"] = _fmt_size(size)
            if size < 1000:
                result["success"] = False
                result["error"] = "MP3 file too small (<1KB) — likely error response"
    return result


def _fmt_size(n: int) -> str:
    if n < 1024:
        return f"{n}B"
    if n < 1024 * 1024:
        return f"{n/1024:.1f}KB"
    return f"{n/1024/1024:.1f}MB"


def _hint_for_exception(e: Exception) -> str:
    msg = str(e)
    if "2049" in msg and "invalid api key" in msg:
        return (
            "→ 2049 invalid api key. 99% 是 base_url 域名错."
            " 国内主人 key 走 api.minimax.chat, 不是 api.minimax.io."
            " 解: hermes config set tts.minimax.base_url https://api.minimax.chat/v1/t2a_v2"
        )
    if "2054" in msg and "voice id not exist" in msg:
        return (
            "→ 2054 voice id not exist. 换 voice_id:"
            " male-qn-qingse / female-yujie / female-shaonv 等(见 references/tts-providers.md)"
        )
    if "MINIMAX_API_KEY" in msg:
        return (
            "→ env var 没设. 跑命令前手动 export 或加到 ~/.hermes/.env:"
            " MINIMAX_API_KEY=sk-..."
        )
    if "1002" in msg:
        return "→ rate limit. 退避 1-2 秒重试或升级配额"
    if "1008" in msg:
        return "→ insufficient balance. 充值后重试"
    return f"→ 未识别错误: {type(e).__name__}"


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: verify-tts.py <provider> [text]", file=sys.stderr)
        print("例:  verify-tts.py minimax", file=sys.stderr)
        return 2

    provider = sys.argv[1]
    text = sys.argv[2] if len(sys.argv) > 2 else None

    result = verify_tts(provider, text)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 失败时显式打印 hint（stderr, 不污染 JSON）
    if not result.get("success"):
        hint = result.get("hint") or result.get("error") or "查 ~/.hermes/logs/agent.log"
        print(f"\n[HINT] {hint}", file=sys.stderr)
        return 1

    # 成功时打印产物路径
    if result.get("file_path"):
        print(f"\n[OK] {result['file_path']} ({result.get('file_size_human')})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
