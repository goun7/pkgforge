"""Coverage itmesi — cli.py komut handlerlari."""
from __future__ import annotations

import argparse

import cli


def _doctor_report(ok=True):
    return {
        "version": "2.0.0",
        "tools": {"ok": ok, "missing_required": [] if ok else ["pacman"],
                  "missing_optional": [], "debtap": ok, "pkexec": ok,
                  "distrobox": False},
        "keyring": {"ok": False, "detail": "yok"},
        "storage": {"ok": True, "profile": "default",
                    "config_dir": "/tmp/x", "history_db_exists": True,
                    "queue_db_exists": False},
        "dbus": {"ok": False},
        "scheduler": {"ok": True, "tasks": 4},
        "ok": ok,
    }


def test_cmd_doctor_healthy(monkeypatch, capsys):
    monkeypatch.setattr("core.doctor.run_doctor", lambda: _doctor_report(True))
    rc = cli._cmd_doctor(argparse.Namespace())
    out = capsys.readouterr().out
    assert rc == 0
    assert "PkgForge Doctor" in out
    assert "Genel" in out


def test_cmd_doctor_missing_tools(monkeypatch, capsys):
    monkeypatch.setattr("core.doctor.run_doctor",
                        lambda: _doctor_report(False))
    rc = cli._cmd_doctor(argparse.Namespace())
    out = capsys.readouterr().out
    assert rc == 1
    assert "pacman" in out


def test_cmd_wrapped_empty_year(monkeypatch, capsys):
    data = {"year": 2026, "total": 0}
    monkeypatch.setattr("core.stats_wrapped.build_wrapped",
                        lambda year=None: data)
    rc = cli._cmd_wrapped(argparse.Namespace(year=2026))
    out = capsys.readouterr().out
    assert rc == 0
    assert "2026" in out


def test_cmd_wrapped_full(monkeypatch, capsys):
    data = {"year": 2026, "total": 5, "success": 4, "failed": 1,
            "success_rate": 80.0, "distinct_packages": 3,
            "busiest_month": "Mart", "by_type": {"deb": 4, "rpm": 1},
            "top_packages": [{"name": "hello", "count": 2}]}
    monkeypatch.setattr("core.stats_wrapped.build_wrapped",
                        lambda year=None: data)
    rc = cli._cmd_wrapped(argparse.Namespace(year=None))
    out = capsys.readouterr().out
    assert rc == 0
    assert "Toplam dönüşüm: 5" in out
    assert "Mart" in out
    assert "hello" in out


def test_cmd_benchmark_saves_baseline(monkeypatch, tmp_path, capsys):
    from core.benchmark import BenchmarkReport, BenchmarkResult
    rep = BenchmarkReport()
    rep.results.append(BenchmarkResult(name="hizli", duration_ms=7))
    monkeypatch.setattr("core.benchmark.run_benchmarks",
                        lambda test_file=None, quick=False: rep)
    target = tmp_path / "base.json"
    rc = cli._cmd_benchmark(argparse.Namespace(
        bench_file=None, quick=True, baseline=None,
        save_baseline=str(target)))
    out = capsys.readouterr().out
    assert rc == 0
    assert target.is_file()
    assert "Baseline kaydedildi" in out


def test_cmd_benchmark_baseline_regression(monkeypatch, tmp_path, capsys):
    from core.benchmark import BenchmarkReport, BenchmarkResult
    base = tmp_path / "base.json"
    base.write_text(chr(123) + chr(34) + "results" + chr(34)
                    + ": {" + chr(34) + "x" + chr(34) + ": {"
                    + chr(34) + "duration_ms" + chr(34) + ": 100}}}")
    rep = BenchmarkReport()
    rep.results.append(BenchmarkResult(name="x", duration_ms=500))
    monkeypatch.setattr("core.benchmark.run_benchmarks",
                        lambda test_file=None, quick=False: rep)
    rc = cli._cmd_benchmark(argparse.Namespace(
        bench_file=None, quick=True, baseline=str(base),
        save_baseline=None))
    out = capsys.readouterr().out
    assert rc == 1
    assert "regresyon" in out or chr(10060) in out


def test_cmd_list_empty_is_quiet_ok(capsys):
    rc = cli._cmd_list(argparse.Namespace())
    out = capsys.readouterr().out
    assert rc == 0 and out.strip() != ""


def test_cmd_health_empty_history(capsys):
    rc = cli._cmd_health(argparse.Namespace())
    out = capsys.readouterr().out
    assert rc == 0
    assert "Henüz kayıtlı dönüşüm" in out


def test_cmd_delta_status(monkeypatch, capsys):
    st = {"systemctl_available": True, "installed": False,
          "active": False, "next_run": "",
          "xdelta3_available": True, "experimental": True}
    monkeypatch.setattr("core.delta_updater.get_auto_update_status",
                        lambda: st)
    rc = cli._cmd_delta(argparse.Namespace(delta_action="status"))
    out = capsys.readouterr().out
    assert rc == 0 and "Delta Auto-Update" in out


def test_cmd_delta_enable_disable(monkeypatch, capsys):
    monkeypatch.setattr("core.delta_updater.enable_auto_update",
                        lambda: (True, "etkin"))
    assert cli._cmd_delta(
        argparse.Namespace(delta_action="enable")) == 0
    monkeypatch.setattr("core.delta_updater.disable_auto_update",
                        lambda: (False, "reddi"))
    assert cli._cmd_delta(
        argparse.Namespace(delta_action="disable")) == 1


def test_cmd_delta_invalid_action(capsys):
    rc = cli._cmd_delta(argparse.Namespace(delta_action="boyle-bisey"))
    out = capsys.readouterr().out
    assert rc == 1 and "Geçersiz delta" in out


def test_cmd_completion_bash(capsys):
    rc = cli._cmd_completion(argparse.Namespace(shell="bash"))
    out = capsys.readouterr().out
    assert rc == 0 and "pkgforge" in out


def test_cmd_sign_missing_file(tmp_path, capsys):
    rc = cli._cmd_sign(argparse.Namespace(
        package=str(tmp_path / "yok.pkg.tar.zst"), key=None))
    out = capsys.readouterr().out
    assert rc == 1 and "bulunamad" in out


def test_cmd_remove_invalid_name(monkeypatch, capsys):
    called = {"n": 0}
    monkeypatch.setattr(cli, "safe_run",
                        lambda cmd, timeout=None: called.update(n=1))
    rc = cli._cmd_remove(argparse.Namespace(package="kötü isim"))
    capsys.readouterr()
    assert rc == 1 and called["n"] == 0
