#!/usr/bin/env python3
"""
responses-proxy — Responses API → Chat Completions proxy for Codex CLI.

Codex CLI only supports wire_api = "responses", but OpenCode Go GLM-5.2 only
provides /v1/chat/completions. This proxy sits in between, translating both ways.

Pure stdlib, zero third-party deps (conda env on this machine has broken
fastapi/httpx/aiohttp/requests due to version mismatches).

Usage:
  python3 ~/.codex/responses-proxy.py --port 8848 --api-key YOUR_KEY
  OPENCODE_API_KEY=sk-... python3 ~/.codex/responses-proxy.py --port 8848

Codex config.toml:
  base_url = "http://127.0.0.1:8848/v1"
  wire_api = "responses"
"""

import argparse
import json
import os
import sys
import time
import uuid
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler

UPSTREAM_BASE = "https://opencode.ai/zen/go/v1"
API_KEY = ""


def responses_to_chat(body):
    """Convert Responses API request to Chat Completions format."""
    messages = []

    instructions = body.get("instructions")
    if instructions:
        messages.append({"role": "system", "content": instructions})

    input_data = body.get("input", [])
    if isinstance(input_data, str):
        messages.append({"role": "user", "content": input_data})
    elif isinstance(input_data, list):
        for item in input_data:
            if isinstance(item, str):
                messages.append({"role": "user", "content": item})
            elif isinstance(item, dict):
                item_type = item.get("type", "")
                role = item.get("role", "user")

                if item_type == "function_call":
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": item.get("call_id", item.get("id", "")),
                            "type": "function",
                            "function": {
                                "name": item.get("name", ""),
                                "arguments": item.get("arguments", "{}"),
                            }
                        }]
                    })
                elif item_type == "function_call_output":
                    messages.append({
                        "role": "tool",
                        "tool_call_id": item.get("call_id", ""),
                        "content": item.get("output", ""),
                    })
                elif item_type == "message":
                    content = item.get("content", "")
                    if isinstance(content, list):
                        text_parts = []
                        for part in content:
                            if isinstance(part, dict):
                                if part.get("type") in ("text", "output_text"):
                                    text_parts.append(part.get("text", ""))
                            elif isinstance(part, str):
                                text_parts.append(part)
                        content = "\n".join(text_parts)
                    messages.append({"role": role, "content": content})
                else:
                    content = item.get("content", "")
                    if isinstance(content, list):
                        text_parts = []
                        for part in content:
                            if isinstance(part, dict):
                                if part.get("type") in ("text", "output_text"):
                                    text_parts.append(part.get("text", ""))
                            elif isinstance(part, str):
                                text_parts.append(part)
                        content = "\n".join(text_parts)
                    messages.append({"role": role, "content": content})

    tools = []
    for tool in body.get("tools", []):
        if tool.get("type") == "function":
            tools.append({
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
                }
            })

    chat_body = {
        "model": body.get("model", "glm-5.2"),
        "messages": messages,
        "stream": body.get("stream", False),
    }

    if tools:
        chat_body["tools"] = tools

    max_tokens = body.get("max_output_tokens")
    if max_tokens:
        chat_body["max_tokens"] = max_tokens

    temp = body.get("temperature")
    if temp is not None:
        chat_body["temperature"] = temp

    reasoning = body.get("reasoning", {})
    if reasoning:
        effort = reasoning.get("effort", "medium")
        if effort == "low":
            chat_body.setdefault("temperature", 0.3)
        elif effort == "high":
            chat_body.setdefault("temperature", 0.7)
        elif effort == "xhigh":
            chat_body.setdefault("temperature", 0.9)

    return chat_body


def chat_to_responses(chat_resp, model):
    """Convert Chat Completions response to Responses API format."""
    choice = chat_resp.get("choices", [{}])[0]
    message = choice.get("message", {})

    content_items = []

    reasoning_content = message.get("reasoning_content", "")
    if reasoning_content:
        content_items.append({
            "type": "reasoning",
            "summary": reasoning_content,
        })

    text_content = message.get("content", "")
    if text_content:
        content_items.append({
            "type": "output_text",
            "text": text_content,
        })

    output_items = []

    item_id = f"msg_{uuid.uuid4().hex[:24]}"
    output_items.append({
        "id": item_id,
        "type": "message",
        "role": "assistant",
        "status": "completed",
        "content": content_items if content_items else [{"type": "output_text", "text": ""}],
    })

    tool_calls = message.get("tool_calls", [])
    for tc in tool_calls:
        func = tc.get("function", {})
        output_items.append({
            "id": f"fc_{uuid.uuid4().hex[:24]}",
            "type": "function_call",
            "call_id": tc.get("id", f"call_{uuid.uuid4().hex[:24]}"),
            "name": func.get("name", ""),
            "arguments": func.get("arguments", "{}"),
        })

    usage = chat_resp.get("usage", {})

    return {
        "id": f"resp_{uuid.uuid4().hex[:24]}",
        "object": "response",
        "created_at": int(time.time()),
        "model": model,
        "output": output_items,
        "status": "completed",
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
    }


