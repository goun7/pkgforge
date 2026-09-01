"""PkgForge — Structured JSON Logging.

Provides a JSON log formatter for use with log aggregation tools
(ELK, Datadog, CloudWatch, etc.). Falls back to standard formatting
when not in structured mode.

Tur-55 B5: request-id / trace-id propagation via contextvars — every log
record emitted inside a `with request_context("abc123")` block carries
the id, enabling distributed-trace style correlation in aggregated logs.

Usage:
    from core.structured_log import (
        setup_structured_logging, get_logger, request_context,
    )
    setup_structured_logging(json_mode=True)
    log = get_logger("core.pipeline")
    with request_context() as rid:
        log.info("started", extra={"package_name": "foo.deb"})
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import ClassVar

# ---- request-id context ----------------------------------------------------

_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "pkgforge_request_id", default=None
)


class RequestContextFilter(logging.Filter):
    """Inject the active request-id (if any) into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        rid = _request_id_var.get()
        if rid is not None:
            record.request_id = rid
        return True


class request_context:
    """Context manager that sets a request/trace id for the current task.

    ```
    with request_context() as rid:
        log.info("hello")  # log record gets request_id=rid
    ```

    The id is auto-generated (uuid4 hex) if `rid` is not provided. Nested
    contexts inherit the outer id unless they explicitly pass a new one.
    """

    __slots__ = ("_new_id", "_token", "id")

    def __init__(self, rid: str | None = None) -> None:
        self._new_id = rid
        self.id: str = ""
        self._token: contextvars.Token[str | None] | None = None

    def __enter__(self) -> str:
        outer = _request_id_var.get()
        if self._new_id is not None:
            self.id = self._new_id
        elif outer is not None:
            # Nested context: inherit outer id so logs still correlate.
            self.id = outer
        else:
            # Short, grep-friendly id (first 12 hex of uuid4).
            self.id = uuid.uuid4().hex[:12]
        self._token = _request_id_var.set(self.id)
        return self.id

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._token is not None:
            _request_id_var.reset(self._token)
            self._token = None


def current_request_id() -> str | None:
    """Return the active request-id (or None if no context is open)."""
    return _request_id_var.get()


def new_request_id() -> str:
    """Generate a fresh 12-hex request id (does not set the context)."""
    return uuid.uuid4().hex[:12]


# ---- formatters ------------------------------------------------------------

class JSONFormatter(logging.Formatter):
    """Formats log records as JSON for structured log aggregation."""

    EXTRA_FIELDS: ClassVar[tuple[str, ...]] = (
        "package_name",
        "duration_ms",
        "success",
        "method",
        "error",
        "request_id",
    )

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
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

        # request_id always present (nullable) so consumers can rely on key.
        rid = getattr(record, "request_id", None)
        log_entry["request_id"] = rid

        # Add exception info if present
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        # Add extra fields
        for key in self.EXTRA_FIELDS:
            val = getattr(record, key, None)
            if val is not None and key not in log_entry:
                log_entry[key] = val

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class HumanFormatter(logging.Formatter):
    """Human-readable formatter for terminal output."""

    COLORS: ClassVar[dict[str, str]] = {
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
        rid = getattr(record, "request_id", None)
        rid_part = f" [rid:{rid}]" if rid else ""
        return f"{ts} {level} [{name}]{rid_part} {msg}"


# ---- setup -----------------------------------------------------------------

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

    # Console handler — Filter injects request_id on every record.
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    console.addFilter(RequestContextFilter())
    root.addHandler(console)

    # Optional file handler — always JSON, also request-id aware.
    if log_file:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3
        )
        file_handler.setFormatter(JSONFormatter())
        file_handler.addFilter(RequestContextFilter())
        root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a child logger for a specific module."""
    return logging.getLogger(f"pkgforge.{name}")
