"""HKUDS hub-style CLI entry — 把 ljg_ppt_design.cli 包装成 cli-anything-ljg-ppt-design。

HKUDS 期望的 entry point 格式: cli_anything.<name>.__main__:main
"""

from __future__ import annotations

import sys
from pathlib import Path

# 把 ~/.claude/skills/ 加进 path
_HERE = Path(__file__).resolve().parent
_SKILLS_ROOT = _HERE.parent.parent.parent
for _p in (str(_SKILLS_ROOT), str(_HERE.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ljg_ppt_design import cli as _ljg_cli  # noqa: E402


def main() -> int:
    """HKUDS-style entry point."""
    return _ljg_cli.main()


if __name__ == "__main__":
    sys.exit(main())
