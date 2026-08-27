"""Coverage itmesi — cli.py komut handlerlari."""
from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

import cli
import core.malware_scanner as MS


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


def _mini_zst(tmp_path):
    import subprocess
    d = tmp_path / "stage"
    d.mkdir(exist_ok=True)
    (d / ".PKGINFO").write_text("pkgname = demo")
    tar = tmp_path / "a.tar"
    with open(tar, "wb") as fh:
        subprocess.run(["tar", "cf", "-", "-C", str(d), ".PKGINFO"],
                       stdout=fh, check=True)
    zst = tmp_path / "demo-1.0-1-x86_64.pkg.tar.zst"
    subprocess.run(["zstd", "-qf", str(tar), "-o", str(zst)], check=True)
    return zst


def test_cmd_sbom_missing_package(capsys, tmp_path):
    rc = cli._cmd_sbom(argparse.Namespace(
        package=str(tmp_path / "yok.pkg.tar.zst"), output_dir=None,
        no_hashes=False, diff=None))
    assert rc == 1 and "bulunamad" in capsys.readouterr().out


def test_cmd_sbom_requires_package_arg(capsys):
    rc = cli._cmd_sbom(argparse.Namespace(
        package=None, output_dir=None, no_hashes=False, diff=None))
    out = capsys.readouterr().out
    assert rc == 1 and "Paket yolu gerekli" in out


def test_cmd_sbom_generates_json(tmp_path, capsys):
    pkg = _mini_zst(tmp_path)
    outdir = tmp_path / "cikti"
    rc = cli._cmd_sbom(argparse.Namespace(
        package=str(pkg), output_dir=str(outdir), no_hashes=True,
        diff=None))
    out = capsys.readouterr().out
    assert rc == 0
    assert (outdir / "demo-1.0-1-x86_64.pkg.tar.zst.spdx.json").is_file()
    assert "SBOM dosyası" in out


def test_cmd_sbom_diff_missing_old(capsys, tmp_path):
    rc = cli._cmd_sbom(argparse.Namespace(
        package=None, output_dir=None, no_hashes=False,
        diff=[str(tmp_path / "eski.pkg.tar.zst"),
              str(tmp_path / "yeni.pkg.tar.zst")]))
    assert rc == 1


def test_cmd_abi_check_missing_file(capsys, tmp_path):
    rc = cli._cmd_abi_check(argparse.Namespace(
        package=str(tmp_path / "yok.pkg.tar.zst")))
    assert rc == 1 and "bulunamad" in capsys.readouterr().out


def test_cmd_abi_check_report_paths(monkeypatch, capsys, tmp_path):
    from types import SimpleNamespace as NS
    good = NS(summary=lambda: "rapor", passed=True, error_count=0)
    monkeypatch.setattr("core.abi_scanner.check_abi_compatibility",
                        lambda p: good)
    f = tmp_path / "x.pkg.tar.zst"
    f.write_bytes(b"x")
    assert cli._cmd_abi_check(argparse.Namespace(package=str(f))) == 0
    bad = NS(summary=lambda: "kotu", passed=False, error_count=3)
    monkeypatch.setattr("core.abi_scanner.check_abi_compatibility",
                        lambda p: bad)
    assert cli._cmd_abi_check(argparse.Namespace(package=str(f))) == 1


def test_cmd_quality_missing_file(capsys, tmp_path):
    rc = cli._cmd_quality(argparse.Namespace(
        package=str(tmp_path / "yok.pkg.tar.zst")))
    assert rc == 1 and "bulunamad" in capsys.readouterr().out


def test_cmd_quality_pass_and_fail(monkeypatch, capsys, tmp_path):
    from types import SimpleNamespace as NS
    f = tmp_path / "x.pkg.tar.zst"
    f.write_bytes(b"x")
    monkeypatch.setattr("core.quality_score.score_package",
                        lambda p, t: NS(summary=lambda: "skor", passed=True))
    assert cli._cmd_quality(argparse.Namespace(package=str(f))) == 0
    monkeypatch.setattr("core.quality_score.score_package",
                        lambda p, t: NS(summary=lambda: "dusuk", passed=False))
    assert cli._cmd_quality(argparse.Namespace(package=str(f))) == 1


