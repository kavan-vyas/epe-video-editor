#!/usr/bin/env python3
"""End-to-end test suite for main.py.

Generates synthetic recordings covering the awkward input shapes the pipeline
must survive, runs the full pipeline on each, and checks the output:
  - pipeline exits 0
  - output duration ~= intro + trimmed body + outro
  - the ENTIRE output decodes without a single bitstream error
  - rotated inputs keep their display rotation

Usage:  python3 tests.py [substring-filter]
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(ROOT, "main.py")
FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

TRIM_START, TRIM_END = "5", "20"   # every test trims 5s..20s -> 15s body
BOOKENDS = 4.8 * 2                 # intro + outro (approx, checked loosely)

V = ["-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30"]
A = ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000"]

FIXTURES = {
    # name: (generation args after inputs, inputs, container ext)
    "baseline_h264_aac": (V + A, ["-c:v", "libx264", "-g", "30",
                                  "-pix_fmt", "yuv420p", "-c:a", "aac"], ".mp4"),
    "hevc_8bit": (V + A, ["-c:v", "libx265", "-tag:v", "hvc1", "-g", "30",
                          "-pix_fmt", "yuv420p", "-c:a", "aac",
                          "-x265-params", "log-level=error"], ".mp4"),
    "hevc_10bit": (V + A, ["-c:v", "libx265", "-tag:v", "hvc1", "-g", "30",
                           "-pix_fmt", "yuv420p10le", "-c:a", "aac",
                           "-x265-params", "log-level=error"], ".mp4"),
    "no_audio": (V, ["-c:v", "libx264", "-g", "30",
                     "-pix_fmt", "yuv420p"], ".mp4"),
    "mono_44k": (V + ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100"],
                 ["-c:v", "libx264", "-g", "30", "-pix_fmt", "yuv420p",
                  "-c:a", "aac", "-ac", "1", "-ar", "44100"], ".mp4"),
    "mp3_audio": (V + A, ["-c:v", "libx264", "-g", "30", "-pix_fmt", "yuv420p",
                          "-c:a", "libmp3lame"], ".mp4"),
    "matroska": (V + A, ["-c:v", "libx264", "-g", "30",
                         "-pix_fmt", "yuv420p", "-c:a", "aac"], ".mkv"),
    "quicktime_mov": (V + A, ["-c:v", "libx264", "-g", "30",
                              "-pix_fmt", "yuv420p", "-c:a", "aac"], ".mov"),
    "single_keyframe": (V + A, ["-c:v", "libx264", "-g", "9999",
                                "-pix_fmt", "yuv420p", "-c:a", "aac"], ".mp4"),
    "fragmented": (V + A, ["-c:v", "libx264", "-g", "30", "-pix_fmt", "yuv420p",
                           "-c:a", "aac",
                           "-movflags", "frag_keyframe+empty_moov"], ".mp4"),
    "multi_audio": (V + A + ["-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000"],
                    ["-map", "0:v", "-map", "1:a", "-map", "2:a",
                     "-c:v", "libx264", "-g", "30", "-pix_fmt", "yuv420p",
                     "-c:a", "aac"], ".mp4"),
    "odd_resolution": (["-f", "lavfi", "-i", "testsrc2=size=852x480:rate=24"] + A,
                       ["-c:v", "libx264", "-g", "24",
                        "-pix_fmt", "yuv420p", "-c:a", "aac"], ".mp4"),
    "high_fps_4k": (["-f", "lavfi", "-i", "testsrc2=size=3840x2160:rate=60"] + A,
                    ["-c:v", "libx264", "-preset", "ultrafast", "-g", "60",
                     "-pix_fmt", "yuv420p", "-c:a", "aac"], ".mp4"),
    "apostrophe name": (V + A, ["-c:v", "libx264", "-g", "30",
                                "-pix_fmt", "yuv420p", "-c:a", "aac"], ".mp4"),
}
ROTATED = {"rot90": 90, "rot180": 180, "rot270": 270}


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def gen_fixture(name, workdir):
    if name in ROTATED:
        flat = os.path.join(workdir, "rot_base.mp4")
        if not os.path.exists(flat):
            r = sh([FFMPEG, "-y", "-v", "error"] + V + A +
                   ["-t", "30", "-c:v", "libx264", "-g", "30",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", flat])
            assert r.returncode == 0, r.stderr
        path = os.path.join(workdir, name + ".mp4")
        r = sh([FFMPEG, "-y", "-v", "error",
                "-display_rotation", str(ROTATED[name]), "-i", flat,
                "-c", "copy", path])
        assert r.returncode == 0, r.stderr
        return path
    inputs, codecs, ext = FIXTURES[name]
    fname = ("teacher's lesson.mp4" if name == "apostrophe name"
             else name + ext)
    path = os.path.join(workdir, fname)
    r = sh([FFMPEG, "-y", "-v", "error"] + inputs + ["-t", "30"] + codecs + [path])
    assert r.returncode == 0, f"fixture gen failed: {r.stderr}"
    return path


def check_output(out_path, rotation=0):
    """Returns error string or None."""
    r = sh([FFPROBE, "-v", "error", "-show_streams", "-show_format",
            "-of", "json", out_path])
    if r.returncode != 0:
        return f"output unreadable: {r.stderr[-200:]}"
    info = json.loads(r.stdout)
    dur = float(info["format"]["duration"])
    expected = 15 + BOOKENDS
    # start snapping to an earlier keyframe can only ADD footage (up to the
    # requested start of 5s); allow small rounding slack below
    if not (expected - 2 <= dur <= expected + 6.5):
        return f"duration {dur:.1f}s, expected ~{expected:.1f}s"
    if rotation:
        video = next(s for s in info["streams"] if s["codec_type"] == "video")
        rots = [int(sd["rotation"]) % 360
                for sd in video.get("side_data_list", []) if "rotation" in sd]
        if rotation not in rots:
            return f"display rotation lost (wanted {rotation}, got {rots})"
    r = sh([FFMPEG, "-v", "error", "-xerror", "-i", out_path,
            "-map", "0", "-f", "null", "-"])
    if r.returncode != 0:
        return f"decode error: {r.stderr[-300:]}"
    return None


def rejection_tests(workdir, base):
    """Bad input must fail fast with a clear error, not a traceback."""
    cases = {
        "reject_end_before_start": [base, "maths", "20", "5"],
        "reject_start_past_eof": [base, "maths", "500", "600"],
        "reject_missing_recording": ["no_such_file.mp4", "maths", "5", "20"],
        "reject_unknown_intro": [base, "underwaterbasketweaving", "5", "20"],
        "reject_bad_time": [base, "maths", "banana", "20"],
    }
    results = {}
    for name, argv in cases.items():
        out = os.path.join(workdir, name + ".mp4")
        r = sh(["python3", MAIN] + argv + ["-o", out], cwd=ROOT)
        if r.returncode == 0:
            results[name] = "accepted bad input"
        elif "Traceback" in r.stderr:
            results[name] = f"crashed with traceback: {r.stderr[-200:]}"
        else:
            results[name] = None
    return results


def main():
    filt = sys.argv[1] if len(sys.argv) > 1 else ""
    names = [n for n in list(FIXTURES) + list(ROTATED) if filt in n]
    results = {}
    with tempfile.TemporaryDirectory(prefix="epe-tests-") as workdir:
        for name in names:
            path = gen_fixture(name, workdir)
            out = os.path.join(workdir, f"out_{name.replace(' ', '_')}.mp4")
            r = sh(["python3", MAIN, path, "maths", TRIM_START, TRIM_END,
                    "-o", out], cwd=ROOT)
            if r.returncode != 0:
                results[name] = f"pipeline failed:\n{r.stdout[-300:]}{r.stderr[-300:]}"
                continue
            results[name] = check_output(out, ROTATED.get(name, 0))
        if not filt:
            base = gen_fixture("baseline_h264_aac", workdir)
            results.update(rejection_tests(workdir, base))
            names = list(results)

    width = max(len(n) for n in names)
    failed = 0
    print()
    for name, err in results.items():
        status = "PASS" if err is None else f"FAIL - {err}"
        failed += err is not None
        print(f"  {name:<{width}}  {status}")
    print(f"\n{len(results) - failed}/{len(results)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
