"""Tur-32 — api_server isleyici katmani, birinci parti (senkron _run)."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import core.api_server as AS


@pytest.fixture()
def senkron(monkeypatch):
    """_run_thread/_run_security_thread'i senkrona cevir, olaylari kaydet."""
    kayit = []

    def sahte(fn, event_name="event/security_done"):
        try:
            sonuc = fn()
            kayit.append((event_name, {"ok": True, "sonuc": sonuc}))
        except (RuntimeError, ValueError, FileNotFoundError, OSError) as exc:
            kayit.append((event_name, {"ok": False, "hata": str(exc)}))

    monkeypatch.setattr(AS, "_run_thread", sahte)
    monkeypatch.setattr(AS, "_run_security_thread", sahte)
    olaylar = []
    monkeypatch.setattr(AS, "_event", lambda m, p: olaylar.append((m, p)))
    return kayit, olaylar


def _mod(monkeypatch, ad, **ozellikler):
    try:
        mod = __import__(ad, fromlist=["x"])
    except ImportError:
        mod = NS()
        monkeypatch.setitem(sys.modules, ad, mod)
    for k, v in ozellikler.items():
        if hasattr(mod, k):
            monkeypatch.setattr(mod, k, v)
        else:
            monkeypatch.setattr(mod, k, v, raising=False)
            # NS modullerde calisir; gercek modulde yeni ozellik eklenmis
            # olur ve undo ile silinir.
    return mod


def test_pipeline_start_ok_and_gates(senkron, tmp_path, monkeypatch):
    import io
    import tarfile

    _, _olaylar = senkron
    olmayan = tmp_path / "yok.deb"
    with pytest.raises(FileNotFoundError):
        AS.handle_pipeline_start({"path": str(olmayan)})

    # Gecersiz mod -> ValueError
    kotu = tmp_path / "kotu.txt"
    kotu.write_text("x")
    with pytest.raises(ValueError, match="Unknown mode"):
        AS.handle_pipeline_start({"path": str(kotu), "mode": "gecersiz"})

    # Belirsiz tarball (hem kaynak hem binary) + mod yok -> ValueError
    belirsiz = tmp_path / "belirsiz.tar.gz"
    with tarfile.open(belirsiz, "w:gz") as tf:
        for name in ("Cargo.toml", "usr/bin/app"):
            info = tarfile.TarInfo(name=name)
            info.size = 1
            tf.addfile(info, io.BytesIO(b"x"))
    with pytest.raises(ValueError, match="Ambiguous"):
        AS.handle_pipeline_start({"path": str(belirsiz)})

    dogru = tmp_path / "iyi.deb"
    dogru.write_bytes(b"D")

    class SahteBoru:
        def __init__(self):
            self.step_changed = NS(connect=lambda f: None)
            self.progress = NS(connect=lambda f: None)
            self.log_message = NS(connect=lambda f: None)
            self.compatibility_ready = NS(connect=lambda f: None)
            self.finished = NS(connect=lambda f: None)

        def stage(self, p, forced=None):
            pass

        def run_staged(self):
            pass

    monkeypatch.setitem(sys.modules, "core.pipeline",
                        NS(ConversionPipeline=SahteBoru))
    yanit = AS.handle_pipeline_start({"path": str(dogru)})
    assert yanit["started"] is True

    AS._pipeline = None
    assert AS.handle_pipeline_cancel({}) == {"ok": True}       # 151-153
    assert AS.handle_pipeline_approve({}) == {"ok": True}      # 157-159
    assert AS.handle_pipeline_dismiss({"message": "m"}) == {"ok": True}


def test_history_handlers(senkron, monkeypatch, tmp_path):
    with pytest.raises(ValueError, match="Invalid package name"):
        AS.handle_history_uninstall({"name": "kötü;rm"})        # 172-173
    iyi = AS.handle_history_uninstall({"name": "demo"})
    assert iyi["requires_privilege"] is True

    with pytest.raises(ValueError, match="Invalid package name"):
        AS.handle_history_rollback({"name": "kötü;rm"})

    _mod(monkeypatch, "core.history_db")   # sadece importi garanti et
    # daha okunur: sahte sinif
    class SahteDB:
        def __init__(self):
            pass
        def get_records_for_package(self, n):
            return []
        def clear_history(self):
            SahteDB.temizlendi = True
    monkeypatch.setitem(sys.modules, "core.history_db",
                        NS(HistoryDB=SahteDB))
    with pytest.raises(FileNotFoundError):
        AS.handle_history_rollback({"name": "demo"})            # 189-190

    kayit = NS(backup_pkg=str(tmp_path / "yedek.pkg.tar.zst"))
    (tmp_path / "yedek.pkg.tar.zst").write_bytes(b"y")
    SahteDB.get_records_for_package = lambda self, n: [kayit]
    sonuc = AS.handle_history_rollback({"name": "demo"})        # 191
    assert sonuc["backup"].endswith("yedek.pkg.tar.zst")

    SahteDB.temizlendi = False
    assert AS.handle_history_clear({}) == {"ok": True}          # 198
    assert SahteDB.temizlendi is True

    # Faz 9 (5.7): history.restore (undo)
    SahteDB.restore_records = lambda self, recs: len(recs)
    assert AS.handle_history_restore({"records": [{}, {}, {}]}) == {"ok": True, "restored": 3}
    assert AS.handle_history_restore({}) == {"ok": True, "restored": 0}
    with pytest.raises(ValueError, match="liste"):
        AS.handle_history_restore({"records": "not-a-list"})


