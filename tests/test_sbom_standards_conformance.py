"""SBOM standart uygunlugu: SPDX 2.3 ve CycloneDX 1.6 disa aktarimlari.

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory — generate_sbom GERCEK paketle calistirilmaz, belgenin
         kendisi elle kurulur; disa aktarim salt-saf (komut/ag yok).

Neden var: core/sbom.py modul docstring'i "SPDX ve CycloneDX'tan esinlenmis
hafif JSON" diyordu ama CLI cikti dosyasi `.spdx.json` adıyla yaziliyordu ve
SPDX okuyucularin bekledigi HICBIR alan (spdxVersion, dataLicense, SPDXID,
creationInfo, packages) yoktu — yani tedarik-zinciri araclari (Dependency-Track,
grype, osv-scanner) belgeyi yutamazdi. Simdi `--format spdx|cyclonedx` gercekten
uyumlu uretiyor; `internal` varsayilan olarak korundu (geriye donuk uyum).
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from core.sbom import SBOMDocument, SBOMEntry, save_sbom


def _belge(**kw) -> SBOMDocument:
    base = {
        "spdx_version": "SPDX-2.3",
        "document_name": "pkgforge-ghost-dep",
        "document_namespace": "https://pkgforge.invalid/sbom/ghost-dep-1.0",
        "created": "2026-10-12T12:00:00+00:00",
        "package_name": "ghost-dep",
        "package_version": "1.0",
        "package_arch": "x86_64",
        "package_description": "deneme paketi",
        "files": [
            SBOMEntry(path="usr/bin/tool", file_type="elf",
                      sha256="a" * 64, size_bytes=100),
            SBOMEntry(path="usr/share/doc/x", file_type="text",
                      sha256="b" * 64, size_bytes=10),
        ],
        "dependencies": ["libyok.so.1"],
        "total_files": 2,
        "total_size_bytes": 110,
    }
    base.update(kw)
    return SBOMDocument(**base)


# == SPDX 2.3 ==================================================================================

def test_spdx_zorunlu_alanlar():
    d = _belge().to_spdx_dict()
    for key in ("spdxVersion", "dataLicense", "SPDXID", "name",
                "documentNamespace", "creationInfo", "packages"):
        assert key in d, f"SPDX zorunlu alan eksik: {key}"
    assert d["spdxVersion"] == "SPDX-2.3"
    assert d["dataLicense"] == "CC0-1.0"
    assert d["SPDXID"] == "SPDXRef-DOCUMENT"


def test_spdx_creationinfo():
    ci = _belge().to_spdx_dict()["creationInfo"]
    assert ci["created"] == "2026-10-12T12:00:00+00:00"
    assert any(c.startswith("Tool: PkgForge") for c in ci["creators"])
    # uydurma "Organization" uretilmez (yalnizca gercek bilinen senderler)
    assert not any(c.startswith("Organization:") for c in ci["creators"])


def test_spdx_dosya_kosinim_ve_iliskileri():
    d = _belge().to_spdx_dict()
    assert len(d["files"]) == 2
    f0 = d["files"][0]
    assert f0["SPDXID"].startswith("SPDXRef-File")
    assert f0["fileName"] == "usr/bin/tool"
    assert f0["checksums"] == [{"algorithm": "SHA256", "checksumValue": "a" * 64}]
    rels = {(r["spdxElementId"], r["relationshipType"], r["relatedSpdxElement"])
            for r in d["relationships"]}
    assert ("SPDXRef-DOCUMENT", "DESCRIBES", "SPDXRef-Package") in rels
    assert ("SPDXRef-Package", "CONTAINS", "SPDXRef-File-0") in rels


def test_spdx_hashsize_bos_sha256da_kosin_yok():
    d = _belge(files=[SBOMEntry(path="d", file_type="directory", sha256="")]).to_spdx_dict()
    assert d["files"][0]["checksums"] == []


def test_spdx_versiyon_aciklamasi_kosullu():
    d = _belge(package_version="", package_description="").to_spdx_dict()
    pkg = d["packages"][0]
    assert "versionInfo" not in pkg
    assert "description" not in pkg
    assert pkg["name"] == "ghost-dep"


def test_spdx_bos_isim_unknown_olur():
    d = _belge(package_name="").to_spdx_dict()
    assert d["packages"][0]["name"] == "unknown"


def test_spdx_json_serializable():
    json.dumps(_belge().to_spdx_dict())


# == CycloneDX 1.6 ==============================================================================

def test_cdx_zorunlu_alanlar():
    d = _belge().to_cyclonedx_dict()
    for key in ("bomFormat", "specVersion", "serialNumber", "version",
                "metadata", "components"):
        assert key in d, f"CycloneDX zorunlu alan eksik: {key}"
    assert d["bomFormat"] == "CycloneDX"
    assert d["specVersion"] == "1.6"
    assert d["version"] == 1


def test_cdx_serialnumber_gercek_uuid():
    sn = _belge().to_cyclonedx_dict()["serialNumber"]
    assert sn.startswith("urn:uuid:")
    uuid.UUID(sn.split("urn:uuid:", 1)[1])  # ValueError atmaz


def test_cdx_serialnumber_nil_uuid_degil_ve_tekrarlanabilir():
    b = _belge()
    sn = b.to_cyclonedx_dict()["serialNumber"]
    assert "00000000-0000-0000-0000-000000000000" not in sn
    assert sn == b.to_cyclonedx_dict()["serialNumber"]   # deterministik


def test_cdx_serialnumber_icerikten_turetilir():
    a = _belge(package_version="1.0").to_cyclonedx_dict()["serialNumber"]
    b = _belge(package_version="2.0").to_cyclonedx_dict()["serialNumber"]
    assert a != b


def test_cdx_bilesenler_dosya_ve_soname():
    d = _belge().to_cyclonedx_dict()
    tipler = {c["type"] for c in d["components"]}
    assert tipler == {"file", "library"}
    dosya = next(c for c in d["components"] if c["type"] == "file")
    assert dosya["name"] == "usr/bin/tool"
    assert dosya["hashes"] == [{"alg": "SHA-256", "content": "a" * 64}]
    assert {"type": "library", "name": "libyok.so.1"} in d["components"]


def test_cdx_metadata_component():
    m = _belge().to_cyclonedx_dict()["metadata"]
    assert m["timestamp"] == "2026-10-12T12:00:00+00:00"
    assert m["component"]["type"] == "application"
    assert m["component"]["name"] == "ghost-dep"
    assert m["component"]["version"] == "1.0"
    assert m["tools"][0]["version"] == "2.2.0"


def test_cdx_bos_belge_yine_gecerli():
    d = _belge(files=[], dependencies=[]).to_cyclonedx_dict()
    assert d["components"] == []
    json.dumps(d)


# == save_sbom fmt secimi ======================================================================

def test_save_internal_varsayilan(tmp_path):
    p = save_sbom(_belge(), tmp_path / "x.json")
    d = json.loads(p.read_text(encoding="utf-8"))
    assert "spdx_version" in d and "spdxVersion" not in d   # PkgForge seklei


def test_save_spdx_format(tmp_path):
    d = json.loads(save_sbom(_belge(), tmp_path / "s.json", "spdx").read_text())
    assert d["SPDXID"] == "SPDXRef-DOCUMENT"


def test_save_cyclonedx_format(tmp_path):
    d = json.loads(save_sbom(_belge(), tmp_path / "c.json", "cyclonedx").read_text())
    assert d["bomFormat"] == "CycloneDX"


def test_save_bilinmeyen_format_ic_dsese_duser(tmp_path):
    """ORTAM: SBOM yazimi donusumu asla yarmamali — tanisiz fmt -> internal."""
    d = json.loads(save_sbom(_belge(), tmp_path / "y.json", "xml").read_text())
    assert "spdx_version" in d


def test_save_none_format_ic_dsese_duser(tmp_path):
    """ORTAM: fmt=None (getattr default'u) -> internal, crash yok."""
    p = save_sbom(_belge(), tmp_path / "n3.json", None)
    assert "spdx_version" in json.loads(p.read_text(encoding="utf-8"))


def test_uydurma_anahtar_to_dict_korunur():
    """internal seklei dokunulmadi: eski tuketiciler ayni alanlari okur."""
    d = _belge().to_dict()
    assert d["document_name"] == "pkgforge-ghost-dep"
    assert d["files"][0]["sha256"] == "a" * 64


# == CLI yonlendirme (real _cmd_sbom, stub'lu) ================================================

def test_cli_format_bayragi_uzantiya_yansir(tmp_path, monkeypatch, capsys):
    """--format cyclonedx -> .cdx.json + save_sbom'a fmt iletilir."""
    from types import SimpleNamespace as NS

    import cli

    hedef = tmp_path / "p.pkg.tar.zst"
    hedef.write_bytes(b"P")
    kaydedilen = {}

    def fake_save(s, path, fmt="internal"):
        kaydedilen["path"] = Path(path)
        kaydedilen["fmt"] = fmt
        return Path(path)

    monkeypatch.setattr(cli, "discover_tools",
                        lambda: NS(pkexec="", pacman=""))
    monkeypatch.setattr("core.sbom.generate_sbom",
                        lambda p, t, include_hashes=True: _belge())
    monkeypatch.setattr("core.sbom.save_sbom", fake_save)
    rc = cli._cmd_sbom(NS(package=str(hedef), diff=False, no_hashes=True,
                          output_dir=str(tmp_path), format="cyclonedx"))
    assert rc == 0
    assert kaydedilen["fmt"] == "cyclonedx"
    assert kaydedilen["path"].name.endswith(".cdx.json")


def test_cli_spdx_format_uzantisi_spdx_json_kalir(tmp_path, monkeypatch, capsys):
    from types import SimpleNamespace as NS

    import cli

    hedef = tmp_path / "p.pkg.tar.zst"
    hedef.write_bytes(b"P")
    gorulen = {}

    def fake_save(s, path, fmt="internal"):
        gorulen["path"] = Path(path)
        gorulen["fmt"] = fmt
        return Path(path)

    monkeypatch.setattr(cli, "discover_tools", lambda: NS(pkexec="", pacman=""))
    monkeypatch.setattr("core.sbom.generate_sbom",
                        lambda p, t, include_hashes=True: _belge())
    monkeypatch.setattr("core.sbom.save_sbom", fake_save)
    rc = cli._cmd_sbom(NS(package=str(hedef), diff=False, no_hashes=True,
                          output_dir=str(tmp_path), format="spdx"))
    assert rc == 0 and gorulen["fmt"] == "spdx"
    assert gorulen["path"].name.endswith(".spdx.json")
