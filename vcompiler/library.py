"""Filesystem layout helpers (pipeline.md §5): discovering recordings, intros,
the shared outro, subject auto-matching, and output-name sanitisation.
"""

from __future__ import annotations

import os
import re

RECORDINGS_DIR = "recordings"
BOOKENDS_DIR = "introandoutro"
OUTPUT_DIR = "output"
OUTRO_NAME = "mainoutro.mp4"
DEFAULT_OUTPUT = "final.mp4"


def list_recordings(root: str) -> list[str]:
    d = os.path.join(root, RECORDINGS_DIR)
    if not os.path.isdir(d):
        return []
    return sorted(
        os.path.join(d, f)
        for f in os.listdir(d)
        if f.lower().endswith(".mp4")
    )


def list_intros(root: str) -> list[str]:
    """Intros are bookend clips whose filename contains 'intro' (pipeline.md §5)."""
    d = os.path.join(root, BOOKENDS_DIR)
    if not os.path.isdir(d):
        return []
    return sorted(
        os.path.join(d, f)
        for f in os.listdir(d)
        if f.lower().endswith(".mp4") and "intro" in f.lower()
    )


def find_outro(root: str) -> str | None:
    p = os.path.join(root, BOOKENDS_DIR, OUTRO_NAME)
    return p if os.path.isfile(p) else None


def subject_of(recording_path: str) -> str:
    """'recordings/maths.mp4' → 'maths' (stretch goal: subject auto-match)."""
    return os.path.splitext(os.path.basename(recording_path))[0].lower()


def match_intro_for(root: str, recording_path: str) -> str | None:
    """Auto-pick the intro for a recording by subject (maths.mp4 → *maths*intro*)."""
    subject = subject_of(recording_path)
    intros = list_intros(root)
    # Prefer an intro whose name starts with the subject, else just contains it.
    starts = [i for i in intros if os.path.basename(i).lower().startswith(subject)]
    if starts:
        return starts[0]
    contains = [i for i in intros if subject in os.path.basename(i).lower()]
    return contains[0] if contains else None


def sanitize_output_name(name: str | None, output_dir: str) -> str:
    """Reduce to a safe basename inside output_dir; ensure .mp4 (pipeline.md §7.4)."""
    if not name or not name.strip():
        name = DEFAULT_OUTPUT
    # Strip any directory components — no path traversal.
    base = os.path.basename(name.strip())
    base = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", base)
    if not base or base in (".", ".."):
        base = DEFAULT_OUTPUT
    if not base.lower().endswith(".mp4"):
        base += ".mp4"
    return os.path.join(output_dir, base)


def ensure_output_dir(root: str) -> str:
    d = os.path.join(root, OUTPUT_DIR)
    os.makedirs(d, exist_ok=True)
    return d
