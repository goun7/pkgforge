"""Coverage itmesi — pipeline _run_pipeline bloklari ve donusturucu modlari."""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest
from PyQt6.QtCore import QCoreApplication, QTimer

import core.pipeline as PL
from core.pipeline import ConversionPipeline


@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


@pytest.fixture()
def pipe(qapp, monkeypatch):
    monkeypatch.setattr(PL, "discover_tools",
                        lambda: NS(missing_required=[], missing_optional=[],
                                   debtap=""))
    return ConversionPipeline()


class Sig:
    def __init__(self):
        self.fns = []

    def connect(self, fn):
        self.fns.append(fn)

    def disconnect(self, fn=None):
        pass

    def emit(self, *a):
        for fn in list(self.fns):
            fn(*a)


DEB = "application/x-deb"


def _meta(**kw):
    base = {"name": "hello", "version": "1.0.0", "arch": "x86_64",
            "arch_mapped": "x86_64", "arch_compatible": True,
            "already_installed": False, "installed_version": "",
            "file_list": [], "package_type": "deb", "depends": []}
    base.update(kw)
    return NS(**base)


def _security_happy(monkeypatch, mime=DEB):
    # NOT: pipeline bu adi modul duzeyinde bagladigi icin PL.* yamalanir
    monkeypatch.setattr(PL, "validate_mime_type", lambda fp, t: mime)
    monkeypatch.setattr(PL, "validate_file_size", lambda fp, mx, wn: None)
    monkeypatch.setattr(PL, "sha256_hash", lambda fp: "a" * 64)
    monkeypatch.setattr(PL, "verify_deb_signature",
                        lambda fp, t: NS(has_signature=False, detail="imzasız"))
    monkeypatch.setattr(PL, "verify_rpm_signature",
                        lambda fp, t: NS(has_signature=False, detail="imzasız"))
    monkeypatch.setattr("core.security.check_compression_bomb",
                        lambda fp, t: None)


def _analysis(monkeypatch, meta=None, boom=False):
    if boom:
        def _raise(fp, t):
            raise ValueError("bozuk deb")
        monkeypatch.setattr(PL, "analyze_package", _raise)
    else:
        monkeypatch.setattr(PL, "analyze_package",
                            lambda fp, t: meta or _meta())


def _settings(monkeypatch, **kw):
    vals = {"clamav_scan": False, "aur_check": False}
    vals.update(kw)

    def load_setting(key, default=False):
        return vals.get(key, default)
    monkeypatch.setattr("i18n.load_setting", load_setting)


def test_missing_required_tools_short_circuits(pipe, tmp_path):
    pipe._tools = NS(missing_required=["makepkg"], missing_optional=[],
                     debtap="")
    pipe._run_pipeline(tmp_path / "x.deb")
    assert "Gerekli araçlar bulunamadı" in pipe._result.message


def test_optional_missing_warns(pipe, tmp_path):
    got = []
    pipe._tools = NS(missing_required=[], missing_optional=["clamscan"],
                     debtap="")
    pipe._log = lambda level, msg: got.append((level, msg))
    pipe._cancelled = True
    pipe._run_pipeline(tmp_path / "x.deb")
    assert any("İsteğe bağlı araçlar eksik" in m for _, m in got)


def test_mime_reject_short_circuits(pipe, monkeypatch, tmp_path):
    def bad(fp, t):
        raise ValueError("kötü MIME")
    monkeypatch.setattr(PL, "validate_mime_type", bad)
    monkeypatch.setattr(PL, "validate_file_size", lambda fp, mx, wn: None)
    f = tmp_path / "x.deb"
    f.write_bytes(b"x")
    pipe._run_pipeline(f)
    assert "kötü MIME" in pipe._result.message


# --- malware tarama blogu -----------------------------------------------------

