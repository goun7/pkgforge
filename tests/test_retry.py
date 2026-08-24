"""Coverage itmesi — core/retry.py (ustel geri cekilme)."""
from __future__ import annotations

import pytest

from core.retry import RetryConfig, retry_with_backoff


def test_get_delay_no_jitter_deterministic():
    cfg = RetryConfig(base_delay=1.0, backoff_factor=2.0, max_delay=30.0,
                      jitter=False)
    assert cfg.get_delay(0) == 1.0
    assert cfg.get_delay(1) == 2.0
    assert cfg.get_delay(2) == 4.0


def test_get_delay_respects_max_cap():
    cfg = RetryConfig(base_delay=1.0, backoff_factor=10.0, max_delay=5.0,
                      jitter=False)
    assert cfg.get_delay(3) == 5.0


def test_get_delay_jitter_bounded():
    cfg = RetryConfig(base_delay=2.0, backoff_factor=1.0, max_delay=30.0,
                      jitter=True)
    for _ in range(20):
        d = cfg.get_delay(0)
        assert 1.0 <= d <= 2.0  # %50-100 araligi


def test_success_first_try():
    calls = {"n": 0}

    def ok():
        calls["n"] += 1
        return "done"

    cfg = RetryConfig(max_retries=3, base_delay=0.0)
    assert retry_with_backoff(ok, config=cfg) == "done"
    assert calls["n"] == 1


def test_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr("core.retry.time.sleep", lambda s: None)
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("gecici")
        return "ok"

    cfg = RetryConfig(max_retries=5, base_delay=0.0)
    assert retry_with_backoff(flaky, config=cfg) == "ok"
    assert calls["n"] == 3


def test_exhausts_and_raises(monkeypatch):
    monkeypatch.setattr("core.retry.time.sleep", lambda s: None)

    def always_fail():
        raise TimeoutError("surekli")

    cfg = RetryConfig(max_retries=2, base_delay=0.0)
    with pytest.raises(TimeoutError):
        retry_with_backoff(always_fail, config=cfg)


def test_non_retryable_raises_immediately(monkeypatch):
    monkeypatch.setattr("core.retry.time.sleep", lambda s: None)
    calls = {"n": 0}

    def bad():
        calls["n"] += 1
        raise ValueError("tekrarlanamaz")

    cfg = RetryConfig(max_retries=5, base_delay=0.0)
    with pytest.raises(ValueError):
        retry_with_backoff(bad, config=cfg)
    assert calls["n"] == 1  # hemen firlatilir, tekrar denenmez


def test_default_config_used_when_none(monkeypatch):
    monkeypatch.setattr("core.retry.time.sleep", lambda s: None)
    assert retry_with_backoff(lambda: 42) == 42
