"""Playback orchestration for randomized local video segments."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import random
from typing import Sequence

from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SegmentPlan:
    """Chosen segment boundaries in milliseconds."""

    start_ms: int
    duration_ms: int


@dataclass(frozen=True, slots=True)
class SegmentInfo:
    """Runtime payload emitted to UI for status updates."""

    file_path: Path
    start_ms: int
    duration_ms: int
    playlist_index: int
    playlist_total: int


class SessionQueue:
    """Shuffled queue that reshuffles on each full pass when loop is enabled."""

    def __init__(self) -> None:
        self._loop = True
        self._source: list[Path] = []
        self._queue: list[Path] = []
        self._index = 0

    def configure(self, paths: Sequence[Path], loop: bool = True) -> None:
        self._loop = loop
        self._source = list(paths)
        self._queue = list(self._source)
        random.shuffle(self._queue)
        self._index = 0

    @property
    def total(self) -> int:
        return len(self._queue)

    @property
    def index(self) -> int:
        return self._index

    def next_path(self) -> Path | None:
        if not self._queue:
            return None
        if self._index >= len(self._queue):
            if not self._loop:
                return None
            random.shuffle(self._queue)
            self._index = 0

        path = self._queue[self._index]
        self._index += 1
        return path


def choose_segment(duration_ms: int, min_seconds: int, max_seconds: int) -> SegmentPlan:
    """Choose random segment boundaries that fit inside media duration."""
    if duration_ms <= 0:
        raise ValueError("Media duration must be positive")

    min_seconds = max(1, min_seconds)
    max_seconds = max(min_seconds, max_seconds)

    min_ms = min_seconds * 1000
    max_ms = max_seconds * 1000

    if duration_ms <= min_ms:
        return SegmentPlan(start_ms=0, duration_ms=duration_ms)

    duration_choice = random.randint(min_ms, max_ms)
    duration_choice = min(duration_choice, duration_ms)

    max_start = max(0, duration_ms - duration_choice)
    start_ms = random.randint(0, max_start) if max_start else 0
    return SegmentPlan(start_ms=start_ms, duration_ms=duration_choice)


class SegmentPlayer(QObject):
    """Qt media player wrapper implementing random segmented playback."""

    segment_started = Signal(object)  # SegmentInfo
    playback_error = Signal(str)
    queue_empty = Signal()

    def __init__(self, video_widget: QVideoWidget) -> None:
        super().__init__()
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._player.setAudioOutput(self._audio)
        self._player.setVideoOutput(video_widget)

        self._segment_timer = QTimer(self)
        self._segment_timer.setSingleShot(True)
        self._segment_timer.timeout.connect(self.next_segment)

        self._session = SessionQueue()
        self._active = False
        self._paused_remaining_ms: int | None = None

        self._min_seconds = 60
        self._max_seconds = 120

        self._pending_file: Path | None = None
        self._pending_duration_retries = 0

        self._player.mediaStatusChanged.connect(self._on_media_status_changed)
        self._player.errorOccurred.connect(self._on_error)

    def configure_session(self, playlist: Sequence[Path], min_seconds: int, max_seconds: int, loop: bool) -> None:
        """Initialize a new session with a newly shuffled queue."""
        self.stop()
        self._session.configure(playlist, loop=loop)
        self._min_seconds = min_seconds
        self._max_seconds = max_seconds

    def start(self) -> None:
        """Start playback from next queue item."""
        if self._session.total == 0:
            self.queue_empty.emit()
            return
        self._active = True
        self.next_segment()

    @Slot()
    def next_segment(self) -> None:
        """Advance to next random source segment."""
        if not self._active:
            return

        self._segment_timer.stop()
        self._paused_remaining_ms = None

        next_path = self._session.next_path()
        if next_path is None:
            self._active = False
            self.queue_empty.emit()
            return

        self._pending_file = next_path
        self._pending_duration_retries = 0

        self._player.stop()
        self._player.setSource(QUrl.fromLocalFile(str(next_path)))

    def stop(self) -> None:
        """Stop playback and clear active session state."""
        self._active = False
        self._pending_file = None
        self._segment_timer.stop()
        self._paused_remaining_ms = None
        self._player.stop()

    def pause(self) -> None:
        """Pause current segment playback."""
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
            if self._segment_timer.isActive():
                self._paused_remaining_ms = self._segment_timer.remainingTime()
                self._segment_timer.stop()

    def resume(self) -> None:
        """Resume playback and segment timer."""
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PausedState:
            self._player.play()
            if self._paused_remaining_ms and self._paused_remaining_ms > 0:
                self._segment_timer.start(self._paused_remaining_ms)

    def set_volume(self, level: int) -> None:
        self._audio.setVolume(max(0.0, min(1.0, level / 100.0)))

    def set_muted(self, muted: bool) -> None:
        self._audio.setMuted(muted)

    def is_active(self) -> bool:
        return self._active

    @Slot("QMediaPlayer::MediaStatus")
    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if self._pending_file is None:
            return

        if status not in {
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        }:
            return

        duration_ms = self._player.duration()
        if duration_ms <= 0 and self._pending_duration_retries < 10:
            self._pending_duration_retries += 1
            QTimer.singleShot(100, lambda: self._on_media_status_changed(status))
            return

        if duration_ms <= 0:
            self.playback_error.emit(f"Unable to determine duration for {self._pending_file.name}")
            self._pending_file = None
            self.next_segment()
            return

        plan = choose_segment(duration_ms, self._min_seconds, self._max_seconds)
        current_file = self._pending_file
        self._pending_file = None

        self._player.setPosition(plan.start_ms)
        self._player.play()
        self._segment_timer.start(plan.duration_ms)

        self.segment_started.emit(
            SegmentInfo(
                file_path=current_file,
                start_ms=plan.start_ms,
                duration_ms=plan.duration_ms,
                playlist_index=self._session.index,
                playlist_total=self._session.total,
            )
        )

    @Slot("QMediaPlayer::Error", str)
    def _on_error(self, _error: QMediaPlayer.Error, message: str) -> None:
        error_message = message or "Unknown playback error"
        LOGGER.error("Playback error: %s", error_message)
        self.playback_error.emit(error_message)
        self._pending_file = None
        if self._active:
            self.next_segment()
