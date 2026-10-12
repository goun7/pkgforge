"""CLI donusum onizlemesi: uyumluluk notunun GEREKCESI terminale dusmeli.

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory — convert/history/provenance/analiz/compat hepsi
         MONKEYPATCH; gercek makepkg, pacman, ag veya dosya yazimi YOK
         (cikti tmp_path).

Neden var: `convert` yalnizca "Compatibility grade: D (error)" basiyordu;
pipeline check loglari terminale ulasmiyor, yani kullanici notun nedenini
gormuyordu ve hiçbir sey yapamiyordu. Ayrica bu satirlar birden fazla kaynaktan
basildigi icin dublasyon regresyona acik — sayi kilitle dogrulanıyor.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import cli
import core.cli_bridge as BR
import core.compatibility_checker as CC
import core.package_analyzer as PA
import core.provenance as PRV
from core.compatibility_checker import CheckSeverity

SEV = CheckSeverity


class FakeDB:
    def backup_package(self, p):
        return None

    def add_record(self, **kw):
        return None


def _tools():
    return NS(missing_required=[], missing_optional=[], pkexec="pkexec",
              pacman="pacman")


def _args(tmp_path, target, **kw):
    base = {"target": str(target), "output_dir": str(tmp_path), "install": False,
            "dry_run": True, "yes": True, "to_oci": False, "oci_tag": None,
            "verify_build": False, "resolve_deps": False, "sign": False,
            "sign_key": None, "delta": False}
    base.update(kw)
    return NS(**base)


def _temel(monkeypatch, tmp_path, *, checks, scripts=None, depends=None):
    """convert akisini stub'larla kurar; onizleme raporu `checks` ile doner."""
    monkeypatch.setattr(cli, "discover_tools", _tools)
    hedef = tmp_path / "girdi.deb"
    hedef.write_bytes(b"D")          # _cmd_convert hedefin var olmasini ister
    pkg = tmp_path / "cikti.pkg.tar.zst"
    pkg.write_bytes(b"P")
    monkeypatch.setattr(BR, "convert_deb_sync",
                        lambda fp, od, tools=None, progress_callback=None:
                        NS(success=True, message="ok", output_pkg=pkg))
    monkeypatch.setattr(cli, "HistoryDB", FakeDB)
    monkeypatch.setattr(PRV, "create_provenance", lambda **kw: NS())
    monkeypatch.setattr(PRV, "save_provenance", lambda pr, p: Path(p))

    meta = NS(file_list=["./usr/bin/arac"], depends=depends or [], name="demo",
              version="1.0", maintainer_scripts=scripts or [])
    monkeypatch.setattr(PA, "analyze_package", lambda fp, tools: meta)

    def sahte_compat(pkg_path, files, deps, tools, mscripts=None):
        assert mscripts == (scripts or []), "betik listesi report'a tasinmadi"
        return NS(grade="D" if any(c.severity is SEV.ERROR for c in checks) else "A",
                  overall=checks[0].severity if checks else SEV.PASS,
                  value=None, checks=checks)

    monkeypatch.setattr(CC, "run_compatibility_checks", sahte_compat)
    return hedef


def _satirlar(capsys):
    return capsys.readouterr().out.splitlines()


def test_hata_gerekcesi_basilmali(monkeypatch, tmp_path, capsys):
    hedef = _temel(monkeypatch, tmp_path, checks=[NS(
        name="Namcap Analizi", severity=SEV.ERROR,
        message="1 hata tespit edildi", details=["demo E: sukray"])])
    rc = cli._cmd_convert(_args(tmp_path, str(hedef)))
    satirlar = _satirlar(capsys)
    assert rc == 0
    assert any(ln.startswith("📊") for ln in satirlar), "not satiri yok"
    assert any("[error] Namcap Analizi: 1 hata tespit edildi" in ln
               for ln in satirlar)
    assert any(ln.strip() == "demo E: sukray" for ln in satirlar)


