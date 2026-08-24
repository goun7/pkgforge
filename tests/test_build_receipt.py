"""Faz 5 (F5.15) — build receipt: arac surumleri + debtap-db tarihi."""
from __future__ import annotations

import time

import core.build_receipt as BR
from core.build_receipt import collect_build_receipt, debtap_db_date


def test_collect_receipt_shape():
    r = collect_build_receipt()
    assert "tool_versions" in r
    assert "debtap_db_date" in r
    assert isinstance(r["tool_versions"], dict)
    assert isinstance(r["debtap_db_date"], str)


def test_debtap_db_date_finds_seeded_file(tmp_path, monkeypatch):
    db = tmp_path / "db"
    db.write_bytes(b"x")
    monkeypatch.setattr(BR.Path, "home", staticmethod(lambda: tmp_path))
    # candidates include <home>/.local/share/debtap/db etc.; seed one.
    real = tmp_path / ".local" / "share" / "debtap"
    real.mkdir(parents=True)
    (real / "db").write_bytes(b"x")
    out = debtap_db_date()
    assert out != ""
    # format sanity: YYYY-MM-DDTHH:MM:SS
    time.strptime(out, "%Y-%m-%dT%H:%M:%S")


def test_debtap_db_date_empty_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(BR.Path, "home", staticmethod(lambda: tmp_path))
    assert debtap_db_date() == ""


def test_provenance_embeds_receipt(tmp_path, monkeypatch):
    import core.provenance as P

    src = tmp_path / "a.deb"
    src.write_bytes(b"fake")
    monkeypatch.setattr(
        BR, "collect_build_receipt",
        lambda tools=None: {"tool_versions": {"debtap": "9.9.9"},
                            "debtap_db_date": "2026-01-01T00:00:00"})
    prov = P.create_provenance(source_file=src, source_type="deb")
    assert prov.tool_versions == {"debtap": "9.9.9"}
    assert prov.debtap_db_date == "2026-01-01T00:00:00"


def test_attestation_environment_includes_receipt(tmp_path, monkeypatch):
    import core.provenance as P

    src = tmp_path / "a.deb"
    src.write_bytes(b"fake")
    monkeypatch.setattr(
        BR, "collect_build_receipt",
        lambda tools=None: {"tool_versions": {"pacman": "7.0"},
                            "debtap_db_date": "2026-02-02T00:00:00"})
    prov = P.create_provenance(source_file=src, source_type="deb",
                               output_file=str(tmp_path / "o.pkg.tar.zst"))
    att = P.create_attestation(prov)
    env = att.predicate["environment"]
    assert env["tool_versions"] == {"pacman": "7.0"}
    assert env["debtap_db_date"] == "2026-02-02T00:00:00"


def test_sbom_document_has_receipt_field():
    from core.sbom import SBOMDocument

    doc = SBOMDocument()
    assert doc.build_receipt == {}
    assert "build_receipt" in doc.to_dict()


def test_generate_sbom_embeds_receipt(tmp_path, monkeypatch):
    import core.sbom as S

    monkeypatch.setattr(
        BR, "collect_build_receipt",
        lambda tools=None: {"tool_versions": {"bsdtar": "3.8"},
                            "debtap_db_date": ""})
    # Build a minimal .pkg.tar.zst with a .PKGINFO (tarfile + zstd CLI).
    import shutil
    import subprocess
    import tarfile

    if not shutil.which("zstd"):
        import pytest

        pytest.skip("zstd CLI yok")
    pkg = tmp_path / "x-1.0-1-x86_64.pkg.tar.zst"
    pkginfo = tmp_path / "PKGINFO"
    pkginfo.write_text(
        chr(10).join(["pkgname = x", "pkgver = 1.0", "arch = x86_64", ""]))
    tar_path = tmp_path / "x.pkg.tar"
    with tarfile.open(tar_path, "w") as tf:
        tf.add(pkginfo, arcname=".PKGINFO")
    with open(pkg, "wb") as out:
        subprocess.run(["zstd", "-q", "-c", str(tar_path)],
                       stdout=out, check=True)
    from config import discover_tools

    doc = S.generate_sbom(pkg, discover_tools(), include_hashes=False,
                          offline=True)
    assert doc.build_receipt.get("tool_versions") == {"bsdtar": "3.8"}
