"""Front-end: interactive UX (pipeline.md §8) plus a non-interactive flag mode
and batch mode (stretch goals). Both paths build CompileRequest objects and run
them through pipeline.compile_video.
"""

from __future__ import annotations

import argparse
import os
import sys

from . import library
from .ffmpeg import FFmpegError, Tools, find_tools
from .pipeline import CompileRequest, CompileResult, compile_video
from .probe import probe
from .timecode import TimecodeError, format_timecode, parse_timecode

BANNER = r"""
╔══════════════════════════════════════════════════════════╗
║   Video Compiler — lossless intro + body + outro builder  ║
║   stream-copy fast · the body is never re-encoded         ║
╚══════════════════════════════════════════════════════════╝
"""


def log(msg: str) -> None:
    print(msg, flush=True)


# --------------------------------------------------------------------------- #
# Interactive helpers
# --------------------------------------------------------------------------- #

def _prompt(msg: str) -> str:
    try:
        return input(msg)
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        sys.exit(130)


def _choose(items: list[str], label: str) -> str:
    print(f"\nAvailable {label}:")
    for i, item in enumerate(items, 1):
        print(f"  [{i}] {os.path.basename(item)}")
    while True:
        raw = _prompt(f"Select {label} [1-{len(items)}]: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(items):
            return items[int(raw) - 1]
        print("  Invalid selection, try again.")


def _prompt_times() -> tuple[float, float | None]:
    print(
        "\nEnter trim times as MM:SS (minutes may exceed 60; "
        "blank end = to end of file)."
    )
    print("Note: the start cut SNAPS to the nearest keyframe at or before it.")
    while True:
        start_raw = _prompt("  Start time (MM:SS): ").strip()
        try:
            start = parse_timecode(start_raw)
        except TimecodeError as exc:
            print(f"  {exc}")
            continue
        end_raw = _prompt("  End time (MM:SS, blank = EOF): ").strip()
        if not end_raw:
            return start, None
        try:
            end = parse_timecode(end_raw)
        except TimecodeError as exc:
            print(f"  {exc}")
            continue
        if end <= start:
            print("  End must be after start; try again.")
            continue
        return start, end


def run_interactive(root: str, tools: Tools) -> int:
    print(BANNER)
    output_dir = library.ensure_output_dir(root)

    recordings = library.list_recordings(root)
    if not recordings:
        print(
            f"No recordings found in {os.path.join(root, library.RECORDINGS_DIR)}/.\n"
            "Add *.mp4 files there and re-run."
        )
        return 2

    recording = _choose(recordings, "recordings")
    info = probe(tools, recording)
    print(f"\nSelected: {os.path.basename(recording)}")
    print(f"  {info.human()}")

    start, end = _prompt_times()

    # Intro: offer auto-match first, then manual choice.
    intros = library.list_intros(root)
    intro: str | None = None
    if not intros:
        print("\nWarning: no intro clips found (introandoutro/*intro*.mp4). Skipping intro.")
    else:
        auto = library.match_intro_for(root, recording)
        if auto:
            ans = _prompt(
                f"\nAuto-matched intro '{os.path.basename(auto)}' for subject "
                f"'{library.subject_of(recording)}'. Use it? [Y/n]: "
            ).strip().lower()
            intro = auto if ans in ("", "y", "yes") else _choose(intros, "intros")
        else:
            intro = _choose(intros, "intros")

    outro = library.find_outro(root)
    if outro:
        print(f"\nOutro: {library.OUTRO_NAME} (auto-selected)")
    else:
        print(f"\nWarning: {library.OUTRO_NAME} not found. Skipping outro.")

    name = _prompt(
        f"\nOutput filename [default {library.DEFAULT_OUTPUT}]: "
    ).strip()
    out_path = library.sanitize_output_name(name, output_dir)

    req = CompileRequest(
        recording=recording, start=start, end=end,
        intro=intro, outro=outro, output=out_path,
    )
    print()
    return _run_one(tools, req)


# --------------------------------------------------------------------------- #
# Non-interactive
# --------------------------------------------------------------------------- #

def _run_one(tools: Tools, req: CompileRequest) -> int:
    try:
        result = compile_video(tools, req, log=log)
    except (FFmpegError, ValueError, RuntimeError) as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1
    _print_success(result)
    return 0


def _print_success(result: CompileResult) -> None:
    snap_note = ""
    if abs(result.snapped_start - result.requested_start) > 0.05:
        snap_note = (
            f" (start snapped {format_timecode(result.requested_start)}"
            f"→{format_timecode(result.snapped_start)})"
        )
    print(
        f"\nSUCCESS  {result.output}\n"
        f"         duration {result.actual_duration:.2f}s · "
        f"{result.elapsed:.2f}s wall clock{snap_note}"
    )


def run_noninteractive(root: str, tools: Tools, args: argparse.Namespace) -> int:
    output_dir = library.ensure_output_dir(root)

    # Resolve recording: explicit path, or subject/name under recordings/.
    recording = _resolve_recording(root, args.recording)
    if recording is None:
        print(f"Recording not found: {args.recording}", file=sys.stderr)
        return 2

    try:
        start = parse_timecode(args.start) if args.start else 0.0
        end = parse_timecode(args.end) if args.end else None
    except TimecodeError as exc:
        print(f"Bad time: {exc}", file=sys.stderr)
        return 2
    if end is not None and end <= start:
        print("End must be after start.", file=sys.stderr)
        return 2

    # Intro resolution: explicit, auto-match, or none.
    if args.no_intro:
        intro = None
    elif args.intro:
        intro = _resolve_bookend(root, args.intro)
        if intro is None:
            print(f"Intro not found: {args.intro}", file=sys.stderr)
            return 2
    else:
        intro = library.match_intro_for(root, recording)
        if intro is None:
            print("Warning: no intro auto-matched; continuing without one.", file=sys.stderr)

    outro = None if args.no_outro else library.find_outro(root)

    out_path = library.sanitize_output_name(args.output, output_dir)
    req = CompileRequest(
        recording=recording, start=start, end=end,
        intro=intro, outro=outro, output=out_path,
        faststart=not args.no_faststart, keep_temp=args.keep_temp,
    )
    return _run_one(tools, req)


def run_batch(root: str, tools: Tools, args: argparse.Namespace) -> int:
    """Process every recording in one run (stretch goal). Uses the same
    start/end for all; intros are auto-matched per subject."""
    output_dir = library.ensure_output_dir(root)
    recordings = library.list_recordings(root)
    if not recordings:
        print("No recordings to batch.", file=sys.stderr)
        return 2

    try:
        start = parse_timecode(args.start) if args.start else 0.0
        end = parse_timecode(args.end) if args.end else None
    except TimecodeError as exc:
        print(f"Bad time: {exc}", file=sys.stderr)
        return 2

    outro = None if args.no_outro else library.find_outro(root)
    failures = 0
    for rec in recordings:
        subject = library.subject_of(rec)
        intro = None if args.no_intro else library.match_intro_for(root, rec)
        out_path = library.sanitize_output_name(f"{subject}_final.mp4", output_dir)
        print(f"\n=== {os.path.basename(rec)} → {os.path.basename(out_path)} ===")
        req = CompileRequest(
            recording=rec, start=start, end=end,
            intro=intro, outro=outro, output=out_path,
            faststart=not args.no_faststart, keep_temp=args.keep_temp,
        )
        if _run_one(tools, req) != 0:
            failures += 1
    print(f"\nBatch complete: {len(recordings) - failures}/{len(recordings)} succeeded.")
    return 1 if failures else 0


def _resolve_recording(root: str, value: str) -> str | None:
    if os.path.isfile(value):
        return value
    # Treat as subject/name under recordings/.
    cand = os.path.join(root, library.RECORDINGS_DIR, value)
    if os.path.isfile(cand):
        return cand
    if not value.lower().endswith(".mp4"):
        cand_mp4 = cand + ".mp4"
        if os.path.isfile(cand_mp4):
            return cand_mp4
    return None


def _resolve_bookend(root: str, value: str) -> str | None:
    if os.path.isfile(value):
        return value
    cand = os.path.join(root, library.BOOKENDS_DIR, value)
    if os.path.isfile(cand):
        return cand
    if not value.lower().endswith(".mp4"):
        cand_mp4 = cand + ".mp4"
        if os.path.isfile(cand_mp4):
            return cand_mp4
    return None


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="vcompiler",
        description="Lossless intro + trimmed body + outro MP4 builder (stream copy).",
    )
    p.add_argument("--root", default=".", help="project root (default: cwd)")
    p.add_argument("-r", "--recording", help="recording path or subject name (non-interactive)")
    p.add_argument("-s", "--start", help="start time MM:SS (default 00:00)")
    p.add_argument("-e", "--end", help="end time MM:SS (default EOF)")
    p.add_argument("-i", "--intro", help="intro path/name (default: auto-match by subject)")
    p.add_argument("-o", "--output", help=f"output filename (default {library.DEFAULT_OUTPUT})")
    p.add_argument("--no-intro", action="store_true", help="omit the intro")
    p.add_argument("--no-outro", action="store_true", help="omit the outro")
    p.add_argument("--no-faststart", action="store_true", help="do not relocate moov to front")
    p.add_argument("--keep-temp", action="store_true", help="keep intermediate temp files")
    p.add_argument("--batch", action="store_true", help="process every recording in one run")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = os.path.abspath(args.root)

    try:
        tools = find_tools()
    except FFmpegError as exc:
        print(exc.stderr, file=sys.stderr)
        return 3

    if args.batch:
        return run_batch(root, tools, args)
    if args.recording:
        return run_noninteractive(root, tools, args)
    return run_interactive(root, tools)