def _reach_conversion(pipe, monkeypatch, tmp_path, *, scan=None,
                      db_fresh=None, clam_available=True,
                      aur_status=None, aur_boom=False):
    """Guvenlik+analizi sahteleyip donusum adimina kadar surer; donusum
    basarili oldugunda cancel bayragi kaldirir (temiz cikis)."""
    logs = []
    pipe._log = lambda level, msg: logs.append((level, msg))
    _security_happy(monkeypatch)
    _analysis(monkeypatch)
    settings = {"clamav_scan": scan is not None or not clam_available,
                "aur_check": aur_status is not None or aur_boom}
    _settings(monkeypatch, **settings)
    if scan is not None or db_fresh is not None or not clam_available:
        monkeypatch.setattr("core.malware_scanner.check_database_freshness",
                            lambda: db_fresh)
        monkeypatch.setattr("core.malware_scanner.is_clamav_available",
                            lambda: clam_available)
        if scan is not None:
            monkeypatch.setattr("core.malware_scanner.scan_file", scan)
    if aur_status is not None:
        monkeypatch.setattr("core.aur_checker.check_aur",
                            lambda name, ver: NS(status=aur_status,
                                                 aur_version="9.9.9"))
    if aur_boom:
        def boom(name, ver):
            raise RuntimeError("ag yok")
        monkeypatch.setattr("core.aur_checker.check_aur", boom)
    fin = Sig()

    class FakeConv:
        def __init__(self, tools, parent=None):
            self.output_line = Sig()
            self.finished = fin

        def convert(self, deb_path, output_dir):
            def fire():
                pipe._cancelled = True
                fin.emit(True, "ok", "p")
            QTimer.singleShot(0, fire)
    monkeypatch.setattr("core.native_deb_converter.NativeDebConverter", FakeConv)
    f = tmp_path / "x.deb"
    f.write_bytes(b"x")
    pipe._run_pipeline(f)
    return logs


def test_malware_scan_clean_logs_engine(pipe, monkeypatch, tmp_path):
    scan_result = NS(infected=False, engine_version="ClamAV 0.103.0",
                     detail="temiz", infected_files=[])
    logs = _reach_conversion(pipe, monkeypatch, tmp_path, scan=lambda fp, t: scan_result)
    assert any("ClamAV motoru" in m for _, m in logs)
    assert any("temiz" in m for _, m in logs)


def test_malware_scan_db_freshness_warning(pipe, monkeypatch, tmp_path):
    scan_result = NS(infected=False, engine_version="", detail="temiz",
                     infected_files=[])
    logs = _reach_conversion(pipe, monkeypatch, tmp_path,
                             scan=lambda fp, t: scan_result,
                             db_fresh="veritabanı eski")
    assert any("veritabanı eski" in m for _, m in logs)


def test_malware_infected_aborts(pipe, monkeypatch, tmp_path):
    scan_result = NS(infected=True, engine_version="CV", detail="Eicar",
                     infected_files=["eicar.com"])
    _reach_conversion(pipe, monkeypatch, tmp_path, scan=lambda fp, t: scan_result)
    assert "Malware tespit edildi" in pipe._result.message


def test_malware_scanner_exception_tolerated(pipe, monkeypatch, tmp_path):
    def boom(fp, t):
        raise RuntimeError("clamd öldü")
    logs = _reach_conversion(pipe, monkeypatch, tmp_path, scan=boom)
    assert any("Malware taraması başarısız" in m for _, m in logs)


def test_malware_unavailable_skips(pipe, monkeypatch, tmp_path):
    logs = _reach_conversion(pipe, monkeypatch, tmp_path, clam_available=False)
    assert any("clamscan bulunamadı" in m for _, m in logs)


# --- analiz dallari ------------------------------------------------------------

def test_analysis_boom_sets_error(pipe, monkeypatch, tmp_path):
    _security_happy(monkeypatch)
    _settings(monkeypatch)
    _analysis(monkeypatch, boom=True)
    f = tmp_path / "x.deb"
    f.write_bytes(b"x")
    pipe._run_pipeline(f)
    assert "Paket analizi başarısız" in pipe._result.message


def test_incompatible_arch_aborts(pipe, monkeypatch, tmp_path):
    _security_happy(monkeypatch)
    _settings(monkeypatch)
    _analysis(monkeypatch, _meta(arch="arm64", arch_mapped="arm64",
                                 arch_compatible=False))
    f = tmp_path / "x.deb"
    f.write_bytes(b"x")
    pipe._run_pipeline(f)
    assert "Uyumsuz mimari" in pipe._result.message


