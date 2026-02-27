"""Desktop GUI for the Random Home Movie Channel app."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
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
    """Background scanner worker."""

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
    """Main window and event handlers."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Random Home Movie Channel")
        self.resize(1280, 800)

        self.library = VideoLibrary()
        self._scan_thread: QThread | None = None

        self._build_ui()
        self.player = SegmentPlayer(self.video_widget)
        self.player.segment_started.connect(self._on_segment_started)
        self.player.playback_error.connect(self._on_playback_error)
        self.player.queue_empty.connect(self._on_queue_empty)

        self.player.set_volume(self.volume_slider.value())

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        self.video_widget = QVideoWidget(self)
        self.video_widget.setMinimumHeight(460)
        layout.addWidget(self.video_widget, stretch=2)

        controls = QGroupBox("Controls", self)
        controls_layout = QGridLayout(controls)

        self.folder_edit = QLineEdit(self)
        self.folder_edit.setReadOnly(True)
        self.pick_folder_btn = QPushButton("Choose Folder", self)
        self.rescan_btn = QPushButton("Rescan", self)

        self.start_btn = QPushButton("Start Session", self)
        self.pause_btn = QPushButton("Pause", self)
        self.resume_btn = QPushButton("Resume", self)
        self.next_btn = QPushButton("Next", self)
        self.stop_btn = QPushButton("Stop", self)
        self.fullscreen_btn = QPushButton("Fullscreen", self)

        self.min_seconds = QSpinBox(self)
        self.min_seconds.setRange(1, 3600)
        self.min_seconds.setValue(60)
        self.max_seconds = QSpinBox(self)
        self.max_seconds.setRange(1, 7200)
        self.max_seconds.setValue(120)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.mute_checkbox = QCheckBox("Mute", self)

        controls_layout.addWidget(QLabel("Folder:"), 0, 0)
        controls_layout.addWidget(self.folder_edit, 0, 1, 1, 4)
        controls_layout.addWidget(self.pick_folder_btn, 0, 5)
        controls_layout.addWidget(self.rescan_btn, 0, 6)

        controls_layout.addWidget(QLabel("Min segment (s):"), 1, 0)
        controls_layout.addWidget(self.min_seconds, 1, 1)
        controls_layout.addWidget(QLabel("Max segment (s):"), 1, 2)
        controls_layout.addWidget(self.max_seconds, 1, 3)

        controls_layout.addWidget(self.start_btn, 2, 0)
        controls_layout.addWidget(self.pause_btn, 2, 1)
        controls_layout.addWidget(self.resume_btn, 2, 2)
        controls_layout.addWidget(self.next_btn, 2, 3)
        controls_layout.addWidget(self.stop_btn, 2, 4)
        controls_layout.addWidget(self.fullscreen_btn, 2, 5)

        controls_layout.addWidget(QLabel("Volume:"), 3, 0)
        controls_layout.addWidget(self.volume_slider, 3, 1, 1, 2)
        controls_layout.addWidget(self.mute_checkbox, 3, 3)

        layout.addWidget(controls)

        status = QGroupBox("Status", self)
        status_layout = QFormLayout(status)
        self.current_file_label = QLabel("-")
        self.segment_label = QLabel("-")
        self.progress_label = QLabel("0 / 0")
        self.library_count_label = QLabel("0 files")
        status_layout.addRow("Current file:", self.current_file_label)
        status_layout.addRow("Segment:", self.segment_label)
        status_layout.addRow("Session progress:", self.progress_label)
        status_layout.addRow("Library:", self.library_count_label)
        layout.addWidget(status)

        self.log_text = QTextEdit(self)
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(120)
        layout.addWidget(self.log_text)

        self.pick_folder_btn.clicked.connect(self.on_pick_folder)
        self.rescan_btn.clicked.connect(self.on_rescan)
        self.start_btn.clicked.connect(self.on_start_session)
        self.pause_btn.clicked.connect(self.on_pause)
        self.resume_btn.clicked.connect(self.on_resume)
        self.next_btn.clicked.connect(self.on_next)
        self.stop_btn.clicked.connect(self.on_stop)
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        self.volume_slider.valueChanged.connect(self.player_set_volume)
        self.mute_checkbox.toggled.connect(self.player_set_mute)

    @Slot()
    def on_pick_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select video folder")
        if not folder:
            return
        self.folder_edit.setText(folder)
        self._scan_async(Path(folder))

    @Slot()
    def on_rescan(self) -> None:
        text = self.folder_edit.text().strip()
        if not text:
            QMessageBox.information(self, "Folder required", "Please choose a folder first.")
            return
        self._scan_async(Path(text))

    def _scan_async(self, folder: Path) -> None:
        if self._scan_thread and self._scan_thread.isRunning():
            QMessageBox.information(self, "Scan in progress", "Please wait for the current scan to finish.")
            return

        self._append_log(f"Scanning folder: {folder}")

        worker = ScanWorker(folder)
        thread = QThread(self)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(lambda items: self._on_scan_finished(folder, items))
        worker.failed.connect(self._on_scan_failed)

        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._scan_thread = thread
        thread.start()

    def _on_scan_finished(self, folder: Path, items: list[VideoItem]) -> None:
        self.library.update(folder, items)
        self.library_count_label.setText(f"{len(items)} files")
        self._append_log(f"Scan complete: {len(items)} .mp4 file(s)")

    def _on_scan_failed(self, message: str) -> None:
        LOGGER.error("Library scan failed: %s", message)
        self._append_log(f"Scan failed: {message}")
        QMessageBox.warning(self, "Scan failed", message)

    @Slot()
    def on_start_session(self) -> None:
        items = self.library.items
        if not items:
            QMessageBox.warning(self, "No videos", "No .mp4 videos discovered. Choose folder and rescan.")
            return

        min_seconds, max_seconds = self._normalized_duration_range()
        paths = [item.path for item in items]

        self.player.configure_session(paths, min_seconds=min_seconds, max_seconds=max_seconds, loop=True)
        self.player.start()
        self._append_log("Session started. Playlist shuffled.")

    @Slot()
    def on_pause(self) -> None:
        self.player.pause()
        self._append_log("Paused")

    @Slot()
    def on_resume(self) -> None:
        self.player.resume()
        self._append_log("Resumed")

    @Slot()
    def on_next(self) -> None:
        if self.player.is_active():
            self.player.next_segment()

    @Slot()
    def on_stop(self) -> None:
        self.player.stop()
        self._append_log("Stopped")

    @Slot(int)
    def player_set_volume(self, value: int) -> None:
        self.player.set_volume(value)

    @Slot(bool)
    def player_set_mute(self, checked: bool) -> None:
        self.player.set_muted(checked)

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
    def _on_segment_started(self, info: SegmentInfo) -> None:
        start = info.start_ms / 1000
        duration = info.duration_ms / 1000
        self.current_file_label.setText(info.file_path.name)
        self.segment_label.setText(f"start={start:.2f}s, duration={duration:.2f}s")
        self.progress_label.setText(f"{info.playlist_index} / {info.playlist_total}")
        self._append_log(
            f"Now playing: {info.file_path.name} | start {start:.2f}s | duration {duration:.2f}s"
        )

    @Slot(str)
    def _on_playback_error(self, message: str) -> None:
        self._append_log(f"Playback error: {message}; skipping.")

    @Slot()
    def _on_queue_empty(self) -> None:
        self._append_log("No items available in session queue.")

    def _normalized_duration_range(self) -> tuple[int, int]:
        min_seconds = self.min_seconds.value()
        max_seconds = self.max_seconds.value()
        if min_seconds > max_seconds:
            min_seconds, max_seconds = max_seconds, min_seconds
        return min_seconds, max_seconds

    def _append_log(self, message: str) -> None:
        LOGGER.info(message)
        self.log_text.append(message)
