"""Faz 3 (C3) tests — backup bundles & WebDAV sync."""
from __future__ import annotations

import io
import json
import urllib.request
import zipfile
from pathlib import Path

import pytest

import config
from core.cloud_sync import (
    SyncError,
    export_backup,
    import_backup,
    webdav_pull,
    webdav_push,
)


@pytest.fixture
def cfg_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "pkgforge-config"
    root.mkdir()
    monkeypatch.setattr(config, "CONFIG_DIR", root)
    return root


def _seed_default_state() -> None:
    from core.history_db import HistoryDB
    from i18n import save_settings

    save_settings({"theme": "dark"})
    HistoryDB()  # creates history.db


# --- export / import --------------------------------------------------------

def test_export_creates_bundle_with_marker_and_data(cfg_root: Path):
    _seed_default_state()
    out = cfg_root / "backups" / "b.zip"
    result = export_backup(str(out))

    assert result["ok"] is True
    assert out.is_file()
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert "pkgforge-backup.json" in names
        assert "default/settings.json" in names
        assert "default/history.db" in names


def test_export_covers_all_profiles(cfg_root: Path):
    from core import profiles
    from i18n import save_settings

    _seed_default_state()
    profiles.create_profile("work")
    profiles.switch_profile("work")
    save_settings({"theme": "light"})

    out = cfg_root / "b.zip"
    export_backup(str(out))
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    assert "default/settings.json" in names
    assert "work/settings.json" in names


def test_export_without_anything_raises(cfg_root: Path):
    with pytest.raises(SyncError):
        export_backup()


def test_import_roundtrip_restores_settings(cfg_root: Path):
    from i18n import load_settings, save_settings

    _seed_default_state()
    bundle = str(cfg_root / "roundtrip.zip")
    export_backup(bundle)

    save_settings({"theme": "light"})  # mutate current state
    assert load_settings()["theme"] == "light"

    result = import_backup(bundle)
    assert "default/settings.json" in result["restored"]
    assert load_settings()["theme"] == "dark"


def test_import_rejects_foreign_zip(cfg_root: Path):
    foreign = cfg_root / "foreign.zip"
    with zipfile.ZipFile(foreign, "w") as zf:
        zf.writestr("something.txt", "nope")
    with pytest.raises(SyncError):
        import_backup(str(foreign))


def test_import_rejects_traversal_members(cfg_root: Path):
    evil = cfg_root / "evil.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("pkgforge-backup.json", "{}")
        zf.writestr("../escaped.txt", "x")
    evil.write_bytes(buf.getvalue())
    with pytest.raises(SyncError):
        import_backup(str(evil))


def test_manifest_present_and_tamper_detected(cfg_root: Path):
    import zipfile as _zip

    _seed_default_state()
    bundle = cfg_root / "tamper.zip"
    export_backup(str(bundle))

    # Rewrite the archive with a corrupted payload but original manifest.
    with _zip.ZipFile(bundle) as zf:
        names = zf.namelist()
        blobs = {n: zf.read(n) for n in names}
    blobs["default/settings.json"] = b'{"theme": "evil"}'
    with _zip.ZipFile(bundle, "w") as zf:
        for n, b in blobs.items():
            zf.writestr(n, b)

    with pytest.raises(SyncError, match="Bütünlük"):
        import_backup(str(bundle))


def test_missing_backup_file_raises(cfg_root: Path):
    with pytest.raises(SyncError):
        import_backup(str(cfg_root / "yok.zip"))


# --- webdav -----------------------------------------------------------------

def _configure(url: str, **extra) -> None:
    from i18n import save_settings

    save_settings({"sync_url": url, "sync_username": "u", "sync_password": "p", **extra})


class _FakeResponse:
    def __init__(self, payload: bytes = b""):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None


def test_push_without_config_raises(cfg_root: Path):
    with pytest.raises(SyncError, match="yapılandırılmadı"):
        webdav_push()


def test_push_blocks_plain_http_by_default(cfg_root: Path):
    _seed_default_state()
    _configure("http://cloud.example/dav/")
    with pytest.raises(SyncError, match="https"):
        webdav_push()


def test_push_uploads_bundle(cfg_root: Path, monkeypatch: pytest.MonkeyPatch):
    captured: dict = {}

    def fake_urlopen(req, timeout=0):
        captured["method"] = req.method
        captured["url"] = req.full_url
        captured["auth"] = req.headers.get("Authorization", "")
        return _FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    _seed_default_state()
    _configure("https://cloud.example/dav/")

    result = webdav_push()
    assert result["ok"] is True
    assert captured["method"] == "PUT"
    assert captured["url"].endswith("/dav/pkgforge-backup.zip")
    assert captured["auth"].startswith("Basic ")
    assert result["size"] > 0


def test_pull_restores_remote_bundle(cfg_root: Path, monkeypatch: pytest.MonkeyPatch):
    _seed_default_state()
    bundle_path = cfg_root / "seed.zip"
    export_backup(str(bundle_path))
    remote_bytes = bundle_path.read_bytes()

    from i18n import save_settings

    save_settings({"theme": "light"})  # local drift

    calls: list[str] = []

    def fake_urlopen(req, timeout=0):
        calls.append(req.method)
        return _FakeResponse(remote_bytes)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    _configure("https://cloud.example/dav/", allow_insecure_http=True)

    result = webdav_pull()
    assert calls == ["GET"]
    assert result["ok"] is True
    from i18n import load_settings

    assert load_settings()["theme"] == "dark"


def test_pull_http_error_maps_to_syncerror(cfg_root: Path, monkeypatch: pytest.MonkeyPatch):
    import urllib.error

    def fake_urlopen(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 404, "nf", hdrs=None, fp=None)  # type: ignore[arg-type]

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    _configure("https://cloud.example/dav/")
    with pytest.raises(SyncError, match="404"):
        webdav_pull()


def test_marker_payload_is_valid_json(cfg_root: Path):
    _seed_default_state()
    out = cfg_root / "m.zip"
    export_backup(str(out))
    with zipfile.ZipFile(out) as zf:
        meta = json.loads(zf.read("pkgforge-backup.json"))
    assert meta["app"] == "PkgForge"
