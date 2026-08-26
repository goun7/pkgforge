"""Tur-54 — privileged + distrobox + cloud_sync kalan satirlari (test-only)."""
from __future__ import annotations

import sys
import urllib.error
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import core.privileged as PR

# ── privileged 49 / 130-146 ──────────────────────────────────────────────────────

def test_find_privileged_helper_fallback(monkeypatch):
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    sonuc = PR.find_privileged_helper()
    assert sonuc == PR.PRIVILEGED_HELPER or str(sonuc).endswith(
        PR.PRIVILEGED_HELPER_NAME)                                     # 48-49


def test_install_polkit_assets_dry_run_and_guards(monkeypatch, tmp_path):
    # dry_run plan dondurur (123-129 zaten kismen; garanti)
    plan = PR.install_polkit_assets(dry_run=True)
    assert plan["dry_run"] is True and plan["installed"] is False

    # root degil -> PermissionError (130-132)
    monkeypatch.setattr(PR.os, "geteuid", lambda: 1000)
    with pytest.raises(PermissionError):
        PR.install_polkit_assets(dry_run=False)

    # root ama helper kaynagi yok (133-134)
    monkeypatch.setattr(PR.os, "geteuid", lambda: 0)
    gercek_isfile = Path.is_file

    def sahte_isfile(self):
        if self.name == "install_helper.sh":
            return False
        return gercek_isfile(self)

    monkeypatch.setattr(Path, "is_file", sahte_isfile)
    with pytest.raises(FileNotFoundError):
        PR.install_polkit_assets(dry_run=False)


def test_install_polkit_assets_real_write(monkeypatch, tmp_path):
    """135-146: gecici-dosya yazimi, chmod, atomik replace."""
    monkeypatch.setattr(PR.os, "geteuid", lambda: 0)

    politika = tmp_path / "polkit" / "policy.json"
    yardimci = tmp_path / "bin" / "helper.sh"

    monkeypatch.setattr(PR, "POLICY_SYSTEM_PATH", str(politika))
    monkeypatch.setattr(PR, "HELPER_SYSTEM_PATH", str(yardimci))

    sonuc = PR.install_polkit_assets(dry_run=False)                 # 135-146
    assert sonuc == {"installed": True, "dry_run": False,
                     "units": [str(politika), str(yardimci)]}
    politika_metni = politika.read_text(encoding="utf-8")
    assert "<policyconfig>" in politika_metni


# ── distrobox 134-177 ────────────────────────────────────────────────────────────

class SahteSignal:
    def __init__(self):
        self._aboneler = []

    def connect(self, fn):
        self._aboneler.append(fn)

    def emit(self, *a):
        for fn in list(self._aboneler):
            fn(*a)


class SahteSurec:
    NotRunning = 0

    def __init__(self):
        self.output_line = SahteSignal()
        self.finished = SahteSignal()
        self.errorOccurred = SahteSignal()

    def setProcessChannelMode(self, mod):
        pass

    def start(self, *a):
        pass

    def state(self):
        return 2

    def kill(self):
        pass

    def readAllStandardOutput(self_):
        return NS(data=lambda: b"  cikti satiri\n")


def _kurulum(monkeypatch, tmp_path):
    from config import ToolPaths
    from core.distrobox_fallback import DistroboxFallback
    araclar = ToolPaths(distrobox="/usr/bin/distrobox")
    fb = DistroboxFallback(araclar)
    fb._process = SahteSurec()
    fb._container_name = "kutu"
    fb._pkg_name = "paket"
    return fb


def test_distrobox_install_finished_paths(monkeypatch, tmp_path):
    fb = _kurulum(monkeypatch, tmp_path)
    kayit = []
    fb.finished.connect(lambda ok, msg: kayit.append((ok, msg)))

    monkeypatch.setattr(fb, "_export_app", lambda: None)
    fb._on_install_finished(1, None)                                # 135-137
    assert kayit[-1][0] is False and "başarısız" in kayit[-1][1]

    fb._on_install_finished(0, None)                                # 139-141
    assert fb._phase == "export"