def test_traversal_detected_aborts(pipe, monkeypatch, tmp_path):
    _security_happy(monkeypatch)
    _settings(monkeypatch)
    _analysis(monkeypatch, _meta(file_list=["../../etc/passwd"]))
    f = tmp_path / "x.deb"
    f.write_bytes(b"x")
    pipe._run_pipeline(f)
    assert "Path traversal saldırısı" in pipe._result.message


# --- AUR bilgilendirme dallari --------------------------------------------------

@pytest.mark.parametrize("status", ["found_newer", "out_of_date",
                                    "found_older", "not_found"])
def test_aur_status_branches_log(pipe, monkeypatch, tmp_path, status):
    logs = _reach_conversion(pipe, monkeypatch, tmp_path, aur_status=status)
    assert any("AUR'da kontrol ediliyor" in m for _, m in logs)


def test_aur_checker_exception_tolerated(pipe, monkeypatch, tmp_path):
    logs = _reach_conversion(pipe, monkeypatch, tmp_path, aur_boom=True)
    assert any("AUR kontrolü yapılamadı" in m for _, m in logs)


# --- donusum sonucu dallari ------------------------------------------------------

def _deb_fake(monkeypatch, result, cancel=False, owner=None):
    fin = Sig()

    class FakeConv:
        def __init__(self, tools, parent=None):
            self.output_line = Sig()
            self.finished = fin

        def convert(self, deb_path, output_dir):
            ok, msg, p = result

            def fire():
                if cancel and owner is not None:
                    owner._cancelled = True
                fin.emit(ok, msg, p)
            QTimer.singleShot(0, fire)
    monkeypatch.setattr("core.native_deb_converter.NativeDebConverter", FakeConv)


def test_conversion_failure_message(pipe, monkeypatch, tmp_path):
    _security_happy(monkeypatch)
    _analysis(monkeypatch)
    _settings(monkeypatch)
    _deb_fake(monkeypatch, (False, "makepkg hata", None))
    f = tmp_path / "x.deb"
    f.write_bytes(b"x")
    pipe._run_pipeline(f)
    assert "makepkg hata" in pipe._result.message


def test_conversion_success_without_pkg_path(pipe, monkeypatch, tmp_path):
    _security_happy(monkeypatch)
    _analysis(monkeypatch)
    _settings(monkeypatch)
    _deb_fake(monkeypatch, (True, "ok", None))
    f = tmp_path / "x.deb"
    f.write_bytes(b"x")
    pipe._run_pipeline(f)
    assert "Dönüştürülmüş paket bulunamadı" in pipe._result.message


# --- alt-mod donusturuculer: subprocess / Qt / debtap yedegi --------------------

def _install_subprocess_fake(monkeypatch, where, results, cancel_from=None,
                             owner=None):
    fin = Sig()

    class FakeSub:
        calls = 0

        def __init__(self, tools, parent=None):
            self.output_line = Sig()
            self.finished = fin

        def convert(self, src, out, *extra):
            idx = min(FakeSub.calls, len(results) - 1)
            FakeSub.calls += 1
            ok, msg, pkg = results[idx]
            if cancel_from is not None and owner is not None \
                    and idx >= cancel_from:
                owner._cancelled = True
            self.finished.emit(ok, msg, pkg)
    monkeypatch.setattr(where, FakeSub)


def test_deb_subprocess_mode_and_debtap_fallback(pipe, monkeypatch, tmp_path):
    monkeypatch.setattr(PL, "_HAS_PYQT6", False)
    _security_happy(monkeypatch)
    _analysis(monkeypatch)
    _settings(monkeypatch)
    pipe._tools = NS(missing_required=[], missing_optional=[],
                     debtap="/usr/bin/debtap")
    _install_subprocess_fake(
        monkeypatch,
        "core.subprocess_converters.NativeDebConverterSubprocess",
        [(False, "native patladı", None)])
    _install_subprocess_fake(
        monkeypatch, "core.deb_converter.DebConverter",
        [(True, "debtap oldu", "cikti.pkg.tar.zst")],
        cancel_from=0, owner=pipe)
    f = tmp_path / "x.deb"
    f.write_bytes(b"x")
    pipe._run_pipeline(f)
    assert pipe._async_success is True


