#!/usr/bin/env python3
"""Range-capable static file server for high-latency links.

Serves a directory over HTTP with HEAD + Range support so a Windows-side
parallel segmented downloader (templates/win-parallel-download.ps1) can pull
at N x single-stream speed. Do NOT strip do_HEAD: downloaders probe total
size with HEAD and die on 501.

Usage: python3 range_http_server.py [port] [root_dir]
Run in background; readiness check: curl -sI http://127.0.0.1:<port>/<file>
must return 200, and `curl -r 0-99` must return 206.
"""
import os, re, sys
from http.server import HTTPServer, BaseHTTPRequestHandler

ROOT = "/home/kk/hermes-migrate"
PORT = 8001


class H(BaseHTTPRequestHandler):
    def do_HEAD(self):
        path = os.path.join(ROOT, self.path.lstrip("/"))
        if not os.path.isfile(path):
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Length", str(os.path.getsize(path)))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

    def do_GET(self):
        path = os.path.join(ROOT, self.path.lstrip("/"))
        if not os.path.isfile(path):
            self.send_error(404)
            return
        sz = os.path.getsize(path)
        rng = self.headers.get("Range")
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            if not m:
                self.send_error(416)
                return
            s = int(m.group(1) or 0)
            e = int(m.group(2)) if m.group(2) else sz - 1
            e = min(e, sz - 1)
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {s}-{e}/{sz}")
            self.send_header("Content-Length", str(e - s + 1))
        else:
            s, e = 0, sz - 1
            self.send_response(200)
            self.send_header("Content-Length", str(sz))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(s)
            remaining = e - s + 1
            while remaining > 0:
                chunk = f.read(min(1 << 20, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except Exception:
                    return
                remaining -= len(chunk)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    if len(sys.argv) > 2:
        ROOT = sys.argv[2]
    print(f"serving {ROOT} on 0.0.0.0:{port}", flush=True)
    HTTPServer(("0.0.0.0", port), H).serve_forever()
