#!/usr/bin/env python3
"""kiosk 前端端到端验证：连 WebSocket 看前端实际收到的数据（battery 等）。

用法（推到机器人后执行，websockets 来自 robot_env 的 uvicorn 依赖）：
  scp 本文件到机器人 /tmp/ 后：
  /home/ubuntu/miniconda3/envs/robot_env/bin/python /tmp/ws_battery_check.py [ws_url]

默认 ws://127.0.0.1:8000/ws，最多收 8 条消息，递归搜 battery/percent 字段。
BATTERY: NONE = 桥没收到数据（查 DDS 阵营）；有数值 = 链路通，对照 ROS 侧原始读数。
"""
import asyncio
import json
import sys


async def main():
    import websockets  # robot_env 自带

    url = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:8000/ws"
    msgs = []
    async with websockets.connect(url, max_size=10**7) as ws:
        try:
            while len(msgs) < 8:
                msgs.append(await asyncio.wait_for(ws.recv(), timeout=12))
        except asyncio.TimeoutError:
            pass

    found = []

    def walk(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if "battery" in k.lower() or "percent" in k.lower():
                    found.append(f"{path}.{k}={v}")
                walk(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj[:5]):
                walk(v, f"{path}[{i}]")

    for m in msgs:
        try:
            walk(json.loads(m))
        except Exception:
            pass

    print(f"total_msgs={len(msgs)}")
    for m in msgs[:3]:
        print("SAMPLE:", m[:300])
    print("BATTERY:", found[:3] if found else "NONE — 桥没收到数据，查 DDS 阵营配置")


asyncio.run(main())