def test_security_sign_and_sbom(senkron, monkeypatch, tmp_path):
    kayit, _ = senkron
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"P")

    _mod(monkeypatch, "core.package_signing",
              sign_package=lambda p, key_path=None, passphrase="": (
                  True, "imzalandi"))
    yanit = AS.handle_security_sign({"pkg_path": str(pkg)})
    assert yanit == {"started": True}
    assert kayit[-1][1]["sonuc"]["ok"] is True

    with pytest.raises(FileNotFoundError):
        AS.handle_security_sign({"pkg_path": str(tmp_path / "yok")})

    _mod(monkeypatch, "core.sbom",
                    generate_sbom=lambda p, t, include_hashes=True: NS(
                        to_dict=lambda: {"dosya": 1}))
    monkeypatch.setattr(AS, "discover_tools", lambda: NS())
    AS.handle_security_sbom({"pkg_path": str(pkg)})
    assert kayit[-1][1]["sonuc"] == {"dosya": 1}


def test_security_quality_provenance_cve(senkron, monkeypatch, tmp_path):
    kayit, _ = senkron
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"P")
    monkeypatch.setattr(AS, "discover_tools", lambda: NS())

    from core.quality_score import QualityReport
    monkeypatch.setattr(
        _mod(monkeypatch, "core.quality_score"), "score_package",
        lambda p, t: QualityReport(package_name="demo", total_score=70))
    AS.handle_security_quality({"pkg_path": str(pkg)})          # 305-309
    assert kayit[-1][1]["sonuc"]["passed"] is True

    kaynak = tmp_path / "kaynak.deb"
    kaynak.write_bytes(b"K")
    _mod(monkeypatch, "core.provenance",
                    create_provenance=lambda **k: NS(
                        to_dict=lambda: {"id": "b1"}),
                    save_provenance=lambda pr, yol: Path(yol).write_text("{}"))
    AS.handle_security_provenance_create(
        {"source_file": str(kaynak), "output_file": str(pkg)})   # 323-332
    assert kayit[-1][1]["sonuc"] == {"id": "b1"}
    with pytest.raises(FileNotFoundError):
        AS.handle_security_provenance_create(
            {"source_file": str(tmp_path / "yok")})

    _mod(monkeypatch, "core.cve_scanner",
               scan_package=lambda p, t: {"bulgu": 0})
    AS.handle_security_cve_scan({"pkg_path": str(pkg)})          # 344-345
    assert kayit[-1][1]["sonuc"] == {"bulgu": 0}


def test_delta_handlers(monkeypatch):
    du = NS(get_auto_update_status=lambda: {"kurulu": False})
    monkeypatch.setitem(sys.modules, "core.delta_updater", du)
    assert AS.handle_delta_status({}) == {"kurulu": False}   # 354-356
    yanit = AS.handle_delta_enable({})
    assert yanit["requires_privilege"] is True                    # 362-363
    yanit = AS.handle_delta_disable({})
    assert yanit["requires_privilege"] is True                    # 367-368


def test_export_handlers(senkron, monkeypatch, tmp_path):
    kayit, _ = senkron
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"P")
    monkeypatch.setattr(AS, "discover_tools", lambda: NS())

    _mod(monkeypatch, "core.oci_builder",
               build_oci_image=lambda p, t, tag=None, output_file=None: (
                   True, "hazir", tmp_path / "cikti.oci"))
    AS.handle_export_oci({"pkg_path": str(pkg), "tag": "v1"})     # 381-385
    assert kayit[-1][1]["sonuc"]["ok"] is True

    appimg = tmp_path / "uygulama.AppImage"
    appimg.write_bytes(b"A")
    _mod(monkeypatch, "core.appimage_converter",
              appimage_to_deb=lambda a, o: (True, "tamam",
                                            tmp_path / "c.deb"))
    AS.handle_export_appimage_to_deb(
        {"appimage_path": str(appimg), "output_dir": str(tmp_path)})
    assert kayit[-1][1]["sonuc"]["deb_path"].endswith("c.deb")    # 397-401
    with pytest.raises(FileNotFoundError):
        AS.handle_export_appimage_to_deb(
            {"appimage_path": str(tmp_path / "yok.AppImage")})

    fc = _mod(monkeypatch, "core.flatpak_converter")
    monkeypatch.setattr(fc, "list_installed_apps", lambda: [NS(ad="Uyg")])
    import dataclasses

    @dataclasses.dataclass
    class Uyg:
        ad: str
    monkeypatch.setattr(fc, "list_installed_apps",
                        lambda: [Uyg("Uyg")])
    liste = AS.handle_export_flatpak_list({})                     # 410
    assert liste[0]["ad"] == "Uyg"

    with pytest.raises(ValueError, match="app_id"):
        AS.handle_export_flatpak_to_deb({})
    monkeypatch.setattr(fc, "flatpak_to_deb",
                        lambda aid, od, branch="stable": (
                            True, "tamam", tmp_path / "f.deb"))
    AS.handle_export_flatpak_to_deb({"app_id": "org.demo"})       # 422-426
    assert kayit[-1][1]["sonuc"]["deb_path"].endswith("f.deb")


def test_graph_build_handler(senkron, monkeypatch, tmp_path):
    kayit, _ = senkron
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"P")
    import dataclasses

    @dataclasses.dataclass
    class Dugum:
        ad: str = "demo"
    dugum = NS(root="demo",
               nodes={"demo": Dugum()},
               stats=lambda: {"kenar": 0},
               to_mermaid=lambda: "graph TD",
               warnings=[])
    _mod(monkeypatch, "core.dep_graph",
              build_dep_graph=lambda p: dugum,
              build_file_dep_graph=lambda p: dugum)
    AS.handle_graph_build({"pkg_path": str(pkg)})                 # 440-450
    assert kayit[-1][1]["sonuc"]["root"] == "demo"
    AS.handle_graph_build({"pkg_path": str(pkg), "files": True})