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
├── tests.py          # end-to-end suite: python3 tests.py
├── recordings/       # raw lesson recordings
├── introandoutro/    # mathsintro / englishintro / reasoningintro / mainoutro
│   └── .conformed/   # cache of intros re-encoded to match the recordings
└── output/           # finished lessons
```

## The 5 stages

1. **Inspect** — probe the recording's codec, resolution, audio layout,
   rotation and video timescale; detect fragmented MP4 (remuxed via stream
   copy if found).
2. **Conform bookends** — the intro/outro must match the recording's
   parameters before they can be joined losslessly. If they don't, they are
   re-encoded once (~2 s for a 5 s clip; silent audio synthesized to match,
   pixels pre-rotated for rotated recordings) and cached in
   `introandoutro/.conformed/`, keyed on the recording's shape — every later
   run with the same kind of recording is a cache hit. The recording itself
   is never touched.
3. **Trim** — stream-copy the `[start, end]` slice. Start snaps to the
   nearest keyframe at or before the requested time. H.264/HEVC slices pass
   through an MPEG-TS intermediate (still pure stream copy) so the body
   carries its own codec parameter sets in-band — this is what makes joining
   two differently-encoded files decode correctly everywhere.
4. **Concat** — the ffmpeg concat demuxer joins intro + body + outro via
   stream copy, with exact per-part splice points so seams are frame-clean;
   display rotation is re-attached afterwards if the recording had any.
5. **Verify** — the output must match the expected duration, its timestamps
   must climb cleanly through both seams, and a few seconds around every
   seam (plus head and tail) are actually decoded to prove the file plays.
   On failure the run stops loudly and keeps its intermediate files for
   debugging; on success they are deleted.

## Testing

```bash
python3 tests.py            # full suite (~90 s): 17 input shapes + 5 rejection cases
python3 tests.py hevc       # only tests matching a substring
```

Each test generates a synthetic recording, runs the real pipeline on it, and
fully decodes the result to assert zero bitstream errors.

## Notes

- The start cut snapping to a keyframe means up to a few seconds of extra
  footage may precede your requested start (2 s for Zoom recordings). Ask
  for a slightly later start if that matters.
- New recording shape (camera change, Zoom settings change)? Nothing to do —
  the bookends are re-conformed once for the new shape, automatically.
- Output has `+faststart` (index at the front), so it streams/uploads well.
- The conform cache is safe to delete at any time; it rebuilds in seconds.
