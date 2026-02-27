"""Video library discovery and in-memory management."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
from typing import Iterable

LOGGER = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".mp4"}
IGNORED_NAMES = {
    "$recycle.bin",
    "system volume information",
    "__macosx",
}


@dataclass(frozen=True, slots=True)
class VideoItem:
    """Single discovered video entry."""

    path: Path


class VideoLibrary:
    """Session-scoped in-memory library of videos."""

    def __init__(self) -> None:
        self._root: Path | None = None
        self._items: list[VideoItem] = []

    @property
    def root_folder(self) -> Path | None:
        """Current root folder used for discovery."""
        return self._root

    @property
    def items(self) -> list[VideoItem]:
        """Return a copy of discovered items."""
        return list(self._items)

    def update(self, root_folder: Path, items: Iterable[VideoItem]) -> None:
        """Replace current library contents."""
        self._root = root_folder
        self._items = sorted(list(items), key=lambda item: str(item.path).lower())

    @staticmethod
    def scan_folder(root_folder: Path) -> list[VideoItem]:
        """Recursively scan for supported video files.

        Hidden files/folders and common system folders are skipped where practical.
        """
        if not root_folder.exists() or not root_folder.is_dir():
            raise ValueError(f"Invalid folder: {root_folder}")

        discovered: list[VideoItem] = []
        LOGGER.info("Scanning for videos under: %s", root_folder)

        for current_root, dirs, files in os.walk(root_folder):
            dirs[:] = [d for d in dirs if not is_hidden_or_ignored_name(d)]

            current = Path(current_root)
            for filename in files:
                if is_hidden_or_ignored_name(filename):
                    continue
                candidate = current / filename
                if candidate.suffix.lower() in SUPPORTED_EXTENSIONS:
                    discovered.append(VideoItem(path=candidate))

        LOGGER.info("Found %d video(s)", len(discovered))
        return discovered


def is_hidden_or_ignored_name(name: str) -> bool:
    """Best-effort filename or directory-name filtering."""
    if not name:
        return True
    if name.startswith("."):
        return True
    return name.lower() in IGNORED_NAMES
