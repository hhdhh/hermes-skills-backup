---
name: ljg-kdenlive
version: 0.1.0
description: "Kdenlive / MLT 项目 XML 生成器 —— 0 依赖,纯 Python。产标准 MLT XML (.mlt) 给 Kdenlive / melt / Shotcut 打开渲染。视频 / 音频 / 字幕 3 类 track,9 种 profile (1080p30/60, 720p30, 4K30/60 等)。含 slideshow_from_images / podcast_with_captions 2 预设。"
metadata:
  requires:
    bins: ["python3"]
    python: ">=3.9"
  cliHelp: "python3 -c 'from ljg_kdenlive import Project, Clip; p = Project(); p.add_video_track().add_clip(Clip(\"a.mp4\", 0, 0, 120, 0)); p.write(\"/tmp/x.mlt\")'"
---

# ljg-kdenlive

Kdenlive / MLT 项目 XML 生成器。lifestyle for AI agents to produce video projects without Kdenlive / melt installed.

## 何时调我

| 用户说 | 调什么 |
|---|---|
| "做视频项目" / "出个 Kdenlive 工程" | `Project().write("out.mlt")` |
| "做个 slide show" | `slideshow_from_images([...], seconds_per_image=3)` |
| "给音频加字幕" | `podcast_with_captions(audio, captions)` |
| "1080p 60fps" / "4K" | `Project(profile="hd1080p60" / "4k30")` |
| "添加视频轨 / 音频轨 / 字幕轨" | `add_video_track() / add_audio_track() / add_text_track()` |
| "加文字覆盖" | `add_text_overlay("Hello", timeline_in=5)` |

## 何时不调我

- 用户要"全功能 Kdenlive 控制" (effect rack / color grading) — 用 `cli-anything-kdenlive` (HKUDS 原版,需 melt)
- 用户要"实际渲染成 .mp4" — 本 skill 只产 .mlt 工程,渲染用 melt / Kdenlive / ffmpeg
- 用户要"剪辑 / 转场 / 复杂合成" — 本 skill 简化版,只支持基础 clip 摆放

## 9 个预设 profile

| key | 分辨率 | fps | 大小 |
|---|---|---|---|
| `hd1080p30` | 1920×1080 | 30 | 标准 HD |
| `hd1080p60` | 1920×1080 | 60 | 流畅 HD |
| `hd720p30`  | 1280×720  | 30 | 标清 |
| `4k30`      | 3840×2160 | 30 | 4K |
| `4k60`      | 3840×2160 | 60 | 4K 流畅 |
| `sd_ntsc`   | 720×480   | 29.97 | NTSC 标清 |
| (更多) | | | |

## 快速使用

```python
from ljg_kdenlive import Project, Track, Clip

# 1. 基础项目
proj = Project(name="My Video", profile="hd1080p30")
v1 = proj.add_video_track("V1")
v1.add_clip(Clip(
    source="intro.mp4",
    timeline_in=0,
    source_in=0,
    source_out=120,  # 4 秒 @ 30fps
))
v1.add_clip(Clip(
    source="main.mp4",
    timeline_in=120,
    source_in=0,
    source_out=300,
))
a1 = proj.add_audio_track("A1")
a1.add_clip(Clip("bgm.mp3", 0, 0, 420))
proj.add_text_overlay("Title", timeline_in=10, duration_frames=90)
print(proj.metadata())
# {'name': 'My Video', 'profile': 'hd1080p30', 'width': 1920, 'height': 1080,
#  'fps': '30/1', 'track_count': 3, 'total_duration_frames': 420,
#  'total_duration_sec': 14.0}
proj.write("/tmp/video.mlt")
# → /tmp/video.mlt (Kdenlive / melt 打开渲染)

# 2. 图片 slide show
from ljg_kdenlive import slideshow_from_images
proj = slideshow_from_images(
    ["a.jpg", "b.jpg", "c.jpg"],
    seconds_per_image=3,
    profile="hd1080p30",
)
proj.write("/tmp/slideshow.mlt")

# 3. Podcast + 字幕
from ljg_kdenlive import podcast_with_captions
proj = podcast_with_captions(
    "podcast.mp3",
    [
        {"text": "Hello world", "in_sec": 0, "out_sec": 3},
        {"text": "Today we discuss...", "in_sec": 3, "out_sec": 8},
    ],
)
proj.write("/tmp/podcast.mlt")
```

## 数据契约

`Project` 字段:
- `name: str`
- `profile: str` (key from PROFILES)
- `tracks: List[Track]`
- `metadata: dict`

方法:
- `add_video_track(name) / add_audio_track(name) / add_text_track(name)`
- `add_text_overlay(text, timeline_in, duration_frames)`
- `total_duration_frames() / total_duration_sec()`
- `metadata()` → dict
- `write(path)` → 写 .mlt

`Track`:
- `name, track_type (video/audio/text)`
- `clips: List[Clip]`
- `add_clip(clip)` / `add_text(text, timeline_in, duration_frames)`

`Clip`:
- `source` (路径 / 文本 / producer id)
- `timeline_in, source_in, source_out` (帧)
- `clip_type` (producer/blank/color/text)
- `properties: dict`
- `in_transition / out_transition`

`PROFILES`: 9 个预设 (HD 720p/1080p, 4K, NTSC SD)

`slideshow_from_images(paths, seconds_per_image, profile)`
`podcast_with_captions(audio_path, captions, profile)`

## MLT XML 格式

输出标准 MLT 7.0 XML:
```xml
<mlt LC_NUMERIC="C" version="7.0.0" title="...">
  <profile width="..." height="..." fps="30/1" ... />
  <producer id="..." in="0" out="120" />
  ...
  <playlist id="V1">
    <entry producer="..." in="0" out="120" t="0/30/1" />
  </playlist>
  <tractor id="tractor0" in="0" out="420">
    <multitrack id="V1" />
    <multitrack id="A1" />
    <multitrack id="tractor0" />
  </tractor>
</mlt>
```

Kdenlive / melt / Shotcut 都能直接打开。

## 已知限制

- 只产 .mlt 工程文件,不出 .mp4 (渲染靠 melt/Kdenlive/ffmpeg)
- 不支持 effect rack / color grading (那是 Kdenlive 内部编辑器的能力)
- 不支持 transition / cross-fade (跟原版比,只支持基础 clip 摆放)
- melt / ffmpeg 不在本 skill 安装范围

## 跟 ljg-audacity 整合

```python
# 生成一段 5s 440Hz 音,再生成 Kdenlive 项目
from ljg_audacity import synth_sine
sine = synth_sine(440, 5.0)
sine.write("/tmp/tone.wav")
# 然后 Kdenlive 项目引这个 .wav 当 A1 track
from ljg_kdenlive import Project, Clip
proj = Project()
proj.add_audio_track("A1").add_clip(Clip("/tmp/tone.wav", 0, 0, 5 * 30))
proj.write("/tmp/tone-project.mlt")
```

---

_ljg-kdenlive · 0 依赖 MLT 项目生成器_
_2026-06-18 · 慧慧 从 HKUDS/CLI-Anything kdenlive 套件简化移植_
