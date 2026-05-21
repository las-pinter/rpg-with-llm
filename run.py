"""Entry point for the LLM-Powered RPG.

Run this module to start the Flask development server::

    python run.py
    python run.py  # also supports RPG_LOG_LEVEL=DEBUG env var
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.server import app


def _configure_logging() -> None:
    """Configure logging based on environment variables.

    - ``RPG_LOG_LEVEL`` — Set to ``DEBUG`` for verbose logging (default: INFO)
    - ``RPG_LOG_DIR`` — Custom log directory (default: ``logs/``)
    """
    log_level_name = os.environ.get("RPG_LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    log_dir = Path(os.environ.get("RPG_LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "rpg.log"

    # File handler — always DEBUG level for the file
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5_242_880,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)

    # Console handler — respects the configured log level
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        "[%(levelname)s] %(name)s: %(message)s",
    )
    console_handler.setFormatter(console_formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Root catches everything; handlers filter
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Quiet noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


if __name__ == "__main__":
    _configure_logging()
    app.run(debug=False, host="0.0.0.0", port=5000)
