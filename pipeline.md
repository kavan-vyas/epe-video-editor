# Video Compiler Pipeline — Specification & Build Prompt

> **How to use this document.** You are an AI engineer. This file is the *only* context you
> have. Build the tool described below **from scratch**, then improve on the design where you
> can justify it. Treat every "MUST" as a hard requirement and every "SHOULD" as a strong
> default you may override only with a clear, stated reason. Do not assume any pre-existing
> code exists — there is none. Produce a working, runnable program plus a short README.

---

## 1. The problem (origin)

Every weekend a ~1-hour lesson is recorded over Zoom (subjects: maths, english, reasoning).
Each raw recording needs the same light edit before it is published:

1. **Trim the top** — cut off the dead time before the lesson actually starts.
2. **Trim the bottom** — cut off the dead time after the lesson ends.
3. **Prepend an intro** — a short (~5 second) subject-specific clip.
4. **Append an outro** — a single shared ~5 second closing clip.

That is the *entire* edit. No transitions, no overlays, no colour grading, no per-frame work.

The original solution did this in Camtasia (~30 min "convert" + ~60 min editing ≈ 90 min). A
later attempt re-encoded everything with a frame-by-frame video library, which was correct but
slow (7–15+ minutes per video) because it decoded and re-encoded ~1 hour of footage that was
never actually changed.

**The whole point of this tool is to avoid touching the frames at all.**

## 2. The goal

Produce `intro + trimmed_body + outro` as a single MP4, **losslessly and fast** (target: well
under a minute for a 1-hour 1080p source on a normal laptop), by **stream-copying** the media
instead of re-encoding it.

The body of the lesson — the 99%+ of the runtime that is unchanged — MUST never be decoded or
re-encoded. Only its container metadata is rewritten so it points at the right byte ranges.

## 3. Core insight (read this before designing anything)

An MP4 is a container. The actual compressed audio/video bytes sit in one large `mdat` box; a
separate `moov` box holds index tables (sample sizes, durations, keyframe list, and byte
offsets) that point into `mdat`. Trimming and joining can therefore be done by **copying raw
bytes and rewriting indexes** — no codec involved. This is exactly what `ffmpeg -c copy`
(stream copy) does, and it is the intended foundation of this tool.

Two consequences drive the whole design:

- **A still image is not free.** An intro/outro made from a static image still has to be
  encoded into real video frames *once*. But ~5 seconds is ~150 frames — encode it **a single
  time** when you create the bookend clip, then stream-copy it forever after. The expensive
  per-frame work is paid once, on a tiny clip, not on every weekend's hour-long recording.
- **Stream copy has rules.** You cannot cut at an arbitrary frame, and you cannot blindly join
  arbitrary files. See §6.

## 4. Recommended foundation

**Use `ffmpeg`/`ffprobe` as the engine** (invoked as a subprocess). Rationale: stream copy,
keyframe-accurate trimming, the concat demuxer, fragmented-MP4 handling, and timestamp
continuity are all solved problems in ffmpeg. Reimplementing an MP4 muxer by hand is possible
but is a large surface of edge cases (composition-time offsets, 32→64-bit offset upgrades,
fragmented `moof`/`trun` parsing) for no speed gain — stream copy is I/O-bound either way.

> If, and only if, a zero-external-dependency constraint is explicitly required, a pure
> container-level rewrite is the fallback. Otherwise prefer ffmpeg. State which path you chose
> and why.

## 5. Inputs, layout, and outputs

```
project_root/
├── <the program>             # entry point (e.g. main.py)
├── recordings/               # raw weekly recordings (*.mp4)
│   ├── maths.mp4
│   ├── english.mp4
│   └── reasoning.mp4
├── introandoutro/            # pre-rendered bookend clips (*.mp4)
│   ├── mathsintro.mp4
│   ├── englishintro.mp4
│   ├── reasoningintro.mp4
│   └── mainoutro.mp4         # the single shared outro
└── output/                   # created automatically; final files land here
```

- Intro clips are identified by filename containing `intro`. The outro is `mainoutro.mp4`.
- An intro is "a video version of a static image": it MAY be generated from a still (see §7,
  Stage 0) but is consumed by the pipeline as an ordinary MP4.
- Output: `output/<user-chosen-name>.mp4` (default `final.mp4`).

## 6. Hard constraints & gotchas (the part that actually matters)

These are the things that make a naive implementation silently produce broken video. Handle
them explicitly.

1. **Trim snaps to keyframes.** Lossless cutting can only begin at a keyframe (typically every
   2–5 s). A requested start time MUST resolve to the nearest keyframe at or before it; cutting
   mid-GOP losslessly is impossible. Communicate this to the user — the cut is approximate by
   design. (Re-encoding just the boundary GOP for frame-exact cuts is an optional stretch goal,
   not the default.)

2. **Concat with stream copy requires matching parameters.** To join clips without
   re-encoding, every segment MUST share: video codec, profile/level, resolution, pixel format,
   frame rate / time base, **and** audio codec, sample rate, channel layout. If the bookends
   don't match the recording, concat either fails or produces glitches and A/V drift. This is
   the single most common failure mode — guard against it (see §7, Stage 2).

3. **Bookends must match the recording, so probe first.** Don't assume. `ffprobe` the selected
   recording, read its real parameters, and ensure the intro/outro conform to them. Either
   pre-render bookends to a known house standard and require recordings to match it, or
   normalise the bookends to the recording at use time (a one-time ~5 s encode — cheap).

