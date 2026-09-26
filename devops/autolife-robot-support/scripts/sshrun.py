#!/usr/bin/env python3
"""Password SSH without sshpass/expect — pure stdlib pty driver.

Usage:
  SSH_PW=*** python3 sshrun.py user@host 'remote command' [timeout_sec]
Password comes ONLY from SSH_PW env (or interactive prompt) — never hardcode it.
"""
import os, pty, sys, time, select, getpass

PASSWORD = os.environ.get("SSH_PW") or getpass.getpass("SSH password: ")

def run_remote(host, cmd, timeout=90):
    argv = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
            "-o", "NumberOfPasswordPrompts=1", host, cmd]
    pid, fd = pty.fork()
    if pid == 0:
        os.execvp("ssh", argv)
        os._exit(127)
    buf = b""
    sent_pw = False
    start = time.time()
    status = None
    while True:
        if time.time() - start > timeout:
            os.kill(pid, 9)
            break
        r, _, _ = select.select([fd], [], [], 1.0)
        if not r:
            wpid, st = os.waitpid(pid, os.WNOHANG)
            if wpid:
                status = st
                break
            continue
        try:
            chunk = os.read(fd, 65536)
        except OSError:
            break
        if not chunk:
            break
        buf += chunk
        if not sent_pw and (b"password" in buf.lower() or b"assword:" in chunk):
            time.sleep(0.3)
            os.write(fd, (PASSWORD + "\n").encode())
            sent_pw = True
    if status is None:
        try:
            _, status = os.waitpid(pid, 0)
        except ChildProcessError:
            status = 1
    try:
        os.close(fd)
    except OSError:
        pass
    return buf.decode("utf-8", "replace"), os.waitstatus_to_exitcode(status)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    out, code = run_remote(sys.argv[1], sys.argv[2],
                           int(sys.argv[3]) if len(sys.argv) > 3 else 90)
    print(out)
    sys.exit(code)
