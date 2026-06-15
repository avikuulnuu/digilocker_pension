"""Production-safe logging configuration for the issuer API logger."""

from __future__ import annotations

import sys
from pathlib import Path


def _normalize_log_path(raw_path: str) -> Path | None:
    path = (raw_path or "").strip()
    if not path:
        return None
    return Path(path)


def _ensure_log_directory(log_path: Path, *, base_dir: Path) -> bool:
    """Create the log directory only for project-local paths (dev convenience)."""
    log_dir = log_path.resolve().parent
    base = base_dir.resolve()
    if not log_dir.exists():
        try:
            log_dir.relative_to(base)
        except ValueError:
            return False
        log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir.is_dir()


def build_logging_config(
    *,
    debug: bool,
    verbose: bool,
    log_path: str,
    max_bytes: int,
    backup_count: int,
    base_dir: Path,
    running_tests: bool,
) -> dict:
    """Build Django LOGGING dict with optional rotated API log file.

    Production safety:
    - File handler is INFO+ only (no HMAC/body DEBUG dumps on disk).
    - Console may emit DEBUG when ``debug`` or ``verbose`` is enabled.
    - File handler is skipped during tests and when the path is unset.
    - Absolute log paths must exist and be writable (ops creates /var/log/...).
    """
    issuer_console_level = "DEBUG" if (debug or verbose) else "INFO"
    handlers: dict = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "level": issuer_console_level,
        },
    }
    issuer_handlers = ["console"]

    resolved = _normalize_log_path(log_path)
    if resolved and not running_tests:
        resolved = resolved.resolve()
        use_file_handler = False
        if _ensure_log_directory(resolved, base_dir=base_dir):
            use_file_handler = True
        elif resolved.parent.is_dir():
            use_file_handler = True
        else:
            print(
                f"WARNING: ISSUER_API_LOG_PATH parent directory does not exist: "
                f"{resolved.parent}. API file logging disabled; using console only.",
                file=sys.stderr,
            )

        if use_file_handler:
            try:
                with open(resolved, "a", encoding="utf-8"):
                    pass
            except OSError as exc:
                print(
                    f"WARNING: Could not open ISSUER_API_LOG_PATH={resolved!s}: {exc}. "
                    "API file logging disabled; using console only.",
                    file=sys.stderr,
                )
            else:
                handlers["issuer_api_file"] = {
                    "class": "logging.handlers.RotatingFileHandler",
                    "formatter": "verbose",
                    "filename": str(resolved),
                    "maxBytes": max_bytes,
                    "backupCount": backup_count,
                    "encoding": "utf-8",
                    # Never write DEBUG to disk — avoids HMAC/body dumps in log files.
                    "level": "INFO",
                    "filters": ["no_exc_info"],
                }
                issuer_handlers.append("issuer_api_file")

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "no_exc_info": {
                "()": "config.log_filters.NoExcInfoFilter",
            },
        },
        "formatters": {
            "verbose": {
                "format": "{asctime} {levelname} {name} {message}",
                "style": "{",
            },
        },
        "handlers": handlers,
        "loggers": {
            "issuer": {
                "handlers": issuer_handlers,
                "level": issuer_console_level,
                "propagate": False,
            },
            "django": {
                "handlers": ["console"],
                "level": "WARNING",
            },
        },
    }
