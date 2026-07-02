# Walkthrough — how the lossless assembler works

This document explains what `main.py` actually does, why each step exists,
and how to debug it when something goes wrong.

## The core idea

An MP4 file has two parts:

```
┌──────────────────────────────────────────────┐
│ moov  — the index: "frame 1 is at byte 4096, │
│         lasts 200ms; frame 2 is at ..."      │
├──────────────────────────────────────────────┤
│ mdat  — the actual compressed frames         │
└──────────────────────────────────────────────┘
```

Editing tools like Camtasia decode every frame to pixels, edit, then
re-encode — for a 1-hour video that's ~100,000 frames through a codec, which
is why it takes minutes to hours. But trimming and joining don't need to
touch pixels at all: they only need a **new index** over the existing
compressed bytes. That's what `ffmpeg -c copy` (stream copy) does. The work
becomes pure file I/O, so a 1-hour lesson assembles in seconds with the CPU
nearly idle.

Two constraints come with this:

1. **Cuts can only start on a keyframe.** Most frames are stored as
   differences from previous frames; only keyframes are self-contained. A
   trim that starts mid-group would reference frames that no longer exist.
   So the start cut snaps to the nearest keyframe at or before the requested
   time (Zoom writes one every 2 s). The end cut needs no snapping.
2. **Joined parts must be codec-identical.** A decoder can't switch
   resolution/codec/audio-layout mid-track. The intro and outro must be made
   to match the recording exactly — never the other way around, because the
   bookends are 5 s and the recording is an hour.

## Data flow

```
recording.mp4 (any shape) ──[1 inspect]──> spec {codec, size, fps, audio,
                                                 rotation, timescale}
                                              │
mathsintro.mp4 ──[2 conform: one-time encode, cached]──> intro'  (matches spec)
mainoutro.mp4  ──[2 conform: one-time encode, cached]──> outro'  (matches spec)
                                              │
recording ──[3 trim: stream copy]──> body.mp4 (the [start,end] slice)
                                              │
intro' + body + outro' ──[4 concat: stream copy]──> output/final.mp4
                                              │
                       [5 verify: duration + timestamps + seam decode]
```

## Stage 1 — inspect

`ffprobe` reads the recording's parameters into a `spec` dict: video codec,
width/height, pixel format, framerate, video track timescale, rotation
metadata, audio codec/sample-rate/channels, duration.

Two special cases handled here:

- **Fragmented MP4** (`moof` boxes instead of one `moov` — what you get if a
  recorder crashes or streams). Detected by walking the file's top-level
  boxes directly (16 lines of struct-unpacking in `is_fragmented_mp4`);
  remuxed to a plain MP4 via stream copy first, because seeking in fMP4 is
  unreliable.
- **Rotation** (phone recordings): stored sideways with a "rotate on
  display" flag. The flag lives in `side_data_list` and matters in stages 2
  and 4.

## Stage 2 — conform the bookends

The intro/outro almost never match the recording (ours were 1080p30 with no
audio track; Zoom records 720p5 with AAC). Re-encoding the 5-second bookends
is cheap (~2 s) and happens **once per recording shape**: the result is
cached in `introandoutro/.conformed/`, keyed by a hash of the spec + the
bookend's mtime. Every following week is a cache hit and stage 2 costs
nothing.

What conforming does:

- scale + pad to the recording's display size, encode with the *same codec*
  (codec→encoder map: h264→libx264, hevc→libx265, …)
- synthesize **silent audio** matching the recording's codec/rate/channels
  (`anullsrc`) — every joined part must have the same stream layout, and a
  missing audio track counts as a different layout. If the recording has no
  audio, the bookends get `-an` instead.
- force the recording's **video track timescale** (see "war stories" below)
- for rotated recordings: render at display size, then transpose the pixels
  into the recording's stored orientation, so that the player's rotation
  step displays everything upright.

## Stage 3 — trim

```
ffmpeg -ss <keyframe> -to <end> -i recording -map 0:v:0 -map 0:a:0? \
       -c copy -avoid_negative_ts make_zero ... body.mp4
```

- `-ss` *before* `-i` = demuxer seek, no decoding.
- The actual start keyframe is found first with `ffprobe -read_intervals`
  (a window scan that widens 60 s → 600 s → whole file, so screen recordings
  with one keyframe total still work — they fall back to 0:00 with a
  warning).
- Only the first video and first audio stream are kept. Extra audio tracks,
  subtitles, or iPhone timecode tracks would make the concat layouts
  mismatch.
