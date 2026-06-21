"""Stage 5 — verify the output (pipeline.md §6.7, §7).

A run that exits 0 but yields an unplayable file is a failure. We assert:
  * the file exists and probes cleanly,
  * the duration is within tolerance of intro + trimmed_body + outro,
  * it carries the expected video (and audio) streams,
  * ffmpeg can decode it end-to-end without errors.
"""

from __future__ import annotations

from dataclasses import dataclass

from .ffmpeg import FFmpegError, Tools, run
from .probe import MediaInfo, probe


@dataclass
class VerifyResult:
    ok: bool
    actual_duration: float
    expected_duration: float
    messages: list[str]


def verify_output(
    tools: Tools,
    out_path: str,
    expected_duration: float,
    reference: MediaInfo,
    *,
    tolerance: float = 1.5,
) -> VerifyResult:
    messages: list[str] = []
    ok = True

    try:
        info = probe(tools, out_path)
    except FFmpegError as exc:
        return VerifyResult(False, 0.0, expected_duration, [f"output does not probe: {exc}"])

    if info.video is None:
        ok = False
        messages.append("output has no video stream")

    if reference.audio is not None and info.audio is None:
        ok = False
        messages.append("expected an audio stream but output has none")

    delta = abs(info.duration - expected_duration)
    # Allow the larger of the absolute tolerance or 2% of expected duration —
    # keyframe-snapped trims legitimately shift the body length a little.
    allowed = max(tolerance, expected_duration * 0.02)
    if delta > allowed:
        ok = False
        messages.append(
            f"duration {info.duration:.2f}s differs from expected "
            f"{expected_duration:.2f}s by {delta:.2f}s (allowed {allowed:.2f}s)"
        )
    else:
        messages.append(
            f"duration {info.duration:.2f}s ≈ expected {expected_duration:.2f}s "
            f"(Δ{delta:.2f}s)"
        )

    # Full decode pass: catches truncated/corrupt output that a header probe
    # alone would miss.
    try:
        run([
            tools.ffmpeg, "-v", "error", "-xerror",
            "-i", out_path, "-f", "null", "-",
        ], capture=False)
        messages.append("full decode pass: no errors")
    except FFmpegError as exc:
        ok = False
        messages.append(f"decode pass reported errors: {exc.stderr[:300]}")

    return VerifyResult(ok, info.duration, expected_duration, messages)
