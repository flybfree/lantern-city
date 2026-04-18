"""Logging configuration for Lantern City.

Enable debug logging by setting the environment variable:

    LANTERN_DEBUG=1

Logs are written to a file alongside the database (e.g. my-city.log).
Nothing is written to stderr so the TUI display is never corrupted.

Usage in any module:

    from lantern_city.log import get_logger
    log = get_logger(__name__)
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

_configured = False


def configure(database_path: str | Path | None = None) -> None:
    """Call once at process startup (from CLI or TUI main)."""
    global _configured
    if _configured:
        return
    _configured = True

    if not os.getenv("LANTERN_DEBUG"):
        logging.getLogger("lantern_city").addHandler(logging.NullHandler())
        return

    log_path = (
        Path(database_path).with_suffix(".log")
        if database_path
        else Path("lantern-city.log")
    )

    handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
            datefmt="%H:%M:%S",
        )
    )

    root = logging.getLogger("lantern_city")
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)
    root.info("=== Lantern City debug log started (db=%s) ===", database_path)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
