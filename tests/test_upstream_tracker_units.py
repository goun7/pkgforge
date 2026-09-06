"""Coverage itmesi — core/upstream_tracker.py kontrol dallari."""
from __future__ import annotations

import urllib.error
from types import SimpleNamespace

import pytest

from core.upstream_tracker import check_upstream_update


@pytest.fixture(autouse=True)
def _sahte_host_guvenligi(monkeypatch):
    # SSRF guard test hostuna takilmamali (ag zaten sahte)
    monkeypatch.setattr("core.downloader.assert_public_host",
                        lambda *a, **k: None)


class _Resp:
    def __init__(self, headers):
        self.headers = headers

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _rec(url="https://ornek.test/p.deb", etag="", last_mod=""):
    return SimpleNamespace(package_name="demo", source_url=url,
                           http_etag=etag, http_last_modified=last_mod,
                           id=7)


def test_offline_skips_network():
    r = check_upstream_update(_rec(), offline=True)
    assert r.status == "offline" and r.has_update is False


def test_no_url_and_non_http():
    assert check_upstream_update(_rec("")).status == "no_url"
    assert check_upstream_update(_rec("ftp://x")).status == "no_url"


def test_first_check_no_update(monkeypatch):
    monkeypatch.setattr("core.downloader._open_url",
                        lambda req, timeout=10: _Resp(
                            {"ETag": chr(34) + "abc" + chr(34),
                             "Last-Modified": "dun",
                             "Content-Length": "10"}))
    r = check_upstream_update(_rec(etag="", last_mod=""))
    assert r.status == "checked" and r.has_update is False
    assert r.etag == "abc"
    assert "lk kontrol" in r.detail


def test_etag_change_flags_update(monkeypatch):
    monkeypatch.setattr("core.downloader._open_url",
                        lambda req, timeout=10: _Resp({"ETag": "yeni"}))
    r = check_upstream_update(_rec(etag="eski", last_mod="dun"))
    assert r.has_update is True and "ETag" in r.detail


def test_lastmod_change_flags_update(monkeypatch):
    monkeypatch.setattr("core.downloader._open_url",
                        lambda req, timeout=10: _Resp(
                            {"Last-Modified": "bugun"}))
    r = check_upstream_update(_rec(etag="", last_mod="eski-gun"))
    assert r.has_update is True and "Last-Modified" in r.detail


def test_url_error_yields_error_status(monkeypatch):
    def boom(req, timeout=10):
        raise urllib.error.URLError("ulasilamadi")
    monkeypatch.setattr("core.downloader._open_url", boom)
    r = check_upstream_update(_rec())
    assert r.status == "error" and r.has_update is False
