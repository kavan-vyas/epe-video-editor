"""Stage 0 / Stage 2 — bookend preparation and conforming (pipeline.md §6.2-6.3, §7).

A bookend (intro/outro) MUST share the recording's full A/V signature or the
stream-copy concat will fail or glitch. We:

  * compare the bookend's probed signature to the recording (Stage 2),
  * if it already matches → use as-is (pure copy path, zero encoding),
  * if not → normalise it to the recording with a one-time ~5 s encode,
  * and (stretch goal) synthesise a missing intro/outro from a still image.

Only the tiny bookends are ever encoded. The hour-long body is never touched.
"""

from __future__ import annotations

import os

from .ffmpeg import Tools, run
from .probe import MediaInfo, probe

DEFAULT_BOOKEND_SECONDS = 5.0


def _audio_encode_args(target: MediaInfo) -> list[str]:
    """ffmpeg args to produce an audio track matching the recording. If the
    recording has no audio we emit none (and the recording has none to mismatch).
    """
    if target.audio is None:
        return ["-an"]
    a = target.audio
    layout = a.channel_layout if a.channel_layout not in ("", "?") else (
        "stereo" if a.channels >= 2 else "mono"
    )
    return [
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", str(a.sample_rate or 48000),
        "-ac", str(a.channels or 2),
        "-channel_layout", layout,
    ]


def _video_encode_args(target: MediaInfo) -> list[str]:
    """ffmpeg args to encode video matching the recording's signature."""
    v = target.video
    assert v is not None
    args = [
        "-c:v", "libx264" if v.codec in ("h264", "libx264") else "libx264",
        "-pix_fmt", v.pix_fmt if v.pix_fmt not in ("", "?") else "yuv420p",
        "-r", f"{v.fps:.5f}" if v.fps else "30",
        "-s", f"{v.width}x{v.height}",
        # Make every frame a keyframe-friendly short GOP so the clip starts on a
        # keyframe (§6.6) and concatenation is clean.
        "-g", "30",
        "-profile:v", _x264_profile(v.profile),
        "-preset", "veryfast",
    ]
    return args


def _x264_profile(profile: str) -> str:
    p = (profile or "").lower()
    if "high" in p:
        return "high"
    if "main" in p:
        return "main"
    if "baseline" in p or "constrained" in p:
        return "baseline"
    return "high"


def conform_bookend(
    tools: Tools,
    bookend: MediaInfo,
    target: MediaInfo,
    out_path: str,
) -> str:
    """Re-encode `bookend` to `target`'s signature. One-time short encode."""
    silent_audio = target.audio is not None and bookend.audio is None

    args = [tools.ffmpeg, "-y", "-loglevel", "error"]
    if silent_audio:
        # Bookend lacks audio but the recording has it → add a silent track so
        # the stream layout matches for concat.
        a = target.audio
        args += [
            "-f", "lavfi",
            "-t", f"{max(bookend.duration, 0.1):.3f}",
            "-i", f"anullsrc=channel_layout={a.channel_layout or 'stereo'}:sample_rate={a.sample_rate or 48000}",
        ]
    args += ["-i", bookend.path]
    args += _video_encode_args(target)
    args += _audio_encode_args(target)
    if silent_audio:
        args += ["-map", "1:v:0", "-map", "0:a:0", "-shortest"]
    else:
        args += ["-map", "0:v:0"]
        if target.audio is not None:
            args += ["-map", "0:a:0?"]
    args += ["-movflags", "+faststart", out_path]
    run(args, capture=False)
    return out_path


def generate_from_still(
    tools: Tools,
    image_path: str,
    target: MediaInfo,
    out_path: str,
    seconds: float = DEFAULT_BOOKEND_SECONDS,
) -> str:
    """Stretch goal: build a bookend MP4 from a static image, encoded straight
    to the recording's signature (with a silent audio track if needed)."""
    v = target.video
    assert v is not None
    args = [
        tools.ffmpeg, "-y", "-loglevel", "error",
        "-loop", "1", "-t", f"{seconds:.3f}", "-i", image_path,
    ]
    if target.audio is not None:
        a = target.audio
        args += [
            "-f", "lavfi", "-t", f"{seconds:.3f}",
            "-i", f"anullsrc=channel_layout={a.channel_layout or 'stereo'}:sample_rate={a.sample_rate or 48000}",
        ]
    # Scale+pad the still to the exact target resolution, preserving aspect.
    vf = (
        f"scale={v.width}:{v.height}:force_original_aspect_ratio=decrease,"
        f"pad={v.width}:{v.height}:(ow-iw)/2:(oh-ih)/2,"
        f"format={v.pix_fmt if v.pix_fmt not in ('', '?') else 'yuv420p'}"
    )
    args += ["-vf", vf]
    args += _video_encode_args(target)
    if target.audio is not None:
        args += _audio_encode_args(target)
        args += ["-map", "0:v:0", "-map", "1:a:0", "-shortest"]
    else:
        args += ["-an", "-map", "0:v:0"]
    args += ["-movflags", "+faststart", out_path]
    run(args, capture=False)
    return out_path


def ensure_conformed(
    tools: Tools,
    bookend_path: str,
    target: MediaInfo,
    workdir: str,
    label: str,
    log,
) -> str:
    """Return a path to a bookend that matches `target`. Uses the original
    untouched (pure copy path) when it already conforms; otherwise writes a
    conformed copy into `workdir`.
    """
    info = probe(tools, bookend_path)
    if info.video is None:
        raise ValueError(f"{label} {bookend_path!r} has no video stream")

    if info.conforms_to(target):
        log(f"  {label}: already matches house standard → using as-is (no encode)")
        return bookend_path

    log(f"  {label}: parameters differ → conforming (one-time ~{info.duration:.0f}s encode)")
    log(f"      bookend: {info.human()}")
    log(f"      target : {target.human()}")
    out_path = os.path.join(workdir, f"conformed_{label}.mp4")
    return conform_bookend(tools, info, target, out_path)
