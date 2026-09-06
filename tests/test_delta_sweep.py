"""Coverage itmesi — core/delta_updater.py xdelta akislari ve systemd zamanlayici."""
from __future__ import annotations

import os
import time
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import core.delta_updater as DU


def _rc(code, stdout="", stderr=""):
    return NS(returncode=code, stdout=stdout, stderr=stderr)


@pytest.fixture(autouse=True)
def _xdelta_yok(monkeypatch):
    """Varsayilan: xdelta3 yok — her test kendi kararini verir."""
    monkeypatch.setattr("shutil.which", lambda n: None)


# --- kullanilabilirlik ----------------------------------------------------------

def test_xdelta3_presence_variants(monkeypatch):
    assert DU.is_xdelta3_available() is False
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/xdelta3")
    assert DU.is_xdelta3_available() is True


def _uc_dosya(tmp_path):
    eski = tmp_path / "eski.deb"; eski.write_bytes(b"A" * 100)
    yeni = tmp_path / "yeni.deb"; yeni.write_bytes(b"B" * 100)
    fark = tmp_path / "f.xdelta"
    return eski, yeni, fark


def test_create_delta_without_tool_false(monkeypatch, tmp_path):
    e, y, f = _uc_dosya(tmp_path)
    assert DU.create_delta(e, y, f) is False


