"""Application entry point for Random Home Movie Channel."""

from __future__ import annotations

import logging
from pathlib import Path
import sys

from PySide6.QtWidgets import QApplication

from ui import MainWindow


def configure_logging() -> None:
    """Set up local console + file logging."""
    log_dir = Path.cwd() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "random_home_movie_channel.log"

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)

    root.addHandler(console)
    root.addHandler(file_handler)

    logging.getLogger(__name__).info("Logging initialized: %s", log_path)


def main() -> int:
    """Launch the desktop GUI."""
    configure_logging()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
