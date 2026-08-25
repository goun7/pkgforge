"""Coverage itmesi — cli provenance/attest/sbom komutlari."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import cli
import core.provenance as PRV


def _pkg(tmp_path):
    f = tmp_path / "p.pkg.tar.zst"
    f.write_bytes(b"x")
    return f


def _prov():
    return NS(
        tool_name="PkgForge", tool_version="2.0.0", build_id="bid-1",
        source_file="a.deb", source_url="https://s", source_sha256="ab" * 33,
        output_file="p.pkg.tar.zst", output_sha256="cd" * 33,
        build_timestamp="t", build_host="h", build_os="linux",
        package_name="demo", package_version="1.0", package_arch="x86_64",
        clamav_result="temiz", decompression_bomb_result="guvenli",
        signature_valid=True)


def test_provenance_paths(capsys, monkeypatch, tmp_path):
    rc = cli._cmd_provenance(NS(package=str(tmp_path / "yok.zst")))
    assert rc == 1 and "bulunamadı" in capsys.readouterr().out

    f = _pkg(tmp_path)
    monkeypatch.setattr(PRV, "find_provenance", lambda p: None)
    rc2 = cli._cmd_provenance(NS(package=str(f)))
    assert rc2 == 1 and "Provenance dosyası bulunamadı" in capsys.readouterr().out

    monkeypatch.setattr(PRV, "find_provenance", lambda p: tmp_path / "p.json")
    monkeypatch.setattr(PRV, "load_provenance", lambda p: None)
    rc3 = cli._cmd_provenance(NS(package=str(f)))
    assert rc3 == 1 and "okunamadı" in capsys.readouterr().out

    monkeypatch.setattr(PRV, "load_provenance", lambda p: _prov())
    monkeypatch.setattr(PRV, "verify_provenance", lambda pr: (True, "gecerli"))
    rc4 = cli._cmd_provenance(NS(package=str(f)))
    out = capsys.readouterr().out
    assert rc4 == 0 and "gecerli" in out and "ClamAV" in out

    monkeypatch.setattr(PRV, "verify_provenance", lambda pr: (False, "bozuk"))
    rc5 = cli._cmd_provenance(NS(package=str(f)))
    assert rc5 == 1 and "bozuk" in capsys.readouterr().out


def test_attest_paths(capsys, monkeypatch, tmp_path):
    rc = cli._cmd_attest(NS(package=str(tmp_path / "yok.zst"), key=None))
    assert rc == 1 and "bulunamadı" in capsys.readouterr().out

    f = _pkg(tmp_path)
    monkeypatch.setattr(PRV, "find_provenance", lambda p: None)
    rc2 = cli._cmd_attest(NS(package=str(f), key=None))
    assert rc2 == 1 and "Provenance kaydı bulunamadı" in capsys.readouterr().out

    monkeypatch.setattr(PRV, "find_provenance", lambda p: tmp_path / "p.json")
    monkeypatch.setattr(PRV, "load_provenance", lambda p: None)
    rc3 = cli._cmd_attest(NS(package=str(f), key=None))
    assert rc3 == 1 and "yüklenemedi" in capsys.readouterr().out

    att = NS(_type="Statement", predicate_type="slsa", subject=[{"name": "p"}],
             predicate={"builder": {"id": "b"}, "metadata": {}, "security": {}})
    monkeypatch.setattr(PRV, "load_provenance", lambda p: _prov())
    monkeypatch.setattr(PRV, "create_attestation",
                        lambda pr, signer_key="": att)
    saved = {}

    def fake_save(a, path):
        saved["path"] = Path(path)
        return Path(path)
    monkeypatch.setattr(PRV, "save_attestation", fake_save)
    rc4 = cli._cmd_attest(NS(package=str(f), key="/keys/k"))
    out = capsys.readouterr().out
    assert rc4 == 0 and "SLSA" in out and "/keys/k" not in out
    assert saved["path"].name == "p.pkg.tar.zst.attestation.json"


def test_sbom_guards(capsys, monkeypatch, tmp_path):
    import core.sbom as SB
    rc = cli._cmd_sbom(NS(package=None, diff=False))
    assert rc == 1 and "gerekli" in capsys.readouterr().out

    rc2 = cli._cmd_sbom(NS(package=str(tmp_path / "yok.zst"), diff=False))
    assert rc2 == 1 and "bulunamadı" in capsys.readouterr().out

    f = _pkg(tmp_path)
    sbom = NS(summary=lambda: "SPDM ozet")
    saved = {}

    def fake_save(s, path):
        saved["path"] = Path(path)
        return Path(path)
    monkeypatch.setattr(SB, "discover_tools", lambda: NS()) if hasattr(
        SB, "discover_tools") else None
    monkeypatch.setattr("core.sbom.generate_sbom", lambda p, t, include_hashes=True: sbom)
    monkeypatch.setattr("core.sbom.save_sbom", fake_save)
    rc3 = cli._cmd_sbom(NS(package=str(f), diff=False, no_hashes=True,
                           output_dir=str(tmp_path)))
    out = capsys.readouterr().out
    assert rc3 == 0 and "ozet" in out
    assert saved["path"].name == "p.pkg.tar.zst.spdx.json"
