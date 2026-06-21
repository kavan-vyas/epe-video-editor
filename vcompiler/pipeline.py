"""Orchestrator — wires Stages 1-5 together (pipeline.md §7).

This module is UI-agnostic: it takes a fully-resolved CompileRequest and runs
the pipeline, emitting progress through a `log` callback. The interactive and
non-interactive front-ends in cli.py both funnel into `compile_video`.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field

from . import bookends, concat, trim, verify
from .ffmpeg import Tools
from .probe import MediaInfo, probe
from .timecode import format_timecode


@dataclass
class CompileRequest:
    recording: str                 # path to raw recording
    start: float                   # requested start (seconds)
    end: float | None              # requested end (seconds) or None = EOF
    intro: str | None              # path to intro bookend or None
    outro: str | None              # path to outro bookend or None
    output: str                    # absolute output path
    faststart: bool = True
    keep_temp: bool = False


@dataclass
class CompileResult:
    output: str
    elapsed: float
    expected_duration: float
    actual_duration: float
    snapped_start: float
    requested_start: float
    verify: verify.VerifyResult
    segments: list[str] = field(default_factory=list)


def _noop(_msg: str) -> None:
    pass


def compile_video(tools: Tools, req: CompileRequest, log=_noop) -> CompileResult:
    started = time.monotonic()
    workdir = tempfile.mkdtemp(prefix="vcompiler_")
    try:
        # --- Stage 1: Select & inspect -------------------------------------
        log("Stage 1 — inspecting recording")
        rec = probe(tools, req.recording)
        if rec.video is None:
            raise ValueError(f"recording {req.recording!r} has no video stream")
        log(f"  {rec.human()}")
        if rec.fragmented:
            log("  note: fragmented MP4 detected — ffmpeg handles this on copy")

        # --- Stage 2: Conform bookends -------------------------------------
        log("Stage 2 — conforming bookends to recording")
        intro_seg = None
        outro_seg = None
        if req.intro:
            intro_seg = bookends.ensure_conformed(
                tools, req.intro, rec, workdir, "intro", log
            )
        else:
            log("  intro: none selected (skipping, warning)")
        if req.outro:
            outro_seg = bookends.ensure_conformed(
                tools, req.outro, rec, workdir, "outro", log
            )
        else:
            log("  outro: none found (skipping, warning)")

        # --- Stage 3: Trim the body (stream copy) --------------------------
        log("Stage 3 — trimming body (stream copy, no re-encode)")
        body_path = os.path.join(workdir, "body.mp4")
        snapped_start, eff_end = trim.trim_body(
            tools, rec, body_path, req.start, req.end
        )
        if abs(snapped_start - req.start) > 0.05:
            log(
                f"  start {format_timecode(req.start)} snapped back to keyframe "
                f"{format_timecode(snapped_start)} (lossless cut)"
            )
        else:
            log(f"  start at keyframe {format_timecode(snapped_start)}")
        log(f"  body range {format_timecode(snapped_start)} → {format_timecode(eff_end)}")
        body_info = probe(tools, body_path)
        log(f"  trimmed body duration {body_info.duration:.2f}s")

        # --- Stage 4: Concatenate ------------------------------------------
        log("Stage 4 — concatenating (concat demuxer, stream copy)")
        segments: list[str] = []
        if intro_seg:
            segments.append(intro_seg)
        segments.append(body_path)
        if outro_seg:
            segments.append(outro_seg)
        log("  order: " + " + ".join(os.path.basename(s) for s in segments))
        concat.concat_segments(
            tools, segments, req.output, workdir, faststart=req.faststart
        )

        # Expected duration for verification.
        intro_d = probe(tools, intro_seg).duration if intro_seg else 0.0
        outro_d = probe(tools, outro_seg).duration if outro_seg else 0.0
        expected = intro_d + body_info.duration + outro_d

        # --- Stage 5: Verify & clean up ------------------------------------
        log("Stage 5 — verifying output")
        vresult = verify.verify_output(tools, req.output, expected, rec)
        for msg in vresult.messages:
            log(f"  {msg}")
        if not vresult.ok:
            raise RuntimeError(
                "output verification failed:\n  - "
                + "\n  - ".join(vresult.messages)
            )

        elapsed = time.monotonic() - started
        return CompileResult(
            output=req.output,
            elapsed=elapsed,
            expected_duration=expected,
            actual_duration=vresult.actual_duration,
            snapped_start=snapped_start,
            requested_start=req.start,
            verify=vresult,
            segments=segments,
        )
    finally:
        if req.keep_temp:
            log(f"  (kept temp dir: {workdir})")
        else:
            shutil.rmtree(workdir, ignore_errors=True)
