"""PkgForge — Structured JSON Logging.

Provides a JSON log formatter for use with log aggregation tools
(ELK, Datadog, CloudWatch, etc.). Falls back to standard formatting
when not in structured mode.

Usage:
    from core.structured_log import setup_structured_logging
    setup_structured_logging(json_mode=True)
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Formats log records as JSON for structured log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        # Add extra fields
        for key in ["package_name", "duration_ms", "success", "method", "error"]:
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class HumanFormatter(logging.Formatter):
    """Human-readable formatter for terminal output."""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors and sys.stderr.isatty()

    def format(self, record: logging.LogRecord) -> str:
        ts = time.strftime("%H:%M:%S", time.localtime(record.created))
        level = record.levelname.ljust(8)

        if self.use_colors:
            color = self.COLORS.get(record.levelname, "")
            level = f"{color}{level}{self.RESET}"

        msg = record.getMessage()
        name = record.name.split(".")[-1]  # Short logger name

        return f"{ts} {level} [{name}] {msg}"


def setup_structured_logging(
    json_mode: bool = False,
    level: int = logging.INFO,
    log_file: str | None = None,
) -> None:
    """Configure PkgForge logging.

    Args:
        json_mode: If True, use JSON formatter. Otherwise human-readable.
        level: Minimum log level.
        log_file: Optional file path for log output.
    """
    root = logging.getLogger("pkgforge")
    root.setLevel(level)

    # Remove existing handlers
    root.handlers.clear()

    formatter: logging.Formatter
    if json_mode:
        formatter = JSONFormatter()
    else:
        formatter = HumanFormatter()

    # Console handler
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    root.addHandler(console)

    # Optional file handler
    if log_file:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3
        )
        file_handler.setFormatter(JSONFormatter())  # Always JSON for files
        root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a child logger for a specific module."""
    return logging.getLogger(f"pkgforge.{name}")
