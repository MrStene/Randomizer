# Random Home Movie Channel

A local-only desktop app that plays random segments from `.mp4` files in a chosen folder tree.

## Features

- Recursively scans a folder and subfolders for `.mp4` videos.
- Creates a new shuffled playlist each session start.
- For each video, seeks to a random timestamp and plays for a random duration between min/max limits.
- Auto-advances to the next video segment and reshuffles/loops when the playlist ends.
- Controls: Start Session, Pause, Resume, Next, Stop, fullscreen toggle (Esc exits fullscreen).
- Status display for current file, segment timing, playlist progress, and library size.
- Local logging to console and `logs/random_home_movie_channel.log`.

## Requirements

- Python 3.10+
- `PySide6`

## Install

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

## Notes

- This app is local-only and makes no network calls.
- If a video fails to load/play, the app logs the error and skips to the next item.
- Hidden/system-like folders are skipped during scanning when practical.
