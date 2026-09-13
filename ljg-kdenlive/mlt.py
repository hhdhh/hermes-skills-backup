"""Kdenlive / MLT 项目 XML 生成器 (0 依赖,纯 Python)。

MLT = MediaLovinToolkit XML 框架,Kdenlive / melt / Shotcut 都用。
本 skill 输出标准 MLT XML,能直接被 Kdenlive / melt 打开渲染。

用法:
  from ljg_kdenlive import Project, Track, Clip
  proj = Project(name="My Video", profile="hd1080p30")
  track = proj.add_video_track("V1")
  track.add_clip(Clip("intro.mp4", source_in=0, source_out=120, timeline_in=0))
  track.add_clip(Clip("main.mp4", source_in=0, source_out=300, timeline_in=120))
  proj.add_audio_track("A1").add_clip(...)
  proj.add_text_overlay("Hello", timeline_in=5, duration=3)
  proj.write("/tmp/video.mlt")
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from xml.etree import ElementTree as ET


# ── 预设 profile (跟 Kdenlive 标准对齐) ──────────────────
PROFILES: dict = {
    "hd1080p30": {"width": 1920, "height": 1080, "fps_num": 30, "fps_den": 1, "progressive": 1, "dar_num": 16, "dar_den": 9},
    "hd1080p60": {"width": 1920, "height": 1080, "fps_num": 60, "fps_den": 1, "progressive": 1, "dar_num": 16, "dar_den": 9},
    "hd720p30":  {"width": 1280, "height": 720,  "fps_num": 30, "fps_den": 1, "progressive": 1, "dar_num": 16, "dar_den": 9},
    "4k30":      {"width": 3840, "height": 2160, "fps_num": 30, "fps_den": 1, "progressive": 1, "dar_num": 16, "dar_den": 9},
    "4k60":      {"width": 3840, "height": 2160, "fps_num": 60, "fps_den": 1, "progressive": 1, "dar_num": 16, "dar_den": 9},
    "sd_ntsc":   {"width": 720,  "height": 480,  "fps_num": 30000, "fps_den": 1001, "progressive": 0, "dar_num": 4, "dar_den": 3},
}


# ── Clip ──────────────────────────────────────────────
@dataclass
class Clip:
    """MLT clip (一个媒体片段)。"""
    source: str                     # 媒体路径 / 文本 / producer id
    timeline_in: int = 0            # 在 timeline 上的起点 (帧)
    source_in: int = 0              # 媒体内入点 (帧)
    source_out: int = 0             # 媒体内出点 (帧); 0 = 整段
    clip_type: str = "producer"     # producer / blank / color / text
    properties: dict = field(default_factory=dict)
    in_transition: Optional[str] = None
    out_transition: Optional[str] = None
    id: Optional[str] = None

    def duration_frames(self) -> int:
        if self.source_out > self.source_in:
            return self.source_out - self.source_in
        return 0


# ── Track ──────────────────────────────────────────────
@dataclass
class Track:
    """MLT track (视频 / 音频 / 字幕轨)。"""
    name: str
    track_type: str = "video"        # video / audio / text
    clips: List[Clip] = field(default_factory=list)

    def add_clip(self, clip: Clip) -> "Track":
        self.clips.append(clip)
        return self

    def add_text(self, text: str, timeline_in: int, duration_frames: int) -> "Track":
        """加文字 (作为 producer-type clip)。"""
        clip = Clip(
            source=text,
            timeline_in=timeline_in,
            source_in=0,
            source_out=duration_frames,
            clip_type="text",
        )
        return self.add_clip(clip)


# ── Project ──────────────────────────────────────────
@dataclass
class Project:
    """MLT project。"""
    name: str = "untitled"
    profile: str = "hd1080p30"
    tracks: List[Track] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def add_video_track(self, name: str = "V1") -> Track:
        t = Track(name=name, track_type="video")
        self.tracks.append(t)
        return t

    def add_audio_track(self, name: str = "A1") -> Track:
        t = Track(name=name, track_type="audio")
        self.tracks.append(t)
        return t

    def add_text_track(self, name: str = "T1") -> Track:
        t = Track(name=name, track_type="text")
        self.tracks.append(t)
        return t

    def add_text_overlay(self, text: str, timeline_in: int = 0,
                          duration_frames: int = 60) -> "Project":
        """加全屏文字覆盖。"""
        text_track = None
        for t in self.tracks:
            if t.track_type == "text":
                text_track = t
                break
        if text_track is None:
            text_track = self.add_text_track()
        text_track.add_text(text, timeline_in, duration_frames)
        return self

    def total_duration_frames(self) -> int:
        """整 project 最长时长 (帧)。"""
        max_end = 0
        for t in self.tracks:
            for c in t.clips:
                end = c.timeline_in + c.duration_frames()
                if end > max_end:
                    max_end = end
        return max_end

    def total_duration_sec(self) -> float:
        p = PROFILES.get(self.profile, PROFILES["hd1080p30"])
        fps = p["fps_num"] / p["fps_den"]
        return self.total_duration_frames() / fps if fps else 0.0

    # ── MLT XML 输出 ──────────────────────────────────
    def _to_xml(self) -> ET.Element:
        p = PROFILES.get(self.profile, PROFILES["hd1080p30"])
        # MLT root
        mlt = ET.Element("mlt", attrib={
            "LC_NUMERIC": "C",
            "version": "7.0.0",
            "title": self.name,
        })
        # Profile
        ET.SubElement(mlt, "profile", attrib={
            "width": str(p["width"]),
            "height": str(p["height"]),
            "fps": f"{p['fps_num']}/{p['fps_den']}",
            "progressive": str(p["progressive"]),
            "display_aspect_num": str(p["dar_num"]),
            "display_aspect_den": str(p["dar_den"]),
        })
        # Producers (media refs)
        producer_ids = set()
        for t in self.tracks:
            for c in t.clips:
                if c.source not in producer_ids and c.clip_type in ("producer", "text", "color"):
                    pid = c.id or f"producer_{len(producer_ids)}"
                    c.id = pid
                    producer_ids.add(c.source)
                    if c.clip_type == "text":
                        ET.SubElement(mlt, "producer", attrib={
                            "id": pid,
                            "in": str(c.source_in),
                            "out": str(c.source_out),
                        }).text = c.source
                    else:
                        ET.SubElement(mlt, "producer", attrib={
                            "id": pid,
                            "in": str(c.source_in),
                            "out": str(c.source_out),
                        })
        # Playlists (tracks)
        for t in self.tracks:
            playlist = ET.SubElement(mlt, "playlist", attrib={"id": t.name})
            for c in t.clips:
                entry_attrs = {
                    "producer": c.id or c.source,
                    "in": str(c.source_in),
                    "out": str(c.source_out),
                }
                if c.timeline_in > 0:
                    entry_attrs["t"] = f"{c.timeline_in}/{self._total_fps()}"
                ET.SubElement(playlist, "entry", attrib=entry_attrs)
        # Tractor (root container with tracks)
        tractor = ET.SubElement(mlt, "tractor", attrib={
            "id": "tractor0",
            "in": "0",
            "out": str(self.total_duration_frames()),
        })
        for t in self.tracks:
            ET.SubElement(tractor, "multitrack", attrib={"id": t.name})
        ET.SubElement(tractor, "multitrack", attrib={"id": "tractor0"})
        return mlt

    def _total_fps(self) -> str:
        p = PROFILES.get(self.profile, PROFILES["hd1080p30"])
        return f"{p['fps_num']}/{p['fps_den']}"

    def to_string(self) -> str:
        root = self._to_xml()
        ET.indent(root, space="  ")
        return ET.tostring(root, encoding="unicode")

    def write(self, path: str) -> str:
        parent = Path(path).parent
        if parent:
            parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n')
            f.write(self.to_string())
        return path

    def metadata_dict(self) -> dict:
        """项目元数据 (避免跟 field 同名)。"""
        p = PROFILES.get(self.profile, PROFILES["hd1080p30"])
        return {
            "name": self.name,
            "profile": self.profile,
            "width": p["width"],
            "height": p["height"],
            "fps": f"{p['fps_num']}/{p['fps_den']}",
            "track_count": len(self.tracks),
            "total_duration_frames": self.total_duration_frames(),
            "total_duration_sec": round(self.total_duration_sec(), 2),
        }


# ── 预设模板 ──────────────────────────────────────────
def slideshow_from_images(
    image_paths: List[str],
    seconds_per_image: float = 3.0,
    profile: str = "hd1080p30",
) -> Project:
    """从图片列表生成 slide show (Kdenlive / melt 能直接渲染)。"""
    p = PROFILES[profile]
    fps = p["fps_num"] / p["fps_den"]
    dur_frames = int(seconds_per_image * fps)

    proj = Project(name="slideshow", profile=profile)
    v1 = proj.add_video_track("V1")
    for i, path in enumerate(image_paths):
        v1.add_clip(Clip(
            source=path,
            timeline_in=i * dur_frames,
            source_in=0,
            source_out=dur_frames,
        ))
    a1 = proj.add_audio_track("A1")
    a1.add_clip(Clip(
        source="background_music.mp3",
        timeline_in=0,
        source_in=0,
        source_out=len(image_paths) * dur_frames,
    ))
    return proj


def podcast_with_captions(
    audio_path: str,
    captions: List[dict],
    profile: str = "hd1080p30",
) -> Project:
    """从音频 + 字幕列表生成 podcast 项目 (字幕叠在黑底视频上)。

    captions: [{'text': 'Hello', 'in_sec': 0, 'out_sec': 3}, ...]
    """
    proj = Project(name="podcast", profile=profile)
    # 黑色背景视频轨 (30 秒占位)
    proj.add_video_track("V1").add_clip(Clip(
        source="black",
        timeline_in=0,
        source_in=0,
        source_out=int(proj.total_duration_frames() or 30 * 30),
        clip_type="color",
    ))
    proj.add_audio_track("A1").add_clip(Clip(
        source=audio_path,
        timeline_in=0,
        source_in=0,
        source_out=0,  # 0 = use file duration (melt 决定)
    ))
    p = PROFILES[profile]
    fps = p["fps_num"] / p["fps_den"]
    t1 = proj.add_text_track("T1")
    for cap in captions:
        t1.add_text(
            cap["text"],
            timeline_in=int(cap["in_sec"] * fps),
            duration_frames=int((cap["out_sec"] - cap["in_sec"]) * fps),
        )
    return proj
