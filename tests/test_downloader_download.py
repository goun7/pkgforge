"""Coverage itmesi — core/downloader.py download_package govdesi."""
from __future__ import annotations

import pytest

from core.downloader import download_package


class _Resp:
    def __init__(self, headers, chunks):
        self.headers = headers
        self._chunks = list(chunks)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n):
        return self._chunks.pop(0) if self._chunks else b""


def _patch_open(monkeypatch, resp):
    seen = {}

    def fake_open(req, timeout=30, require_https=True, **k):
        seen["url"] = req.full_url
        seen["require_https"] = require_https
        return resp
    monkeypatch.setattr("core.downloader._open_url", fake_open)
    return seen


def test_rejects_non_http_scheme(tmp_path):
    with pytest.raises(ValueError) as ei:
        download_package("ftp://x/p.deb", dest_dir=tmp_path)
    assert "şema" in str(ei.value)


def test_rejects_http_by_default(tmp_path):
    with pytest.raises(ValueError) as ei:
        download_package("http://x/p.deb", dest_dir=tmp_path)
    assert "HTTPS" in str(ei.value)


def test_successful_download_captures_headers(monkeypatch, tmp_path):
    info = {}
    seen = _patch_open(monkeypatch, _Resp(
        {"ETag": chr(34) + "e1" + chr(34), "Last-Modified": "dun",
         "Content-Length": "5"}, [b"merha", b"ba"]))
    out = download_package("https://x/y/p.deb", dest_dir=tmp_path,
                           response_info=info, allow_private_hosts=True)
    assert out == tmp_path / "p.deb"
    assert out.read_bytes() == b"merhaba"
    assert info["etag"] == "e1" and info["last_modified"] == "dun"
    assert info["content_length"] == "5"
    assert seen["url"] == "https://x/y/p.deb"


def test_oversize_content_length_rejected(monkeypatch, tmp_path):
    big = 9999 * 1024 * 1024
    _patch_open(monkeypatch, _Resp({"Content-Length": str(big)}, []))
    with pytest.raises(RuntimeError) as ei:
        download_package("https://x/p.deb", dest_dir=tmp_path,
                         allow_private_hosts=True)
    assert "büyük" in str(ei.value)


def test_sha256_mismatch_deletes_file(monkeypatch, tmp_path):
    _patch_open(monkeypatch, _Resp(
        {"Content-Length": "2"}, [b"ok"]))
    bad = "0" * 64
    with pytest.raises(ValueError) as ei:
        download_package("https://x/p.deb", dest_dir=tmp_path,
                         expected_sha256=bad, allow_private_hosts=True)
    assert "SHA-256" in str(ei.value)
    assert not (tmp_path / "p.deb").exists()


def test_sha256_match_keeps_file(monkeypatch, tmp_path):
    import hashlib

    good = hashlib.sha256(b"ok").hexdigest()
    _patch_open(monkeypatch, _Resp(
        {"Content-Length": "2"}, [b"ok"]))
    out = download_package("https://x/p.deb", dest_dir=tmp_path,
                           expected_sha256=good.upper(), allow_private_hosts=True)
    assert out.is_file()
