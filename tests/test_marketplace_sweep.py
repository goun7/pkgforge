"""Coverage itmesi - marketplace: indirme, listeleme, guncelleme, denetim."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import core.plugins.marketplace as MK


class FakeResp:
    """copyfileobj uyumlu: boyutlu okuma ve bir kerelik tükenme."""

    def __init__(self, payload: bytes = b""):
        self._buf = payload

    def __enter__(self):
        return self

    def read(self, n: int = -1) -> bytes:
        if n < 0:
            out, self._buf = self._buf, b""
            return out
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def __exit__(self, *a):
        return False


@pytest.fixture()
def plugdir(tmp_path, monkeypatch):
    d = tmp_path / "plugins"
    monkeypatch.setattr(MK, "PLUGIN_DIR", d)
    return d


# --- yardimcilar ---------------------------------------------------------------

def test_user_agent_contains_app_identity():
    ua = MK._get_user_agent()
    assert "/" in ua and "plugin-marketplace" in ua


def test_download_file_rejects_http(tmp_path):
    with pytest.raises(ValueError, match="HTTPS"):
        MK._download_file("http://example.com/p.py", tmp_path / "p.py")


def test_download_file_https_writes_payload(tmp_path, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=0: FakeResp(b"icerik"))
    dest = tmp_path / "p.py"
    MK._download_file("https://example.com/p.py", dest)
    assert dest.read_bytes() == b"icerik"


def test_fetch_json_ok_and_http_reject(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=0: FakeResp(json.dumps({"a": 1}).encode()))
    assert MK._fetch_json("https://x/list.json") == {"a": 1}
    with pytest.raises(ValueError, match="HTTPS"):
        MK._fetch_json("ftp://x/list.json")


def test_sha256_file_matches_hashlib(tmp_path):
    f = tmp_path / "d"
    f.write_bytes(b"abc")
    assert MK._sha256_file(f) == hashlib.sha256(b"abc").hexdigest()


# --- listeleme -----------------------------------------------------------------

def test_list_installed_no_dir(plugdir):
    assert MK.list_installed_plugins() == []


def test_list_installed_skips_underscore_sorted(plugdir):
    plugdir.mkdir()
    (plugdir / "zeta.py").write_text("x=1")
    (plugdir / "_gizli.py").write_text("x=2")
    (plugdir / "alfa.py").write_text("x" * 33)
    out = MK.list_installed_plugins()
    assert [p["name"] for p in out] == ["alfa", "zeta"]
    assert out[0]["size"] == "33"


# --- guncelleme ----------------------------------------------------------------

def test_update_plugin_not_installed(plugdir):
    ok, msg, path = MK.update_plugin("yok")
    assert ok is False and path is None and "kurulu değil" in msg


def test_update_plugin_success(plugdir, monkeypatch, tmp_path):
    plugdir.mkdir()
    (plugdir / "var.py").write_text("eski")
    hedef = tmp_path / "yeni.py"
    hedef.write_text("yeni")
    monkeypatch.setattr(MK, "install_plugin",
                        lambda name, force=False: hedef)
    ok, msg, path = MK.update_plugin("var")
    assert ok is True and path == hedef and "güncellendi" in msg


@pytest.mark.parametrize("exc", [
    FileNotFoundError("dosya yok"),
    ValueError("kötü checksum"),
])
def test_update_plugin_error_mapping(plugdir, monkeypatch, exc):
    plugdir.mkdir()
    (plugdir / "var.py").write_text("x")
    def boom(name, force=False):
        raise exc
    monkeypatch.setattr(MK, "install_plugin", boom)
    ok, msg, path = MK.update_plugin("var")
    assert ok is False and path is None and str(exc) in msg


# --- denetim -------------------------------------------------------------------

def _write_plugin(plugdir: Path, name="eklenti", body=b"kod") -> Path:
    plugdir.mkdir(parents=True, exist_ok=True)
    p = plugdir / f"{name}.py"
    p.write_bytes(body)
    return p


def test_audit_unknown_when_marketplace_empty(plugdir, monkeypatch):
    _write_plugin(plugdir)
    monkeypatch.setattr(MK, "fetch_available_plugins", lambda offline=False: [])
    out = MK.audit_plugins()
    assert out == [{"name": "eklenti", "status": "unknown",
                    "message": out[0]["message"]}]


def test_audit_ok_on_matching_checksum(plugdir, monkeypatch):
    body = b"guvenilir kod"
    _write_plugin(plugdir, body=body)
    good = hashlib.sha256(body).hexdigest()
    monkeypatch.setattr(
        MK, "fetch_available_plugins",
        lambda offline=False: [{"name": "eklenti",
                                "sha256_url": "https://m/eklenti.py.sha256"}])

    def fake_download(url, dest, timeout=0):
        dest.write_text(good + "\n")
    monkeypatch.setattr(MK, "_download_file", fake_download)
    out = MK.audit_plugins()
    assert out[0]["status"] == "ok"


def test_audit_changed_on_mismatch(plugdir, monkeypatch):
    _write_plugin(plugdir, body=b"degismis")
    monkeypatch.setattr(
        MK, "fetch_available_plugins",
        lambda offline=False: [{"name": "eklenti",
                                "sha256_url": "https://m/e.sha256"}])
    monkeypatch.setattr(MK, "_download_file",
                        lambda url, dest, timeout=0:
                        dest.write_text("farklı-hash\n"))
    out = MK.audit_plugins()
    assert out[0]["status"] == "changed"


def test_audit_sha_download_failure_maps_to_unknown(plugdir, monkeypatch):
    _write_plugin(plugdir)
    monkeypatch.setattr(
        MK, "fetch_available_plugins",
        lambda offline=False: [{"name": "eklenti",
                                "sha256_url": "https://m/e.sha256"}])
    def boom(url, dest, timeout=0):
        raise OSError("ag yok")
    monkeypatch.setattr(MK, "_download_file", boom)
    out = MK.audit_plugins()
    assert out[0]["status"] == "unknown"


def test_audit_hash_read_failure_maps_to_error(plugdir, monkeypatch):
    _write_plugin(plugdir)
    def boom(path):
        raise RuntimeError("okunamadı")
    monkeypatch.setattr(MK, "_sha256_file", boom)
    out = MK.audit_plugins()
    assert out[0]["status"] == "error" and "Audit hatası" in out[0]["message"]
