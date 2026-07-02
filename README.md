# Lossless Lesson Video Assembler

Trims a weekly lesson recording and wraps it with a subject intro and a shared
outro — **without re-encoding the recording**. A ~1-hour lesson is assembled
in **under 5 seconds**, because only container metadata is rewritten; the
compressed video frames are copied as-is.

## Speed

| Method | Time for a 1-hour lesson |
|---|---|
| Camtasia (manual) | ~90 min |
| Old MoviePy script (full re-encode) | ~7–15 min |
| This pipeline (stream copy) | **~4 s** |

## Why it's fast

A video file is a container: an index pointing into a blob of compressed
frames. Trimming and joining only need a new index — `ffmpeg -c copy` writes
one without ever decoding the video. The single unavoidable constraint: a
lossless cut can only *start* on a keyframe (Zoom records one every 2 s, so
cuts land within 2 s of what you ask for; the end cut is exact).

## Usage

```bash
# interactive: pick recording, intro, times, output name
python3 main.py

# direct
python3 main.py long.mp4 maths 1:30 55:00
python3 main.py long.mp4 english 2:00 61:30 -o english_week12.mp4

# any path works, not just files inside recordings/
python3 main.py ~/Downloads/lesson.mkv reasoning 90 3300
```

Times are `MM:SS` (minutes may exceed 60), `HH:MM:SS`, or plain seconds.
The intro argument matches by substring (`maths` finds `mathsintro.mp4`) or
can be a path. `mainoutro.mp4` is always appended. Output lands in `output/`
(default `final.mp4`).

## What it accepts

Tested against all of these input shapes (see `tests.py`):

- H.264, HEVC 8-bit and 10-bit video; any resolution, framerate, up to 4K60
- MP4 / M4V / MOV / MKV containers; fragmented MP4 (auto-remuxed)
- AAC, MP3, mono/stereo, any sample rate — or no audio at all
- Rotated phone recordings (90/180/270° display rotation is preserved,
  intros are rotated to match)
- Multiple audio tracks (the first is kept), data/subtitle tracks (dropped)
- Screen recordings with a single keyframe (cut falls back to the start,
  with a warning about the extra footage)
- Awkward filenames (spaces, apostrophes)

Bad input (missing files, reversed times, times past the end) fails fast
with a one-line error.

## Requirements

- Python 3.9+ (standard library only)
- ffmpeg + ffprobe on PATH (`brew install ffmpeg`)

## Folder layout

```
epe/
├── main.py

