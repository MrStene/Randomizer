"""Entry point for the Random Home Movie Channel application."""

from __future__ import annotations

import logging
from pathlib import Path
import sys

from PySide6.QtWidgets import QApplication

from ui import MainWindow


def configure_logging() -> None:
    """Configure console and file logging for the application."""
    log_dir = Path.cwd() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "random_home_movie_channel.log"

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    root_logger.handlers.clear()
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)

    logging.getLogger(__name__).info("Logging initialized. Writing logs to %s", log_file)


def main() -> int:
    """Launch the GUI application."""
    configure_logging()

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
