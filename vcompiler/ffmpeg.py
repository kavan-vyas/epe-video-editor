"""Thin wrappers around the ffmpeg/ffprobe binaries.

Everything that shells out lives here so the rest of the package never builds a
subprocess command by hand. We deliberately keep ffmpeg quiet (`-loglevel error`)
and only surface stderr when a call actually fails.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


class FFmpegError(RuntimeError):
    """A ffmpeg/ffprobe invocation exited non-zero."""

    def __init__(self, args: list[str], returncode: int, stderr: str):
        self.args = args
        self.returncode = returncode
        self.stderr = stderr.strip()
        super().__init__(
            f"command failed (exit {returncode}): {' '.join(args)}\n{self.stderr}"
        )


@dataclass(frozen=True)
class Tools:
    """Resolved absolute paths to the ffmpeg and ffprobe binaries."""

    ffmpeg: str
    ffprobe: str


def find_tools() -> Tools:
    """Locate ffmpeg and ffprobe on PATH, or fail loudly with install hints."""
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    missing = [n for n, p in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe)) if not p]
    if missing:
        raise FFmpegError(
            args=missing,
            returncode=127,
            stderr=(
                f"Required tool(s) not found on PATH: {', '.join(missing)}.\n"
                "Install ffmpeg (which bundles ffprobe):\n"
                "  macOS:   brew install ffmpeg\n"
                "  Debian:  sudo apt install ffmpeg\n"
                "  Windows: winget install Gyan.FFmpeg"
            ),
        )
    return Tools(ffmpeg=ffmpeg, ffprobe=ffprobe)


def run(args: list[str], *, capture: bool = True) -> str:
    """Run a command, raising FFmpegError on failure. Returns stdout text."""
    proc = subprocess.run(
        args,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        raise FFmpegError(args, proc.returncode, proc.stderr or "")
    return proc.stdout or ""
