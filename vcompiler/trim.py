"""Stage 3 — trim the body losslessly via stream copy (pipeline.md §6.1, §7).

The body is the hour of footage we MUST NOT decode. We resolve the requested
start down to the nearest keyframe at or before it (lossless cuts can only begin
on a keyframe) and then `-c copy` the [start, end] byte range.
"""

from __future__ import annotations

import json

from .ffmpeg import Tools, run
from .probe import MediaInfo


def nearest_keyframe_at_or_before(tools: Tools, path: str, start: float) -> float:
    """Return the PTS (seconds) of the last video keyframe at or before `start`.

    We read only keyframe packets up to `start` (+ a small lookahead so a
    keyframe sitting essentially on the boundary is included), which is cheap —
    ffprobe reads the index, not the frames.
    """
    if start <= 0:
        return 0.0

    raw = run(
        [
            tools.ffprobe,
            "-v", "error",
            "-select_streams", "v:0",
            "-skip_frame", "nokey",
            "-show_entries", "frame=pts_time,pkt_pts_time,best_effort_timestamp_time",
            "-read_intervals", f"%{start + 0.5}",
            "-of", "json",
            path,
        ]
    )
    frames = json.loads(raw).get("frames", [])
    keyframe_times: list[float] = []
    for fr in frames:
        for key in ("pts_time", "best_effort_timestamp_time", "pkt_pts_time"):
            val = fr.get(key)
            if val not in (None, "N/A"):
                try:
                    keyframe_times.append(float(val))
                except ValueError:
                    pass
                break

    candidates = [t for t in keyframe_times if t <= start + 1e-3]
    if not candidates:
        # No keyframe before the request (e.g. start inside the first GOP) →
        # the only lossless option is to begin at 0.
        return 0.0
    return max(candidates)


def trim_body(
    tools: Tools,
    info: MediaInfo,
    out_path: str,
    start: float,
    end: float | None,
) -> tuple[float, float]:
    """Stream-copy [start_keyframe, end] to `out_path`.

    Returns (snapped_start, effective_end). `end` is clamped to EOF; None means
    'to the end of the file'. Raises ValueError if the range is empty.
    """
    duration = info.duration
    if end is None:
        end = duration
    if duration > 0:
        end = min(end, duration)

    snapped_start = nearest_keyframe_at_or_before(tools, info.path, start)

    if end <= snapped_start:
        raise ValueError(
            f"empty trim range: end ({end:.2f}s) is not after the keyframe-"
            f"snapped start ({snapped_start:.2f}s). Pick an end after the start."
        )

    args = [
        tools.ffmpeg,
        "-y",
        "-loglevel", "error",
        # `-ss` before `-i` seeks by the index to the keyframe — fast and exact
        # because we already snapped to a real keyframe time.
        "-ss", f"{snapped_start:.6f}",
    ]
    # Only add `-to` if we actually have a finite end short of EOF.
    if not (duration > 0 and abs(end - duration) < 1e-3):
        args += ["-to", f"{end:.6f}"]
    args += [
        "-i", info.path,
        "-map", "0",
        "-c", "copy",
        # Keep timestamps continuous from zero so the later concat joins cleanly.
        "-avoid_negative_ts", "make_zero",
        "-movflags", "+faststart",
        out_path,
    ]
    run(args, capture=False)
    return snapped_start, end