4. **Fragmented MP4 (fMP4).** Zoom/screen recordings are sometimes fragmented (`moov` + `mvex`
   with `moof`/`mdat` fragments). ffmpeg handles this transparently on copy; if you go the
   hand-rolled route you MUST unfragment first. Detect and handle it either way.

5. **Audio priming / timestamp continuity at joins.** AAC encoder delay and per-segment PTS can
   introduce small gaps or sync slips at concat boundaries. Prefer the concat **demuxer**
   (`-f concat`) over the concat protocol for MP4, and regenerate timestamps if needed.

6. **Every segment should begin on a keyframe** for a clean join. Freshly encoded bookends will;
   a stream-copy-trimmed body will (because the trim snapped the start to a keyframe).

7. **Validate the output.** A run that exits 0 but yields an unplayable file is a failure.
   After writing, `ffprobe` the result and assert duration ≈ (intro + trimmed_body + outro),
   stream count/params as expected, and no decode errors.

## 7. The pipeline, stage by stage

### Stage 0 — Bookend preparation (one-time, per subject)
Create each intro and the shared outro from a static image (or a short clip), encoded to the
**house standard** codec parameters (resolution, codec, profile, pixfmt, fps, audio
codec/rate/layout). Include a (possibly silent) audio track so it concatenates cleanly with
recordings that have audio. This is the only place real encoding happens, and it happens once.

### Stage 1 — Select & inspect
1. List `recordings/*.mp4`; user picks one.
2. `ffprobe` it: duration, keyframe interval, and all stream parameters from §6.2.
3. Detect fragmentation; unfragment/normalise if required.

### Stage 2 — Conform bookends
1. Pick the subject intro and `mainoutro.mp4`.
2. Compare their parameters to the recording.
3. If they already match the house standard the recording also matches → use as-is (pure copy
   path). If they don't match → normalise the bookends to the recording's parameters with a
   one-time short encode. Never normalise the hour-long body.

### Stage 3 — Trim the body (stream copy)
1. Take user start/end times (`MM:SS`, where minutes MAY exceed 60).
2. Resolve start to the nearest keyframe ≤ requested start; resolve end (clamp to EOF).
3. Stream-copy the `[start, end]` range to a temp file with **no re-encode**. End must be after
   start; validate.

### Stage 4 — Concatenate
1. Build the ordered list: `intro`, `trimmed_body`, `outro` (omit any that are missing, with a
   warning).
2. Join with the concat demuxer using stream copy.
3. Write to `output/<name>.mp4`. Sanitise the filename to a basename (no path traversal); add
   `.mp4` if missing; default `final.mp4`.

### Stage 5 — Verify & clean up
1. `ffprobe` the output; assert duration and stream parameters (§6.7).
2. Delete temp files. Report the output path and total wall-clock time.

## 8. CLI / UX specification

Interactive, terminal-driven, runnable with a single command (e.g. `python main.py`):

- Print a clear banner.
- Create `output/` if absent.
- List recordings numbered; reject invalid selections and re-prompt.
- Prompt start time, then end time (`MM:SS`); validate format and that end > start; re-prompt on
  bad input. Warn that cuts snap to the nearest keyframe.
- List intros numbered; allow selection; auto-select `mainoutro.mp4`; warn (don't crash) if
  either is missing.
- Prompt output filename with a default.
- Show progress per stage and a final SUCCESS line with the path and elapsed seconds.
- Fail loudly and clearly: missing folders, missing ffmpeg, mismatched parameters that can't be
  reconciled, invalid trim range, unplayable output. Never silently emit a broken file.

## 9. Performance targets

- 1-hour 1080p source, trim + two 5 s bookends: **< ~60 s** wall clock on a typical laptop,
  dominated by disk I/O, not CPU.
- The body is **never** re-encoded. CPU use should be near-idle except during the one-time
  bookend encode in Stage 0/2.

## 10. Acceptance criteria (definition of done)

- [ ] Runs from a single command with the folder layout in §5.
- [ ] Trims top and bottom losslessly via stream copy (keyframe-snapped start).
- [ ] Prepends the chosen intro and appends `mainoutro.mp4`.
- [ ] Never re-encodes the recording body; bookends encoded at most once.
- [ ] Detects/handles parameter mismatches and fragmented MP4 instead of producing glitches.
- [ ] Validates the output with `ffprobe` before declaring success.
- [ ] Clear interactive UX with input validation and honest error messages.
- [ ] Hits the performance target in §9.
- [ ] Short README: requirements (ffmpeg), setup, usage, and the keyframe-snap caveat.

## 11. Your task

Using only this document:

1. Choose the foundation (§4) and state your choice and reasoning.
2. Design the module/file structure.
3. Implement the full pipeline (§7) with the UX (§8) and constraint handling (§6).
4. Write the README.
5. Where you can improve on this spec — better failure handling, smarter parameter
   conforming, optional frame-exact trimming, batch mode, a non-interactive flag-driven
   mode — do so, but call out each deviation and why it's better.

Optimise for **correctness and speed via stream copy**, then for clarity. Do not reach for
frame-by-frame processing; if you think you need it, re-read §3 and §6.1.

## 12. Stretch goals (optional)

- Frame-exact trimming by re-encoding only the boundary GOPs (smart cut).
- Non-interactive CLI (flags/JSON config) for automation / scheduling.
- Batch processing of multiple recordings in one run.
- Auto-matching intro to recording by subject name (`maths.mp4` → `mathsintro.mp4`).
- "Fast start" output (`moov` relocated to the front) for instant web playback.
- Generate bookends from a still image on the fly if the clip is missing.
