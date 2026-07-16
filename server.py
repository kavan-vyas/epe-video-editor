#!/usr/bin/env python3
"""fabld — web UI for the lossless lesson-video assembler.

Standard library only. Serves the frontend in web/, exposes a small JSON API,
streams video with HTTP Range support (so the browser player can seek), builds
filmstrip thumbnails + keyframe lists for the scrubber, and runs main.py as a
background job while streaming its progress log to the page.

Run:  python3 server.py          (opens your browser automatically)
"""

import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
RECORDINGS_DIR = os.path.join(ROOT, "recordings")
BOOKENDS_DIR = os.path.join(ROOT, "introandoutro")
OUTPUT_DIR = os.path.join(ROOT, "output")
WEB_DIR = os.path.join(ROOT, "web")
CACHE_DIR = os.path.join(ROOT, ".fabld-cache")
MAIN_PY = os.path.join(ROOT, "main.py")

VIDEO_EXTS = (".mp4", ".m4v", ".mov", ".mkv")
THUMB_COUNT = 28

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

DIRS = {"recording": RECORDINGS_DIR, "intro": BOOKENDS_DIR, "output": OUTPUT_DIR}

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
    ".json": "application/json",
}

JOBS = {}
JOBS_LOCK = threading.Lock()
THUMB_LOCKS = {}
THUMB_LOCKS_GUARD = threading.Lock()


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def list_videos(directory, contains=None):
    if not os.path.isdir(directory):
        return []
    return [f for f in sorted(os.listdir(directory))
            if f.lower().endswith(VIDEO_EXTS)
            and (contains is None or contains in f.lower())]


def resolve_media(kind, name):
    """Map (kind, filename) to a real path; refuse anything outside our dirs."""
    base = DIRS.get(kind)
    if base is None or not name or "/" in name or "\\" in name or name.startswith("."):
        return None
    path = os.path.join(base, name)
    if not os.path.isfile(path) or not name.lower().endswith(VIDEO_EXTS):
        return None
    return path


def file_key(path):
    st = os.stat(path)
    raw = f"{path}|{st.st_mtime_ns}|{st.st_size}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def ffprobe_json(path):
    proc = subprocess.run(
        [FFPROBE, "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
        capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-500:])
    return json.loads(proc.stdout)


def inspect_media(path):
    info = ffprobe_json(path)
    video = next((s for s in info["streams"] if s["codec_type"] == "video"
                  and s.get("disposition", {}).get("attached_pic", 0) == 0), None)
    audio = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    duration = float(info["format"].get("duration")
                     or (video.get("duration") if video else 0) or 0)
    fps = "?"
    if video and video.get("avg_frame_rate", "0/0") not in ("0/0", "?"):
        num, _, den = video["avg_frame_rate"].partition("/")
        try:
            fps = round(float(num) / float(den or 1), 2)
        except (ValueError, ZeroDivisionError):
            pass
    return {
        "duration": duration,
        "width": video["width"] if video else 0,
        "height": video["height"] if video else 0,
        "vcodec": video["codec_name"] if video else None,
        "acodec": audio["codec_name"] if audio else None,
        "fps": fps,
        "size": os.path.getsize(path),
    }


def keyframes_of(path):
    """All video keyframe timestamps, cached (demux only — no decoding)."""
    cache = os.path.join(CACHE_DIR, file_key(path) + ".keyframes.json")
    if os.path.exists(cache):
        with open(cache) as f:
            return json.load(f)
    proc = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_packets",
         "-show_entries", "packet=pts_time,flags", "-of", "csv", path],
        capture_output=True, text=True)
    times = []
    for line in proc.stdout.splitlines():
        parts = line.split(",")
        if len(parts) >= 3 and "K" in parts[2]:
            try:
                times.append(round(float(parts[1]), 3))
            except ValueError:
                continue
    times.sort()
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(cache, "w") as f:
        json.dump(times, f)
    return times


