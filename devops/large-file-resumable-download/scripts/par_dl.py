#!/usr/bin/env python3
"""通用多线程分段下载器（慢代理环境）。
用法: python3 par_dl.py URL OUT_PATH TOTAL_SIZE [N_THREADS]
行为: 按 Range 切段并发下载，每段短读自动续传重试；全部达标后拼接并断言总长。
"""
import os
import sys
import threading
import urllib.request

PROXY = "http://127.0.0.1:7890"  # 无代理环境改成 None 并用 urllib.request.build_opener()
RETRY = 15
CHUNK = 1 << 20

URL, OUT, SZ = sys.argv[1], sys.argv[2], int(sys.argv[3])
N = int(sys.argv[4]) if len(sys.argv) > 4 else 8
PER = SZ // N

opener = urllib.request.build_opener(
    urllib.request.ProxyHandler({"https": PROXY, "http": PROXY})
)


def rng(i):
    a = PER * i
    b = (PER * (i + 1) - 1) if i < N - 1 else SZ - 1
    return a, b


def dl(i):
    a, b = rng(i)
    want = b - a + 1
    p = f"{OUT}.tpart_{i}"
    have = os.path.getsize(p) if os.path.exists(p) else 0
    for _ in range(RETRY):
        if have >= want:
            break
        try:
            req = urllib.request.Request(
                URL, headers={"Range": f"bytes={a + have}-{b}"}
            )
            with opener.open(req, timeout=60) as r, open(p, "ab") as f:
                while True:
                    chunk = r.read(CHUNK)
                    if not chunk:
                        break
                    f.write(chunk)
                    have += len(chunk)
        except Exception as e:  # 短读/超时/重置：从已收位置续传
            print(f"tpart{i} 异常 {e}，续传重试", flush=True)
    print(
        f"tpart{i} {'OK' if have >= want else 'SHORT'} {have}/{want}", flush=True
    )


threads = [threading.Thread(target=dl, args=(i,)) for i in range(N)]
for t in threads:
    t.start()
for t in threads:
    t.join()

total = sum(os.path.getsize(f"{OUT}.tpart_{i}") for i in range(N))
assert total == SZ, f"总长 {total} != {SZ}（定位短段后用 curl -r 补尾再重拼）"

with open(OUT, "wb") as out:
    for i in range(N):
        with open(f"{OUT}.tpart_{i}", "rb") as f:
            while True:
                c = f.read(1 << 22)
                if not c:
                    break
                out.write(c)
for i in range(N):
    os.remove(f"{OUT}.tpart_{i}")
print(f"ALL_OK {os.path.getsize(OUT)}")
