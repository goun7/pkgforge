"""Tur-47 — Installer kurulus-govdesi, cancel, cikti ve hata haritasi."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace as NS

from config import ToolPaths
from core.installer import INSTALL_HELPER, Installer, _find_install_helper

ARACLAR = ToolPaths(pkexec="/bin/true", pacman="/bin/true")


def _kur(kayit):
    kurucu = Installer(ARACLAR)
    kurucu.finished.connect(lambda ok, msg: kayit.append((ok, msg)))
    return kurucu


# --- 37: hicbir aday yoksa ilk aday doner -----------------------------------------

def test_find_install_helper_fallback(monkeypatch):
    monkeypatch.setattr(Path, "is_file",
                        lambda self: False, raising=True)
    sonuc = _find_install_helper()
    assert sonuc == INSTALL_HELPER or sonuc.is_absolute()      # 34-37


# --- 83-131: kurulus govdesi (snapshot dallari + QProcess baslangici) --------------

def _snapshot_modulleri_hazirla(monkeypatch, mod):
    if "core.snapshot_manager" not in sys.modules:
        monkeypatch.setitem(sys.modules, "core.snapshot_manager", NS())
    sm = sys.modules["core.snapshot_manager"]
    monkeypatch.setattr(sm, "detect_backend",
                        lambda: mod.get("backend", "snapper"), raising=False)
    monkeypatch.setattr(sm, "snapshot_name",
                        lambda label: mod.get("ad", "snap_1"), raising=False)


class _SahteIsaret:
    def __init__(self):
        self.baglilar = []

    def connect(self, fn):
        self.baglilar.append(fn)


class _SahteByte:
    def __init__(self, veri: bytes):
        self._veri = veri

    def data(self) -> bytes:
        return self._veri


class _SahteSurec:
    """QProcess yerine argv yakalayan sahte surec (tek-diyalog sozlesmesi)."""

    def __init__(self, cikti: bytes = b""):
        self.readyReadStandardOutput = _SahteIsaret()
        self.finished = _SahteIsaret()
        self.errorOccurred = _SahteIsaret()
        self.baslatilan = []
        self._cikti = cikti

    def setProcessChannelMode(self, _m):
        pass

    def start(self, prog, args):
        self.baslatilan.append((prog, list(args)))

    def readAllStandardOutput(self):
        return _SahteByte(self._cikti)


def _kuru_argv_yakala(kayit, cikti=b""):
    sahte = _SahteSurec(cikti)
    kurucu = Installer(ARACLAR, process_factory=lambda _p: sahte)
    kurucu.finished.connect(lambda ok, msg: kayit.append((ok, msg)))
    return kurucu, sahte


def test_install_body_snapshot_success(monkeypatch, tmp_path):
    pkg = tmp_path / "demo-1-1-x86_64.pkg.tar.zst"
    pkg.write_bytes(b"P")
    import i18n
    monkeypatch.setattr(i18n, "load_setting", lambda k, d: True)
    _snapshot_modulleri_hazirla(
        monkeypatch, {"success": True, "ad": "pre_demo"})
    kayit = []
    kurucu, sahte = _kuru_argv_yakala(kayit)
    kurucu.install(pkg, "demo")                                # 83-99
    prog, argv = sahte.baslatilan[0]
    assert "--snapshot" in argv and "pre_demo" in argv
    assert argv[-1] == str(pkg)
    # helper snapshot-ok satiri → ad kaydedilir + bilgi basilir
    kurucu2, _s2 = _kuru_argv_yakala(kayit, cikti=b"snapshot-ok: /pre_demo\n")
    ciktilar = []
    kurucu2.output_line.connect(ciktilar.append)
    kurucu2.install(pkg, "demo")
    kurucu2._on_output()
    assert kurucu2._snapshot_name == "/pre_demo"
    assert any("📸" in s for s in ciktilar)


def test_install_body_snapshot_fail_and_none(monkeypatch, tmp_path):
    pkg = tmp_path / "demo-1-1-x86_64.pkg.tar.zst"
    pkg.write_bytes(b"P")
    import i18n
    monkeypatch.setattr(i18n, "load_setting", lambda k, d: True)

    # ad uretimi patlarsa bayrak duser, kurulum devam eder
    import core.snapshot_manager as SM
    monkeypatch.setattr(SM, "detect_backend", lambda: "btrfs")

    def patlak(_label):
        raise RuntimeError("disk dolu")

    monkeypatch.setattr(SM, "snapshot_name", patlak)
    kayit = []
    kurucu, sahte = _kuru_argv_yakala(kayit)
    kurucu.install(pkg, "demo")
    assert kurucu._snapshot_name == ""
    _prog, argv = sahte.baslatilan[0]
    assert "--snapshot" not in argv

    # backend none → bayrak yok
    _snapshot_modulleri_hazirla(monkeypatch, {"backend": "none",
                                              "success": True})
    kurucu2, sahte2 = _kuru_argv_yakala(kayit)
    kurucu2.install(pkg, "demo")
    assert kurucu2._snapshot_name == ""
    assert "--snapshot" not in sahte2.baslatilan[0][1]

    # ayar kapali
    monkeypatch.setattr(i18n, "load_setting", lambda k, d: False)
    kurucu4, sahte4 = _kuru_argv_yakala(kayit)
    kurucu4.install(pkg, "demo")
    assert kurucu4._snapshot_name == ""
    assert "--snapshot" not in sahte4.baslatilan[0][1]

    # yardimci yok -> dogrudan pacman dalı (125-131)
    import core.installer as INS
    monkeypatch.setattr(INS, "INSTALL_HELPER",
                        tmp_path / "yok.sh", raising=False)
    kurucu5, sahte5 = _kuru_argv_yakala(kayit)
    kurucu5.install(pkg, "demo")
    _prog5, argv5 = sahte5.baslatilan[0]
    assert argv5[1:4] == ["-U", "--noconfirm", "--"]


# --- 133-138: cancel -------------------------------------------------------------

def test_cancel_with_live_process():
    kurucu = Installer(ARACLAR)
    ciktilar = []
    kurucu.output_line.connect(ciktilar.append)

    class SahteSurec:
        NotRunning = 0
        def state(self):
            return 2  # calisiyor
        def kill(self):
            ciktilar.append("__oldu__")

    kurucu._process = SahteSurec()
    kurucu.cancel()                                            # 133-138
    assert "__oldu__" in ciktilar
    assert kurucu._cancelled is True


def test_cancel_without_process():
    kurucu = Installer(ARACLAR)
    kurucu.cancel()          # _process None -> sadece bayrak        # 135


# --- 140-147: cikti akisi ---------------------------------------------------------

def test_on_output_lines():
    kurucu = Installer(ARACLAR)
    ciktilar = []
    kurucu.output_line.connect(ciktilar.append)

    class SahteSurec:
        def readAllStandardOutput(self_):
            return NS(data=lambda: b"  satir A\n\n  satir B\n")

    kurucu._process = SahteSurec()
    kurucu._on_output()                                        # 140-147
    assert ciktilar[-2:] == ["  satir A", "  satir B"]


def test_on_output_none_process():
    kurucu = Installer(ARACLAR)
    kurucu._process = None
    kurucu._on_output()                                        # 141-142


# --- 174-181: hata haritasi --------------------------------------------------------

def test_on_error_known_and_unknown():
    from PyQt6.QtCore import QProcess
    kurucu = Installer(ARACLAR)
    kayit = []
    kurucu.finished.connect(lambda ok, msg: kayit.append((ok, msg)))
    kurucu._on_error(QProcess.ProcessError.FailedToStart)      # 176
    kurucu._on_error(QProcess.ProcessError.Crashed)            # 177
    kurucu._on_error(QProcess.ProcessError.Timedout)           # 178
    kurucu._on_error(QProcess.ProcessError.UnknownError)       # 180-181
    mesajlar = [m for _ok, m in kayit]
    assert "başlatılamadı" in mesajlar[0]
    assert "çöktü" in mesajlar[1]
    assert "zaman aşımı" in mesajlar[2]
    assert "Kurulum hatası" in mesajlar[3]
