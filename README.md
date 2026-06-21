# Video Compiler

Lossless, **stream-copy** lesson-video builder. It takes a raw weekend recording,
trims the dead time off the top and bottom, prepends a subject intro, appends a
shared outro, and writes a single MP4 — **without ever decoding or re-encoding the
hour-long body**. A 1-hour 1080p recording compiles in seconds, not minutes,
because the work is I/O (copying bytes + rewriting the container index), not CPU.

See [pipeline.md](pipeline.md) for the full specification this implements.

---

## Foundation: why ffmpeg (§4)

This tool drives **`ffmpeg` / `ffprobe` as subprocesses** rather than hand-rolling
an MP4 muxer. Stream copy (`-c copy`), keyframe-accurate trimming, the concat
demuxer, fragmented-MP4 (`moof`/`mvex`) handling, and timestamp continuity are all
solved problems in ffmpeg. A pure container rewrite would be a huge surface of edge
cases (composition-time offsets, 32→64-bit offset upgrades, `trun` parsing) **for no
speed gain** — stream copy is I/O-bound either way. The hand-rolled path is only
worth it under a hard zero-dependency constraint, which we don't have here.

## Requirements

- **Python 3.10+** (standard library only — no pip install needed)
- **ffmpeg and ffprobe** on your `PATH`
  - macOS: `brew install ffmpeg`
  - Debian/Ubuntu: `sudo apt install ffmpeg`
  - Windows: `winget install Gyan.FFmpeg`

## Folder layout (§5)

```
project_root/
├── main.py
├── recordings/               # raw weekly recordings (*.mp4)
│   ├── maths.mp4
│   ├── english.mp4
│   └── reasoning.mp4
├── introandoutro/            # pre-rendered bookend clips (*.mp4)
│   ├── mathsintro.mp4        # intros: filename contains "intro"
│   ├── englishintro.mp4
│   ├── reasoningintro.mp4
│   └── mainoutro.mp4         # the single shared outro
└── output/                   # created automatically; finals land here
```

## Usage

### Interactive (default)

```bash
python main.py
```

Walks you through: pick a recording → enter start/end (`MM:SS`, minutes may exceed
60) → confirm the auto-matched intro → name the output. It validates every input
and re-prompts on bad entries.

### Non-interactive (scriptable)

```bash
# subject name resolves to recordings/maths.mp4; intro auto-matched by subject
python main.py -r maths -s 01:30 -e 58:00 -o maths_week1
```

| flag | meaning |
|------|---------|
| `-r, --recording` | recording path or subject name (e.g. `maths`) |
| `-s, --start` | start time `MM:SS` / `HH:MM:SS` / seconds (default `00:00`) |
| `-e, --end` | end time (default end-of-file) |
| `-i, --intro` | intro path/name (default: auto-match by subject) |
| `-o, --output` | output filename (default `final.mp4`) |
| `--no-intro` / `--no-outro` | omit a bookend |
| `--no-faststart` | don't relocate `moov` to the front |
| `--keep-temp` | keep intermediate files for debugging |
| `--batch` | process **every** recording in one run |

### Batch

```bash
python main.py --batch -s 01:30 -e 58:00
```

Compiles every recording, auto-matching each subject's intro, to
`output/<subject>_final.mp4`.

## How it works (the five stages, §7)

1. **Inspect** — `ffprobe` the recording for duration, stream parameters, and
   fragmentation.
2. **Conform bookends** — compare each bookend's A/V signature to the recording. If
   it already matches → use as-is (**pure copy, zero encoding**). If not → a
   one-time ~5 s re-encode brings it into line. The body is never touched.
3. **Trim** — snap the requested start back to the nearest keyframe ≤ it, then
   `-c copy` the `[start, end]` range. No frames decoded.
4. **Concatenate** — join `intro + body + outro` with the concat **demuxer** and
   stream copy (chosen over the concat protocol for clean MP4 timestamps / AAC
   priming).
5. **Verify** — `ffprobe` the result, assert duration ≈ intro + body + outro and
   the expected streams, then run a full decode pass. A file that exits 0 but
   doesn't play is treated as a failure.

## The keyframe-snap caveat (§6.1 — read this)

Lossless cutting can only **begin on a keyframe** (typically one every 2–5 s). When
you ask to start at `01:33`, the tool snaps the cut back to the last keyframe at or
before it and tells you so. This is by design — cutting mid-GOP losslessly is
impossible. Frame-exact cuts would require re-encoding the boundary GOP (a documented
stretch goal, not the default).

## Constraint handling (§6)

- **Keyframe-snapped trims** — start always resolves to a real keyframe.
- **Parameter-mismatch guard** — bookends that don't match the recording are
  conformed (or fail loudly) instead of silently glitching the concat.
- **Fragmented MP4** — detected and handled transparently by ffmpeg on copy.
- **Timestamp continuity** — concat demuxer + `genpts` / `avoid_negative_ts` smooth
  over per-segment PTS and AAC priming at joins.
- **Output validation** — duration + stream + full-decode assertions before success.
- **Honest errors** — missing ffmpeg, missing folders, irreconcilable parameters,
  empty trim ranges, and unplayable output all fail loudly with a clear message.

## Improvements over the base spec (§11.5)

Each is a deliberate addition, called out here:

- **Non-interactive flag mode** — fully scriptable for automation/scheduling.
- **Batch mode** — one command compiles every recording.
- **Subject auto-matching** — `maths.mp4` → `mathsintro.mp4` without prompting.
- **On-the-fly bookend generation** from a still image
  (`vcompiler.bookends.generate_from_still`) — scale/pad to the recording's exact
  resolution with a silent audio track, so a missing intro can be synthesised.
- **Fast-start output** — `moov` relocated to the front for instant web playback
  (toggle with `--no-faststart`).
- **Full-decode verification** — beyond a header probe, we decode the whole output
  to catch truncation/corruption a header check would miss.
- **Tolerance-aware duration check** — allows the small, legitimate length shift
  introduced by keyframe snapping instead of failing on it.

## Module structure

```
main.py                 # entry point
vcompiler/
├── cli.py              # interactive UX + flag/batch front-ends (§8)
├── pipeline.py         # stage orchestrator (§7)
├── library.py          # folder discovery, subject match, name sanitisation (§5)
├── probe.py            # ffprobe → MediaInfo / A·V signatures (§6.2-6.4)
├── trim.py             # keyframe-snapped stream-copy trim (§6.1, §7.3)
├── bookends.py         # conform / generate bookends (§6.2-6.3, §7.0/7.2)
├── concat.py           # concat demuxer join (§6.5, §7.4)
├── verify.py           # output assertions (§6.7, §7.5)
├── timecode.py         # MM:SS parsing (minutes may exceed 60)
└── ffmpeg.py           # subprocess wrappers + tool discovery
```

## Performance

On the synthetic test fixtures (40 s 720p source, two 5 s bookends) the full
compile — including a complete decode-verification pass — runs in well under a
second. For a real 1-hour 1080p recording the work is dominated by disk I/O, not
CPU, comfortably inside the **< ~60 s** target in §9. CPU is near-idle except during
the one-time bookend conform encode (when a bookend doesn't already match).
