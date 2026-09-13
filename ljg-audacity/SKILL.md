---
name: ljg-audacity
version: 0.1.0
description: "WAV 音频处理 —— 0 依赖,纯 Python stdlib wave。读 PCM WAV (8/16/24/32-bit, 1-8 ch) → 元数据 + 波形字符画 + 处理 (fade/gain/normalize/trim/reverse) → 写新 WAV。也能合成正弦波 / 白噪声 / 和弦。无需 sox / ffmpeg / Audacity 安装。"
metadata:
  requires:
    bins: ["python3"]
    python: ">=3.9"
  cliHelp: "python3 -c 'from ljg_audacity import synth_sine; w = synth_sine(440, 1.0); w.write(\"/tmp/a.wav\"); print(w.metadata())'"
---

# ljg-audacity

WAV 音频处理。lifestyle for AI agents to process audio without Audacity installed.

## 何时调我

| 用户说 | 调什么 |
|---|---|
| "做一段音频" / "生成 440Hz 音" | `synth_sine(440, 1.0).write("out.wav")` |
| "做个和弦" / "C 大调和弦" | `make_chord([261.63, 329.63, 392.00])` |
| "读这个 wav" / "看音频元数据" | `WavFile.read("x.wav").metadata()` |
| "画波形图" | `wav.waveform_ascii(width=80)` |
| "淡入淡出" / "fade" | `wav.fade_in(0.5).fade_out(0.5)` |
| "音量标准化" | `wav.normalize(-3.0)` |
| "加 6dB" | `wav.gain(6.0)` |
| "裁剪 [2s, 5s]" | `wav.trim(2.0, 5.0)` |

## 何时不调我

- 用户要"全功能 Audacity 控制" (spectrogram / effect rack / plug-in) — 用 `cli-anything-audacity` (HKUDS 原版, 需 sox)
- 非 WAV 格式 (mp3/flac/ogg) — 需要 ffmpeg
- 流式播放 — 本 skill 是文件级处理

## 限制

- **只支持 PCM WAV** (8/16/24/32-bit integer, 1-8 ch)
- **不支持** mp3/flac/ogg/aac (需要 ffmpeg)
- **不支持** 效果链 (reverb/compress/EQ) — 原版 Audacity 有,本 skill 简化
- 输出固定 16-bit PCM

## 快速使用

```python
from ljg_audacity import WavFile, synth_sine, make_chord

# 1. 读 + 分析
wav = WavFile.read("input.wav")
print(wav.metadata())
# {'sample_rate': 44100, 'channels': 2, 'bit_depth': 16,
#  'duration_sec': 3.5, 'num_samples': 154350,
#  'peak_db': -3.2, 'rms_db': -18.7}
print(wav.waveform_ascii(width=80))

# 2. 处理链
wav.gain(-3)             # 降 3dB
   .fade_in(0.5)         # 0.5s 淡入
   .fade_out(0.5)        # 0.5s 淡出
   .normalize(-3.0)      # 标准化到 -3dB peak
   .write("output.wav")

# 3. 合成
sine = synth_sine(440, 1.0)              # A4
chord = make_chord([261.63, 329.63, 392.00])  # C major
chord.write("chord.wav")
```

## 数据契约

`WavFile` 字段:
- `sample_rate: int` (Hz, default 44100)
- `channels: int` (1-8)
- `sample_width: int` (bytes: 1/2/3/4)
- `samples: List[List[float]]` — [channel][sample],归一化 [-1, 1]

属性:
- `duration_sec / num_samples / bit_depth`
- `peak / peak_db` (dBFS,0 dB = full scale)
- `rms / rms_db`
- `waveform_ascii(width, height)` — 字符画波形

方法:
- `fade_in(duration_sec) / fade_out(duration_sec)`
- `gain(db)` — 增益
- `normalize(target_db)` — 标准到 target dB peak
- `trim(start_sec, end_sec)` — 裁剪
- `reverse()` — 反向
- `read(path)` / `write(path)` — I/O

工厂:
- `synth_sine(freq_hz, duration_sec, sample_rate, amplitude)`
- `synth_white_noise(duration_sec, sample_rate, amplitude)`
- `make_chord(notes_hz, duration_sec)` — 叠加多个正弦波 + normalize

## 跟 ljg-ppt-design 整合

音频波形图直接进 ljg-ppt-design content_image (round 5 真插图已支持):
```python
import subprocess
# 先把 wav 转 PNG (需要 ffmpeg / matplotlib)
# 简单替代:用 waveform_ascii() 输出到 PPT
```

---

_ljg-audacity · 0 依赖 WAV 处理_
_2026-06-18 · 慧慧 从 HKUDS/CLI-Anything audacity 套件简化移植_
