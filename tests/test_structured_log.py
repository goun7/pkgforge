"""Coverage itmesi — core/structured_log.py (JSON loglama)."""
from __future__ import annotations

import json
import logging

from core.structured_log import (
    HumanFormatter,
    JSONFormatter,
    get_logger,
    setup_structured_logging,
)


def _record(msg="merhaba", level=logging.INFO, **extra):
    return logging.LogRecord(
        name="pkgforge.test", level=level, pathname=__file__, lineno=10,
        msg=msg, args=None, exc_info=None)


def test_json_formatter_valid_json_with_fields():
    rec = _record()
    out = json.loads(JSONFormatter().format(rec))
    assert out["message"] == "merhaba"
    assert out["level"] == "INFO"
    assert out["logger"] == "pkgforge.test"
    assert "timestamp" in out


def test_json_formatter_includes_exception():
    try:
        raise ValueError("hata")
    except ValueError:
        import sys

        rec = logging.LogRecord(
            name="pkgforge.x", level=logging.ERROR, pathname=__file__,
            lineno=1, msg="hatali", args=None, exc_info=sys.exc_info())
    out = json.loads(JSONFormatter().format(rec))
    assert out["exception"]["type"] == "ValueError"
    assert "traceback" in out["exception"]


def test_json_formatter_includes_extra_fields():
    rec = _record()
    rec.package_name = "deneme"
    rec.duration_ms = 123
    out = json.loads(JSONFormatter().format(rec))
    assert out["package_name"] == "deneme"
    assert out["duration_ms"] == 123


def test_human_formatter_readable():
    rec = _record("selam")
    out = HumanFormatter(use_colors=False).format(rec)
    assert "selam" in out
    assert "test" in out  # kisa logger adi


def test_setup_structured_logging_json_mode():
    setup_structured_logging(json_mode=True)
    root = logging.getLogger("pkgforge")
    assert any(isinstance(h.formatter, JSONFormatter) for h in root.handlers)
    setup_structured_logging(json_mode=False)  # temizle


def test_get_logger_child():
    lg = get_logger("modul")
    assert lg.name == "pkgforge.modul"
