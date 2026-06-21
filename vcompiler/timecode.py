"""MM:SS timecode parsing (minutes may exceed 60, per pipeline.md §7 Stage 3)."""

from __future__ import annotations

import re

_MMSS = re.compile(r"^\s*(\d+):([0-5]?\d)\s*$")
_HHMMSS = re.compile(r"^\s*(\d+):([0-5]?\d):([0-5]?\d)\s*$")


class TimecodeError(ValueError):
    pass


def parse_timecode(text: str) -> float:
    """Parse 'MM:SS' (minutes may exceed 60) or 'HH:MM:SS' into seconds.

    Also accepts a bare number of seconds for convenience in scripted use.
    """
    text = text.strip()
    m = _MMSS.match(text)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    m = _HHMMSS.match(text)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    # Bare seconds (int or float) — handy for --start 12.5 in scripts.
    try:
        return float(text)
    except ValueError as exc:
        raise TimecodeError(
            f"invalid time {text!r}; expected MM:SS (e.g. 03:45) or HH:MM:SS"
        ) from exc


def format_timecode(seconds: float) -> str:
    """Render seconds as H:MM:SS.mmm for human-readable logs."""
    if seconds < 0:
        seconds = 0.0
    total_ms = round(seconds * 1000)
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h}:{m:02d}:{s:02d}.{ms:03d}"