def test_cmd_verify_rollback_paths(monkeypatch, capsys):
    from types import SimpleNamespace as NS
    monkeypatch.setattr("core.rollback_verify.verify_rollback",
                        lambda: NS(detail="drill ok", verified=True))
    assert cli._cmd_verify_rollback(argparse.Namespace()) == 0
    monkeypatch.setattr("core.rollback_verify.verify_rollback",
                        lambda: NS(detail="kırık", verified=False))
    assert cli._cmd_verify_rollback(argparse.Namespace()) == 1


def test_cmd_graph_missing_file(capsys):
    rc = cli._cmd_graph(argparse.Namespace(
        package="yok-paket-abc", files=False, format="ascii"))
    out = capsys.readouterr().out
    assert rc == 1 and "bulunamadı" in out


def _stage_pkg(tmp_path):
    import subprocess
    d = tmp_path / "st"
    d.mkdir(exist_ok=True)
    (d / ".PKGINFO").write_text(
        chr(10).join(["pkgname = demo", "pkgver = 1.0",
                      "depend = glibc"]))
    tar = tmp_path / "a.tar"
    with open(tar, "wb") as fh:
        subprocess.run(["tar", "cf", "-", "-C", str(d), ".PKGINFO"],
                       stdout=fh, check=True)
    zst = tmp_path / "demo-1.0-1-x86_64.pkg.tar.zst"
    subprocess.run(["zstd", "-qf", str(tar), "-o", str(zst)], check=True)
    return zst


