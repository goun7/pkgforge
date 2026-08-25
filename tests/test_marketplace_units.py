"""Coverage itmesi — plugins/marketplace kur/guncelle/dogrula akislari."""
from __future__ import annotations

import hashlib

import pytest

import core.plugins.marketplace as MP


def test_plugin_name_validation():
    for good in ("a", "abc_1-x", "z" * 64):
        assert MP.is_valid_plugin_name(good) is True, good
    for bad in ("", "Upper", "-bas", "nokta.x", "../evil", "z" * 65):
        assert MP.is_valid_plugin_name(bad) is False, bad
    with pytest.raises(ValueError):
        MP._validate_plugin_name("../evil")


def test_require_https():
    MP._require_https("https://x/y")
    for bad in ("http://x/y", "ftp://x/y"):
        with pytest.raises(ValueError):
            MP._require_https(bad)


def test_fetch_offline_and_parse(monkeypatch):
    assert MP.fetch_available_plugins(offline=True) == []
    data = {"tag_name": "v2", "assets": [
        {"name": "alfa.py", "browser_download_url": "https://h/alfa.py"},
        {"name": "beta.py.sig", "browser_download_url": "https://h/x"},
        {"name": "gama.py", "browser_download_url": "https://h/gama.py"},
    ]}
    monkeypatch.setattr(MP, "_fetch_json", lambda url, timeout=10: data)
    out = MP.fetch_available_plugins()
    assert [p["name"] for p in out] == ["alfa", "gama"]
    assert all(p["version"] == "v2" for p in out)
    assert all(p["sha256_url"].endswith(".sha256") for p in out)


def test_fetch_network_error(monkeypatch):
    import urllib.error

    def boom(url, timeout=10):
        raise urllib.error.URLError("yok")
    monkeypatch.setattr(MP, "_fetch_json", boom)
    assert MP.fetch_available_plugins() == []


def _use_tmp_plugin_dir(monkeypatch, tmp_path):
    pdir = tmp_path / "plugins"
    monkeypatch.setattr(MP, "PLUGIN_DIR", pdir)
    return pdir


def test_install_already_present(monkeypatch, tmp_path):
    pdir = _use_tmp_plugin_dir(monkeypatch, tmp_path)
    pdir.mkdir(parents=True)
    existing = pdir / "alfa.py"
    existing.write_text("eski")
    got = MP.install_plugin("alfa")
    assert got == existing and existing.read_text() == "eski"


def test_install_not_found_lists_available(monkeypatch, tmp_path):
    _use_tmp_plugin_dir(monkeypatch, tmp_path)
    monkeypatch.setattr(MP, "fetch_available_plugins",
                        lambda offline=False: [
                            {"name": "baska", "version": "v1"}])
    with pytest.raises(FileNotFoundError) as ei:
        MP.install_plugin("yok-plugin")
    assert "baska" in str(ei.value)


def _seed_index(monkeypatch):
    monkeypatch.setattr(MP, "fetch_available_plugins", lambda offline=False: [{
        "name": "alfa", "version": "v1",
        "download_url": "https://h/alfa.py",
        "sha256_url": "https://h/alfa.py.sha256"}])


def test_install_checksum_mismatch_fail_closed(monkeypatch, tmp_path):
    pdir = _use_tmp_plugin_dir(monkeypatch, tmp_path)
    _seed_index(monkeypatch)

    def fake_dl(url, dest, timeout=30):
        if url.endswith(".sha256"):
            dest.write_text("deadbeef")
        else:
            dest.write_text("icerik")
    monkeypatch.setattr(MP, "_download_file", fake_dl)
    with pytest.raises(RuntimeError) as ei:
        MP.install_plugin("alfa")
    assert "Checksum mismatch" in str(ei.value)
    assert not (pdir / "alfa.py").exists()


def test_install_checksum_unreachable_fail_closed(monkeypatch, tmp_path):
    import urllib.error
    pdir = _use_tmp_plugin_dir(monkeypatch, tmp_path)
    _seed_index(monkeypatch)

    def fake_dl(url, dest, timeout=30):
        if url.endswith(".sha256"):
            raise urllib.error.URLError("sha yok")
        dest.write_text("icerik")
    monkeypatch.setattr(MP, "_download_file", fake_dl)
    with pytest.raises(RuntimeError) as ei:
        MP.install_plugin("alfa")
    assert "alınamadı" in str(ei.value)
    assert not (pdir / "alfa.py").exists()


def test_install_success_with_matching_sha(monkeypatch, tmp_path):
    _pdir = _use_tmp_plugin_dir(monkeypatch, tmp_path)
    _seed_index(monkeypatch)
    body = b"plugin-kodu"

    def fake_dl(url, dest, timeout=30):
        if url.endswith(".sha256"):
            dest.write_text(hashlib.sha256(body).hexdigest())
        else:
            dest.write_bytes(body)
    monkeypatch.setattr(MP, "_download_file", fake_dl)
    got = MP.install_plugin("alfa")
    assert got.is_file() and got.read_bytes() == body


def test_install_skip_verification(monkeypatch, tmp_path):
    _pdir = _use_tmp_plugin_dir(monkeypatch, tmp_path)
    _seed_index(monkeypatch)

    def fake_dl(url, dest, timeout=30):
        if url.endswith(".sha256"):
            raise AssertionError("cagrilmamali")
        dest.write_text("kod")
    monkeypatch.setattr(MP, "_download_file", fake_dl)
    got = MP.install_plugin("alfa", verify_checksum=False)
    assert got.read_text() == "kod"


def test_uninstall_found_and_missing(monkeypatch, tmp_path):
    pdir = _use_tmp_plugin_dir(monkeypatch, tmp_path)
    pdir.mkdir(parents=True)
    f = pdir / "alfa.py"
    f.write_text("x")
    assert MP.uninstall_plugin("alfa") is True
    assert f.exists() is False
    assert MP.uninstall_plugin("alfa") is False