def test_distrobox_export_finished_and_output(monkeypatch, tmp_path):
    fb = _kurulum(monkeypatch, tmp_path)
    kayit = []
    ciktilar = []
    fb.finished.connect(lambda ok, msg: kayit.append((ok, msg)))
    fb.output_line.connect(ciktilar.append)

    fb._on_export_finished(3, None)                                 # 158-162
    assert kayit[-1][0] is True and "manuel" in kayit[-1][1]

    fb._on_export_finished(0, None)                                 # 163-165
    assert "entegre" in kayit[-1][1]

    fb._on_output()                                                 # 167-174
    assert any("cikti satiri" in s for s in ciktilar)

    fb._process = None
    fb._on_output()                                                 # 168-169


def test_distrobox_on_error(monkeypatch, tmp_path):
    fb = _kurulum(monkeypatch, tmp_path)
    kayit = []
    fb.finished.connect(lambda ok, msg: kayit.append((ok, msg)))
    fb._on_error("Crashed")                                         # 176-177
    assert kayit[-1][0] is False and "Distrobox hatası" in kayit[-1][1]


# ── cloud_sync 43 / 240-241 / 262-265 / 277-280 ──────────────────────────────────

def test_net_reason_variants():
    from core.cloud_sync import _net_reason
    assert _net_reason(urllib.error.URLError("sebep")) == "sebep"   # 43
    io_hatasi = OSError("io")
    assert _net_reason(io_hatasi) is io_hatasi


def _webdav_ortam(monkeypatch, tmp_path):
    import core.cloud_sync as CS
    import i18n
    monkeypatch.setattr(i18n, "load_settings",
                        lambda: {"sync_url": "https://dav.example/eg/",
                                 "sync_username": "ayse",
                                 "sync_password": ""})
    class PatlakMagaza:
        def __init__(self, user):
            pass
        def get_secret(self):
            raise RuntimeError("keyring koptu")

    monkeypatch.setitem(sys.modules, "core.secrets_store",
                        NS(available=lambda: True,
                           webdav_store=PatlakMagaza))
    return CS


def test_webdav_push_error_branches(monkeypatch, tmp_path):
    CS = _webdav_ortam(monkeypatch, tmp_path)

    # HTTPError -> SyncError sunucu hatasi (262-263)
    def http_hata(req, timeout=0):
        raise urllib.error.HTTPError("u", 500, "sunucu", {}, None)
    monkeypatch.setattr(CS.urllib.request, "urlopen", http_hata)
    monkeypatch.setattr(CS, "export_backup",
                        lambda: {"path": str(tmp_path / "y.json")}, raising=False)
    (tmp_path / "y.json").write_bytes(b"B")
    with pytest.raises(CS.SyncError, match="Sunucu hatası"):
        CS.webdav_push()

    # URLError -> SyncError ulasilamadi (264-265)
    def url_hata(req, timeout=0):
        raise urllib.error.URLError("dns")
    monkeypatch.setattr(CS.urllib.request, "urlopen", url_hata)
    with pytest.raises(CS.SyncError, match="ulaşılamadı"):
        CS.webdav_push()


def test_webdav_pull_error_branches(monkeypatch, tmp_path):
    CS = _webdav_ortam(monkeypatch, tmp_path)

    def http_hata(req, timeout=0):
        raise urllib.error.HTTPError("u", 404, "yok", {}, None)
    monkeypatch.setattr(CS.urllib.request, "urlopen", http_hata)
    with pytest.raises(CS.SyncError, match="HTTP 404"):              # 277-278
        CS.webdav_pull()

    def url_hata(req, timeout=0):
        raise TimeoutError("zaman")
    monkeypatch.setattr(CS.urllib.request, "urlopen", url_hata)
    with pytest.raises(CS.SyncError, match="ulaşılamadı"):           # 279-280
        CS.webdav_pull()


def test_keyring_fail_debug_branch(monkeypatch, tmp_path, caplog):
    """240-242: keyring patlamasi push'u bozmaz."""
    CS = _webdav_ortam(monkeypatch, tmp_path)

    class SahteYanit:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def read(self):
            return b""

    monkeypatch.setattr(CS.urllib.request, "urlopen",
                        lambda req, timeout=0: SahteYanit())
    monkeypatch.setattr(CS, "export_backup",
                        lambda: {"path": str(tmp_path / "b.json")},
                        raising=False)
    (tmp_path / "b.json").write_bytes(b"B")
    sonuc = CS.webdav_push()                                        # 236-242
    assert sonuc["ok"] is True and sonuc["size"] == 1