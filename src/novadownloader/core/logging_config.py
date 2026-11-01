"""Bounded local logs; never collect process environments or authentication headers."""

import logging
import os
import re
from logging.handlers import RotatingFileHandler

from novadownloader.core.paths import AppPaths


def safe_detail(value: object) -> str:
    text = str(value)
    text = re.sub(r"https?://\S+", "[URL]", text)
    text = re.sub(r"(?i)(token|password|authorization|cookie)\s*[:=]\s*\S+", r"\1=[REDACTED]", text)
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    return text[:4000]


def get_logger() -> logging.Logger:
    logger = logging.getLogger("novadownloader")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        logger.propagate = False
        try:
            directory = AppPaths.discover().state
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            path = directory / "application.log"
            fd = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
            os.close(fd)
            handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
        except OSError:
            handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def log_failure(context: str, error: object) -> None:
    get_logger().warning("%s: %s", context, safe_detail(error))