- For H.264/HEVC the slice detours through an MPEG-TS intermediate and back
  (both steps still stream copy). Reason: MP4 keeps codec parameters (SPS —
  frame dimensions, entropy mode, etc.) in one per-track header, and after
  joining, that header belongs to the *intro*. The TS conversion inserts the
  body's own parameters **in-band before every keyframe**, and they survive
  the remux back — so the body decodes correctly on any player even though
  the container header isn't its own.

## Stage 4 — concat

A list file drives ffmpeg's concat demuxer:

```
file 'intro.mp4'
duration 4.800000
file 'body.mp4'
duration 3210.804980
file 'outro.mp4'
duration 4.800000
```

`-f concat -c copy` copies all three parts into one file, offsetting the
timestamps of each part by the accumulated duration. The explicit `duration`
lines pin each splice point *past the last frame* of the part — computed by
probing the real end (`max(pts + duration)` over the final packets), because
container metadata can undercount trailing B-frames. Without this, the next
part starts slightly early, its timestamps overlap the seam, and the muxer
"fixes" the collision by silently mangling ~10 frames.

`+faststart` puts the index at the front so the file streams well. If the
recording was rotated, one extra stream-copy remux re-attaches the display
rotation flag (concat takes track properties from the first part — the
intro — and drops it).

## Stage 5 — verify

Three checks, all cheap, all there because stream-copy bugs are *silent* —
ffmpeg exits 0 and hands you a broken file:

1. **Duration**: output ≈ intro + body + outro (±1.5 s).
2. **Timestamp walk**: every video DTS must strictly increase, and no
   cluster of frames may be bunched within a millisecond — bunching is the
   fingerprint of a bad seam (see war stories).
3. **Seam decode**: actually decode ~4 s around each seam plus the head and
   tail (`ffmpeg -xerror -f null`). Timestamp checks can't see codec
   parameter mismatches; decoding can.

On failure the run aborts with the reason and **keeps its temp directory**
(`output/lesson-*/`) for inspection. On success temps are deleted.

## War stories (bugs the design now guards against)

These all produced files that "worked" — ffmpeg exit 0, plays at first
glance — and were only caught by packet-level inspection. Each one turned
into a permanent fix plus a verify check.

**Mixed timescales corrupt seams.** The bookends had video timebase 1/15360,
the Zoom recording 1/10240. The concat demuxer mis-rescales across differing
timescales; the muxer papers over the resulting DTS collisions by clamping
~10 frames into 0.6 ms — they flash by at the seam. Fix: everything is
forced to the recording's timescale (`-video_track_timescale`) in both
conform and trim. Guard: the bunching check in verify.

**Container durations lie about B-frames.** The trimmed body's metadata said
3210.75 s but its last frame *displayed* until 3211.22 s. Concat spliced the
outro at the metadata time, overlapping the body's final frames. Fix: splice
points computed from real packet timestamps (`end_time()`). Guard: same
bunching check.

**`dump_extra` corrupts MP4 H.264.** First attempt at the in-band-parameters
problem used ffmpeg's `dump_extra` bitstream filter — it prepends raw
header bytes into a length-prefixed stream, producing `Invalid NAL unit
size` garbage. Caught immediately by the test suite (0/17). Replaced with
the MPEG-TS round-trip. Guard: the seam decode check.

## Self-debugging

When a run fails, the error names the stage and the temp dir survives.
Useful commands, roughly in the order to reach for them:

```bash
# what does ffmpeg/ffprobe think this file is?
ffprobe -v error -show_streams -show_format -of json file.mp4

# where are the keyframes? (cuts can only start on these)
ffprobe -v error -select_streams v -show_packets \
        -show_entries packet=pts_time,flags -of csv file.mp4 | grep K | head

# inspect timestamps around a seam (e.g. ~4.8s = intro->body)
ffprobe -v error -select_streams v -show_packets \
        -show_entries packet=pts_time,dts_time,flags -of csv out.mp4 |
        awk -F, '$2 > 4 && $2 < 6'

# does the whole file decode cleanly? (exit code + stderr are the answer)
ffmpeg -v error -xerror -i out.mp4 -map 0 -f null -

# see the warnings main.py suppresses: re-run its printed command with -v warning
```

Reading seam dumps: healthy output has strictly increasing `dts_time` with
per-frame spacing (0.2 s at 5 fps), and a keyframe (`K` flag) as the first
packet of each part. Trouble signs: several packets microseconds apart
(muxer clamped a collision), `pts` jumping backwards across a part boundary
(splice point too early), or decode errors only near a seam (codec parameter
mismatch — the body isn't carrying its parameters in-band).

The test suite is the other debugging tool: `python3 tests.py hevc` runs
just the matching fixtures, and each failure prints the pipeline's own
output. Adding a new fixture to `FIXTURES` in `tests.py` is the fastest way
to reproduce a report of "my recording from X doesn't work".
