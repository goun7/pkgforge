"""Tur-55 B5: request_id context propagates to JSON / human log records."""
from __future__ import annotations

import io
import json
import logging

from core.structured_log import (
    HumanFormatter,
    JSONFormatter,
    RequestContextFilter,
    current_request_id,
    new_request_id,
    request_context,
)


def _capture_root(level: int = logging.INFO) -> io.StringIO:
    """Attach a fresh stream handler to the pkgforge root logger and return buf."""
    root = logging.getLogger("pkgforge")
    root.handlers.clear()
    root.setLevel(level)
    buf = io.StringIO()
    h = logging.StreamHandler(buf)
    h.setFormatter(JSONFormatter())
    h.addFilter(RequestContextFilter())
    root.addHandler(h)
    return buf


def test_request_id_isolated_by_default() -> None:
    """No open context → log records have request_id=None (key always present)."""
    buf = _capture_root()
    log = logging.getLogger("pkgforge.test.isolated")
    log.info("hello")
    rec = json.loads(buf.getvalue().strip())
    assert "request_id" in rec
    assert rec["request_id"] is None


def test_request_context_injects_id() -> None:
    """Inside a request_context block, request_id is set on every record."""
    buf = _capture_root()
    log = logging.getLogger("pkgforge.test.ctx")
    with request_context("abc123") as rid:
        assert rid == "abc123"
        log.info("step1")
        log.info("step2", extra={"package_name": "foo.deb"})
    lines = [ln for ln in buf.getvalue().strip().splitlines() if ln]
    assert len(lines) == 2
    a = json.loads(lines[0])
    b = json.loads(lines[1])
    assert a["request_id"] == "abc123"
    assert b["request_id"] == "abc123"
    assert b["package_name"] == "foo.deb"
    # Outside the block — no id
    log.info("after")
    c = json.loads(buf.getvalue().strip().splitlines()[-1])
    assert c["request_id"] is None


def test_request_context_auto_generates_id() -> None:
    """Without explicit rid, a short 12-hex id is generated."""
    with request_context() as rid:
        assert isinstance(rid, str)
        assert len(rid) == 12
        assert current_request_id() == rid
    assert current_request_id() is None


def test_nested_context_inherits_outer_id() -> None:
    """Nested request_context() without explicit rid keeps the outer id."""
    with request_context("outer-id"):
        assert current_request_id() == "outer-id"
        with request_context():
            assert current_request_id() == "outer-id"
        # Still outer after inner exits.
        assert current_request_id() == "outer-id"


def test_new_request_id_helper() -> None:
    """new_request_id returns 12 hex chars and does NOT set the context."""
    rid = new_request_id()
    assert len(rid) == 12
    assert all(c in "0123456789abcdef" for c in rid)
    assert current_request_id() is None  # helper must not pollute context


def test_human_formatter_shows_rid() -> None:
    """HumanFormatter includes [rid:...] in output when an id is active."""
    fmt = HumanFormatter(use_colors=False)
    record = logging.LogRecord(
        name="pkgforge.test.human",
        level=logging.INFO,
        pathname="x.py", lineno=1, msg="hi", args=(), exc_info=None,
    )
    record.request_id = "deadbeef"
    out = fmt.format(record)
    assert "[rid:deadbeef]" in out
    # Without id — no marker
    record2 = logging.LogRecord(
        name="pkgforge.test.human",
        level=logging.INFO,
        pathname="x.py", lineno=1, msg="hi", args=(), exc_info=None,
    )
    out2 = fmt.format(record2)
    assert "[rid:" not in out2


def test_json_formatter_includes_extra_fields() -> None:
    """JSON formatter propagates extra= fields like package_name."""
    fmt = JSONFormatter()
    record = logging.LogRecord(
        name="pkgforge.test.extra",
        level=logging.WARNING,
        pathname="x.py", lineno=1, msg="slow op", args=(), exc_info=None,
    )
    record.duration_ms = 1234
    record.package_name = "bar.rpm"
    out = json.loads(fmt.format(record))
    assert out["duration_ms"] == 1234
    assert out["package_name"] == "bar.rpm"
    assert out["level"] == "WARNING"
