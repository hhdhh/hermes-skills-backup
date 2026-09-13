"""ljg-audacity — WAV 音频处理 (0 依赖,纯 Python)。

来源: 简化适配 HKUDS/CLI-Anything (audacity 套件)。
原版调 sox (系统 binary) 跑转码,本 skill 走 0 依赖路线 (只支持 PCM WAV,够 demo 用)。

用法:
  from ljg_audacity import WavFile, synth_sine, make_chord
  wav = WavFile.read("input.wav")
  print(wav.metadata())
  print(wav.waveform_ascii(width=80))
  wav.gain(-3).fade_in(0.1).fade_out(0.5).write("output.wav")

  # 合成
  chord = make_chord([261.63, 329.63, 392.00])  # C major
  chord.write("chord.wav")
"""

from __future__ import annotations

from .wav import WavFile, synth_sine, synth_white_noise, make_chord

__version__ = "0.1.0"
__all__ = ["WavFile", "synth_sine", "synth_white_noise", "make_chord"]
