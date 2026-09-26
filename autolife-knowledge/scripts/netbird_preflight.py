"""NetBird connection preflight.

Remote knowledge-base access is only allowed over the self-hosted NetBird
overlay network, so every script calls :func:`ensure_netbird` before touching
the API.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone

DEFAULT_MANAGEMENT_URL = "https://netbird.autolife-robotics.com:443"

_KNOWN_PATHS = [
    r"C:\Program Files\NetBird\netbird.exe",
    r"C:\Program Files (x86)\NetBird\netbird.exe",
    "/usr/bin/netbird",
    "/usr/local/bin/netbird",
    "/opt/homebrew/bin/netbird",
]

# Python <= 3.10 only accepts 3 or 6 fractional digits in fromisoformat, while
# NetBird reports nanosecond precision (e.g. 2026-09-15T02:05:24.109646607Z).
_FRACTION = re.compile(r"^(?P<head>.*\.\d{6})\d+(?P<tz>Z|[+-]\d{2}:?\d{2})?$")


def _netbird_binary() -> str:
    binary = shutil.which("netbird")
    if binary:
        return binary
    for path in _KNOWN_PATHS:
        if os.path.isfile(path):
            return path
    raise RuntimeError(
        "未找到 NetBird CLI，请先安装并登录 NetBird"
        "（Windows 默认路径 C:\\Program Files\\NetBird\\netbird.exe）"
    )


def parse_timestamp(text: str) -> datetime:
    """Parse an ISO-8601 timestamp, tolerating nanosecond precision."""
    value = str(text).strip()
    match = _FRACTION.match(value)
    if match:
        value = match.group("head") + (match.group("tz") or "")
    elif value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def check_netbird(expected_management_url: str | None = None) -> dict:
    """Verify the NetBird session, raising RuntimeError on any failed check."""
    expected = (
        expected_management_url
        or os.environ.get("NETBIRD_MANAGEMENT_URL", DEFAULT_MANAGEMENT_URL)
    ).rstrip("/")

    try:
        result = subprocess.run(
            [_netbird_binary(), "status", "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("NetBird status 查询超时，请确认 daemon 正在运行") from exc

    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "未知错误"
        raise RuntimeError(f"NetBird status 查询失败：{message}")

    try:
        status = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("NetBird 返回了无效的 status JSON") from exc

    management = status.get("management") if isinstance(status.get("management"), dict) else {}
    signal = status.get("signal") if isinstance(status.get("signal"), dict) else {}
    daemon = status.get("daemonStatus")
    if isinstance(daemon, dict):
        daemon = daemon.get("state") or daemon.get("status")

    management_url = str(management.get("url", "")).rstrip("/")
    management_connected = management.get("connected") is True
    signal_connected = signal.get("connected") is True
    daemon_connected = str(daemon or "").lower() in {"connected", "up", "running"}
    errors = []

    if not daemon_connected:
        errors.append(f"NetBird daemon 未连接（状态：{daemon or 'unknown'}）")
    if not management_connected:
        errors.append("NetBird Management 通道未连接")
    if not signal_connected:
        errors.append("NetBird Signal 通道未连接")
    if management_url and management_url != expected:
        errors.append(f"NetBird 服务器不正确：{management_url}，期望：{expected}")

    expiry_text = status.get("sessionExpiresAt")
    expiry = None
    if expiry_text:
        try:
            expiry = parse_timestamp(expiry_text)
        except ValueError:
            errors.append(f"无法解析 NetBird 会话过期时间：{expiry_text}")
        else:
            if expiry <= datetime.now(timezone.utc):
                errors.append("NetBird 会话已过期，请重新登录")

    report = {
        "ok": not errors,
        "management_url": management_url,
        "expected_management_url": expected,
        "management_connected": management_connected,
        "signal_connected": signal_connected,
        "daemon_status": daemon,
        "netbird_ip": status.get("netbirdIp"),
        "profile": status.get("profileName"),
        "session_expires_at": expiry.isoformat() if expiry else expiry_text,
        "errors": errors,
    }
    if errors:
        raise RuntimeError("；".join(errors))
    return report


def ensure_netbird(expected_management_url: str | None = None) -> dict:
    """Alias kept for call sites that read as a precondition."""
    return check_netbird(expected_management_url)


def main() -> int:
    try:
        report = ensure_netbird()
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"NetBird 预检失败：{exc}")
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
