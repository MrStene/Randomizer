# Random Home Movie Channel

A **local-only** Python desktop app that scans a folder of home movies and continuously plays randomized `.mp4` segments.

## What it does

- Lets you choose a root folder and recursively discovers `.mp4` files in all subfolders.
- Ignores hidden files/folders and common system folders where practical.
- Starts a session with a freshly shuffled playlist each time you click **Start Session**.
- For each video, chooses:
  - a random segment length between your min/max values
  - a random start timestamp that fits inside the file duration
- Plays only that segment, then auto-advances to the next file.
- Reshuffles and loops automatically at end of playlist (until you stop).

## Controls

- Folder controls: **Choose Folder**, **Rescan**
- Playback controls: **Start Session**, **Pause**, **Resume**, **Next**, **Stop**
- Display controls: **Fullscreen** (press **Esc** to exit fullscreen)
- Segment controls: minimum and maximum segment length (seconds)
- Audio controls: volume slider + mute checkbox

## Status shown in the app

- Current file name
- Segment start time and segment duration
- Session progress (`current / total`)
- Library size (number of discovered files)
- Rolling log messages in a status log area

## Local-only behavior

- No server is started.
- No network sockets or external ports are used.
- No telemetry, updater, or remote API calls.

## Requirements

- Python 3.10+
- `PySide6`

## Install

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

## Notes

- If a file cannot be loaded or played, the app logs the error and skips to the next file.
- Log file path: `logs/random_home_movie_channel.log`.
