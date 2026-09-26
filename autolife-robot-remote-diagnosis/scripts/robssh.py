#!/usr/bin/env python3
"""SSH helper for AutoLife robot diagnosis (password auth via paramiko).

Usage: python3 robssh.py <host> <timeout_sec> <command...>
Requires: pip install paramiko -i https://pypi.tuna.tsinghua.edu.cn/simple
"""
import sys

import paramiko

USER = "ubuntu"
PASSWORD = os.environ["ROBOT_PASSWORD"]


def run(host: str, cmd: str, timeout: int = 30) -> str:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(host, username=USER, password=PASSWORD,
                       timeout=10, banner_timeout=10, auth_timeout=10)
        _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        stdout.channel.recv_exit_status()
        result = out
        if err.strip():
            result += "\n[stderr] " + err
        return result.strip()
    finally:
        client.close()


if __name__ == "__main__":
    print(run(sys.argv[1], " ".join(sys.argv[3:]), int(sys.argv[2])))