def thumbs_of(path, count=THUMB_COUNT):
    """Filmstrip thumbnails for the scrubber, cached per file version."""
    key = file_key(path)
    with THUMB_LOCKS_GUARD:
        lock = THUMB_LOCKS.setdefault(key, threading.Lock())
    with lock:
        tdir = os.path.join(CACHE_DIR, key)
        marker = os.path.join(tdir, "done")
        duration = inspect_media(path)["duration"]
        times = [max(0.0, (i + 0.5) * duration / count) for i in range(count)]
        if not os.path.exists(marker):
            os.makedirs(tdir, exist_ok=True)
            for i, t in enumerate(times):
                out = os.path.join(tdir, f"{i:02d}.jpg")
                subprocess.run(
                    [FFMPEG, "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", path,
                     "-frames:v", "1", "-vf", "scale=220:-2", "-q:v", "5", out],
                    capture_output=True)
            with open(marker, "w") as f:
                f.write("ok")
        urls = [f"/cache/{key}/{i:02d}.jpg" for i in range(count)
                if os.path.exists(os.path.join(tdir, f"{i:02d}.jpg"))]
        return {"urls": urls, "times": times[:len(urls)], "duration": duration}


# --------------------------------------------------------------------------
# assemble job (runs main.py, streams its log)
# --------------------------------------------------------------------------

STAGE_RE = re.compile(r"^\[(\d)/5\]")


def start_job(recording, intro, start, end, output_name):
    job_id = uuid.uuid4().hex[:12]
    if not output_name.lower().endswith(".mp4"):
        output_name += ".mp4"
    job = {
        "id": job_id, "state": "running", "stage": 0, "log": [],
        "output": output_name, "error": None, "started": time.time(),
    }
    with JOBS_LOCK:
        JOBS[job_id] = job

    def run():
        cmd = [sys.executable, MAIN_PY, recording, intro,
               f"{start:.3f}", f"{end:.3f}", "-o", output_name]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            m = STAGE_RE.match(line)
            with JOBS_LOCK:
                job["log"].append(line)
                if m:
                    job["stage"] = int(m.group(1))
        proc.wait()
        with JOBS_LOCK:
            if proc.returncode == 0:
                job["state"] = "done"
                job["stage"] = 5
                job["elapsed"] = round(time.time() - job["started"], 1)
            else:
                job["state"] = "failed"
                job["error"] = next(
                    (l for l in reversed(job["log"]) if "error" in l.lower()
                     or "FAILED" in l), "assembly failed — see log")

    threading.Thread(target=run, daemon=True).start()
    return job_id


