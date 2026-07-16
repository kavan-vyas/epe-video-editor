# fabld — the lesson video maker

fabld takes a long lesson recording, cuts out the part you want, and wraps it
with your subject intro and the shared outro. A one-hour lesson is ready in
about **5 seconds**, at full original quality.

Everything happens in your web browser — no video editor needed.

---

## How to start

**On a Mac**

1. Double-click **`Start fabld.command`** (in this folder).
   *First time only:* if your Mac refuses to open it, right-click it →
   **Open** → **Open**. You only do that once.
2. Your browser opens with the fabld editor by itself.

**On Windows**

1. Double-click **`Start fabld.bat`** (in this folder).
2. Your browser opens with the fabld editor by itself.

Leave the small terminal window open in the background while you work.
Close it (or press `Ctrl+C` in it) when you're done.

*If fabld says a helper program is missing, it prints the exact one-line
install command to copy-paste — do that once and start fabld again.*

## How to make a video

The page walks you through 4 numbered steps:

1. **Pick your recording** — click the video you want to trim.
   (New recordings go into the `recordings` folder.)
2. **Pick the intro** — maths, english, reasoning… To add a new subject, just
   drop a clip whose name contains the word *intro* into the `introandoutro`
   folder and it appears here. The outro is added automatically.
3. **Choose start & end** — play the video, then drag the two green handles
   on the picture strip around the part you want to keep. Use *Preview my
   selection* to check it. (The orange line shows where the cut really
   starts — always at, or a second or two before, your choice.)
4. **Name it & press the big green button** — watch the 5 steps tick off, then
   your video appears with a player, **Show in folder** and **Save a copy**.

Finished videos live in the `output` folder and are listed at the bottom of
the page under **My finished videos**.

## Folders

```
epe/
├── Start fabld.command   ← double-click this on a Mac
├── Start fabld.bat       ← double-click this on Windows
├── recordings/           ← put your lesson recordings here
├── introandoutro/        ← intro clips + mainoutro.mp4
├── output/               ← finished videos appear here
├── server.py             ← the fabld app (web UI)
├── web/                  ← the pages your browser shows
└── main.py               ← the video engine (also works from the terminal)
```

## If something looks wrong

- **Browser didn't open** — the terminal window prints an address like
  `http://127.0.0.1:8765`. Type that into your browser.
- **My new recording or intro isn't listed** — make sure it's in the right
  folder, then press *Refresh* on the page (or just click back into the tab).
- **The video starts a moment before where I put the handle** — normal, and
  shown in orange: lossless cuts can only start on a keyframe (Zoom makes one
  every 2 seconds). The end cut is always exact.
- **Mac: "can't be opened because it is from an unidentified developer"** —
  right-click `Start fabld.command` → Open → Open. One time only.

---

Curious how it works, or want to use it from the terminal?
The problem it solves, the lossless pipeline, and the full command-line usage
are all in **[info.md](info.md)**.
