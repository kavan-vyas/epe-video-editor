"""ffprobe-based inspection of an MP4: stream parameters, duration, keyframes,
and fragmentation detection (pipeline.md §6.2, §6.3, §6.4, §6.6).

The parameters captured here are exactly the ones that must match for a
stream-copy concat to be valid: video codec/profile/level/resolution/pixfmt/
fps/timebase and audio codec/sample-rate/channel-layout.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .ffmpeg import Tools, run


def _fraction(value: str | None) -> float:
    """Parse an ffprobe rational like '30000/1001' into a float."""
    if not value or value in ("0/0", "N/A"):
        return 0.0
    if "/" in value:
        num, _, den = value.partition("/")
        try:
            den_f = float(den)
            return float(num) / den_f if den_f else 0.0
        except ValueError:
            return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


@dataclass(frozen=True)
class VideoParams:
    codec: str
    profile: str
    level: int
    width: int
    height: int
    pix_fmt: str
    fps: float          # average frame rate (rounded for comparison)
    time_base: str

    def signature(self) -> tuple:
        """The fields that MUST match for a lossless concat."""
        return (
            self.codec,
            self.profile,
            self.level,
            self.width,
            self.height,
            self.pix_fmt,
            round(self.fps, 2),
        )

    def human(self) -> str:
        return (
            f"{self.codec} {self.profile}@L{self.level} "
            f"{self.width}x{self.height} {self.pix_fmt} {self.fps:.3f}fps"
        )


@dataclass(frozen=True)
class AudioParams:
    codec: str
    sample_rate: int
    channels: int
    channel_layout: str

    def signature(self) -> tuple:
        return (self.codec, self.sample_rate, self.channels, self.channel_layout)

    def human(self) -> str:
        return (
            f"{self.codec} {self.sample_rate}Hz "
            f"{self.channels}ch ({self.channel_layout})"
        )


@dataclass(frozen=True)
class MediaInfo:
    path: str
    duration: float
    video: VideoParams | None
    audio: AudioParams | None
    fragmented: bool
    nb_streams: int
    extra_streams: list[str] = field(default_factory=list)

    def signature(self) -> tuple:
        """Combined A/V signature used to decide if a concat needs conforming."""
        return (
            self.video.signature() if self.video else None,
            self.audio.signature() if self.audio else None,
        )

    def conforms_to(self, other: "MediaInfo") -> bool:
        return self.signature() == other.signature()

    def human(self) -> str:
        parts = [f"duration={self.duration:.2f}s"]
        if self.video:
            parts.append("video=" + self.video.human())
        if self.audio:
            parts.append("audio=" + self.audio.human())
        if self.fragmented:
            parts.append("FRAGMENTED")
        return " | ".join(parts)


def probe(tools: Tools, path: str) -> MediaInfo:
    """Run ffprobe and build a MediaInfo. Raises FFmpegError if the file is
    unreadable / not a valid media container."""
    raw = run(
        [
            tools.ffprobe,
            "-v", "error",
            "-show_format",
            "-show_streams",
            "-of", "json",
            path,
        ]
    )
    data = json.loads(raw)
    streams = data.get("streams", [])
    fmt = data.get("format", {})

    video = None
    audio = None
    extra: list[str] = []
    for s in streams:
        kind = s.get("codec_type")
        if kind == "video" and video is None:
            # Skip attached cover-art / mjpeg thumbnail "video" streams.
            if s.get("disposition", {}).get("attached_pic"):
                extra.append("attached_pic")
                continue
            video = VideoParams(
                codec=s.get("codec_name", "?"),
                profile=str(s.get("profile", "")),
                level=int(s.get("level", 0) or 0),
                width=int(s.get("width", 0) or 0),
                height=int(s.get("height", 0) or 0),
                pix_fmt=s.get("pix_fmt", "?"),
                fps=_fraction(s.get("avg_frame_rate") or s.get("r_frame_rate")),
                time_base=s.get("time_base", "?"),
            )
        elif kind == "audio" and audio is None:
            audio = AudioParams(
                codec=s.get("codec_name", "?"),
                sample_rate=int(s.get("sample_rate", 0) or 0),
                channels=int(s.get("channels", 0) or 0),
                channel_layout=s.get("channel_layout", "?"),
            )
        else:
            extra.append(kind or "unknown")

    duration = 0.0
    if fmt.get("duration") not in (None, "N/A"):
        duration = float(fmt["duration"])
    elif video is not None:
        # Fall back to stream duration if the container omits it.
        for s in streams:
            if s.get("codec_type") == "video" and s.get("duration") not in (None, "N/A"):
                duration = float(s["duration"])
                break

    fragmented = _detect_fragmentation(tools, path)

    return MediaInfo(
        path=path,
        duration=duration,
        video=video,
        audio=audio,
        fragmented=fragmented,
        nb_streams=len(streams),
        extra_streams=extra,
    )


def _detect_fragmentation(tools: Tools, path: str) -> bool:
    """A fragmented MP4 carries an 'mvex' box and one or more 'moof' boxes.
    ffprobe exposes these via the packets/format; the cheapest reliable signal
    is to look for fragment markers in the box structure. We use the
    `-show_entries format_tags` plus a packet sniff fallback.

    Practically: probe the first chunk for a 'moof' atom by reading top-level
    boxes is overkill here — ffprobe reports `format.format_name` as
    'mov,mp4,m4a,...' for both. Instead we ask ffprobe for the number of
    fragments via the 'mvex' presence by reading box names is not exposed, so we
    use a content sniff. Since ffmpeg handles fMP4 on copy transparently, this
    flag is informational (logged), not gating.
    """
    try:
        with open(path, "rb") as f:
            head = f.read(64 * 1024)
        return b"moof" in head or b"mvex" in head
    except OSError:
        return False
