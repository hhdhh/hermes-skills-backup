# DDS 阵营分裂：统一修复参考

## 两套阵营配置

**组播版（正确，gv-control/gv-slam 原生用法）**：

```
Environment="CYCLONEDDS_URI=<CycloneDDS><Domain Id=\"any\"><General><Interfaces><NetworkInterface name=\"lo\" multicast=\"true\"/></Interfaces><AllowMulticast>true</AllowMulticast><EnableMulticastLoopback>true</EnableMulticastLoopback></General><Discovery><ParticipantIndex>none</ParticipantIndex></Discovery></Domain></CycloneDDS>"
```

**单播版（废弃写法，病根）**：`NetworkInterfaceAddress 127.0.0.1` + ParticipantIndex=auto + MaxAutoParticipantIndex=255。废弃元素触发 lo 非组播判定 → `disabling multicast` → 与组播阵营互不可见。

诊断时在 shell 里 export 组播版（注意外层引号内 `\"` 转义）即可进入组播阵营视角。

## 曾属单播阵营的服务清单（S1 出厂状态）

logo-backend（kiosk 前端桥）、vision、flow、arm-control、face-detection、data-logger、ai-grasp、rosbag-record、dashboard-backend。修复 = 把这些全部换成组播版。

## 批量修复脚本骨架（paramiko + sftp）

对每个 unit：读文件 → `cp unit unit.bak-$(date +%Y%m%d-%H%M%S)` → 逐行找到 `Environment="CYCLONEDDS_URI` 开头的行整行替换为组播版 → 写回 → `grep -c EnableMulticastLoopback` 验证写入 → 最后统一 `systemctl --user daemon-reload` + 批量 restart（skip 本就 inactive 的 unit）。

## 端到端验证脚本（机器人上跑，用 robot_env 的 python）

```python
import asyncio, json
from collections import Counter
async def main():
    import websockets
    types = Counter()
    async with websockets.connect("ws://127.0.0.1:8000/ws", max_size=10**7) as ws:
        end = asyncio.get_event_loop().time() + 20
        while asyncio.get_event_loop().time() < end:
            try:
                m = await asyncio.wait_for(ws.recv(), timeout=3)
            except asyncio.TimeoutError:
                continue
            for k in json.loads(m):
                types[k] += 1
    print(types)  # 期待: battery ~21/20s, agent ~400/20s；agent=0 即内容链路断
asyncio.run(main())
```

## 回滚

`cp <unit>.bak-<ts> <unit>` 逐个还原 + daemon-reload + restart。备份时间戳以机器上 `ls *.bak*` 为准，不要凭记忆报时间戳。