"""Logging filters for production-safe handlers."""

from __future__ import annotations

import logging


class NoExcInfoFilter(logging.Filter):
    """Strip exception tracebacks so file logs contain messages only."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.exc_info = None
        record.exc_text = None
        return True
