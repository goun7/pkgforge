"""Tur-33 — api_server isleyici katmani, ikinci parti."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import core.api_server as AS


@pytest.fixture()
def senkron(monkeypatch):
    kayit = []

    def sahte(fn, event_name="event/x"):
        try:
            sonuc = fn()
            kayit.append((event_name, {"ok": True, "sonuc": sonuc}))
        except Exception as exc:  # noqa: BLE001
            kayit.append((event_name, {"ok": False, "hata": str(exc)}))

    monkeypatch.setattr(AS, "_run_thread", sahte)
    monkeypatch.setattr(AS, "_run_security_thread", sahte)
    monkeypatch.setattr(AS, "_event",
                        lambda m, p: kayit.append(("olay:" + m, p)))
    return kayit


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
    return mod


# --- source_generate -------------------------------------------------------------

def test_source_generate_gates_and_flow(senkron, monkeypatch, tmp_path):
    with pytest.raises(ValueError, match="repo_url"):
        AS.handle_source_generate({})

    fs = _mod(monkeypatch, "core.from_source")
    sec = _mod(monkeypatch, "core.security")

    def sahte_safe_run(cmd, timeout=0, **k):
        repo = Path(cmd[4])
        repo.mkdir(parents=True, exist_ok=True)
        (repo / "CMakeLists.txt").write_text("project(demo)")
        return NS(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(sec, "safe_run", sahte_safe_run)
    monkeypatch.setattr(fs, "generate_pkgbuild_from_source",
                        lambda name, url, bs, rd: f"PKGBUILD {name} {bs}")

    yanit = AS.handle_source_generate({"repo_url": "https://x/y/demo.git",
                                       "output_dir": str(tmp_path)})
    assert yanit["started"] is True
    bulunan = [r for r in senkron if r[0] == "event/source_done"]
    assert bulunan and bulunan[0][1]["sonuc"]["build_system"] == "cmake"

    # clone basarisiz yolu
    def kirik_clone(cmd, timeout=0, **k):
        return NS(returncode=128, stderr="baglanti yok")
    monkeypatch.setattr(sec, "safe_run", kirik_clone)
    AS.handle_source_generate({"repo_url": "https://x/kirik.git",
                               "output_dir": str(tmp_path)})
    hatali = [r for r in senkron if r[0] == "event/source_done"
              and not r[1]["ok"]]
    assert hatali and "git clone failed" in hatali[-1][1]["hata"]


# --- system ----------------------------------------------------------------------

def test_system_handlers(senkron, monkeypatch):
    with pytest.raises(ValueError, match="package_name"):
        AS.handle_system_cross_check({})
    cc = _mod(monkeypatch, "core.cross_check")
    from dataclasses import dataclass

    @dataclass
    class Rapor:
        yerel: str = "1.0"
    monkeypatch.setattr(cc, "cross_check_package",
                        lambda n, v="": Rapor())
    AS.handle_system_cross_check({"package_name": "demo"})       # 521-524
    assert senkron[-1][1]["sonuc"]["yerel"] == "1.0"

    sc = _mod(monkeypatch, "core.snapshot_cleanup")
    monkeypatch.setattr(sc, "get_cleanup_status",
                        lambda: {"kurulu": False})
    monkeypatch.setattr(sc, "install_cleanup_service",
                        lambda max_age_days=7: (True, "kuruldu"))
    monkeypatch.setattr(sc, "remove_cleanup_service",
                        lambda: (True, "kaldirildi"))
    assert AS.handle_system_snapshot_status({}) == {"kurulu": False}
    # artik gercek kurulumu baslatir (thread), hemen {"started": True} doner
    assert AS.handle_system_snapshot_install({})["started"] is True
    assert AS.handle_system_snapshot_remove({})["started"] is True

    rv = _mod(monkeypatch, "core.rollback_verify")

    @dataclass
    class Sonuc:
        dogrulandi: bool = True
    monkeypatch.setattr(rv, "verify_rollback", lambda: Sonuc())
    AS.handle_system_verify_rollback({})                          # 549-552
    assert senkron[-1][1]["sonuc"]["dogrulandi"] is True

    bm = _mod(monkeypatch, "core.benchmark")

    @dataclass
    class Bench:
        skor: int = 9
        passed: bool = True
    monkeypatch.setattr(bm, "run_benchmarks",
                        lambda quick=False: Bench())
    AS.handle_system_benchmark({"quick": True})                   # 563-567
    assert senkron[-1][1]["sonuc"]["skor"] == 9


def test_system_open_path(senkron, monkeypatch, tmp_path):
    import subprocess as _sp

    with pytest.raises(FileNotFoundError):
        AS.handle_system_open_path({"path": str(tmp_path / "yok")})

    calls = []

    def sahte_popen(cmd, **k):
        calls.append(cmd)
        return NS()

    monkeypatch.setattr(_sp, "Popen", sahte_popen)

    dosya = tmp_path / "paket.pkg.tar.zst"
    dosya.write_bytes(b"P")
    assert AS.handle_system_open_path({"path": str(dosya)}) == {"ok": True}
    assert calls[-1] == ["xdg-open", str(tmp_path)]

    assert AS.handle_system_open_path({"path": str(tmp_path)}) == {"ok": True}
    assert calls[-1] == ["xdg-open", str(tmp_path)]


def test_system_install_pkg(senkron, monkeypatch, tmp_path):
    with pytest.raises(FileNotFoundError):
        AS.handle_system_install_pkg({"pkg_path": str(tmp_path / "yok.pkg.tar.zst")})

    duz = tmp_path / "duz.txt"
    duz.write_bytes(b"x")
    with pytest.raises(ValueError):
        AS.handle_system_install_pkg({"pkg_path": str(duz)})

    pkg = tmp_path / "demo-1.0-1-x86_64.pkg.tar.zst"
    pkg.write_bytes(b"P")

    monkeypatch.setattr(AS, "discover_tools", lambda: NS(pkexec="", pacman=""))
    with pytest.raises(RuntimeError):
        AS.handle_system_install_pkg({"pkg_path": str(pkg)})

    sec = _mod(monkeypatch, "core.security")
    monkeypatch.setattr(sec, "safe_run",
                        lambda cmd, timeout=0, **k: NS(returncode=0))
    monkeypatch.setattr(AS, "discover_tools",
                        lambda: NS(pkexec="/usr/bin/pkexec", pacman="/usr/bin/pacman"))
    assert AS.handle_system_install_pkg({"pkg_path": str(pkg)})["started"] is True
    bulunan = [r for r in senkron if r[0] == "event/install_done"]
    assert bulunan and bulunan[-1][1]["sonuc"]["ok"] is True

    monkeypatch.setattr(sec, "safe_run",
                        lambda cmd, timeout=0, **k: NS(returncode=1))
    AS.handle_system_install_pkg({"pkg_path": str(pkg)})
    hatali = [r for r in senkron if r[0] == "event/install_done"]
    assert hatali and hatali[-1][1]["sonuc"]["ok"] is False


# --- plugin ----------------------------------------------------------------------

def test_plugin_handlers(senkron, monkeypatch):
    pi = _mod(monkeypatch, "core.plugins")
    monkeypatch.setattr(pi, "reload_plugins", lambda: None)
    mp = _mod(monkeypatch, "core.plugins.marketplace")
    monkeypatch.setattr(mp, "install_plugin",
                        lambda name, version="latest", force=False: (
                            Path("/eklenti") / name))

    AS.handle_plugin_install({"name": "demo"})                    # 583-586
    assert senkron[-1][1]["sonuc"]["path"] == "/eklenti/demo"

    monkeypatch.setattr(mp, "is_valid_plugin_name", lambda n: n == "demo")
    monkeypatch.setattr(mp, "uninstall_plugin", lambda n: True)
    assert AS.handle_plugin_uninstall({"name": "demo"}) == {"ok": True}

    with pytest.raises(ValueError, match="Invalid plugin"):
        AS.handle_plugin_uninstall({"name": "kotu!"})
    monkeypatch.setattr(mp, "uninstall_plugin", lambda n: False)
    with pytest.raises(FileNotFoundError):
        AS.handle_plugin_uninstall({"name": "demo"})

    monkeypatch.setattr(mp, "update_plugin",
                        lambda n: (True, "guncellendi", Path("/yeni")))
    AS.handle_plugin_update({"name": "demo"})                     # 612-616
    assert senkron[-1][1]["sonuc"]["ok"] is True


# --- compare_diff ----------------------------------------------------------------

def test_compare_diff(senkron, monkeypatch, tmp_path):
    eski = tmp_path / "eski.pkg.tar.zst"
    yeni = tmp_path / "yeni.pkg.tar.zst"
    eski.write_bytes(b"E"); yeni.write_bytes(b"Y")
    sbom_mod = _mod(monkeypatch, "core.sbom")
    belge = NS()
    monkeypatch.setattr(sbom_mod, "generate_sbom",
                        lambda p, t, include_hashes=True: belge)
    monkeypatch.setattr(sbom_mod, "diff_sboms",
                        lambda a, b: NS(to_dict=lambda: {"fark": 0}))
    monkeypatch.setattr(AS, "discover_tools", lambda: NS())
    AS.handle_compare_diff({"old_path": str(eski), "new_path": str(yeni)})
    assert senkron[-1][1]["sonuc"] == {"fark": 0}                 # 635-639

    with pytest.raises(FileNotFoundError):
        AS.handle_compare_diff({"old_path": str(tmp_path / "yok"),
                                "new_path": str(yeni)})
    with pytest.raises(FileNotFoundError):
        AS.handle_compare_diff({"old_path": str(eski),
                                "new_path": str(tmp_path / "yok")})


# --- aur -------------------------------------------------------------------------

def test_validate_aur_name():
    for kotu in ("", "-bas", ".nokta", "..", "a" * 256):
        with pytest.raises(ValueError):
            AS._validate_aur_name(kotu)
    AS._validate_aur_name("yay-bin")                  # gecerli


def test_aur_handlers(senkron, monkeypatch, tmp_path):
    ac = _mod(monkeypatch, "core.aur_checker")
    monkeypatch.setattr(ac, "search_aur",
                        lambda q, limit=25: [{"isim": q}])
    AS.handle_aur_search({"query": "yay", "limit": 5})            # 664-667
    assert senkron[-1][1]["sonuc"][0]["isim"] == "yay"

    from dataclasses import dataclass

    @dataclass
    class AurBilgi:
        ad: str = "yay"
    monkeypatch.setattr(ac, "check_aur", lambda n: AurBilgi())
    AS.handle_aur_info({"name": "yay"})                           # 679-682
    assert senkron[-1][1]["sonuc"]["ad"] == "yay"

    with pytest.raises(ValueError):
        AS.handle_aur_info({"name": "-kotu"})
    with pytest.raises(ValueError):
        AS.handle_aur_build({"name": ""})

    import subprocess as _sp

    def sahte_run(cmd, **k):
        if cmd[:2] == ["git", "clone"]:
            hedef = Path(cmd[4]); hedef.mkdir(parents=True, exist_ok=True)
            (hedef / "PKGBUILD").write_text("pkgname=x")
            return NS(returncode=0, stderr="")
        if cmd[0] == "makepkg":
            wd = Path(k["cwd"])
            (wd / "x-1.0-1-x86_64.pkg.tar.zst").write_bytes(b"P")
            return NS(returncode=0, stderr="")
        return NS(returncode=0, stderr="")

    monkeypatch.setattr(_sp, "run", sahte_run)
    AS.handle_aur_build({"name": "demo-paket"})                   # 695-720
    mutlu_kayit = [r for r in senkron if r[0] == "event/aur_build_done"
                   and r[1]["ok"]][-1]
    sonuc = mutlu_kayit[1]["sonuc"]
    assert sonuc["name"] == "demo-paket" and sonuc["installed"] is False

    # clone basarisiz
    def kirik(cmd, **k):
        return NS(returncode=128, stderr="agir erisim reddi")
    monkeypatch.setattr(_sp, "run", kirik)
    AS.handle_aur_build({"name": "kirik"})
    hata_kaydi = [r for r in senkron if r[0] == "event/aur_build_done"
                  and not r[1]["ok"]]
    assert hata_kaydi and "git clone başarısız" in hata_kaydi[-1][1]["hata"]