def test_deb_subprocess_fallback_also_fails(pipe, monkeypatch, tmp_path):
    monkeypatch.setattr(PL, "_HAS_PYQT6", False)
    _security_happy(monkeypatch)
    _analysis(monkeypatch)
    _settings(monkeypatch)
    pipe._tools = NS(missing_required=[], missing_optional=[],
                     debtap="/usr/bin/debtap")
    _install_subprocess_fake(
        monkeypatch,
        "core.subprocess_converters.NativeDebConverterSubprocess",
        [(False, "native", None)])
    _install_subprocess_fake(
        monkeypatch, "core.deb_converter.DebConverter",
        [(False, "debtap da patladı", None)])
    f = tmp_path / "x.deb"
    f.write_bytes(b"x")
    pipe._run_pipeline(f)
    assert pipe._async_success is False
    assert "debtap da patladı" in pipe._result.message


def test_rpm_qt_mode_success(pipe, monkeypatch, tmp_path):
    _security_happy(monkeypatch)
    _settings(monkeypatch)
    _analysis(monkeypatch, _meta(package_type="rpm"))
    fin = Sig()

    class FakeRpm:
        def __init__(self, tools, parent=None):
            self.output_line = Sig()
            self.finished = fin

        def convert(self, rpm_path, work_dir, meta):
            QTimer.singleShot(
                0, lambda: (setattr(pipe, "_cancelled", True),
                            fin.emit(True, "rpm ok", "r.pkg.tar.zst")))
    monkeypatch.setattr(PL, "RpmConverter", FakeRpm)
    f = tmp_path / "x.rpm"
    f.write_bytes(b"x")
    pipe._run_pipeline(f)
    assert pipe._async_pkg_path == "r.pkg.tar.zst"


def test_rpm_subprocess_mode_success(pipe, monkeypatch, tmp_path):
    monkeypatch.setattr(PL, "_HAS_PYQT6", False)
    _security_happy(monkeypatch)
    _analysis(monkeypatch, _meta(package_type="rpm"))
    _settings(monkeypatch)
    _install_subprocess_fake(
        monkeypatch,
        "core.subprocess_converters.RpmConverterSubprocess",
        [(True, "rpm sub ok", "r2.pkg.tar.zst")],
        cancel_from=0, owner=pipe)
    f = tmp_path / "x.rpm"
    f.write_bytes(b"x")
    pipe._run_pipeline(f)
    assert pipe._async_pkg_path == "r2.pkg.tar.zst"


# --- temizlik -------------------------------------------------------------------

def test_cleanup_oserror_tolerated(pipe, monkeypatch, tmp_path):
    import shutil as _shutil
    d = tmp_path / "gecici"
    d.mkdir()
    pipe._temp_dir = d
    logs = []
    pipe._log = lambda level, msg: logs.append((level, msg))

    def boom(path):
        raise OSError("kilitli")
    monkeypatch.setattr(_shutil, "rmtree", boom)
    pipe._cleanup()
    assert any("Temizlik hatası" in m for _, m in logs)


# --- kalan tekil dallar ---------------------------------------------------------

def test_cancel_forwards_to_rpm_and_installer(pipe):
    calls = []
    pipe._rpm_converter = NS(cancel=lambda: calls.append("r"))
    pipe._installer = NS(cancel=lambda: calls.append("i"))
    pipe.cancel()
    assert calls == ["r", "i"]


def test_size_warning_recorded_on_result(pipe, monkeypatch, tmp_path):
    _security_happy(monkeypatch)
    monkeypatch.setattr(PL, "validate_file_size",
                        lambda fp, mx, wn: "paket oldukça büyük")
    _analysis(monkeypatch)
    _settings(monkeypatch)
    _deb_fake(monkeypatch, (True, "ok", "p.pkg.tar.zst"), cancel=True,
              owner=pipe)
    f = tmp_path / "x.deb"
    f.write_bytes(b"x")
    pipe._run_pipeline(f)
    assert pipe._result.size_warning == "paket oldukça büyük"


