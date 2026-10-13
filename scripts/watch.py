#!/usr/bin/env python3
"""
Combined Video Watch Skill: Extract frames and generate a structured notes template using yt-dlp and ffmpeg.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def format_time(seconds):
    """Convert seconds to MM:SS format."""
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    return f"{minutes:02d}:{seconds:02d}"


def parse_time(time_str):
    """Parse time string (SS, MM:SS, or HH:MM:SS) into seconds. Returns None if time_str is None."""
    if time_str is None:
        return None
    try:
        parts = list(map(int, time_str.split(":")))
        if len(parts) == 1:
            return parts[0]
        elif len(parts) == 2:
            return parts[0] * 60 + parts[1]
        elif len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
    except ValueError:
        return None


def _js_runtime_args():
    """Return yt-dlp --js-runtimes args.

    YouTube extraction requires a JS runtime. Prefer `node` on PATH; fall back
    to well-known install locations (including Hermes's bundled node) so the
    script works under any agent (Hermes, Claude Code, Codex, etc.).
    """
    node = shutil.which("node")
    if node is None:
        candidates = sorted(Path.home().glob(".hermes/tools/node*/bin/node"))
        candidates += [Path("/usr/local/bin/node"), Path("/usr/bin/node")]
        for c in candidates:
            try:
                if c.is_file() and os.access(c, os.X_OK):
                    node = str(c)
                    break
            except OSError:
                continue
    if node:
        return ["--js-runtimes", f"node:{node}"]
    print("[watch] warning: node not found; YouTube downloads may fail with 403", file=sys.stderr)
    return []


def probe_duration(video_path):
    """Return video duration in seconds via ffprobe, or 0.0 on failure."""
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
        capture_output=True, text=True,
    )
    try:
        return float(probe.stdout.strip())
    except ValueError:
        return 0.0


def extract_frames(video_path, output_dir, start_time=None, end_time=None, max_frames=80):
    """Extract frames from a video using ffmpeg. Returns (frames, fps)."""
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(exist_ok=True)

    # Pick fps so we extract at most max_frames frames over the span
    duration = probe_duration(video_path)
    span = duration
    if start_time is not None:
        span = max(span - start_time, 0.0)
    if end_time is not None:
        span = min(span, max(end_time - (start_time or 0.0), 0.0))
    fps = min(10.0, max_frames / span) if span > 0 else 1.0

    # Build ffmpeg command as a list and run WITHOUT shell=True:
    # with shell=True only cmd[0] is executed by the shell and the remaining
    # list items become shell positional args ($0, $1, ...), so ffmpeg ran
    # with no arguments and just printed its usage text.
    cmd = ["ffmpeg", "-y", "-ss", str(start_time if start_time is not None else 0),
           "-i", str(video_path)]
    if end_time is not None:
        # -ss is before -i, so -to is relative to the seek point
        cmd.extend(["-to", str(end_time - (start_time or 0.0))])
    cmd.extend(["-vf", f"fps={fps:.4f},scale=512:-1",
                str(frames_dir / "frame_%04d.jpg")])

    print(f"[watch] Running: {' '.join(cmd)}", file=sys.stderr)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[watch] ffmpeg error: {result.stderr}", file=sys.stderr)
        return [], fps

    # List extracted frames
    frames = []
    offset = start_time or 0
    for i in range(1, max_frames + 1):
        frame_path = frames_dir / f"frame_{i:04d}.jpg"
        if frame_path.exists():
            frames.append({
                "path": str(frame_path),
                "timestamp_seconds": offset + ((i - 1) / fps if fps > 0 else 0),
            })

    return frames, fps


def generate_notes_template(frames, source, title=None, uploader=None, duration=None):
    """Generate a structured markdown notes template."""
    notes = []
    
    # Header
    notes.append("# Video Notes")
    notes.append(f"**Source:** {source}")
    if title:
        notes.append(f"**Title:** {title}")
    if uploader:
        notes.append(f"**Uploader:** {uploader}")
    if duration:
        notes.append(f"**Duration:** {format_time(float(duration))}")
    notes.append("\n")
    
    # One-line summary
    notes.append("## One-line Summary")
    notes.append("<Fill this in after reading frames>")
    notes.append("\n")
    
    # TL;DR
    notes.append("## TL;DR")
    notes.append("- Bullet point 1")
    notes.append("- Bullet point 2")
    notes.append("- Bullet point 3")
    notes.append("\n")
    
    # Timeline
    notes.append("## Timeline")
    for frame in frames:
        timestamp = format_time(frame['timestamp_seconds'])
        notes.append(f"- **[{timestamp}]** <Describe frame and transcript>")
    notes.append("\n")
    
    # Key quotes
    notes.append("## Key Quotes")
    notes.append("> \"<QUOTE>\" — [MM:SS]")
    notes.append("\n")
    
    # Visual notes
    notes.append("## Visual Notes")
    notes.append("<Describe visuals not in transcript>")
    notes.append("\n")
    
    return "\n".join(notes)


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="watch",
        description="Download a video, extract frames, and generate a structured notes template.",
    )
    ap.add_argument("source", help="Video URL or local file path")
    ap.add_argument("--start", type=str, default=None, help="Range start (SS, MM:SS, or HH:MM:SS)")
    ap.add_argument("--end", type=str, default=None, help="Range end (SS, MM:SS, or HH:MM:SS)")
    ap.add_argument("--out-dir", type=str, default=None, help="Working directory (default: tmp)")
    ap.add_argument("--max-frames", type=int, default=80, help="Cap on number of frames to extract")
    args = ap.parse_args()

    if args.out_dir:
        work = Path(args.out_dir).expanduser().resolve()
    else:
        work = Path(tempfile.mkdtemp(prefix="watch-"))
    work.mkdir(parents=True, exist_ok=True)
    print(f"[watch] working dir: {work}", file=sys.stderr)

    print("[watch] downloading via yt-dlp…", file=sys.stderr)
    
    # Download video using yt-dlp with explicit output format.
    # YouTube now requires a JS runtime; locate node robustly so this works
    # under any agent (Hermes, Claude Code, Codex, etc.).
    video_path = work / "video.%(ext)s"
    cmd = ["yt-dlp", *_js_runtime_args(), "-o", str(video_path), args.source]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[watch] yt-dlp error: {result.stderr}", file=sys.stderr)
        return 1
    
    # Verify the video file exists
    video_files = list(work.glob("video.*"))
    if not video_files:
        print(f"[watch] Error: No video file found in {work}", file=sys.stderr)
        return 1
    
    video_path = video_files[0]

    # Parse start and end times (convert to seconds)
    start_sec = parse_time(args.start)
    end_sec = parse_time(args.end)

    # Extract frames
    frames, fps = extract_frames(video_path, work, start_sec, end_sec, max_frames=args.max_frames)

    # Get video metadata in a single yt-dlp call
    meta_cmd = ["yt-dlp", *_js_runtime_args(), "--print", "%(title)s\t%(uploader)s\t%(duration)s", args.source]
    meta_result = subprocess.run(meta_cmd, capture_output=True, text=True)
    title, uploader, duration = "Sample Video", "YouTube", 0.0
    if meta_result.returncode == 0 and meta_result.stdout.strip():
        parts = meta_result.stdout.strip().split("\t")
        if len(parts) >= 1 and parts[0]:
            title = parts[0]
        if len(parts) >= 2 and parts[1]:
            uploader = parts[1]
        if len(parts) >= 3:
            try:
                duration = float(parts[2])
            except ValueError:
                duration = 0.0

    # Duration measured from the downloaded file takes precedence
    file_duration = probe_duration(video_path)
    if file_duration > 0:
        duration = file_duration

    # Generate structured notes template
    notes_content = generate_notes_template(
        frames=frames,
        source=args.source,
        title=title,
        uploader=uploader,
        duration=duration,
    )

    # Print markdown report
    print("# Video Notes Report")
    print()
    print(f"- **Source:** {args.source}")
    print(f"- **Title:** {title}")
    print(f"- **Duration:** {format_time(duration)} ({duration:.1f}s)")
    print(f"- **Frames:** {len(frames)} @ {fps:.3f} fps")
    print(f"- **Frame size:** 512px wide")
    print("- **Transcript:** none available (native captions missing)")
    print()
    print("## Frames")
    print()
    print(f"Frames live at: {work / 'frames'}")
    print()
    print("**Read each frame path below with the Read tool to view the image.** Frames are in chronological order; `t=MM:SS` is the absolute timestamp in the source video.")
    print()
    for frame in frames:
        print(f"- {frame['path']} (t={format_time(frame['timestamp_seconds'])})")

    print()
    print("## Structured Notes Template")
    print()
    print(notes_content)
    print()
    print("---")
    print(f"_Work dir: {work} — delete when done._")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())