def test_cmd_graph_ascii_and_mermaid(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("core.dep_graph.shutil.which",
                        lambda n: "/usr/bin/pacman")
    real_run = __import__("core.dep_graph", fromlist=["safe_run"]).safe_run

    def fake_run(cmd, timeout=None):
        if len(cmd) > 1 and cmd[1] == "-Qi":
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        if len(cmd) > 1 and cmd[1] == "xf":
            info = chr(10).join(["pkgname = demo", "pkgver = 1.0",
                                 "depend = glibc"])
            return SimpleNamespace(returncode=0, stdout=info, stderr="")
        return real_run(cmd, timeout=timeout)
    monkeypatch.setattr("core.dep_graph.safe_run", fake_run)
    pkg = _stage_pkg(tmp_path)
    ns = argparse.Namespace(package=str(pkg), files=False, format="ascii")
    assert cli._cmd_graph(ns) == 0
    out = capsys.readouterr().out
    assert "Bağımlılık Grafiği: demo" in out
    ns.format = "mermaid"
    assert cli._cmd_graph(ns) == 0
    assert "demo" in capsys.readouterr().out


def test_cmd_plugin_install_success(monkeypatch, capsys):
    calls = {}

    def fake_install(name, version="latest", force=False):
        calls.update(name=name, version=version, force=force)
        return Path("/plugins/x")
    monkeypatch.setattr("core.plugins.marketplace.install_plugin", fake_install)
    monkeypatch.setattr("core.plugins.reload_plugins", lambda: ["a", "b"])
    ns = argparse.Namespace(plugin_action="install", name="x==1.2",
                            force=False, version="latest")
    rc = cli._cmd_plugin(ns)
    out = capsys.readouterr().out
    assert rc == 0 and calls["version"] == "1.2"
    assert "2 plugin aktif" in out


def test_cmd_plugin_install_failures(monkeypatch, capsys):
    def nf(name, version="latest", force=False):
        raise FileNotFoundError("bulunamadi")
    monkeypatch.setattr("core.plugins.marketplace.install_plugin", nf)
    ns = argparse.Namespace(plugin_action="install", name="x",
                            force=False, version="latest")
    assert cli._cmd_plugin(ns) == 1

    def re_(name, version="latest", force=False):
        raise RuntimeError("indirme hatasi")
    monkeypatch.setattr("core.plugins.marketplace.install_plugin", re_)
    capsys.readouterr()
    assert cli._cmd_plugin(ns) == 1
    assert "Kurulum başarısız" in capsys.readouterr().out


def test_cmd_plugin_remove_paths(monkeypatch, capsys):
    monkeypatch.setattr("core.plugins.marketplace.uninstall_plugin",
                        lambda n: True)
    removed = {"n": 0}
    monkeypatch.setattr("core.plugins.reload_plugins",
                        lambda: removed.update(n=removed["n"] + 1) or [])
    ns = argparse.Namespace(plugin_action="remove", name="x")
    assert cli._cmd_plugin(ns) == 0 and removed["n"] == 1

    monkeypatch.setattr("core.plugins.marketplace.uninstall_plugin",
                        lambda n: False)
    assert cli._cmd_plugin(ns) == 1


def _rec(idx, status="converted", ptype="deb", name="demo",
         ts="2026-08-25 10:00:00", output_pkg="", backup_pkg="",
         source_url=""):
    return SimpleNamespace(
        id=idx, timestamp=ts, package_name=name, package_type=ptype,
        status=status, original_file="/kaynak/" + name + ".deb",
        output_pkg=output_pkg, backup_pkg=backup_pkg,
        source_url=source_url, http_etag="", http_last_modified="")


def _fake_db(monkeypatch, records):
    class FakeDB:
        def get_history(self, limit=100):
            return records
    monkeypatch.setattr(cli, "HistoryDB", FakeDB)


def test_cmd_audit_empty(monkeypatch, capsys):
    _fake_db(monkeypatch, [])
    rc = cli._cmd_audit(argparse.Namespace(date_from=None, date_to=None))
    out = capsys.readouterr().out
    assert rc == 0 and "Kayıt bulunamadı" in out


def test_cmd_audit_date_filter(monkeypatch, capsys):
    recs = [_rec(1, ts="2026-01-01 00:00:00"),
            _rec(2, ts="2026-06-15 12:00:00")]
    _fake_db(monkeypatch, recs)
    ns = argparse.Namespace(date_from="2026-06-01", date_to=None)
    rc = cli._cmd_audit(ns)
    out = capsys.readouterr().out
    assert rc == 0 and "Toplam kayıt: 1" in out


def test_cmd_audit_full_report_with_issues(monkeypatch, tmp_path, capsys):
    missing_out = str(tmp_path / "silinmis.pkg.tar.zst")
    recs = [
        _rec(1, status="installed", name="a", output_pkg=missing_out),
        _rec(2, status="install_failed", name="b"),
        _rec(3, status="oci_built", ptype="rpm", name="c"),
    ]
    recs.extend(_rec(i, status="installed", name="hizli-" + str(i))
                for i in range(4, 9))
    _fake_db(monkeypatch, recs)
    rc = cli._cmd_audit(argparse.Namespace(date_from=None, date_to=None))
    out = capsys.readouterr().out
    assert rc == 0
    assert "bütünlük sorunu" in out
    assert "otomatik süreç" in out
    assert "sorun kalıcı" in out
    assert "Provenance Doğrulama" in out


def test_cmd_audit_clean_and_provenance(monkeypatch, tmp_path, capsys):
    pkg = tmp_path / "mevcut.pkg.tar.zst"
    pkg.write_bytes(b"x")
    (tmp_path / "mevcut.pkg.tar.zst.provenance.json").write_text("{}")
    recs = [_rec(1, status="installed", name="tek",
                 output_pkg=str(pkg), source_url="https://x/y")]
    _fake_db(monkeypatch, recs)
    rc = cli._cmd_audit(argparse.Namespace(date_from=None, date_to=None))
    out = capsys.readouterr().out
    assert rc == 0
    assert "Tüm dosyalar mevcut" in out
    assert "Anomali tespit edilmedi" in out
    assert "1/1 kayıt için provenance" in out


def test_cmd_publish_missing_file(capsys, tmp_path):
    rc = cli._cmd_publish(argparse.Namespace(
        package=str(tmp_path / "yok.pkg.tar.zst"), output_dir=None,
        aur_url=None))
    assert rc == 1 and "bulunamad" in capsys.readouterr().out


def test_cmd_publish_prepare_fail(monkeypatch, capsys, tmp_path):
    f = tmp_path / "x.pkg.tar.zst"
    f.write_bytes(b"x")
    monkeypatch.setattr("core.aur_publish.prepare_aur_package",
                        lambda p, o: (False, "PKGBUILD yok", None))
    rc = cli._cmd_publish(argparse.Namespace(package=str(f),
                                             output_dir=None, aur_url=None))
    out = capsys.readouterr().out
    assert rc == 1 and "PKGBUILD yok" in out


def test_cmd_publish_success_without_push(monkeypatch, capsys, tmp_path):
    f = tmp_path / "x.pkg.tar.zst"
    f.write_bytes(b"x")
    aur_pkg = SimpleNamespace(
        pkgbuild=tmp_path / "PKGBUILD",
        srcinfo=tmp_path / ".SRCINFO", name="hello")
    monkeypatch.setattr("core.aur_publish.prepare_aur_package",
                        lambda p, o: (True, "hazir", aur_pkg))
    pushed = {"n": 0}
    monkeypatch.setattr("core.aur_publish.push_to_aur",
                        lambda d, u: pushed.update(n=1) or (True, "yuklendi"))
    rc = cli._cmd_publish(argparse.Namespace(package=str(f),
                                             output_dir=None, aur_url=None))
    hint = "AUR" + chr(39) + "a yüklemek için"
    out = capsys.readouterr().out
    assert rc == 0 and pushed["n"] == 0
    assert hint in out


def test_cmd_rollback_invalid_name(monkeypatch, capsys):
    called = {"n": 0}
    monkeypatch.setattr(cli, "safe_run",
                        lambda cmd, timeout=None: called.update(n=1))
    rc = cli._cmd_rollback(argparse.Namespace(package="kötü ad"))
    assert rc == 1 and called["n"] == 0


def test_cmd_rollback_no_backup(monkeypatch, tmp_path, capsys):
    class FakeDB:
        def get_records_for_package(self, name):
            return [_rec(1, output_pkg="",
                         backup_pkg=str(tmp_path / "yok.pkg.tar.zst"))]
    monkeypatch.setattr(cli, "HistoryDB", FakeDB)
    rc = cli._cmd_rollback(argparse.Namespace(package="demo"))
    assert rc == 1


def test_cmd_rollback_success_and_failure(monkeypatch, tmp_path, capsys):
    backup = tmp_path / "yedek.pkg.tar.zst"
    backup.write_bytes(b"x")
    class FakeDB:
        def get_records_for_package(self, name):
            return [_rec(1, backup_pkg=str(backup))]
    monkeypatch.setattr(cli, "HistoryDB", FakeDB)
    seen = {}

    def fake_run(cmd, timeout=None):
        seen["cmd"] = list(cmd)
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(cli, "safe_run", fake_run)
    assert cli._cmd_rollback(argparse.Namespace(package="demo")) == 0
    assert "-U" in seen["cmd"] and str(backup) in seen["cmd"]

    def bad_run(cmd, timeout=None):
        return SimpleNamespace(returncode=1, stdout="", stderr="hata")
    monkeypatch.setattr(cli, "safe_run", bad_run)
    assert cli._cmd_rollback(argparse.Namespace(package="demo")) == 1


def test_cmd_check_updates_empty_and_updates(monkeypatch, capsys):
    monkeypatch.setattr("cli.check_all_installed_updates", list)
    ns = argparse.Namespace(watch=False, interval=300)
    assert cli._cmd_check_updates(ns) == 0
    recs = [SimpleNamespace(package_name="a", has_update=True,
                            detail="ETag degisti"),
            SimpleNamespace(package_name="b", has_update=False, detail="")]
    monkeypatch.setattr("cli.check_all_installed_updates",
                        lambda: recs)
    assert cli._cmd_check_updates(ns) == 0
    out = capsys.readouterr().out
    assert "güncelleme mevcut" in out and "a" in out


def test_cmd_verify_missing_file(capsys, tmp_path):
    rc = cli._cmd_verify(argparse.Namespace(
        package=str(tmp_path / "yok.pkg.tar.zst"), sigstore=False))
    assert rc == 1 and "bulunamad" in capsys.readouterr().out


def test_cmd_verify_gpg_paths(monkeypatch, capsys, tmp_path):
    f = tmp_path / "x.pkg.tar.zst"
    f.write_bytes(b"x")
    info = SimpleNamespace(valid=True, signer="Ali", key_id="K1",
                           key_fingerprint="FP", detail="tam")
    monkeypatch.setattr("core.package_signing.verify_signature",
                        lambda p: info)
    ns = argparse.Namespace(package=str(f), sigstore=False)
    assert cli._cmd_verify(ns) == 0
    out = capsys.readouterr().out
    assert "Geçerli" in out and "Ali" in out
    info.valid = False
    assert cli._cmd_verify(ns) == 1


def test_cmd_verify_sigstore_mode(monkeypatch, capsys, tmp_path):
    f = tmp_path / "x.pkg.tar.zst"
    f.write_bytes(b"x")
    res = SimpleNamespace(summary=lambda: "sig", success=False)
    monkeypatch.setattr("core.sigstore.verify_with_sigstore",
                        lambda p: res)
    ns = argparse.Namespace(package=str(f), sigstore=True)
    assert cli._cmd_verify(ns) == 1 and "sig" in capsys.readouterr().out


def test_cmd_scan_image_missing_file(capsys, tmp_path):
    rc = cli._cmd_scan_image(argparse.Namespace(
        image=str(tmp_path / "yok.tar")))
    assert rc == 1 and "bulunamad" in capsys.readouterr().out


def test_cmd_scan_image_no_tools(monkeypatch, capsys, tmp_path):
    f = tmp_path / "imaj.tar"
    f.write_bytes(b"x")
    monkeypatch.setattr(MS.shutil, "which", lambda n: None)
    rc = cli._cmd_scan_image(argparse.Namespace(image=str(f)))
    out = capsys.readouterr().out
    assert rc == 1 and "Tarama aracı bulunamadı" in out


def test_cmd_scan_image_trivy_clean(monkeypatch, capsys, tmp_path):
    f = tmp_path / "imaj.tar"
    f.write_bytes(b"x")
    monkeypatch.setattr(MS.shutil, "which",
                        lambda n: "/usr/bin/trivy" if n == "trivy" else None)
    monkeypatch.setattr(MS, "safe_run",
                        lambda cmd, timeout=None: SimpleNamespace(
                            returncode=0, stdout="", stderr=""))
    rc = cli._cmd_scan_image(argparse.Namespace(image=str(f)))
    out = capsys.readouterr().out
    assert rc == 0 and "Tüm taramalar temiz" in out


def test_cmd_scan_image_grype_findings(monkeypatch, capsys, tmp_path):
    f = tmp_path / "imaj.tar"
    f.write_bytes(b"x")
    monkeypatch.setattr(MS.shutil, "which",
                        lambda n: "/usr/bin/grype" if n == "grype" else None)
    vulns = chr(10).join(["NAME High 1.2.3", "OTHER Critical 9.9"])
    monkeypatch.setattr(MS, "safe_run",
                        lambda cmd, timeout=None: SimpleNamespace(
                            returncode=1, stdout=vulns, stderr=""))
    rc = cli._cmd_scan_image(argparse.Namespace(image=str(f)))
    out = capsys.readouterr().out
    assert rc == 1 and "Grype bulguları" in out


def test_cmd_scan_image_clamav_infected(monkeypatch, capsys, tmp_path):
    f = tmp_path / "imaj.tar"
    f.write_bytes(b"x")
    monkeypatch.setattr(MS.shutil, "which",
                        lambda n: "/usr/bin/clamscan" if n == "clamscan" else None)
    monkeypatch.setattr(MS, "safe_run",
                        lambda cmd, timeout=None: SimpleNamespace(
                            returncode=1, stdout="EICAR", stderr=""))
    rc = cli._cmd_scan_image(argparse.Namespace(image=str(f)))
    out = capsys.readouterr().out
    assert rc == 1 and "enfekte" in out


def test_cmd_flatpak_not_available(monkeypatch, capsys):
    monkeypatch.setattr("core.flatpak_converter.is_flatpak_available",
                        lambda: False)
    rc = cli._cmd_flatpak_export(argparse.Namespace(
        list=False, app_id=None, branch="stable", output_dir=None))
    out = capsys.readouterr().out
    assert rc == 1 and "flatpak bulunamadı" in out


def test_cmd_flatpak_list_modes(monkeypatch, capsys):
    monkeypatch.setattr("core.flatpak_converter.is_flatpak_available",
                        lambda: True)
    monkeypatch.setattr("core.flatpak_converter.list_installed_apps",
                        list)
    ns = argparse.Namespace(list=True, app_id=None, branch="stable",
                            output_dir=None)
    assert cli._cmd_flatpak_export(ns) == 0
    assert "bulunamadı" in capsys.readouterr().out

    apps = [SimpleNamespace(app_id="org.x.Y", name="Y", version="1",
                            branch="stable")]
    monkeypatch.setattr("core.flatpak_converter.list_installed_apps",
                        lambda: apps)
    assert cli._cmd_flatpak_export(ns) == 0
    assert "org.x.Y" in capsys.readouterr().out


def test_cmd_flatpak_export_paths(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("core.flatpak_converter.is_flatpak_available",
                        lambda: True)
    ns_no_id = argparse.Namespace(list=False, app_id=None, branch="stable",
                                  output_dir=None)
    assert cli._cmd_flatpak_export(ns_no_id) == 1
    assert "uygulama ID" in capsys.readouterr().out

    deb = tmp_path / "cikti.deb"
    deb.write_bytes(b"x")
    monkeypatch.setattr("core.flatpak_converter.flatpak_to_deb",
                        lambda aid, odir, br: (True, "hazir", deb))
    ns_ok = argparse.Namespace(list=False, app_id="org.x.Y",
                               branch="stable", output_dir=str(tmp_path))
    assert cli._cmd_flatpak_export(ns_ok) == 0
    assert "dpkg -i" in capsys.readouterr().out

    monkeypatch.setattr("core.flatpak_converter.flatpak_to_deb",
                        lambda aid, odir, br: (False, "basarisiz", None))
    assert cli._cmd_flatpak_export(ns_ok) == 1


def test_cmd_appimage_not_available(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("core.appimage_converter.is_appimage_available",
                        lambda: False)
    rc = cli._cmd_appimage_export(argparse.Namespace(
        appimage=str(tmp_path / "x.AppImage"), output_dir=None))
    out = capsys.readouterr().out
    assert rc == 1 and "unsquashfs" in out


def test_cmd_appimage_paths(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("core.appimage_converter.is_appimage_available",
                        lambda: True)
    ns_missing = argparse.Namespace(
        appimage=str(tmp_path / "yok.AppImage"), output_dir=None)
    assert cli._cmd_appimage_export(ns_missing) == 1

    f = tmp_path / "uygulama.AppImage"
    f.write_bytes(b"x")
    deb = tmp_path / "cikti.deb"
    deb.write_bytes(b"x")
    monkeypatch.setattr("core.appimage_converter.appimage_to_deb",
                        lambda p, o: (True, "hazir", deb))
    ns_ok = argparse.Namespace(appimage=str(f), output_dir=str(tmp_path))
    assert cli._cmd_appimage_export(ns_ok) == 0
    assert "dpkg -i" in capsys.readouterr().out

    monkeypatch.setattr("core.appimage_converter.appimage_to_deb",
                        lambda p, o: (False, "bozuk", None))
    assert cli._cmd_appimage_export(ns_ok) == 1


def test_cmd_snapshot_cleanup_install_remove(monkeypatch, capsys):
    monkeypatch.setattr("core.snapshot_cleanup.install_cleanup_service",
                        lambda max_age_days=7: (True, "kuruldu"))
    ns_in = argparse.Namespace(install=True, remove=False, max_age=14)
    assert cli._cmd_snapshot_cleanup(ns_in) == 0
    assert "kuruldu" in capsys.readouterr().out

    monkeypatch.setattr("core.snapshot_cleanup.install_cleanup_service",
                        lambda max_age_days=7: (False, "reddi"))
    assert cli._cmd_snapshot_cleanup(ns_in) == 1

    monkeypatch.setattr("core.snapshot_cleanup.remove_cleanup_service",
                        lambda: (False, "kaldirilamadi"))
    ns_rm = argparse.Namespace(install=False, remove=False, max_age=7)
    ns_rm.remove = True
    assert cli._cmd_snapshot_cleanup(ns_rm) == 1


def test_cmd_snapshot_cleanup_status_not_installed(monkeypatch, capsys):
    monkeypatch.setattr("core.snapshot_cleanup.get_cleanup_status",
                        lambda: {"installed": False, "active": False,
                                 "next_run": ""})
    monkeypatch.setattr("core.snapshot_manager.detect_backend",
                        lambda: "snapper")
    monkeypatch.setattr("core.snapshot_manager.list_snapshots",
                        list)
    ns = argparse.Namespace(install=False, remove=False, max_age=7)
    assert cli._cmd_snapshot_cleanup(ns) == 0
    out = capsys.readouterr().out
    assert "Servis kurulu değil" in out and "snapper" in out


def test_cmd_snapshot_cleanup_status_installed(monkeypatch, capsys):
    monkeypatch.setattr("core.snapshot_cleanup.get_cleanup_status",
                        lambda: {"installed": True, "active": True,
                                 "next_run": "yarin"})
    monkeypatch.setattr("core.snapshot_manager.detect_backend",
                        lambda: "timeshift")
    snaps = [{"name": "gunluk-1", "date": "2026-08-25"}]
    monkeypatch.setattr("core.snapshot_manager.list_snapshots",
                        lambda: snaps)
    ns = argparse.Namespace(install=False, remove=False, max_age=7)
    assert cli._cmd_snapshot_cleanup(ns) == 0
    out = capsys.readouterr().out
    assert "Aktif" in out and "yarin" in out and "gunluk-1" in out
