"""A small local error log.

The app is a windowed program, so stderr goes nowhere; problems worth keeping
(for example a component that fails to load) are written to
``mosaiq.log`` next to the settings file. The file stays on the PC, is capped
at about 100 KB (plus one older copy) and is never sent anywhere.
Set QRSTUDIO_LOG_DIR to write it somewhere else (used by the tests).
"""
import logging
import logging.handlers
import os
import sys

from utils import settings_store

LOG_NAME = "mosaiq.log"
_logger = None


def log_path():
    folder = os.environ.get("QRSTUDIO_LOG_DIR") or os.path.dirname(settings_store._settings_path())
    return os.path.join(folder, LOG_NAME)


def get_logger():
    global _logger

    if _logger is not None:
        return _logger

    logger = logging.getLogger("mosaiq")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    path = log_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=100_000, backupCount=1, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    except OSError as e:
        # No writable folder: fall back to the console when there is one.
        if sys.stderr is not None:
            logger.addHandler(logging.StreamHandler())
        logger.warning("could not open the log file %s: %s", path, e)

    _logger = logger
    return logger
