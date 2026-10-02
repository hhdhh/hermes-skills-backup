# Qwen realtime 语音输入分层诊断（「说话没反应」排查梯）

机器人说话无反应时，禁止先猜配置改开关（input_vad/main/auxiliary 来回切只会越改越错）——按以下五层自底向上测，每层都有独立裁决力，用实测值定方向。

## 第 1 层 · 硬件（裸 ALSA RMS，ground truth）

短暂停 vision+face，每张卡直接 arecord 算 RMS（完事立刻恢复服务）：

```bash
systemctl --user stop vision-service.service face-detection-service.service
arecord -D hw:1,0 -f S16_LE -r 16000 -d 3 /tmp/probe.wav   # 每张采集卡各来一次
systemctl --user start vision-service.service; sleep 3; systemctl --user start face-detection-service.service
```

- **RMS=0（增益拉满仍纯零）= 硬件死**——软件无解，报修；现场顶用方案是换绑活卡（见下）。
- RMS 几十 = 悬空噪声；说话时 RMS 数千 = 活麦。
- 运行中 SHM 里的数据可能是旧帧/零帧，判硬件必须停服裸录。

## 第 2 层 · SHM 流

读 `/dev/shm/al_mic_<module>_data` 两次采样 diff + RMS：changed_bytes>0 且有声 = 采集服务在写。gadget 模块缓冲 = 32 槽 × 1048 B（48k/2ch/16bit）；face-detection 的 HybridVAD 消费同一 SHM（日志 `Using mic SHM: <module>`）。

## 第 3 层 · VAD gate（journal）

`grep Flushing`：出现 "Flushing N buffered mic chunk(s) after HybridVAD gate opened" = gate 开了。**gate 开 + 零 transcript 零应答 = 问题在 gate 之后（音频从未转发出去），不要再动麦克风配置。**

## 第 4 层 · 网络出口（内核 TX 计数器，零侵入）

找 dashscope websocket 再 5s 窗采样（窗口内对机器人说话）：

```bash
ss -tnp | grep <vision主PID> | grep ':443'      # 找本地端口
ss -tni sport = :<端口> | grep -o 'bytes_sent:[0-9]*'
```

说话期间 TX 平 = **音频从未离开本机**（manager 没调 api 发送），嫌疑集中在 hvaD 转发门；TX 涨 = 服务器侧问题，进第 5 层。

## 第 5 层 · 服务器（独立 websocket 实测，绕开整个机器人栈）

在机器人上跑独立 websockets 客户端（session.update server_vad + pcm16 → 分段 append → commit → 读事件流；真码 `~/.hermes/workspace/robot277_build/standalone_ws_test.py`，key 从 settings.toml 读）。

- **格式硬事实：qwen realtime 服务器只吃 24k 单声道 pcm16**。喂 48k 立体声 commit 直接报 `buffer too small, or have no audio`，且 server_vad 永不触发。
- 24k mono 得到 `speech_started` + 完整 `transcription.completed` = key/出网/模型全好，故障墙内。
- `api.send_audio` 是 base64 透传（ws 帧内容=输入原字节），**格式转换在 manager 层**：绕过 manager 注入必须自带 24k/mono（audioop.tomono→ratecv）。`send_pcm_data` 只入 audio_input_pcm_buffer 不发送（无 ws.send）；`send_audio_sync` 从非事件循环线程直调返回 False；跨线程正解 `asyncio.run_coroutine_threadsafe(api.send_audio(seg), mgr.async_loop)`。

## 麦克风→声卡绑定（不在 settings.toml！）

`ai_audio_input_device = main|auxiliary` 只选逻辑模块，真实卡绑定在
`$SP/autolife_robot_sdk/descriptions/autolife_s1/configs/robot_v2_2.json` → `robot_v2_2.mod_microphone_.<模块>.settings`：
- `mod_name` = mod_microphone_main / mod_microphone_auxiliary（逻辑位）
- `sound_card_name` 与 aplay 卡名字符串匹配（Gadget/D4K/PCH…）
- `control_name` 必须与 `amixer -c N contents` 实名一致（D4K 是 `Mic Capture Volume` 不是 `Capture Volume`）
- `sample_rate/channels` 决定 SHM 采集格式与 hvaD 帧预期

头麦硬件死 → 换绑 USB 摄像头麦：备份 json → 改 sound_card_name/longname/control_name → json.load 校验 → 重启 vision+face。face-detection 环境自己那份 robot_v2_2.json 不用改（它只读 SHM 不开卡）。**现场活动期间那个 USB 摄像头不能拔，拔了重新聋。**

## 实例探针（Cython 栈动态遥测）

无源码时读活状态/包关键方法：main.py 构造 wrapper 后后台遍历找 AIChatbotManager / AudioRealtimeAPIQwen 实例（object-graph finder），api 属性表一次性 dump 列出全部门控（`_ai_audio_active/_hvad_talking/_hvad_enabled/_awaiting_user_response…`）。包装规则：
- api.send_audio/send_text 与 websockets ClientConnection.send 是**纯 Python 可包**（跨对象调用走属性查找）；
- Cython 内部 C 直连调用（manager 内部 self._send_*）**拦不到**，别在编译模块内部调用上浪费时间。
- 探针自检线程用 /tmp marker 防重跑：**每轮重启前必须 rm marker**，否则新版本自检被旧 marker 静默跳过（排查半天的常见假象）。
- audioop 坑：`tomono` 返回 bytes 单值（不能按元组解包），`ratecv` 返回 (bytes, state)。

## hvaD 校准记录器（量化 gate 置信度）

`hybrid_vad_calibration_enabled = true` 每 12s 落 JSONL 于 `scripts/calibration_logs/`，speech/silence 段的 count 与 audio_conf 统计量化 hvaD 置信度。**有人说话期间 count=0 且 audio_conf 全 0、但 gate 有 Flushing = hvaD 置信度从未达转发阈值**（常见根因：该模块 hvaD profile 预期的采样率/声道与实际 SHM 流不匹配）。该开关是诊断工具，用完关掉恢复 settings。

## 大载荷推送纪律

- >100KB 二进制/PCM 用 paramiko `sftp.put` 直推（robput 机号.py 辅助脚本）。robssh 命令通道把 base64 塞 argv：小文件侥幸可用，大文件撞本地 ARG_MAX（argument list too long）或引号嵌套炸。
- robssh sudo 推的文件落盘 root:root——push 后补 `chown ubuntu:ubuntu`，否则后续 ubuntu 用户改写 Permission denied。
- `systemctl --user` 不能走 sudo（丢 session bus）；sudo 只做文件操作，服务重启走普通通道，与重启分两条命令发。
