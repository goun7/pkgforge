"""Coverage itmesi - cli benchmark butcesi, sign/verify, scan-image, check-updates."""
from __future__ import annotations

from types import SimpleNamespace as NS

import cli
import core.malware_scanner as MS


def _tools():
    return NS(missing_required=[], missing_optional=[], pkexec="pk", pacman="pm")


def test_benchmark_pass_with_baseline(capsys, monkeypatch, tmp_path):
    import core.benchmark as BM
    import core.perf_budget as PB
    report = NS(summary=lambda: "ozet", passed=True)
    monkeypatch.setattr(BM, "run_benchmarks", lambda **kw: report)
    base = {"pkg": {"p": 10}}
    monkeypatch.setattr(PB, "load_baseline", lambda p: base)
    monkeypatch.setattr(PB, "compare", lambda r, b:
                        {"compared": 2, "threshold": 0.1, "regressions": [],
                         "improvements": [{"name": "x", "baseline_ms": 20,
                                           "current_ms": 10, "delta_pct": -50.0}],
                         "ok": True})
    rc = cli._cmd_benchmark(NS(bench_file=None, quick=True,
                               baseline=str(tmp_path / "b.json"), save_baseline=None))
    out = capsys.readouterr().out
    assert rc == 0 and "Perf bütçesi içinde" in out and "🚀" in out


def test_benchmark_regressions_fail(capsys, monkeypatch, tmp_path):
    import core.benchmark as BM
    import core.perf_budget as PB
    report = NS(summary=lambda: "ozet", passed=True)
    monkeypatch.setattr(BM, "run_benchmarks", lambda **kw: report)
    monkeypatch.setattr(PB, "load_baseline", lambda p: {"k": 1})
    monkeypatch.setattr(PB, "compare", lambda r, b:
                        {"compared": 2, "threshold": 0.1,
                         "regressions": [{"name": "y", "baseline_ms": 5,
                                          "current_ms": 50, "delta_pct": 900.0}],
                         "improvements": [], "ok": False})
    rc = cli._cmd_benchmark(NS(bench_file=None, quick=False,
                               baseline=str(tmp_path / "b.json"), save_baseline=None))
    assert rc == 1 and "regresyon" in capsys.readouterr().out


def test_benchmark_save_and_missing_baseline(capsys, monkeypatch, tmp_path):
    import core.benchmark as BM
    import core.perf_budget as PB
    report = NS(summary=lambda: "ozet", passed=False)
    monkeypatch.setattr(BM, "run_benchmarks", lambda **kw: report)
    saved = {}

    def fake_save(r, p):
        saved["p"] = str(p)
        return str(p)
    monkeypatch.setattr(PB, "save_baseline", fake_save)
    monkeypatch.setattr(PB, "load_baseline", lambda p: None)
    rc = cli._cmd_benchmark(NS(bench_file=None, quick=False,
                               baseline=str(tmp_path / "yok.json"),
                               save_baseline=str(tmp_path / "out.json")))
    out = capsys.readouterr().out
    assert rc == 1 and "başarısız" in out and "Baseline kaydedildi" in out
    assert "bulunamadı ya da boş" in out


def test_sign_verify_paths(capsys, monkeypatch, tmp_path):
    import core.package_signing as PS
    f = tmp_path / "p.pkg.tar.zst"
    f.write_bytes(b"x")
    calls = []

    def fake_sign(p, key=None):
        calls.append(("sign", key))
        return True, "imzalandi"
    monkeypatch.setattr(PS, "sign_package", fake_sign)
    rc = cli._cmd_sign(NS(package=str(f), key=None))
    assert rc == 0 and calls and calls[0][0] == "sign"

    def bad_sign(p, key=None):
        return False, "anahtar reddi"
    monkeypatch.setattr(PS, "sign_package", bad_sign)
    rc2 = cli._cmd_sign(NS(package=str(f), key=str(tmp_path / "k.key")))
    assert rc2 == 1 and "anahtar reddi" in capsys.readouterr().out


def test_scan_image_no_tools(capsys, monkeypatch, tmp_path):
    f = tmp_path / "img.tar"
    f.write_bytes(b"x")
    monkeypatch.setattr(MS.shutil, "which", lambda n: None)
    rc = cli._cmd_scan_image(NS(image=str(f)))
    assert rc == 1 and "Tarama aracı bulunamadı" in capsys.readouterr().out


def test_check_updates_once_clean(capsys, monkeypatch):
    monkeypatch.setattr(cli, "check_all_installed_updates", list)
    rc = cli._cmd_check_updates(NS(watch=False, interval=5))
    assert rc == 0


def test_check_updates_found(capsys, monkeypatch):
    rows = [NS(has_update=True, package_name="demo", detail="1.0 → 2.0"),
            NS(has_update=False, package_name="sabit", detail="guncel")]
    monkeypatch.setattr(cli, "check_all_installed_updates", lambda: rows)
    rc = cli._cmd_check_updates(NS(watch=False, interval=5))
    out = capsys.readouterr().out
    assert rc == 0 and "1 güncelleme mevcut" in out and "demo" in out