"""GUI and user interaction logic for Random Home Movie Channel."""

from __future__ import annotations

import logging
from pathlib import Path
import random

from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from library import VideoItem, VideoLibrary
from player import SegmentInfo, SegmentPlayer


LOGGER = logging.getLogger(__name__)


class ScanWorker(QObject):
    """Background scanner to keep UI responsive."""

    finished = Signal(list)
    failed = Signal(str)

    def __init__(self, folder: Path) -> None:
        super().__init__()
        self.folder = folder

    @Slot()
    def run(self) -> None:
        try:
            results = VideoLibrary.scan_folder(self.folder)
            self.finished.emit(results)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Random Home Movie Channel")
        self.resize(1200, 760)

        self.library = VideoLibrary()
        self.playlist: list[Path] = []
        self.last_segment: SegmentInfo | None = None

        self._build_ui()
        self.player = SegmentPlayer(self.video_widget, on_next_requested=self.on_next_clicked)
        self.player.segment_changed.connect(self._on_segment_changed)
        self.player.playback_error.connect(self._on_playback_error)
        self.player.queue_empty.connect(self._on_queue_empty)

    def _build_ui(self) -> None:
        container = QWidget(self)
        self.setCentralWidget(container)
        layout = QVBoxLayout(container)

        self.video_widget = QVideoWidget(self)
        self.video_widget.setMinimumHeight(420)
        layout.addWidget(self.video_widget, stretch=2)

        controls_group = QGroupBox("Session Controls", self)
        controls_layout = QGridLayout(controls_group)

        self.folder_line = QLineEdit(self)
        self.folder_line.setReadOnly(True)
        self.pick_folder_btn = QPushButton("Pick Folder")
        self.rescan_btn = QPushButton("Rescan")

        self.start_btn = QPushButton("Start Session")
        self.pause_btn = QPushButton("Pause")
        self.resume_btn = QPushButton("Resume")
        self.next_btn = QPushButton("Next")
        self.stop_btn = QPushButton("Stop")
        self.fullscreen_btn = QPushButton("Toggle Fullscreen")

        self.min_spin = QSpinBox(self)
        self.min_spin.setRange(1, 3600)
        self.min_spin.setValue(60)
        self.max_spin = QSpinBox(self)
        self.max_spin.setRange(1, 7200)
        self.max_spin.setValue(120)

        self.mute_box = QCheckBox("Mute", self)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)

        controls_layout.addWidget(QLabel("Video Folder:"), 0, 0)
        controls_layout.addWidget(self.folder_line, 0, 1, 1, 3)
        controls_layout.addWidget(self.pick_folder_btn, 0, 4)
        controls_layout.addWidget(self.rescan_btn, 0, 5)

        controls_layout.addWidget(QLabel("Min Seconds:"), 1, 0)
        controls_layout.addWidget(self.min_spin, 1, 1)
        controls_layout.addWidget(QLabel("Max Seconds:"), 1, 2)
        controls_layout.addWidget(self.max_spin, 1, 3)

        controls_layout.addWidget(self.start_btn, 2, 0)
        controls_layout.addWidget(self.pause_btn, 2, 1)
        controls_layout.addWidget(self.resume_btn, 2, 2)
        controls_layout.addWidget(self.next_btn, 2, 3)
        controls_layout.addWidget(self.stop_btn, 2, 4)
        controls_layout.addWidget(self.fullscreen_btn, 2, 5)

        controls_layout.addWidget(QLabel("Volume:"), 3, 0)
        controls_layout.addWidget(self.volume_slider, 3, 1, 1, 2)
        controls_layout.addWidget(self.mute_box, 3, 3)

        layout.addWidget(controls_group)

        status_group = QGroupBox("Status", self)
        status_layout = QFormLayout(status_group)
        self.current_file_label = QLabel("-")
        self.segment_label = QLabel("-")
        self.progress_label = QLabel("0 / 0")
        self.library_label = QLabel("0 files")

        status_layout.addRow("Current File:", self.current_file_label)
        status_layout.addRow("Segment:", self.segment_label)
        status_layout.addRow("Session Progress:", self.progress_label)
        status_layout.addRow("Library:", self.library_label)
        layout.addWidget(status_group)

        self.log_view = QTextEdit(self)
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(100)
        layout.addWidget(self.log_view)

        self.pick_folder_btn.clicked.connect(self.on_pick_folder)
        self.rescan_btn.clicked.connect(self.on_rescan_clicked)
        self.start_btn.clicked.connect(self.on_start_clicked)
        self.pause_btn.clicked.connect(self.player_pause)
        self.resume_btn.clicked.connect(self.player_resume)
        self.next_btn.clicked.connect(self.on_next_clicked)
        self.stop_btn.clicked.connect(self.on_stop_clicked)
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        self.mute_box.toggled.connect(self.player_set_mute)
        self.volume_slider.valueChanged.connect(self.player_set_volume)

    @Slot()
    def on_pick_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose Video Folder")
        if not folder:
            return

        self.folder_line.setText(folder)
        self.scan_folder(Path(folder))

    @Slot()
    def on_rescan_clicked(self) -> None:
        folder = self.folder_line.text().strip()
        if not folder:
            QMessageBox.information(self, "Pick a folder", "Please choose a video folder first.")
            return
        self.scan_folder(Path(folder))

    def scan_folder(self, folder: Path) -> None:
        self.append_log(f"Scanning: {folder}")
        self._scan_thread = QThread(self)
        self._scan_worker = ScanWorker(folder)
        self._scan_worker.moveToThread(self._scan_thread)

        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.finished.connect(lambda items: self._on_scan_finished(folder, items))
        self._scan_worker.failed.connect(self._on_scan_failed)

        self._scan_worker.finished.connect(self._scan_thread.quit)
        self._scan_worker.failed.connect(self._scan_thread.quit)
        self._scan_thread.finished.connect(self._scan_worker.deleteLater)
        self._scan_thread.finished.connect(self._scan_thread.deleteLater)

        self._scan_thread.start()

    def _on_scan_finished(self, folder: Path, items: list[VideoItem]) -> None:
        self.library.set_items(folder, items)
        self.library_label.setText(f"{len(items)} files")
        self.append_log(f"Scan complete: {len(items)} .mp4 files")

    def _on_scan_failed(self, message: str) -> None:
        LOGGER.exception("Scan failed: %s", message)
        self.append_log(f"Scan failed: {message}")
        QMessageBox.warning(self, "Scan failed", message)

    @Slot()
    def on_start_clicked(self) -> None:
        items = self.library.items
        if not items:
            QMessageBox.warning(self, "No videos", "No .mp4 files discovered. Pick folder and rescan.")
            return

        min_seconds = self.min_spin.value()
        max_seconds = self.max_spin.value()
        if min_seconds > max_seconds:
            min_seconds, max_seconds = max_seconds, min_seconds

        self.playlist = [item.path for item in items]
        random.shuffle(self.playlist)
        self.player.configure_playlist(self.playlist, loop=True)
        self.player.play_next_segment(min_seconds, max_seconds)
        self.append_log("Session started with shuffled playlist.")

    @Slot()
    def on_next_clicked(self) -> None:
        if not self.player.is_active():
            return

        min_seconds = self.min_spin.value()
        max_seconds = self.max_spin.value()
        if min_seconds > max_seconds:
            min_seconds, max_seconds = max_seconds, min_seconds

        self.player.play_next_segment(min_seconds, max_seconds)

    @Slot()
    def on_stop_clicked(self) -> None:
        self.player.stop()
        self.append_log("Session stopped.")

    @Slot()
    def player_pause(self) -> None:
        self.player.pause()
        self.append_log("Paused.")

    @Slot()
    def player_resume(self) -> None:
        self.player.resume()
        self.append_log("Resumed.")

    @Slot(bool)
    def player_set_mute(self, checked: bool) -> None:
        self.player.set_muted(checked)

    @Slot(int)
    def player_set_volume(self, value: int) -> None:
        self.player.set_volume(value)

    @Slot()
    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()
            event.accept()
            return
        super().keyPressEvent(event)

    @Slot(object)
    def _on_segment_changed(self, info: SegmentInfo) -> None:
        self.last_segment = info
        self.current_file_label.setText(info.file_path.name)
        start_seconds = info.start_ms / 1000
        dur_seconds = info.duration_ms / 1000
        self.segment_label.setText(f"start={start_seconds:.2f}s | duration={dur_seconds:.2f}s")
        self.progress_label.setText(f"{info.playlist_index} / {info.playlist_total}")
        self.append_log(
            f"Playing {info.file_path.name} from {start_seconds:.2f}s for {dur_seconds:.2f}s"
        )

    @Slot(str)
    def _on_playback_error(self, message: str) -> None:
        self.append_log(f"Playback error: {message}. Skipping to next.")
        self.on_next_clicked()

    @Slot()
    def _on_queue_empty(self) -> None:
        self.append_log("Playlist empty. Add videos and rescan.")

    def append_log(self, message: str) -> None:
        LOGGER.info(message)
        self.log_view.append(message)
