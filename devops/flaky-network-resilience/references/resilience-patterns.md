# 韧性加固代码模式

## 模式 A：DNS 缓存补丁（进程级）

放在服务入口 import 段之后、任何网络调用之前：

```python
import socket as _socket
import time

_DNS_CACHE = {}
_orig_getaddrinfo = _socket.getaddrinfo

def _cached_getaddrinfo(host, port, *a, **kw):
    now = time.time()
    hit = _DNS_CACHE.get(host)
    if hit and now - hit[0] < 600:      # 成功结果 10 分钟内直接用
        return hit[1]
    try:
        res = _orig_getaddrinfo(host, port, *a, **kw)
        _DNS_CACHE[host] = (now, res)
        return res
    except Exception:
        if hit:                          # 过期缓存也比解析失败强
            return hit[1]
        raise

_socket.getaddrinfo = _cached_getaddrinfo
```

适用条件：访问的域名集合有限且 IP 稳定（云 API 端点都满足）。注意 websockets/aiohttp/urllib 全走 getaddrinfo，一处补丁全体生效；aiohttp 自己的 resolver 若显式指定了 AsyncResolver 则要单独处理。

## 模式 B：TTS 主备切换（async 伪码）

```python
async def synth(text):
    key = (text, voice)
    if key in CACHE: return CACHE[key]
    engine = 'primary'
    try:
        mp3 = await edge_tts_synth(text)          # 主：免费/音色好
        if not mp3: raise RuntimeError('empty audio')
    except Exception as e:
        log(f'[tts] primary 失败({type(e).__name__})，切备用')
        engine = 'fallback'
        mp3 = await same_channel_tts(text)        # 备：与 ASR 同通道的云 TTS
    pcm = ffmpeg_to_pcm24k(mp3)                   # 失败抛错，勿吞
    chunks = [b64(pcm[i:i+4800]) for i in range(0, len(pcm), 4800)]
    CACHE[key] = chunks
    return chunks
```

要点：主提供商「返回空」也算失败（连接被 reset 时有的 SDK 不抛错只给空）；备选选与其它存活 API 同通道的提供商，坏窗相关性最低。

## 模式 C：话轮级超时

```python
try:
    text = await asyncio.wait_for(asr_transcribe(pcm), timeout=25)
except asyncio.TimeoutError:
    await speak_cached('刚才没听清，您再说一遍？')  # 安抚语也要预缓存
    return                                          # 丢一拍，不卡链
```

## 模式 D+E：即时应答 + 按句流式（语音助手类服务）

分句：`re.split(r'(?<=[。！？；!?;\n])', text)`，短句（<12字）并入前句。

流式发送骨架：

```python
async def send_stream(ws, full_text, sentences):
    await send_response_created_frames(ws)
    for si, sent in enumerate(sentences):
        try:
            chunks = await synth(sent)             # 逐句合成，失败跳句不断链
        except Exception:
            continue
        for c in chunks:
            await ws.send(audio_delta(c)); await asyncio.sleep(0.06)
        if si == 0: log(f'首句开播 {elapsed:.1f}s')
    await send_response_done_frames(ws, full_text)
```

唤醒即时应答：预合成 ack 短语并在服务启动后台预热缓存（`asyncio.create_task(prewarm())` 挂在端口监听后）；捕获唤醒+指令一句流时先播 ack 再进慢管道。

## 分层诊断命令速查（Linux 工作站）

```bash
nmcli -g 802-11-wireless.powersave con show <SSID>        # 省电模式，default=嫌疑
nmcli con modify <SSID> 802-11-wireless.powersave 2 && nmcli dev reapply <dev>
ping -c 8 -i 1 <本地网关>                                  # WiFi 层
ping -c 8 -i 1 <公网API域名>                               # 出口层
ping -I <另一网卡> -c 5 <公网IP>                           # 副接口是否真能出网
cat /proc/net/wireless                                     # 信号质量（无 iw 时）
nslookup <域名> 223.5.5.5                                  # DNS 服务器可用性
curl -s -o /dev/null -w '%{time_total}s\n' -m 10 https://<API域名>   # 端点连通
```

判断表：

| 现象 | 结论 |
|---|---|
| 本地网关延迟跳变几十 ms~秒级、丢包 | WiFi 层（先关省电） |
| 本地网关 <10ms 但公网几百 ms~秒级 | 出口拥塞（软件扛：缓存+备选+超时） |
| 某一域名 SSL reset，其它域正常 | 网络设备针对性掐该端点 → 换同功能备选 |
| API 时而亚秒时而 20s+ | DNS 阵发丢包 → 模式 A |
| 多环节同时慢 | 共享依赖（出网/DNS），别换单个 API |
