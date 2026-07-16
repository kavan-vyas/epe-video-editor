# fabld — background & technical details

## The problem

Every week a lesson is recorded (Zoom, screen recorder, phone). Before it can
be shared, the same three edits are needed every single time:

1. cut off the dead time at the start and end of the recording,
2. put the subject's intro clip in front,
3. put the shared outro clip at the end.

Doing this in a normal video editor (Camtasia, iMovie, …) means importing,
dragging clips around, and then **re-exporting the whole video** — the computer
re-compresses every frame. For a one-hour lesson that takes an hour and a half
of clicking and waiting, and the re-compression slightly damages the picture.

| Method | Time for a 1-hour lesson |
|---|---|
| Camtasia (manual) | ~90 min |
| Old MoviePy script (full re-encode) | ~7–15 min |
| fabld (stream copy) | **~4 s** |

## Why fabld is fast

A video file is a container: an index pointing into a blob of compressed
frames. Trimming and joining only need a *new index* — `ffmpeg -c copy` writes
one without ever decoding the video. So fabld's output is byte-identical
quality and assembles in seconds of pure file I/O.

The single unavoidable constraint: a lossless cut can only **start** on a
keyframe (Zoom records one every 2 s, so cuts land within 2 s of what you ask
for; the end cut is exact). The web UI shows keyframes as ticks on the
scrubber and marks the actual cut point in orange.

## Pipeline (5 stages)

1. **inspect** — probe the recording, detect fragmented MP4, read codec params
2. **conform** — make intro/outro match the recording's codec/resolution/audio
   (one-time encode per recording "shape", cached in `introandoutro/.conformed/`)
3. **trim** — stream-copy the [start, end] slice; start snaps to a keyframe
4. **concat** — concat demuxer joins intro + body + outro via stream copy
5. **verify** — duration, seam-timestamp and seam-decode checks, then cleanup

## Command line usage

The web UI drives `main.py`, which also works standalone:

```bash
# interactive: pick recording, intro, times, output name
python3 main.py

# direct
python3 main.py long.mp4 maths 1:30 55:00
python3 main.py long.mp4 english 2:00 61:30 -o english_week12.mp4

# any path works, not just files inside recordings/
python3 main.py ~/Downloads/lesson.mkv reasoning 90 3300
```

(On Windows use `py -3 main.py …` or `python main.py …`.)

Times are `MM:SS` (minutes may exceed 60), `HH:MM:SS`, or plain seconds. The
intro argument matches by substring (`maths` finds `mathsintro.mp4`) or can be
a path. `mainoutro.mp4` is always appended. Output lands in `output/`
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

Bad input (missing files, reversed times, times past the end) fails fast with
a one-line error.

## The web UI (`server.py` + `web/`)

- Python standard library only — no packages to install.
- Serves the page, streams video with HTTP Range support (so the player can
  seek), builds a cached filmstrip + keyframe list for the scrubber
  (`.fabld-cache/`), and runs `main.py` as a background job while streaming
  its five-stage progress log to the browser.
- Listens on 127.0.0.1 only (your machine, not the network).

## Requirements

- Python 3.9+ (standard library only — the web UI too)
- ffmpeg + ffprobe on PATH
  (`brew install ffmpeg` on macOS, `winget install ffmpeg` on Windows)

Run the test suite with `python3 tests.py`.
