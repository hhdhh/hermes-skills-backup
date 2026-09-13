"""ljg-kdenlive — Kdenlive / MLT 项目 XML 生成器 (0 依赖,纯 Python)。

来源: 简化适配 HKUDS/CLI-Anything (kdenlive 套件)。
原版调 melt / ffmpeg 实际渲染,本 skill 走 0 依赖路线,只产 MLT XML。
生成的 .mlt 文件能直接被 Kdenlive / melt / Shotcut 打开渲染。

用法:
  from ljg_kdenlive import Project, Track, Clip, slideshow_from_images
  proj = Project(name="My Video", profile="hd1080p30")
  v1 = proj.add_video_track()
  v1.add_clip(Clip("intro.mp4", source_in=0, source_out=120, timeline_in=0))
  proj.write("/tmp/video.mlt")

  # 预设: 图片 slide show
  proj = slideshow_from_images(["a.jpg", "b.jpg", "c.jpg"], seconds_per_image=3)
  proj.write("/tmp/slideshow.mlt")
"""

from __future__ import annotations

from .mlt import Project, Track, Clip, PROFILES, slideshow_from_images, podcast_with_captions

__version__ = "0.1.0"
__all__ = [
    "Project", "Track", "Clip", "PROFILES",
    "slideshow_from_images", "podcast_with_captions",
]
