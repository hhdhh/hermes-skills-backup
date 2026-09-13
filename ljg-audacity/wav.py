"""WAV 文件读取 + 简单处理 (0 依赖,纯 Python)。

WAV = RIFF 容器 + fmt + data chunks。
- 8/16/24/32-bit PCM, 1-8 channels
- 读 header → 元数据 (duration/channels/sample_rate)
- 读 samples → 波形分析 (peak / RMS / 简化波形图)
- 写 WAV → 生成新文件 (fade / normalize / mix)

用法:
  from ljg_audacity import WavFile
  wav = WavFile.read("input.wav")
  print(wav.duration_sec, wav.channels, wav.sample_rate)
  print(wav.peak_db, wav.rms_db)
  print(wav.waveform_ascii(width=80))  # 字符画波形
  wav.fade_in(0.5).fade_out(0.5).write("output.wav")
"""

from __future__ import annotations

import math
import struct
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class WavFile:
    """WAV 音频文件 (简化,只支持 PCM 8/16/24/32-bit)。"""

    sample_rate: int = 44100
    channels: int = 1
    sample_width: int = 2          # bytes per sample (1=8bit, 2=16bit, 3=24bit, 4=32bit)
    samples: List[List[float]] = field(default_factory=list)  # [channel][sample], 归一化到 [-1, 1]

    # ── 元数据 ──
    @property
    def num_samples(self) -> int:
        return len(self.samples[0]) if self.samples else 0

    @property
    def duration_sec(self) -> float:
        if self.sample_rate == 0:
            return 0.0
        return self.num_samples / self.sample_rate

    @property
    def bit_depth(self) -> int:
        return self.sample_width * 8

    # ── 波形分析 ──
    @property
    def peak(self) -> float:
        if not self.samples:
            return 0.0
        return max(abs(s) for ch in self.samples for s in ch) or 1e-9

    @property
    def peak_db(self) -> float:
        return 20 * math.log10(self.peak) if self.peak > 0 else -120.0

    @property
    def rms(self) -> float:
        if not self.samples or self.num_samples == 0:
            return 0.0
        total = sum(s * s for ch in self.samples for s in ch)
        return math.sqrt(total / (self.num_samples * self.channels))

    @property
    def rms_db(self) -> float:
        return 20 * math.log10(self.rms) if self.rms > 0 else -120.0

    def waveform_ascii(self, width: int = 80, height: int = 12) -> str:
        """简化波形图 (取每列的 min/max, 字符画)。"""
        if not self.samples or width <= 0:
            return ""
        mixed = self.samples[0] if self.channels == 1 else [
            sum(ch[i] for ch in self.samples) / self.channels
            for i in range(self.num_samples)
        ]
        n = len(mixed)
        if n == 0:
            return ""
        col_size = max(1, n // width)
        lines = []
        for row in range(height, 0, -1):
            threshold = (row / height) * 0.5  # 0 到 0.5
            line = ""
            for col in range(width):
                start = col * col_size
                end = min(start + col_size, n)
                if start >= end:
                    line += " "
                    continue
                seg_max = max(abs(mixed[i]) for i in range(start, end)) if end > start else 0
                line += "█" if seg_max >= threshold else " "
            lines.append(line)
        return "\n".join(lines)

    # ── 处理 ──
    def fade_in(self, duration_sec: float = 0.5) -> "WavFile":
        """线性 fade in (前 duration_sec 秒振幅 0→1)。"""
        fade_samples = int(duration_sec * self.sample_rate)
        for ch in self.samples:
            for i in range(min(fade_samples, self.num_samples)):
                ch[i] *= i / fade_samples
        return self

    def fade_out(self, duration_sec: float = 0.5) -> "WavFile":
        """线性 fade out (后 duration_sec 秒振幅 1→0)。"""
        fade_samples = int(duration_sec * self.sample_rate)
        n = self.num_samples
        for ch in self.samples:
            for i in range(fade_samples):
                idx = n - 1 - i
                if idx < 0:
                    break
                ch[idx] *= i / fade_samples
        return self

    def normalize(self, target_db: float = -3.0) -> "WavFile":
        """normalize 到 target_db (音量标准化)。"""
        target_peak = 10 ** (target_db / 20)
        scale = target_peak / self.peak if self.peak > 0 else 1.0
        for ch in self.samples:
            for i in range(self.num_samples):
                ch[i] *= scale
        return self

    def gain(self, db: float) -> "WavFile":
        """加 db 增益。"""
        scale = 10 ** (db / 20)
        for ch in self.samples:
            for i in range(self.num_samples):
                ch[i] *= scale
        return self

    def reverse(self) -> "WavFile":
        for ch in self.samples:
            ch.reverse()
        return self

    def trim(self, start_sec: float, end_sec: float) -> "WavFile":
        """裁剪 [start_sec, end_sec] 区间。"""
        s = int(start_sec * self.sample_rate)
        e = int(end_sec * self.sample_rate)
        self.samples = [ch[s:e] for ch in self.samples]
        return self

    # ── I/O ──
    @classmethod
    def read(cls, path: str) -> "WavFile":
        """用 stdlib wave 读 PCM WAV。"""
        with wave.open(path, "rb") as w:
            sr = w.getframerate()
            ch = w.getnchannels()
            sw = w.getsampwidth()
            nframes = w.getnframes()
            raw = w.readframes(nframes)

        # 解码 samples 到 [-1, 1] 浮点
        if sw == 1:
            fmt = f"{nframes * ch}B"
            scale = 128.0
        elif sw == 2:
            fmt = f"<{nframes * ch}h"
            scale = 32768.0
        elif sw == 3:
            # 24-bit packed,需要手解
            samples_int = []
            for i in range(0, len(raw), 3):
                b = raw[i:i + 3]
                v = b[0] | (b[1] << 8) | (b[2] << 16)
                if v & 0x800000:
                    v -= 0x1000000
                samples_int.append(v)
            scale = 8388608.0
            samples_iter = iter(samples_int)
        elif sw == 4:
            fmt = f"<{nframes * ch}i"
            scale = 2147483648.0
        else:
            raise ValueError(f"不支持的 sample_width={sw}")

        if sw in (1, 2, 4):
            unpacked = struct.unpack(fmt, raw)
        else:
            unpacked = list(samples_iter)

        # 重排: [channel][sample]
        samples = [[0.0] * nframes for _ in range(ch)]
        for i, v in enumerate(unpacked):
            ch_idx = i % ch
            sample_idx = i // ch
            samples[ch_idx][sample_idx] = v / scale

        return cls(sample_rate=sr, channels=ch, sample_width=sw, samples=samples)

    def write(self, path: str) -> str:
        """写 WAV (16-bit PCM,标准化到 [-32768, 32767])。"""
        if not self.samples:
            raise ValueError("没有 samples")

        # 写 16-bit (兼容性最好)
        nframes = self.num_samples
        with wave.open(path, "wb") as w:
            w.setnchannels(self.channels)
            w.setsampwidth(2)  # 16-bit
            w.setframerate(self.sample_rate)
            # 交织 channels
            max_val = 32767
            frames = bytearray()
            for i in range(nframes):
                for c in range(self.channels):
                    s = max(-1.0, min(1.0, self.samples[c][i]))
                    frames.extend(struct.pack("<h", int(s * max_val)))
            w.writeframes(bytes(frames))
        return path

    def metadata(self) -> dict:
        return {
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "bit_depth": self.bit_depth,
            "duration_sec": round(self.duration_sec, 3),
            "num_samples": self.num_samples,
            "peak_db": round(self.peak_db, 2),
            "rms_db": round(self.rms_db, 2),
        }


# ── 简单合成 ──────────────────────────────────────────
def synth_sine(
    freq_hz: float = 440.0,
    duration_sec: float = 1.0,
    sample_rate: int = 44100,
    amplitude: float = 0.5,
) -> WavFile:
    """生成正弦波 WAV。"""
    n = int(duration_sec * sample_rate)
    samples = [[amplitude * math.sin(2 * math.pi * freq_hz * i / sample_rate)
                for i in range(n)]]
    return WavFile(sample_rate=sample_rate, channels=1, sample_width=2, samples=samples)


def synth_white_noise(
    duration_sec: float = 1.0,
    sample_rate: int = 44100,
    amplitude: float = 0.3,
) -> WavFile:
    """生成白噪声。"""
    import random
    n = int(duration_sec * sample_rate)
    samples = [[random.uniform(-amplitude, amplitude) for _ in range(n)]]
    return WavFile(sample_rate=sample_rate, channels=1, sample_width=2, samples=samples)


# ── 预设效果 ──────────────────────────────────────────
def make_chord(notes_hz: List[float], duration_sec: float = 1.0) -> WavFile:
    """生成和弦 (叠加多个正弦波)。"""
    if not notes_hz:
        raise ValueError("notes_hz 不能空")
    base = synth_sine(notes_hz[0], duration_sec, amplitude=0.3)
    for freq in notes_hz[1:]:
        other = synth_sine(freq, duration_sec, amplitude=0.3)
        for i in range(base.num_samples):
            base.samples[0][i] += other.samples[0][i]
    # normalize
    base.normalize(target_db=-3.0)
    return base