def test_bomb_warning_logged(pipe, monkeypatch, tmp_path):
    logs = []
    pipe._log = lambda level, msg: logs.append((level, msg))
    _security_happy(monkeypatch)
    monkeypatch.setattr("core.security.check_compression_bomb",
                        lambda fp, t: "sıkıştırma bombası şüphesi")
    _analysis(monkeypatch)
    _settings(monkeypatch)
    _deb_fake(monkeypatch, (True, "ok", "p"), cancel=True, owner=pipe)
    f = tmp_path / "x.deb"
    f.write_bytes(b"x")
    pipe._run_pipeline(f)
    assert any("sıkıştırma bombası" in m for _, m in logs)


def test_already_installed_info_logged(pipe, monkeypatch, tmp_path):
    logs = []
    pipe._log = lambda level, msg: logs.append((level, msg))
    _security_happy(monkeypatch)
    _analysis(monkeypatch, _meta(already_installed=True,
                                 installed_version="1.0.0"))
    _settings(monkeypatch)
    _deb_fake(monkeypatch, (True, "ok", "p"), cancel=True, owner=pipe)
    f = tmp_path / "x.deb"
    f.write_bytes(b"x")
    pipe._run_pipeline(f)
    assert any("Zaten kurulu" in m for _, m in logs)


def test_cancel_during_malware_hits_analysis_gate(pipe, monkeypatch, tmp_path):
    _security_happy(monkeypatch)
    _analysis(monkeypatch)
    _settings(monkeypatch, clamav_scan=True)
    def scan(fp, t):
        pipe._cancelled = True
        return NS(infected=False, engine_version="", detail="temiz",
                  infected_files=[])
    monkeypatch.setattr("core.malware_scanner.check_database_freshness",
                        lambda: None)
    monkeypatch.setattr("core.malware_scanner.is_clamav_available",
                        lambda: True)
    monkeypatch.setattr("core.malware_scanner.scan_file", scan)
    f = tmp_path / "x.deb"
    f.write_bytes(b"x")
    pipe._run_pipeline(f)  # analiz kapısinda sessiz cikis (434)
    assert pipe._result.success is False


def test_cancel_after_aur_hits_conversion_gate(pipe, monkeypatch, tmp_path):
    _security_happy(monkeypatch)
    _analysis(monkeypatch)
    _settings(monkeypatch, aur_check=True)
    def check(name, ver):
        pipe._cancelled = True
        return NS(status="not_found", aur_version="")
    monkeypatch.setattr("core.aur_checker.check_aur", check)
    f = tmp_path / "x.deb"
    f.write_bytes(b"x")
    pipe._run_pipeline(f)  # donusum kapisi 495
    assert pipe._result.converted_pkg is None


def test_warning_report_dismissed_with_skip_message(pipe, monkeypatch, tmp_path):
    from core.compatibility_checker import CheckSeverity
    _security_happy(monkeypatch)
    _analysis(monkeypatch)
    _settings(monkeypatch)
    monkeypatch.setattr(PL, "run_compatibility_checks",
                        lambda *a, **k: NS(overall=CheckSeverity.WARNING,
                                           checks=[]))
    pipe._decision_made = True       # onceden reddedilmis karar
    pipe._decision_approved = False
    pipe._skip_install_message = "sadece dönüştür"
    _deb_fake(monkeypatch, (True, "ok", str(tmp_path / "c.pkg.tar.zst")))
    f = tmp_path / "x.deb"
    f.write_bytes(b"x")
    pipe._run_pipeline(f)
    assert pipe._result.success is True
    assert pipe._result.message == "sadece dönüştür"


def test_autoapprove_then_cancel_at_install_gate(pipe, monkeypatch, tmp_path):
    from core.compatibility_checker import CheckSeverity
    _security_happy(monkeypatch)
    _analysis(monkeypatch)
    _settings(monkeypatch)

    seen = []
    def fake_checks(*a, **k):
        seen.append(1)
        pipe._cancelled = True          # kurulum kapisi oncesi iptal
        return NS(overall=CheckSeverity.PASS, checks=[])
    monkeypatch.setattr(PL, "run_compatibility_checks", fake_checks)
    _deb_fake(monkeypatch, (True, "ok", str(tmp_path / "c.pkg.tar.zst")))
    f = tmp_path / "x.deb"
    f.write_bytes(b"x")
    pipe._run_pipeline(f)
    assert seen and pipe._result.success is False
