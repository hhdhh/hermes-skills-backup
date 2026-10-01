#!/usr/bin/env python3
"""goutoujunshi 多用户包装器（Hermes 飞书版适配）

原版 memory_store.py 是单档案设计；Hermes 环境下多位同事共用同一个我，
恋爱/关系档案属于高度隐私，绝不能互相可见。

用法（把 open_id 作为第一个参数传入，其余透传给原版 CLI）：
  python3 goutoujunshi_memory.py <open_id> status
  python3 goutoujunshi_memory.py <open_id> enable
  python3 goutoujunshi_memory.py <open_id> apply --json '{"...delta..."}'
  python3 goutoujunshi_memory.py <open_id> show
  ...

存储布局：~/.local/share/goutoujunshi/users/<open_id>/memory.sqlite3
每一位用户独立 SQLite 库（0700/0600 权限，原版自带），物理隔离。
"""
import os
import subprocess
import sys
import hashlib
import re

ORIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory_store.py")
BASE = os.path.expanduser("~/.local/share/goutoujunshi/users")

OPEN_ID_RE = re.compile(r"^ou_[0-9a-f]{32}$")


def derive_user_dir(open_id: str) -> str:
    # open_id 校验 + 短哈希防目录穿越（校验已保证，双保险）
    if not OPEN_ID_RE.match(open_id):
        raise SystemExit("用法: goutoujunshi_memory.py <open_id> <原版子命令...>\n"
                         "open_id 格式应为 ou_ + 32 位十六进制（飞书用户身份）")
    digest = hashlib.sha256(open_id.encode()).hexdigest()[:12]
    return os.path.join(BASE, f"{digest}_{open_id[3:11]}")


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    open_id, rest = sys.argv[1], sys.argv[2:]
    user_dir = derive_user_dir(open_id)
    os.makedirs(user_dir, exist_ok=True)
    env = dict(os.environ, GOUTOUJUNSHI_MEMORY_DIR=user_dir)
    # 归一化 open_id 长度截断（basename 不超 44 字符，防文件系统限制）
    sys.exit(subprocess.call([sys.executable, ORIG, *rest], env=env))


if __name__ == "__main__":
    main()