def test_gecerli_uyari_gerekcesi_basilmali(monkeypatch, tmp_path, capsys):
    hedef = _temel(monkeypatch, tmp_path, checks=[NS(
        name="Shared Library Kontrolu", severity=SEV.WARNING,
        message="1 eksik kutuphane", details=["Eksik: libyok.so.1"])])
    cli._cmd_convert(_args(tmp_path, str(hedef)))
    out = "\n".join(_satirlar(capsys))
    assert "[warning] Shared Library Kontrolu" in out
    assert "Eksik: libyok.so.1" in out


def test_pass_kontroller_gerekce_basmaz(monkeypatch, tmp_path, capsys):
    hedef = _temel(monkeypatch, tmp_path, checks=[NS(
        name="Bakim Betikleri", severity=SEV.PASS, message="temiz", details=[])])
    cli._cmd_convert(_args(tmp_path, str(hedef)))
    satirlar = _satirlar(capsys)
    gecer = [ln for ln in satirlar if ln.startswith("  [")]
    assert gecer == [], f"PASS kontrolu gerekce olarak basildi: {gecer}"


def test_gerekce_bir_kez_basilir_dublasyon_kilidi(monkeypatch, tmp_path, capsys):
    checks = [NS(name="X", severity=SEV.ERROR, message="sebep", details=["d1"])]
    hedef = _temel(monkeypatch, tmp_path, checks=checks)
    cli._cmd_convert(_args(tmp_path, str(hedef)))
    lines = _satirlar(capsys)
    assert sum(1 for ln in lines if "[error] X: sebep" in ln) == 1
    assert sum(1 for ln in lines if ln.strip() == "d1") == 1


def test_detay_ilk_ucle_sinirli(monkeypatch, tmp_path, capsys):
    hedef = _temel(monkeypatch, tmp_path, checks=[NS(
        name="Y", severity=SEV.WARNING, message="m",
        details=["a", "b", "c", "d", "e"])])
    cli._cmd_convert(_args(tmp_path, str(hedef)))
    # Girdeler '    ' ile basan tek satirlar; dosya onizlemesi de ayni girintiye
    # sahip oldugu icin gerekce satirindan sonrasini aliyoruz.
    satirlar = _satirlar(capsys)
    bas = next(i for i, ln in enumerate(satirlar) if ln.startswith("  [warning] Y"))
    detaylar = [ln.strip() for ln in satirlar[bas + 1:] if ln.startswith("    ")]
    assert detaylar[:3] == ["a", "b", "c"]
    assert "d" not in detaylar and "e" not in detaylar


def test_dusurulen_betikler_yine_basilmali(monkeypatch, tmp_path, capsys):
    hedef = _temel(monkeypatch, tmp_path,
                   checks=[NS(name="Bakim Betikleri", severity=SEV.WARNING,
                              message="2 betik dusturuldu", details=[])],
                   scripts=["postinst", "postrm"])
    cli._cmd_convert(_args(tmp_path, str(hedef)))
    out = "\n".join(_satirlar(capsys))
    assert "postinst" in out and "postrm" in out
    assert "post_install" in out  # Arch hook karsiligi da gorunur


def test_onizleme_patlarsa_convert_devam_eder(monkeypatch, tmp_path, capsys):
    """best-effort sozlesmesi: analiz hatasi donusumu basarisiz yapmaz."""
    hedef = tmp_path / "girdi.deb"
    hedef.write_bytes(b"D")
    pkg = tmp_path / "cikti.pkg.tar.zst"
    monkeypatch.setattr(cli, "discover_tools", _tools)
    pkg.write_bytes(b"P")
    monkeypatch.setattr(BR, "convert_deb_sync",
                        lambda fp, od, tools=None, progress_callback=None:
                        NS(success=True, message="ok", output_pkg=pkg))
    monkeypatch.setattr(cli, "HistoryDB", FakeDB)
    monkeypatch.setattr(PRV, "create_provenance", lambda **kw: NS())
    monkeypatch.setattr(PRV, "save_provenance", lambda pr, p: Path(p))
    monkeypatch.setattr(PA, "analyze_package",
                        lambda fp, tools: (_ for _ in ()).throw(RuntimeError("bozuk .deb")))
    rc = cli._cmd_convert(_args(tmp_path, str(hedef)))
    assert rc == 0
    out = "\n".join(_satirlar(capsys))
    assert "Compatibility grade" not in out
