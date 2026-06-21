#!/usr/bin/env python3
"""
make_long.py — generate `long.mp4`, a test recording that counts up in seconds.

There is no real `maths.mp4` / `english.mp4` in this repo to copy, so this builds
a synthetic stand-in: a video whose screen shows the elapsed whole-second count
(0, 1, 2, ... ) plus an HH:MM:SS readout. Defaults to 96 minutes = 5760 seconds.

This Homebrew ffmpeg has no `drawtext` filter (built without libfreetype), so the
frames are drawn with Pillow and piped to ffmpeg as raw RGB. One distinct frame
per second is rendered and held for `--fps` frames.

Encode settings: H.264 / yuv420p + a silent stereo AAC track + a fixed 2-second
keyframe interval — a faithful, concat-friendly input for the stream-copy pipeline
(see pipeline.md). Trim it and read the on-screen numbers to confirm exactly which
seconds survived.

Usage:
    python make_long.py                 # 96 min -> long.mp4
    python make_long.py --minutes 5     # quick check
"""

import argparse
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def find_font() -> str:
    for path in FONT_CANDIDATES:
        if os.path.isfile(path):
            return path
    sys.exit("No usable .ttf font found. Edit FONT_CANDIDATES with a valid path.")


def require_ffmpeg() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            sys.exit(f"'{tool}' not found on PATH. Install ffmpeg (brew install ffmpeg).")


def centered(draw, text, font, width, cy):
    """Draw `text` horizontally centered, vertically centered on baseline `cy`."""
    l, t, r, b = draw.textbbox((0, 0), text, font=font)
    x = (width - (r - l)) / 2 - l
    y = cy - (b - t) / 2 - t
    return x, y


def render_frame(second: int, width: int, height: int, big, small) -> bytes:
    img = Image.new("RGB", (width, height), (0, 0, 0))
    d = ImageDraw.Draw(img)

    # Big live seconds counter.
    x, y = centered(d, str(second), big, width, height * 0.42)
    d.text((x, y), str(second), fill=(255, 255, 255), font=big)

    # HH:MM:SS readout below it.
    h, m, s = second // 3600, (second % 3600) // 60, second % 60
    tc = f"{h:02d}:{m:02d}:{s:02d}"
    x, y = centered(d, tc, small, width, height * 0.66)
    d.text((x, y), tc, fill=(187, 187, 187), font=small)

    return img.tobytes()


def main() -> None:
    p = argparse.ArgumentParser(description="Generate a seconds-counter test video.")
    p.add_argument("--minutes", type=float, default=96.0, help="length in minutes (default 96)")
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p.add_argument("--fps", type=int, default=5, help="output frame rate (default 5)")
    p.add_argument("--out", default="long.mp4")
    args = p.parse_args()

    require_ffmpeg()
    font_path = find_font()
    total_seconds = round(args.minutes * 60)
    gop = args.fps * 2  # keyframe every 2 seconds

    big = ImageFont.truetype(font_path, size=int(args.height * 0.36))
    small = ImageFont.truetype(font_path, size=int(args.height * 0.13))

    print(f"Generating {args.out}: {args.minutes} min ({total_seconds}s), "
          f"{args.width}x{args.height} @ {args.fps}fps, counting in seconds...")

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{args.width}x{args.height}", "-r", str(args.fps), "-i", "-",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-map", "0:v", "-map", "1:a",
        "-t", str(total_seconds),
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-g", str(gop), "-keyint_min", str(gop), "-sc_threshold", "0",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        args.out,
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for second in range(total_seconds):
            frame = render_frame(second, args.width, args.height, big, small)
            for _ in range(args.fps):  # hold this second for `fps` frames
                proc.stdin.write(frame)
            if second % 600 == 0:
                pct = 100 * second / total_seconds
                print(f"  rendered {second}/{total_seconds}s ({pct:.0f}%)")
        proc.stdin.close()
    except BrokenPipeError:
        pass
    rc = proc.wait()
    if rc != 0:
        sys.exit(f"ffmpeg failed (exit {rc}).")

    dur = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", args.out],
        capture_output=True, text=True,
    ).stdout.strip()
    size_mb = os.path.getsize(args.out) / (1024 * 1024)
    print(f"\nWrote {args.out}: duration={float(dur):.1f}s  size={size_mb:.1f} MB")


if __name__ == "__main__":
    main()
