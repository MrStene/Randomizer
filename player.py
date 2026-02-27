"""Playback controller for random video segments."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import random
from typing import Callable

from PySide6.QtCore import QTimer, QUrl, QObject, Signal, Slot
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class SegmentInfo:
    """Runtime details for a currently scheduled/playing segment."""

    file_path: Path
    start_ms: int
    duration_ms: int
    playlist_index: int
    playlist_total: int


class SegmentPlayer(QObject):
    """Controls media playback and segment scheduling over a shuffled playlist."""

    segment_changed = Signal(object)  # SegmentInfo
    playback_error = Signal(str)
    queue_empty = Signal()

    def __init__(self, video_widget: QVideoWidget, on_next_requested: Callable[[], None]) -> None:
        super().__init__()
        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(video_widget)

        self._segment_end_timer = QTimer(self)
        self._segment_end_timer.setSingleShot(True)
        self._segment_end_timer.timeout.connect(on_next_requested)

        self._playlist: list[Path] = []
        self._index = -1
        self._loop = True
        self._playing = False

        self._pending_start_ms: int | None = None

        self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.media_player.errorOccurred.connect(self._on_error)

    def set_volume(self, value: int) -> None:
        self.audio_output.setVolume(max(0.0, min(1.0, value / 100.0)))

    def set_muted(self, is_muted: bool) -> None:
        self.audio_output.setMuted(is_muted)

    def configure_playlist(self, playlist: list[Path], loop: bool = True) -> None:
        self._playlist = list(playlist)
        self._index = -1
        self._loop = loop
        self._playing = False
        self._segment_end_timer.stop()

    def is_active(self) -> bool:
        return self._playing

    def pause(self) -> None:
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            if self._segment_end_timer.isActive():
                self._remaining_ms = self._segment_end_timer.remainingTime()
                self._segment_end_timer.stop()

    def resume(self) -> None:
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PausedState:
            self.media_player.play()
            remaining = getattr(self, "_remaining_ms", None)
            if remaining is not None and remaining > 0:
                self._segment_end_timer.start(remaining)

    def stop(self) -> None:
        self._playing = False
        self._segment_end_timer.stop()
        self.media_player.stop()

    def play_next_segment(self, min_seconds: int, max_seconds: int) -> None:
        if not self._playlist:
            self.queue_empty.emit()
            return

        self._playing = True
        self._index += 1
        if self._index >= len(self._playlist):
            if not self._loop:
                self.stop()
                self.queue_empty.emit()
                return
            random.shuffle(self._playlist)
            self._index = 0

        file_path = self._playlist[self._index]
        self._schedule_segment(file_path, min_seconds, max_seconds)

    def _schedule_segment(self, file_path: Path, min_seconds: int, max_seconds: int) -> None:
        min_seconds = max(1, min_seconds)
        max_seconds = max(min_seconds, max_seconds)

        # Duration is unknown until media is loaded; store plan and finish in callback.
        self._pending_file = file_path
        self._pending_min_seconds = min_seconds
        self._pending_max_seconds = max_seconds
        self._pending_start_ms = None

        self.media_player.stop()
        self.media_player.setSource(QUrl.fromLocalFile(str(file_path)))

    @Slot("QMediaPlayer::MediaStatus")
    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status != QMediaPlayer.MediaStatus.LoadedMedia:
            return

        if not hasattr(self, "_pending_file"):
            return

        duration_ms = self.media_player.duration()
        if duration_ms <= 0:
            self.playback_error.emit(f"Could not read duration: {self._pending_file}")
            return

        min_ms = self._pending_min_seconds * 1000
        max_ms = self._pending_max_seconds * 1000

        if duration_ms <= min_ms:
            segment_ms = duration_ms
            start_ms = 0
        else:
            segment_ms = random.randint(min_ms, max_ms)
            segment_ms = min(segment_ms, duration_ms)
            max_start = max(0, duration_ms - segment_ms)
            start_ms = random.randint(0, max_start) if max_start > 0 else 0

        self._pending_start_ms = start_ms

        info = SegmentInfo(
            file_path=self._pending_file,
            start_ms=start_ms,
            duration_ms=segment_ms,
            playlist_index=self._index + 1,
            playlist_total=len(self._playlist),
        )
        self.segment_changed.emit(info)

        self.media_player.setPosition(start_ms)
        self.media_player.play()
        self._segment_end_timer.start(segment_ms)

        del self._pending_file

    @Slot("QMediaPlayer::Error", str)
    def _on_error(self, _error: QMediaPlayer.Error, error_string: str) -> None:
        message = error_string or "Unknown playback error"
        LOGGER.error("Playback error: %s", message)
        self.playback_error.emit(message)
