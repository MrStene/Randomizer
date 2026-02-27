"""Library management and video discovery utilities."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
from typing import Iterable


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class VideoItem:
    """Represents a discovered local video file."""

    path: Path


class VideoLibrary:
    """In-memory video library with recursive discovery support."""

    def __init__(self) -> None:
        self._items: list[VideoItem] = []
        self._root_folder: Path | None = None

    @property
    def root_folder(self) -> Path | None:
        """Currently selected root folder."""
        return self._root_folder

    @property
    def items(self) -> list[VideoItem]:
        """Copy of currently discovered videos."""
        return list(self._items)

    def set_items(self, root_folder: Path, items: Iterable[VideoItem]) -> None:
        """Update the library after a scan completes."""
        self._root_folder = root_folder
        self._items = list(items)

    @staticmethod
    def scan_folder(root_folder: Path) -> list[VideoItem]:
        """Recursively discover .mp4 files under root_folder.

        Hidden/system-like folders and hidden files are skipped when practical.
        """
        LOGGER.info("Scanning folder: %s", root_folder)
        if not root_folder.exists() or not root_folder.is_dir():
            raise ValueError(f"Invalid folder: {root_folder}")

        discovered: list[VideoItem] = []

        for current_root, dirs, files in os.walk(root_folder):
            dirs[:] = [d for d in dirs if not _is_hidden_or_system_name(d)]

            current_path = Path(current_root)
            for filename in files:
                if _is_hidden_or_system_name(filename):
                    continue
                full_path = current_path / filename
                if full_path.suffix.lower() == ".mp4":
                    discovered.append(VideoItem(path=full_path))

        LOGGER.info("Discovered %d mp4 files", len(discovered))
        return discovered


def _is_hidden_or_system_name(name: str) -> bool:
    """Best-effort hidden/system detection based on path segment names."""
    if name.startswith("."):
        return True
    return name.lower() in {
        "$recycle.bin",
        "system volume information",
        "__macosx",
        "node_modules",
    }
