/* fabld frontend */
"use strict";

const $ = (id) => document.getElementById(id);

const state = {
  recording: null,   // library entry
  intro: null,       // library entry
  duration: 0,
  keyframes: [],
  start: 0,
  end: 0,
  previewStop: null, // stop playback here during "preview selection"
  job: null,
  outroName: null,
};

/* ---------------- time helpers ---------------- */

function fmt(t, decimals) {
  t = Math.max(0, t);
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = t % 60;
  const ss = decimals ? s.toFixed(1).padStart(4, "0") : String(Math.floor(s)).padStart(2, "0");
  const mm = String(m).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

function parseTime(text) {
  const parts = String(text).trim().split(":").map(Number);
  if (parts.some((n) => Number.isNaN(n) || n < 0)) return null;
  if (parts.length === 1) return parts[0];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  return null;
}

function fmtSize(bytes) {
  if (bytes > 1e9) return (bytes / 1e9).toFixed(2) + " GB";
  if (bytes > 1e6) return (bytes / 1e6).toFixed(1) + " MB";
  return Math.round(bytes / 1e3) + " KB";
}

async function api(path, opts) {
  const res = await fetch(path, opts);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

/* ---------------- library ---------------- */

const SUBJECT_TAGS = [
  [/math/i, "tag-purple", "maths"],
  [/english/i, "tag-orange", "english"],
  [/reason/i, "tag-blue", "reasoning"],
  [/science/i, "tag-green", "science"],
];

function subjectTag(name) {
  for (const [re, cls, label] of SUBJECT_TAGS) if (re.test(name)) return { cls, label };
  return { cls: "tag-pink", label: name.replace(/intro.*$/i, "").replace(/\.[^.]+$/, "") || "intro" };
}

async function loadLibrary() {
  const lib = await api("/api/library");
  state.outroName = lib.outro;
  $("outro-badge").textContent = lib.outro
    ? `${lib.outro} added automatically` : "⚠ no outro file found in introandoutro/";

  renderTiles($("recording-grid"), lib.recordings, "recording");
  $("recording-empty").hidden = lib.recordings.length > 0;
  renderTiles($("intro-grid"), lib.intros, "intro");
  renderOutputs(lib.outputs);
}

function renderTiles(grid, entries, kind) {
  grid.innerHTML = "";
  for (const entry of entries) {
    const tile = document.createElement("button");
    tile.className = "tile";
    tile.dataset.name = entry.name;
    const current = kind === "recording" ? state.recording : state.intro;
    if (current && current.name === entry.name) tile.classList.add("selected");
    const img = document.createElement("img");
    img.className = "tile-thumb";
    img.alt = "";
    img.loading = "lazy";
    const body = document.createElement("div");
    body.className = "tile-body";
    const nameEl = document.createElement("div");
    nameEl.className = "tile-name";
    nameEl.textContent = entry.name;
    const meta = document.createElement("div");
    meta.className = "tile-meta";
    if (kind === "intro") {
      const t = subjectTag(entry.name);
      const tag = document.createElement("span");
      tag.className = `tag ${t.cls}`;
      tag.textContent = t.label;
      meta.appendChild(tag);
    }
    const sizeEl = document.createElement("span");
    sizeEl.textContent = fmtSize(entry.size);
    meta.appendChild(sizeEl);
    const durBadge = document.createElement("span");
    durBadge.className = "badge-dur";
    durBadge.textContent = "…";
    meta.appendChild(durBadge);
    body.append(nameEl, meta);
    tile.append(img, body);
    grid.appendChild(tile);

    // one-frame poster + duration, loaded lazily per tile
    api(`/api/thumbs?kind=${kind}&name=${encodeURIComponent(entry.name)}`)
      .then((d) => {
        if (d.urls.length) img.src = d.urls[Math.floor(d.urls.length / 3)];
        durBadge.textContent = fmt(d.duration);
        entry.duration = d.duration;
      })
      .catch(() => { durBadge.textContent = "?"; });

    tile.addEventListener("click", () => {
      grid.querySelectorAll(".tile").forEach((t) => t.classList.remove("selected"));
      tile.classList.add("selected");
      if (kind === "recording") selectRecording(entry);
      else selectIntro(entry);
    });
  }
}

function renderOutputs(outputs) {
  const list = $("output-list");
  list.innerHTML = "";
  if (!outputs.length) {
    list.innerHTML = '<div class="empty-note">Nothing here yet — your finished videos will appear in this list.</div>';
    return;
  }
  for (const o of outputs) {
    const row = document.createElement("div");
    row.className = "output-row";
    const name = document.createElement("span");
    name.className = "output-name";
    name.textContent = o.name;
    const meta = document.createElement("span");
    meta.className = "output-meta";
    meta.textContent = `${fmtSize(o.size)} · ${new Date(o.mtime * 1000).toLocaleDateString()}`;
    const watch = document.createElement("button");
    watch.className = "btn btn-secondary";
    watch.textContent = "▶ Watch";
    watch.addEventListener("click", () => showDone(o.name, null, false));
    const reveal = document.createElement("button");
    reveal.className = "btn btn-ghost";
    reveal.textContent = "Show in folder";
    reveal.addEventListener("click", () =>
      api("/api/reveal", { method: "POST", body: JSON.stringify({ name: o.name }) }));
    row.append(name, meta, watch, reveal);
    list.appendChild(row);
  }
}

/* ---------------- selection flow ---------------- */

function selectIntro(entry) {
  state.intro = entry;
  $("step2-num").classList.add("done");
  updateCreate();
}

async function selectRecording(entry) {
  state.recording = entry;
  $("step1-num").classList.add("done");
  $("editor-empty").hidden = true;
  $("editor").hidden = false;
  $("strip-loading").hidden = false;
  $("filmstrip").innerHTML = "";
  $("kf-layer").innerHTML = "";

  const player = $("player");
  player.src = entry.url;

  const info = await api(`/api/inspect?kind=recording&name=${encodeURIComponent(entry.name)}`);
  state.duration = info.duration;
  state.start = 0;
  state.end = info.duration;
  $("clock-total").textContent = fmt(info.duration);
  syncTimeUI();
  document.getElementById("step-trim").scrollIntoView({ behavior: "smooth", block: "start" });

  // filmstrip + keyframes load in parallel; UI stays usable meanwhile
  api(`/api/thumbs?kind=recording&name=${encodeURIComponent(entry.name)}`)
    .then((d) => {
      const strip = $("filmstrip");
      strip.innerHTML = "";
      for (const u of d.urls) {
        const im = document.createElement("img");
        im.src = u;
        strip.appendChild(im);
      }
      $("strip-loading").hidden = true;
    })
    .catch(() => { $("strip-loading").textContent = "filmstrip unavailable"; });

  api(`/api/keyframes?kind=recording&name=${encodeURIComponent(entry.name)}`)
    .then((d) => {
      state.keyframes = d.keyframes;
      renderKeyframes();
      syncTimeUI();
    })
    .catch(() => {});

  updateCreate();
}

function renderKeyframes() {
  const layer = $("kf-layer");
  layer.innerHTML = "";
  if (!state.duration) return;
  // cap the tick count so dense keyframes (every 2s over an hour) stay readable
  const maxTicks = 400;
  const step = Math.max(1, Math.ceil(state.keyframes.length / maxTicks));
  for (let i = 0; i < state.keyframes.length; i += step) {
    const tick = document.createElement("div");
    tick.className = "kf-tick";
    tick.style.left = (state.keyframes[i] / state.duration) * 100 + "%";
    layer.appendChild(tick);
  }
}

function snappedStart() {
  let best = 0;
  for (const t of state.keyframes) {
    if (t <= state.start + 0.001 && t > best) best = t;
    if (t > state.start) break;
  }
  return best;
}

/* ---------------- scrubber ---------------- */

const scrubber = $("scrubber");
const player = $("player");

function pctOf(t) { return state.duration ? (t / state.duration) * 100 : 0; }

function syncTimeUI() {
  const startPct = pctOf(state.start);
  const endPct = pctOf(state.end);
  $("shade-left").style.width = startPct + "%";
  $("shade-right").style.width = (100 - endPct) + "%";
  $("selection").style.left = startPct + "%";
  $("selection").style.width = Math.max(0, endPct - startPct) + "%";
  $("handle-start").style.left = `calc(${startPct}% - 18px)`;
  $("handle-end").style.left = endPct + "%";
  if (document.activeElement !== $("start-input")) $("start-input").value = fmt(state.start, true);
  if (document.activeElement !== $("end-input")) $("end-input").value = fmt(state.end, true);
  $("sel-len").textContent = fmt(Math.max(0, state.end - state.start));

  const snap = snappedStart();
  const gap = state.start - snap;
  const marker = $("snap-marker");
  if (state.keyframes.length && gap > 0.05) {
    marker.style.display = "block";
    marker.style.left = pctOf(snap) + "%";
    $("snap-note").textContent =
      `lossless cut starts at the keyframe ${fmt(snap, true)} — ${gap.toFixed(1)}s of extra footage included`;
  } else {
    marker.style.display = "none";
    $("snap-note").textContent = "";
  }
  updateCreate();
}

function timeAtEvent(ev) {
  const rect = scrubber.getBoundingClientRect();
  const x = Math.min(rect.width, Math.max(0, ev.clientX - rect.left));
  return (x / rect.width) * state.duration;
}

let dragging = null; // "start" | "end" | "seek"

scrubber.addEventListener("pointerdown", (ev) => {
  if (!state.duration) return;
  const target = ev.target.closest(".handle");
  dragging = target ? (target.id === "handle-start" ? "start" : "end") : "seek";
  scrubber.setPointerCapture(ev.pointerId);
  onDrag(ev);
});
scrubber.addEventListener("pointermove", (ev) => { if (dragging) onDrag(ev); });
scrubber.addEventListener("pointerup", () => { dragging = null; });
scrubber.addEventListener("pointercancel", () => { dragging = null; });

function onDrag(ev) {
  const t = timeAtEvent(ev);
  if (dragging === "start") {
    state.start = Math.min(t, state.end - 0.5);
    player.currentTime = state.start;
  } else if (dragging === "end") {
    state.end = Math.max(t, state.start + 0.5);
    player.currentTime = state.end;
  } else {
    player.currentTime = t;
  }
  syncTimeUI();
}

/* ---------------- player ---------------- */

function updatePlayhead() {
  $("playhead").style.left = pctOf(player.currentTime) + "%";
  $("clock-now").textContent = fmt(player.currentTime);
  if (state.previewStop !== null && player.currentTime >= state.previewStop) {
    player.pause();
    state.previewStop = null;
  }
  if (!player.paused) requestAnimationFrame(updatePlayhead);
}

player.addEventListener("play", () => {
  $("playpause").textContent = "Pause";
  $("player-overlay").classList.add("playing");
  requestAnimationFrame(updatePlayhead);
});
player.addEventListener("pause", () => {
  $("playpause").textContent = "Play";
  $("player-overlay").classList.remove("playing");
  state.previewStop = null;
});
player.addEventListener("timeupdate", () => { if (player.paused) updatePlayhead(); });

function togglePlay() { player.paused ? player.play() : player.pause(); }
$("playpause").addEventListener("click", togglePlay);
$("player-overlay").addEventListener("click", togglePlay);
$("back5").addEventListener("click", () => { player.currentTime = Math.max(0, player.currentTime - 5); });
$("fwd5").addEventListener("click", () => { player.currentTime = Math.min(state.duration, player.currentTime + 5); });
$("preview-btn").addEventListener("click", () => {
  player.currentTime = snappedStart() || state.start;
  state.previewStop = state.end;
  player.play();
});

$("set-start").addEventListener("click", () => {
  state.start = Math.min(player.currentTime, state.end - 0.5);
  syncTimeUI();
});
$("set-end").addEventListener("click", () => {
  state.end = Math.max(player.currentTime, state.start + 0.5);
  syncTimeUI();
});

for (const btn of document.querySelectorAll(".nudge")) {
  btn.addEventListener("click", () => {
    const d = parseFloat(btn.dataset.d);
    if (btn.dataset.t === "start") state.start = Math.max(0, Math.min(state.start + d, state.end - 0.5));
    else state.end = Math.min(state.duration, Math.max(state.end + d, state.start + 0.5));
    syncTimeUI();
  });
}

for (const [id, key] of [["start-input", "start"], ["end-input", "end"]]) {
  const input = $(id);
  const commit = () => {
    const t = parseTime(input.value);
    if (t === null) { syncTimeUI(); return; }
    if (key === "start") state.start = Math.max(0, Math.min(t, state.end - 0.5));
    else state.end = Math.min(state.duration, Math.max(t, state.start + 0.5));
    syncTimeUI();
  };
  input.addEventListener("change", commit);
  input.addEventListener("keydown", (ev) => { if (ev.key === "Enter") { commit(); input.blur(); } });
}

document.addEventListener("keydown", (ev) => {
  if (ev.target.matches("input, textarea") || $("editor").hidden) return;
  if (ev.code === "Space") { ev.preventDefault(); togglePlay(); }
  else if (ev.key === "ArrowLeft") { player.currentTime = Math.max(0, player.currentTime - (ev.shiftKey ? 1 : 5)); }
  else if (ev.key === "ArrowRight") { player.currentTime = Math.min(state.duration, player.currentTime + (ev.shiftKey ? 1 : 5)); }
  else if (ev.key === "i" || ev.key === "I") { $("set-start").click(); }
  else if (ev.key === "o" || ev.key === "O") { $("set-end").click(); }
});

/* ---------------- create + job ---------------- */

function updateCreate() {
  const ok = state.recording && state.intro && state.end - state.start >= 0.5;
  $("create-btn").disabled = !ok;
  $("step3-num").classList.toggle("done", !!state.recording && state.end - state.start >= 0.5);
  $("summary").innerHTML = ok
    ? `Will create: <strong>${state.intro.name}</strong> + your recording from ` +
      `<strong>${fmt(state.start)}</strong> to <strong>${fmt(state.end)}</strong>` +
      (state.outroName ? ` + <strong>${state.outroName}</strong>` : "") + ` — no re-encoding, full quality.`
    : "Pick a recording and an intro above to unlock this button.";
}

const STAGES = [
  "Inspecting your recording",
  "Preparing intro & outro",
  "Trimming (lossless)",
  "Joining the pieces",
  "Checking the result",
];

function renderStages(current, done) {
  const list = $("stage-list");
  list.innerHTML = "";
  STAGES.forEach((label, i) => {
    const n = i + 1;
    const row = document.createElement("div");
    row.className = "stage" + (n < current || done ? " done" : n === current ? " active" : "");
    const dot = document.createElement("span");
    dot.className = "stage-dot";
    dot.textContent = n < current || done ? "✓" : n;
    const text = document.createElement("span");
    text.textContent = label;
    row.append(dot, text);
    list.appendChild(row);
  });
}

$("create-btn").addEventListener("click", async () => {
  player.pause();
  const name = $("output-name").value.trim() || "final";
  const band = $("progress-band");
  band.hidden = false;
  band.classList.remove("failed");
  $("done-band").hidden = true;
  $("fail-actions").hidden = true;
  $("progress-title").textContent = "Building your video…";
  $("log").textContent = "";
  renderStages(1, false);
  band.scrollIntoView({ behavior: "smooth", block: "center" });

  try {
    const res = await api("/api/assemble", {
      method: "POST",
      body: JSON.stringify({
        recording: state.recording.name,
        intro: state.intro.name,
        start: state.start,
        end: state.end,
        output: name,
      }),
    });
    pollJob(res.job);
  } catch (err) {
    failJob(String(err.message || err));
  }
});

async function pollJob(id) {
  try {
    const job = await api(`/api/job?id=${id}`);
    $("log").textContent = job.log.join("\n");
    const logCard = document.querySelector(".log-card");
    logCard.scrollTop = logCard.scrollHeight;
    renderStages(Math.max(1, job.stage), job.state === "done");
    if (job.state === "running") {
      setTimeout(() => pollJob(id), 600);
    } else if (job.state === "done") {
      $("progress-band").hidden = true;
      showDone(job.output, job.elapsed, true);
      loadLibrary();
    } else {
      failJob(job.error);
    }
  } catch (err) {
    failJob(String(err.message || err));
  }
}

function failJob(message) {
  const band = $("progress-band");
  band.classList.add("failed");
  $("progress-title").textContent = "Something went wrong";
  $("log").textContent += "\n\n" + message;
  $("fail-actions").hidden = false;
}

$("fail-back").addEventListener("click", () => {
  $("progress-band").hidden = true;
  $("step-trim").scrollIntoView({ behavior: "smooth" });
});

function showDone(outputName, elapsed, celebrate) {
  const band = $("done-band");
  band.hidden = false;
  $("done-title").textContent = celebrate ? "Your video is ready" : outputName;
  $("done-sub").textContent = elapsed
    ? `${outputName} — assembled in ${elapsed}s, original quality untouched.`
    : `From your output folder.`;
  const url = `/media/output/${encodeURIComponent(outputName)}`;
  $("done-player").src = url;
  $("download-btn").href = url;
  $("download-btn").setAttribute("download", outputName);
  $("reveal-btn").onclick = () =>
    api("/api/reveal", { method: "POST", body: JSON.stringify({ name: outputName }) });
  band.scrollIntoView({ behavior: "smooth", block: "center" });
}

$("again-btn").addEventListener("click", () => {
  $("done-band").hidden = true;
  $("done-player").pause();
  window.scrollTo({ top: 0, behavior: "smooth" });
});

$("nav-outputs-btn").addEventListener("click", () =>
  $("outputs-section").scrollIntoView({ behavior: "smooth" }));
$("refresh-btn").addEventListener("click", loadLibrary);

// new files dropped into recordings/ or introandoutro/ show up when the user
// comes back to this tab — no manual refresh needed
let lastRefresh = Date.now();
window.addEventListener("focus", () => {
  if (Date.now() - lastRefresh < 3000) return;
  lastRefresh = Date.now();
  loadLibrary().catch(() => {});
});

loadLibrary().catch((err) => {
  $("recording-empty").hidden = false;
  $("recording-empty").textContent = "Could not talk to the fabld server: " + err.message;
});
