"""Stage 4 — concatenate with the concat demuxer + stream copy (pipeline.md §6.5, §7).

We use the concat *demuxer* (`-f concat`), not the concat protocol, because for
MP4 it handles per-segment timestamp continuity and AAC priming far better.
"""

from __future__ import annotations

import os

from .ffmpeg import Tools, run


def _concat_list_file(segments: list[str], list_path: str) -> None:
    """Write a concat-demuxer list file with properly escaped absolute paths."""
    lines = []
    for seg in segments:
        abspath = os.path.abspath(seg)
        # The concat demuxer treats ' as a quote; escape per its grammar.
        escaped = abspath.replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    with open(list_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def concat_segments(
    tools: Tools,
    segments: list[str],
    out_path: str,
    workdir: str,
    faststart: bool = True,
) -> str:
    """Join `segments` in order via stream copy into `out_path`."""
    if not segments:
        raise ValueError("nothing to concatenate")

    list_path = os.path.join(workdir, "concat_list.txt")
    _concat_list_file(segments, list_path)

    movflags = "+faststart" if faststart else "+frag_keyframe"
    args = [
        tools.ffmpeg,
        "-y",
        "-loglevel", "error",
        "-f", "concat",
        "-safe", "0",
        "-i", list_path,
        "-map", "0",
        "-c", "copy",
        # Rebuild timestamps from the demuxer to smooth over per-segment PTS.
        "-fflags", "+genpts",
        "-avoid_negative_ts", "make_zero",
        "-movflags", movflags,
        out_path,
    ]
    run(args, capture=False)
    return out_path