def do_upstream_request(chat_body):
    """Make synchronous request to upstream."""
    data = json.dumps(chat_body).encode("utf-8")
    req = urllib.request.Request(
        f"{UPSTREAM_BASE}/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode("utf-8"))


class ProxyHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/v1/responses":
            self.send_error(404, "Not found")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(content_length)
        body = json.loads(raw)

        model = body.get("model", "glm-5.2")
        is_stream = body.get("stream", False)

        chat_body = responses_to_chat(body)

        if is_stream:
            self.handle_stream(chat_body, model)
        else:
            self.handle_non_stream(chat_body, model)

    def handle_non_stream(self, chat_body, model):
        try:
            chat_resp = do_upstream_request(chat_body)
            responses_resp = chat_to_responses(chat_resp, model)
            data = json.dumps(responses_resp).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": err_body}).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def handle_stream(self, chat_body, model):
        chat_body["stream"] = True
        data = json.dumps(chat_body).encode("utf-8")
        req = urllib.request.Request(
            f"{UPSTREAM_BASE}/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            method="POST",
        )

        try:
            resp = urllib.request.urlopen(req, timeout=300)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": err_body}).encode())
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        created_event = {
            "type": "response.created",
            "response": {
                "id": f"resp_{uuid.uuid4().hex[:24]}",
                "object": "response",
                "model": model,
                "status": "in_progress",
                "output": [],
            }
        }
        self.wfile.write(f"data: {json.dumps(created_event)}\n\n".encode())
        self.wfile.flush()

        msg_id = f"msg_{uuid.uuid4().hex[:24]}"
        sent_msg_created = False

        for line in resp:
            line = line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    done_event = {
                        "type": "response.completed",
                        "response": {
                            "id": f"resp_{uuid.uuid4().hex[:24]}",
                            "object": "response",
                            "model": model,
                            "status": "completed",
                            "output": [],
                        }
                    }
                    self.wfile.write(f"data: {json.dumps(done_event)}\n\n".encode())
                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()
                    break
                try:
                    chunk = json.loads(data_str)
                    choice = chunk.get("choices", [{}])[0]
                    delta = choice.get("delta", {})

                    reasoning = delta.get("reasoning_content", "")
                    if reasoning:
                        ev = {"type": "response.reasoning_summary_text.delta", "delta": reasoning}
                        self.wfile.write(f"data: {json.dumps(ev)}\n\n".encode())
                        self.wfile.flush()

                    text = delta.get("content", "")
                    if text:
                        if not sent_msg_created:
                            ev = {
                                "type": "response.output_item.added",
                                "output_index": 0,
                                "item": {
                                    "id": msg_id,
                                    "type": "message",
                                    "role": "assistant",
                                    "status": "in_progress",
                                    "content": [],
                                }
                            }
                            self.wfile.write(f"data: {json.dumps(ev)}\n\n".encode())
                            sent_msg_created = True

                        ev = {"type": "response.output_text.delta", "delta": text, "item_id": msg_id}
                        self.wfile.write(f"data: {json.dumps(ev)}\n\n".encode())
                        self.wfile.flush()

                    tool_calls = delta.get("tool_calls", [])
                    for tc in tool_calls:
                        func = tc.get("function", {})
                        if func.get("name"):
                            ev = {
                                "type": "response.output_item.added",
                                "output_index": 1,
                                "item": {
                                    "id": f"fc_{uuid.uuid4().hex[:24]}",
                                    "type": "function_call",
                                    "call_id": tc.get("id", f"call_{uuid.uuid4().hex[:24]}"),
                                    "name": func.get("name", ""),
                                    "arguments": "",
                                }
                            }
                            self.wfile.write(f"data: {json.dumps(ev)}\n\n".encode())
                        elif func.get("arguments"):
                            ev = {
                                "type": "response.function_call_arguments.delta",
                                "delta": func.get("arguments", ""),
                                "output_index": 1,
                            }
                            self.wfile.write(f"data: {json.dumps(ev)}\n\n".encode())
                        self.wfile.flush()

                    if choice.get("finish_reason"):
                        if sent_msg_created:
                            ev = {
                                "type": "response.output_item.done",
                                "output_index": 0,
                                "item": {
                                    "id": msg_id,
                                    "type": "message",
                                    "role": "assistant",
                                    "status": "completed",
                                    "content": [{"type": "output_text", "text": ""}],
                                }
                            }
                            self.wfile.write(f"data: {json.dumps(ev)}\n\n".encode())
                            self.wfile.flush()

                except json.JSONDecodeError:
                    continue

    def do_GET(self):
        if self.path == "/v1/models":
            try:
                req = urllib.request.Request(
                    f"{UPSTREAM_BASE}/models",
                    headers={"Authorization": f"Bearer {API_KEY}"},
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = resp.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_error(404, "Not found")

    def log_message(self, format, *args):
        sys.stderr.write(f"[proxy] {args[0]} {args[1] if len(args) > 1 else ''}\n")


def main():
    parser = argparse.ArgumentParser(description="Responses API -> Chat Completions proxy")
    parser.add_argument("--port", type=int, default=8848)
    parser.add_argument("--api-key", type=str, default=os.environ.get("OPENCODE_API_KEY", ""))
    args = parser.parse_args()

    if not args.api_key:
        print("ERROR: No API key. Use --api-key or set OPENCODE_API_KEY env var.")
        sys.exit(1)

    global API_KEY
    API_KEY = args.api_key

    server = HTTPServer(("127.0.0.1", args.port), ProxyHandler)
    print(f"Responses proxy on http://127.0.0.1:{args.port}/v1 -> {UPSTREAM_BASE}")
    print(f"  Health: http://127.0.0.1:{args.port}/health")
    server.serve_forever()


if __name__ == "__main__":
    main()