# --------------------------------------------------------------------------
# HTTP handler
# --------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass  # keep the terminal quiet for non-technical users

    # ---- responses -------------------------------------------------------

    def send_json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, cache=False):
        ext = os.path.splitext(path)[1].lower()
        ctype = MIME.get(ext, "application/octet-stream")
        size = os.path.getsize(path)
        range_header = self.headers.get("Range")
        start, end = 0, size - 1
        status = 200
        if range_header:
            m = re.match(r"bytes=(\d*)-(\d*)", range_header)
            if m:
                if m.group(1):
                    start = int(m.group(1))
                    if m.group(2):
                        end = min(int(m.group(2)), size - 1)
                elif m.group(2):
                    start = max(0, size - int(m.group(2)))
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                status = 206
        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if cache:
            self.send_header("Cache-Control", "max-age=86400")
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(1024 * 512, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                remaining -= len(chunk)

    # ---- routing ---------------------------------------------------------

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        route = parsed.path
        query = dict(urllib.parse.parse_qsl(parsed.query))
        try:
            if route == "/" or route == "/index.html":
                return self.send_file(os.path.join(WEB_DIR, "index.html"))
            if route.startswith("/web/"):
                return self.serve_static(route[len("/web/"):])
            if route.startswith("/media/"):
                return self.serve_media(route)
            if route.startswith("/cache/"):
                return self.serve_cache(route)
            if route == "/api/library":
                return self.api_library()
            if route == "/api/inspect":
                return self.api_inspect(query)
            if route == "/api/keyframes":
                return self.api_keyframes(query)
            if route == "/api/thumbs":
                return self.api_thumbs(query)
            if route == "/api/job":
                return self.api_job(query)
            self.send_json({"error": "not found"}, 404)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:  # keep server alive; surface reason to UI
            try:
                self.send_json({"error": str(exc)}, 500)
            except Exception:
                pass

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self.send_json({"error": "bad json"}, 400)
        try:
            if parsed.path == "/api/assemble":
                return self.api_assemble(data)
            if parsed.path == "/api/reveal":
                return self.api_reveal(data)
            self.send_json({"error": "not found"}, 404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)

    # ---- static / media --------------------------------------------------

    def serve_static(self, rel):
        path = os.path.normpath(os.path.join(WEB_DIR, rel))
        if not path.startswith(WEB_DIR) or not os.path.isfile(path):
            return self.send_json({"error": "not found"}, 404)
        self.send_file(path)

    def serve_media(self, route):
        parts = route.split("/")  # ['', 'media', kind, name]
        if len(parts) != 4:
            return self.send_json({"error": "bad path"}, 400)
        path = resolve_media(parts[2], urllib.parse.unquote(parts[3]))
        if path is None:
            return self.send_json({"error": "not found"}, 404)
        self.send_file(path)

    def serve_cache(self, route):
        rel = urllib.parse.unquote(route[len("/cache/"):])
        path = os.path.normpath(os.path.join(CACHE_DIR, rel))
        if not path.startswith(CACHE_DIR) or not os.path.isfile(path):
            return self.send_json({"error": "not found"}, 404)
        self.send_file(path, cache=True)

    # ---- api -------------------------------------------------------------

    def entry(self, kind, name):
        path = os.path.join(DIRS[kind], name)
        st = os.stat(path)
        return {"name": name, "kind": kind, "size": st.st_size,
                "mtime": int(st.st_mtime), "url": f"/media/{kind}/{urllib.parse.quote(name)}"}

    def api_library(self):
        self.send_json({
            "recordings": [self.entry("recording", n)
                           for n in list_videos(RECORDINGS_DIR)],
            "intros": [self.entry("intro", n)
                       for n in list_videos(BOOKENDS_DIR, contains="intro")],
            "outro": next(iter(list_videos(BOOKENDS_DIR, contains="outro")), None),
            "outputs": sorted((self.entry("output", n)
                               for n in list_videos(OUTPUT_DIR)),
                              key=lambda e: -e["mtime"]),
        })

    def media_from_query(self, query):
        path = resolve_media(query.get("kind", ""), query.get("name", ""))
        if path is None:
            raise RuntimeError("file not found")
        return path

    def api_inspect(self, query):
        self.send_json(inspect_media(self.media_from_query(query)))

    def api_keyframes(self, query):
        self.send_json({"keyframes": keyframes_of(self.media_from_query(query))})

    def api_thumbs(self, query):
        self.send_json(thumbs_of(self.media_from_query(query)))

    def api_assemble(self, data):
        rec = resolve_media("recording", data.get("recording", ""))
        intro = resolve_media("intro", data.get("intro", ""))
        if rec is None or intro is None:
            return self.send_json({"error": "pick a recording and an intro"}, 400)
        try:
            start = float(data["start"])
            end = float(data["end"])
        except (KeyError, TypeError, ValueError):
            return self.send_json({"error": "bad start/end times"}, 400)
        if end <= start:
            return self.send_json({"error": "end must be after start"}, 400)
        name = os.path.basename(str(data.get("output") or "final.mp4").strip()
                                or "final.mp4")
        job_id = start_job(rec, intro, start, end, name)
        self.send_json({"job": job_id})

    def api_job(self, query):
        with JOBS_LOCK:
            job = JOBS.get(query.get("id", ""))
            if job is None:
                return self.send_json({"error": "unknown job"}, 404)
            out = dict(job)
        if out["state"] == "done":
            out["output_url"] = f"/media/output/{urllib.parse.quote(out['output'])}"
        self.send_json(out)

    def api_reveal(self, data):
        path = resolve_media("output", data.get("name", ""))
        if path is None:
            return self.send_json({"error": "not found"}, 404)
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", path])
        elif sys.platform.startswith("linux"):
            subprocess.run(["xdg-open", os.path.dirname(path)])
        else:
            subprocess.run(["explorer", "/select,", path])
        self.send_json({"ok": True})


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------

def pick_port(preferred=8765):
    for port in range(preferred, preferred + 20):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return 0


def main():
    if not FFMPEG or not FFPROBE:
        hint = ("winget install ffmpeg" if sys.platform == "win32"
                else "brew install ffmpeg")
        sys.exit(f"fabld needs ffmpeg. Open a terminal and run:  {hint}")
    os.makedirs(RECORDINGS_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)
    port = pick_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{server.server_address[1]}"
    print(f"\n  fabld is running at  {url}")
    print("  Leave this window open while you edit. Press Ctrl+C to quit.\n")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  fabld stopped. Bye!")


if __name__ == "__main__":
    main()