def test_create_delta_missing_files_false(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/xdelta3")
    e, y, f = _uc_dosya(tmp_path)
    y.unlink()
    assert DU.create_delta(e, y, f) is False


def test_create_delta_failure_code_false(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/xdelta3")
    monkeypatch.setattr(DU, "safe_run",
                        lambda cmd, timeout=0: _rc(1, stderr="patladi"))
    e, y, f = _uc_dosya(tmp_path)
    assert DU.create_delta(e, y, f) is False


def test_create_delta_success_writes_and_true(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/xdelta3")
    e, y, f = _uc_dosya(tmp_path)

    def fake(cmd, timeout=0):
        Path(cmd[-1]).write_bytes(b"D" * 20)   # cikti dosyasi olusur
        return _rc(0)
    monkeypatch.setattr(DU, "safe_run", fake)
    assert DU.create_delta(e, y, f) is True and f.is_file()


def test_apply_delta_branches(monkeypatch, tmp_path):
    e, _, cikti = _uc_dosya(tmp_path)
    fark = tmp_path / "d.xdelta"

    assert DU.apply_delta(e, fark, cikti) is False          # arac yok

    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/xdelta3")
    assert DU.apply_delta(e, fark, cikti) is False          # girdi yok

    fark.write_bytes(b"d")
    monkeypatch.setattr(DU, "safe_run",
                        lambda cmd, timeout=0: _rc(2, stderr="hata"))
    assert DU.apply_delta(e, fark, cikti) is False          # rc!=0

    def basarili(cmd, timeout=0):
        Path(cmd[-1]).write_bytes(b"YENI")
        return _rc(0)
    monkeypatch.setattr(DU, "safe_run", basarili)
    assert DU.apply_delta(e, fark, cikti) is True           # mutlu yol
    assert cikti.read_bytes() == b"YENI"


# --- onceki surum arama ---------------------------------------------------------

def test_find_previous_none_when_dir_missing(monkeypatch, tmp_path):
    assert DU.find_local_previous("demo", tmp_path / "yok") is None


def test_find_previous_picks_newest_matching(monkeypatch, tmp_path):
    (tmp_path / "demo-1.0-1-x86_64.pkg.tar.zst").write_bytes(b"e")
    (tmp_path / "demo-2.0-1-x86_64.pkg.tar.zst").write_bytes(b"y")
    (tmp_path / "demo-3.0.pkg.tar.zst.sig").write_bytes(b"s")   # haric
    (tmp_path / "diger-9.9-1-any.pkg.tar.zst").write_bytes(b"d")  # farkli paket

    eski_zam = time.time() - 3600
    os.utime(tmp_path / "demo-1.0-1-x86_64.pkg.tar.zst", (eski_zam,) * 2)

    sonuc = DU.find_local_previous("DEMO", tmp_path)  # buyuk/kucuk bagisik
    assert sonuc is not None and "2.0" in sonuc.name


# --- delta ile indirme ----------------------------------------------------------

class _Indirici:
    def __init__(self, delta_calisir=True):
        self.delta_calisir = delta_calisir
        self.cagrilar = []

    def __call__(self, url, hedef_dizin, require_https=True, **k):
        self.cagrilar.append((url, require_https))
        p = Path(hedef_dizin) / ("delta.xdelta" if url.endswith(".xdelta")
                                 else "final.pkg.tar.zst")
        if self.delta_calisir is False and url.endswith(".xdelta"):
            raise OSError("delta sunucusu yok")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
        return p


def test_download_full_when_no_old(monkeypatch, tmp_path):
    indirici = _Indirici()
    monkeypatch.setitem(__import__("sys").modules,
                        "core.downloader",
                        NS(download_package=indirici))
    hedef = tmp_path / "cikti" / "final.pkg.tar.zst"
    yol, delta_kullanildi = DU.download_with_delta("https://s/final.pkg.tar.zst",
                                                   hedef, None)
    assert delta_kullanildi is False and yol.name == "final.pkg.tar.zst"


def test_download_delta_success_path(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/xdelta3")
    indirici = _Indirici(delta_calisir=True)
    monkeypatch.setitem(__import__("sys").modules,
                        "core.downloader",
                        NS(download_package=indirici))
    monkeypatch.setattr(DU, "apply_delta", lambda *a, **k: True)
    eski = tmp_path / "eski.pkg.tar.zst"; eski.write_bytes(b"e")
    hedef = tmp_path / "out" / "final.pkg.tar.zst"
    _yol, kullandi = DU.download_with_delta("https://s/final.pkg.tar.zst",
                                            hedef, eski)
    assert kullandi is True
    assert any(u.endswith(".xdelta") for u, _ in indirici.cagrilar)


def test_download_falls_back_when_delta_download_fails(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/xdelta3")
    indirici = _Indirici(delta_calisir=False)
    monkeypatch.setitem(__import__("sys").modules,
                        "core.downloader",
                        NS(download_package=indirici))
    eski = tmp_path / "eski.pkg.tar.zst"; eski.write_bytes(b"e")
    hedef = tmp_path / "out" / "final.pkg.tar.zst"
    yol, kullandi = DU.download_with_delta("https://s/final.pkg.tar.zst",
                                           hedef, eski)
    assert kullandi is False and yol.name == "final.pkg.tar.zst"


# --- systemd otomatik guncelleme ------------------------------------------------

@pytest.fixture(autouse=True)
def _systemctl_var(monkeypatch):
    # Sistemctl aramasini sahtele; diger tum yollar gercek kontrole gitsin.
    orijinal_isfile = os.path.isfile
    monkeypatch.setattr(
        os.path, "isfile",
        lambda p: (True if str(p).endswith("systemctl")
                   else orijinal_isfile(p)))


def test_install_requires_systemctl(monkeypatch):
    monkeypatch.setattr(os.path, "isfile", lambda p: False)
    ok, msg = DU.install_auto_update()
    assert ok is False and "systemctl bulunamadı" in msg


def test_install_happy_path(monkeypatch):
    """Kurulum TEK service-deploy cagrisiyla yapilir; eskiden 4-6 ayri
    pkexec diyalogu vardi (sudo bombardimaninin ana kaynagi)."""
    monkeypatch.setattr("os.path.isfile", lambda p: True)
    calls = []

    def fake(cmd, timeout=0, input=None):
        calls.append(cmd)
        return _rc(0)
    monkeypatch.setattr("core.security.safe_run", fake)

    ok, msg = DU.install_auto_update(interval_hours=12)
    assert ok is True and len(calls) == 1, f"tek diyalog beklenir: {calls}"
    assert "service-deploy" in calls[0]
    assert "12 saatte" in msg or "Timer" in msg


def test_install_script_write_failure(monkeypatch):
    monkeypatch.setattr("os.path.isfile", lambda p: True)
    monkeypatch.setattr("core.security.safe_run",
                        lambda cmd, timeout=0, input=None: _rc(1))
    ok, msg = DU.install_auto_update()
    assert ok is False and "yazılamadı" in msg


def test_remove_happy_and_exception(monkeypatch):
    monkeypatch.setattr("os.path.isfile", lambda p: True)
    monkeypatch.setattr("core.privileged.privileged_remove_argv",
                        lambda tool, path: ["rm", path])
    # Yalniz bu modulun Path'i: /etc birimleri "yok" sayilir
    monkeypatch.setattr(DU, "Path", _YokBirimlerPath)
    monkeypatch.setattr("core.security.safe_run", lambda cmd, timeout=0: _rc(0))
    ok, msg = DU.remove_auto_update()
    assert ok is True

    def patla(*a, **k):
        raise RuntimeError("otobus")
    monkeypatch.setattr("core.security.safe_run", patla)
    ok, msg = DU.remove_auto_update()
    assert ok is False and "Kaldırma başarısız" in msg


def _sahte_safe_run_senaryo(senaryo):
    def fake(cmd, timeout=0, input=None):
        if "is-enabled" in cmd:
            return _rc(0 if senaryo.get("installed") else 1)
        if "is-active" in cmd:
            return _rc(0 if senaryo.get("active") else 1)
        if "show" in cmd:
            return _rc(0, stdout="NextElapseUSecRealtime=yarin\n")
        return _rc(0)
    return fake


def test_status_defaults_without_systemctl(monkeypatch):
    monkeypatch.setattr(os.path, "isfile", lambda p: False)
    d = DU.get_auto_update_status()
    assert d["installed"] is False and d["experimental"] is True
    assert d["xdelta3_available"] is False


def test_status_installed_active_next_run(monkeypatch):
    senaryo = {"installed": True, "active": True}
    monkeypatch.setattr("core.security.safe_run",
                        _sahte_safe_run_senaryo(senaryo))
    d = DU.get_auto_update_status()
    assert d["installed"] is True and d["active"] is True
    assert d["next_run"] == "yarin"


class _YokBirimlerPath(type(Path())):  # type: ignore[misc]
    _yoklar: frozenset[str] = frozenset({
        "/etc/systemd/system/pkgforge-auto-update.service",
        "/etc/systemd/system/pkgforge-auto-update.timer"})

    def exists(self):
        return str(self) not in self._yoklar


class _SadeceTimerPath(type(Path())):  # type: ignore[misc]
    def exists(self):
        return str(self) == "/etc/systemd/system/pkgforge-auto-update.timer"


def test_enable_disable_paths(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda n: None)
    ok, msg = DU.enable_auto_update()
    assert ok is False and "systemctl bulunamadı" in msg

    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/systemctl")
    monkeypatch.setattr(DU, "Path", _YokBirimlerPath)
    ok, msg = DU.enable_auto_update()
    assert ok is False and "bulunamadı" in msg

    monkeypatch.setattr(DU, "Path", _SadeceTimerPath)
    komutlar = []
    monkeypatch.setattr("core.security.safe_run",
                        lambda cmd, timeout=0: komutlar.append(cmd)
                        or _rc(0))
    ok, _msg = DU.enable_auto_update()
    assert ok is True and any("service-enable" in c for c in komutlar)

    ok, msg = DU.disable_auto_update()
    assert ok is True


def test_get_delta_logs_paths(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: None)
    assert "systemctl bulunamadı" in DU.get_delta_logs()

    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/systemctl")
    monkeypatch.setattr("core.security.safe_run",
                        lambda cmd, timeout=0: _rc(0, stdout=b"satir1\nsatir2\n"))
    out = DU.get_delta_logs(10)
    assert out == "satir1\nsatir2"

    monkeypatch.setattr("core.security.safe_run",
                        lambda cmd, timeout=0: _rc(1, stderr="yok"))
    assert "Log okunamadı" in DU.get_delta_logs()


def test_notify_update_available(monkeypatch, capsys):
    assert DU.notify_update_available([]) is False

    monkeypatch.setattr("shutil.which", lambda n: None)
    assert DU.notify_update_available(["a", "b"]) is True
    cikti = capsys.readouterr().out
    assert "a" in cikti and "b" in cikti

    gonderilen = []
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/notify-send")
    monkeypatch.setattr("core.security.safe_run",
                        lambda cmd, timeout=0: gonderilen.append(cmd)
                        or _rc(0))
    assert DU.notify_update_available(["x"]) is True
    assert gonderilen and "x" in gonderilen[0][-1]