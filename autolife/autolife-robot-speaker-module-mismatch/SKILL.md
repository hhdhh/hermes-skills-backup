---
name: autolife-robot-speaker-module-mismatch
description: Use when 机器人播 wav/TTS 报 mod_speaker not found 或无声。
---

# 扬声器逻辑模块与实际声卡不匹配（wav/TTS 播放失败）

症状：手机 app 播 wav/TTS 报 `Error processing TTS_LIST command: Speaker module mod_speaker_main` 类错误，机器人不发声；vision 日志里 GStreamer 层能看到声卡（如 `Speaker registered on CARD=PCH`）但 SDK 模块层报 not found。

## 机制

SDK 机型描述文件（`autolife_robot_sdk/descriptions/autolife_s1/configs/robot_v2_2.json`）把多种扬声器硬件（pc320532 / kt / 3.5mm_jack）都映射到同一逻辑名 `mod_speaker_main`。vision 配置（`autolife_robot_vision/configs/robot_v2_2.json` 的 ENABLED_MODULES）启用哪个物理模块，就按它去找声卡——**机器换了声卡方案（如 USB pc320532 → 板载 PCH）而配置还留旧模块名时，SDK 实例化不出扬声器**，逻辑名解析失败。

## 诊断（对比正常机二分定位）

1. `cat /proc/asound/cards` 看实际声卡（PCH=板载、PC320532=USB 声卡、DICOTA/Gadge 常是摄像头/麦克风）。
2. vision 配置 ENABLED_MODULES 里查 `mod_speaker_*` 启用的是哪个。
3. 找一台正常机对比同一处配置——机型批次换了声卡方案时，故障机的启用模块与正常机必然不同。
4. journal 确认：麦克风逻辑名解析成功而 speaker 失败，即指向模块绑定而非音频链路。

## 修复（机上 30 秒）

```bash
CONF=~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_vision/configs/robot_v2_2.json
cp $CONF $CONF.bak.$(date +%s)
sed -i 's/"mod_speaker_pc320532"/"mod_speaker_3.5mm_jack"/' $CONF   # 按实际声卡选目标模块
python3 -c "import json;d=json.load(open('$CONF'.replace('~','/home/ubuntu')));print('OK' if 'mod_speaker_3.5mm_jack' in str(d) else 'FAIL')"
systemctl --user restart vision-service && sleep 3 && systemctl --user restart face-detection-service
journalctl --user -u vision-service --since "1 min ago" | grep -i speaker   # 应见模块实例化成功、无 not found
```

修完让现场用手机 app 重播 wav 端到端验证。

## 坑

- 3.5mm 插孔机型接的也是板载 PCH 卡——模块名带 3.5mm_jack 不代表是独立 USB 声卡，以 `/proc/asound/cards` 实际为准。
- 改 vision 配置必连带重启 face-detection（共享 shm，硬规范）。
- 日志里 GStreamer 层「registered on CARD=xxx」不代表 SDK 模块层 OK——两层独立，判定以模块实例化日志为准。
