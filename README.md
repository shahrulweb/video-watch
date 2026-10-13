# video-watch

Give any AI agent the ability to **watch any video**. A URL or local file becomes timestamped frames plus a structured report — downloaded, extracted, and handed to your agent. Works with Hermes Agent, Claude Code, Codex, OpenCode, DeepSeek harnesses, and any other agent that can run a script and look at images.

```
video URL ──> yt-dlp download ──> ffprobe duration ──> ffmpeg frame extraction
                                                              │
              markdown report <── notes template <── ~80 timestamped JPGs
```

Agents can't play video. This tool converts one into **~80 still frames + a
structured report** so a vision-capable agent analyzes the video frame by
frame and produces grounded notes: a summary, TL;DR, timestamped timeline,
key quotes, and visual observations — evidence from the video itself, not
guesses. Transcripts miss everything visual (UIs, charts, slides, demos,
on-screen text); frames capture it.

---

## Requirements

| Dependency | Why | Install |
|---|---|---|
| Python 3.10+ | the scripts themselves | preinstalled on most systems |
| `ffmpeg` + `ffprobe` | frame extraction, duration probe | `apt install ffmpeg` / `brew install ffmpeg` |
| `yt-dlp` | video download | `pip install yt-dlp` / `brew install yt-dlp` |
| Node.js | required by yt-dlp for YouTube (auto-detected, see below) | any install works |

No Python packages needed — the scripts use only the standard library.

---

## Choose your agent

### Hermes Agent

Clone the repo, then trigger it with `/watch-video` (the `combined-video-watch` skill):

```bash
git clone https://github.com/shahrulweb/video-watch.git
```

Then in Hermes:

```
/watch-video <url-or-path>
/watch-video <url-or-path> --start 1:00 --end 3:00
```

Or just run the script — Hermes' `vision_analyze` reads each frame.

### Claude Code

**Paste this into Claude Code's message box:**

```
Clone https://github.com/shahrulweb/video-watch and use it to watch this
video: <VIDEO_URL>

Run: python video-watch/scripts/watch.py "<VIDEO_URL>"
Then read each frame path listed in the report output (chronological
order) and fill in the structured notes template with what you see.
```

### Codex / OpenCode / other Agent-Skills hosts

**Paste this into the agent's message box:**

```
Install the video-watch tool:
  git clone https://github.com/shahrulweb/video-watch
Use it to watch <VIDEO_URL>:
  python video-watch/scripts/watch.py "<VIDEO_URL>"
Read every frame path in the output report and produce notes following
the structured template included in the report.
```

### Any agent with a terminal + vision

```bash
git clone https://github.com/shahrulweb/video-watch
python video-watch/scripts/watch.py "<url-or-local-path>"
```

Then hand the agent the frame paths from the report. That's the whole
integration — the output is plain files and plain markdown, no
agent-specific APIs.

> **Note:** the agent's model must support images to interpret the frames.
> The script runs anywhere; a text-only model still gets metadata,
> timestamps, and transcript, but can't describe visuals.

---

## Try your first video

1. Make sure `ffmpeg` and `yt-dlp` are installed.
2. Paste this into your agent's message box:

```
Use video-watch (https://github.com/shahrulweb/video-watch) to watch
<VIDEO_URL> and give me structured notes: one-line summary, TL;DR,
a timestamped timeline, and visual notes.
```

3. The agent runs the script, gets ~80 frame paths, looks at them, and
   fills in the notes template.

**Local file?** Point it at a path instead:

```bash
python video-watch/scripts/watch.py ~/Videos/example.mp4 --out-dir /tmp/notes
```

**No captions?** The report says `Transcript: none available`. Wire up a
Whisper backend via `scripts/whisper.py` (local whisperx, Groq, or OpenAI).

---

## Detail and focus

Frame sampling is **duration-aware**: fps is computed as `max_frames /
duration`, so the frame count never exceeds the cap (`--max-frames`, default
80) regardless of video length.

| Video length | Default sampling |
|---|---|
| 5 minutes | ~1 frame every 3.7s |
| 30 minutes | ~1 frame every 22s |
| 2 hours | ~1 frame every 90s |

For dense sections of a long video, focus the range:

```bash
python video-watch/scripts/watch.py "<url>" --start 10:00 --end 15:00 --max-frames 80
```

Frames are 512px wide JPEGs — small enough to batch through a vision API,
sharp enough to read on-screen text. Timestamps in the report are absolute
(source-relative), so notes map directly back to the video.

**Tip for agent harnesses:** have the agent read frames sequentially, not in
large parallel batches — some vision APIs reject concurrent requests with
409 "duplicate request" errors.

---

## CLI reference

```
usage: watch.py source [--start MM:SS] [--end MM:SS] [--max-frames N] [--out-dir DIR]

positional:
  source            Video URL (YouTube etc.) or local file path

options:
  --start           Range start (SS, MM:SS, or HH:MM:SS)
  --end             Range end
  --max-frames      Cap on extracted frames (default 80)
  --out-dir         Working directory (default: a temp dir)
```

Supporting scripts in `scripts/`:

| File | Purpose |
|---|---|
| `watch.py` | Main entry point (download → frames → report) |
| `download.py` | Standalone downloader |
| `frames.py` | Standalone frame extraction |
| `transcribe.py` | Transcript extraction |
| `whisper.py` | Whisper transcription backends |
| `setup.py` | Dependency setup helper |

---

## Node.js auto-discovery (YouTube 403 fix)

YouTube extraction in recent yt-dlp versions requires a JavaScript runtime,
otherwise downloads fail with `HTTP Error 403: Forbidden`. This script passes
`--js-runtimes node:<path>` automatically, locating node in this order:

1. `node` on PATH
2. `~/.hermes/tools/node*/bin/node` (Hermes Agent's bundled node)
3. `/usr/local/bin/node`
4. `/usr/bin/node`

If none is found it prints a warning and proceeds (non-YouTube sources still work).

---

## Troubleshooting

| Symptom | Next step |
|---|---|
| `yt-dlp error: HTTP Error 403` on YouTube | Node.js not found — install it, or check one of the auto-discovery paths exists. |
| `ffmpeg error: usage:` / 0 frames | Fixed in this repo (`subprocess` list + `shell=False`). If you forked an older copy, don't pass a list to `subprocess.run(..., shell=True)`. |
| Vision API 409 "duplicate request" | Analyze frames one at a time instead of parallel batches. |
| `Transcript: none available` | No captions on the video; add a Whisper backend via `scripts/whisper.py`. |
| Agent can't see frames | The model lacks vision — use a multimodal model, or fall back to transcript-only notes. |

---

## Data and cleanup

Frames land in a temp working dir (`watch-XXXX/frames/`). Delete it when
done — the report prints the exact path. Everything runs locally; nothing is
uploaded anywhere.

MIT licensed — see [LICENSE](LICENSE).

## Attribution

Built on ideas from [bradautomates/claude-video](https://github.com/bradautomates/claude-video) (MIT) and the `watch-video` skill ecosystem.
