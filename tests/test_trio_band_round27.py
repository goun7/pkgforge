"""Tur-27 — from_source/sbom/provenance son dallari."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import core.from_source as FS
import core.provenance as PV
import core.sbom as SB

TOOLS = NS(bsdtar="/usr/bin/bsdtar", rpm2cpio="/usr/bin/rpm2cpio",
           file_cmd="/usr/bin/file")


# --- from_source: OSError dususleri ---------------------------------------------

def _read_text_yoksayici(yasakli):
    gercek = Path.read_text

    def sahte(self, *a, **k):
        if self.name in yasakli:
            raise OSError("okunamaz")
        return gercek(self, *a, **k)

    return sahte


def test_version_file_oserror(monkeypatch, tmp_path):
    (tmp_path / "VERSION").write_text("9.9")
    monkeypatch.setattr(Path, "read_text", _read_text_yoksayici({"VERSION"}))
    assert FS._extract_version_from_file(tmp_path) is None


def test_license_all_sources_oserror(monkeypatch, tmp_path):
    for ad in ("LICENSE", "COPYING", "Cargo.toml", "package.json"):
        (tmp_path / ad).write_text("x")
    monkeypatch.setattr(Path, "read_text", _read_text_yoksayici(
        {"LICENSE", "COPYING", "Cargo.toml", "package.json"}))
    assert FS._detect_license(tmp_path) == "GPL-3.0-or-later"


def test_description_all_sources_oserror(monkeypatch, tmp_path):
    for ad in ("pyproject.toml", "Cargo.toml", "package.json", "README.md"):
        (tmp_path / ad).write_text("x")
    monkeypatch.setattr(Path, "read_text", _read_text_yoksayici(
        {"pyproject.toml", "Cargo.toml", "package.json", "README.md"}))
    sonuc = FS._detect_description(tmp_path, "demo")
    assert "demo" in sonuc and "kaynaktan" in sonuc


def test_binary_name_cargo_and_json_oserror(monkeypatch, tmp_path):
    (tmp_path / "Cargo.toml").write_text("x")
    (tmp_path / "package.json").write_text("{}")
    monkeypatch.setattr(Path, "read_text", _read_text_yoksayici(
        {"Cargo.toml", "package.json"}))
    assert FS._detect_binary_name(tmp_path, "varsayilan") == "varsayilan"


# --- sbom ------------------------------------------------------------------------

def test_summary_many_dependencies():
    d = SB.SBOMDocument()
    d.dependencies = [f"dep{i}" for i in range(13)]
    metin = d.summary()
    assert "... ve 3 tane daha" in metin


def test_parse_tv_line_garbage():
    assert SB._parse_tv_line("bu taninmaz bir satir") is None


def test_read_pkginfo_missing_archive(tmp_path):
    assert SB._read_pkginfo(tmp_path / "yok.pkg.tar.zst") == {}


def test_detect_file_type_bom_magic(tmp_path):
    f = tmp_path / "bom.conf"
    f.write_bytes("\ufeffayar=1".encode("utf-8"))
    assert SB._detect_file_type(f) == "text"


def test_generate_sbom_receipt_failure_swallowed(monkeypatch, tmp_path):
    pkg = tmp_path / "a-1-1-x.pkg.tar.zst"
    pkg.write_bytes(b"P")

    def patla(tools):
        raise RuntimeError("makine yok")
    monkeypatch.setattr("core.build_receipt.collect_build_receipt", patla)
    monkeypatch.setattr(SB, "safe_run",
                        lambda *a, **k: NS(returncode=1, stdout="", stderr="y"))
    dok = SB.generate_sbom(pkg, TOOLS, offline=True)
    assert dok.build_receipt == {}


def test_generate_sbom_bad_line_and_hash_error(monkeypatch, tmp_path):
    pkg = tmp_path / "a-1-1-x.pkg.tar.zst"
    pkg.write_bytes(b"P")
    cikti = {"n": 0}

    def sirali(cmd, timeout=0, **k):
        birlesik = " ".join(str(c) for c in cmd)
        if "-tvf" in birlesik:
            satirlar = [
                "-rw-r--r-- root/root 12 2024-01-01 00:00 notlar.txt",
                "bozuk-satir",
                "drwxr-xr-x root/root 0 2024-01-01 00:00 klasor",
            ]
            return NS(returncode=0, stdout="\n".join(satirlar) + "\n")
        cikti["n"] += 1
        if cikti["n"] == 2:
            raise ValueError("ic hata")          # 232-233
        return NS(returncode=0, stdout="icerik")

    monkeypatch.setattr(SB, "safe_run", sirali)
    dok = SB.generate_sbom(pkg, TOOLS, offline=True)
    yollar = [f.path for f in dok.files]
    assert yollar == ["notlar.txt", "klasor"], yollar
    assert dok.files[0].sha256 == ""             # hash hatasi yutuldu


def test_generate_sbom_listing_crash_caught(monkeypatch, tmp_path):
    pkg = tmp_path / "a-1-1-x.pkg.tar.zst"
    pkg.write_bytes(b"P")
    # stdout None -> splitlines AttributeError -> 250-251 yakalanir
    monkeypatch.setattr(SB, "safe_run",
                        lambda *a, **k: NS(returncode=0, stdout=None))
    dok = SB.generate_sbom(pkg, TOOLS, offline=True)
    assert dok.package_name                       # dosya-adi dususu


def test_generate_sbom_dep_resolution_failure(monkeypatch, tmp_path):
    pkg = tmp_path / "a-1-1-x.pkg.tar.zst"
    pkg.write_bytes(b"P")

    def patla(*a, **k):
        raise RuntimeError("cozulemedi")
    monkeypatch.setattr("core.dep_resolver.resolve_runtime_dependencies",
                        patla)
    monkeypatch.setattr(SB, "safe_run",
                        lambda *a, **k: NS(returncode=1, stdout="", stderr=""))
    dok = SB.generate_sbom(pkg, TOOLS, offline=False)
    assert dok.dependencies == []


def test_diff_summary_branches():
    eski = SB.SBOMDocument(); eski.files = []
    yeni = SB.SBOMDocument(); yeni.files = []
    fark = SB.diff_sboms(eski, yeni)
    fark.added_deps = ["yeni-kitaplik"]
    fark.removed_deps = ["eski-kitaplik"]
    fark.changed_files = [{"path": "/usr/bin/a",
                           "old_sha256": "aa", "new_sha256": "bb"}]
    metin = fark.summary()
    assert "Yeni bağımlılıklar" in metin
    assert "Kaldırılan bağımlılıklar" in metin
    assert "Değişen dosyalar" in metin
    # temiz durum
    bos = SB.SBOMDiff()
    assert "Fark yok" in bos.summary()


# --- provenance ------------------------------------------------------------------

def test_create_provenance_receipt_and_sha_failures(monkeypatch, tmp_path):
    kaynak = tmp_path / "kaynak.deb"; kaynak.write_bytes(b"K")
    cikti = tmp_path / "cikti.pkg.tar.zst"; cikti.write_bytes(b"C")

    def receipt_patla(tools):
        raise RuntimeError("receipt yok")
    monkeypatch.setattr("core.build_receipt.collect_build_receipt",
                        receipt_patla)

    def sha_patla(p):
        raise OSError("sha yok")
    monkeypatch.setattr("core.security.sha256_hash", sha_patla)

    prov = PV.create_provenance(source_file=kaynak, output_file=cikti,
                                tools=TOOLS)
    assert prov.tool_versions == {}
    assert prov.source_sha256 == "" and prov.output_sha256 == ""


def test_verify_provenance_source_mismatch(monkeypatch, tmp_path):
    kaynak = tmp_path / "kaynak.deb"; kaynak.write_bytes(b"K")
    prov = PV.BuildProvenance()
    prov.source_file = str(kaynak)
    prov.source_sha256 = "ff" * 32
    monkeypatch.setattr("core.security.sha256_hash", lambda p: "ee" * 32)
    ok, msg = PV.verify_provenance(prov)
    assert ok is False and "uyuşmuyor" in msg


def test_verify_provenance_output_mismatch(monkeypatch, tmp_path):
    cikti = tmp_path / "cikti.pkg.tar.zst"; cikti.write_bytes(b"C")
    prov = PV.BuildProvenance()
    prov.output_file = str(cikti)
    prov.output_sha256 = "ff" * 32
    monkeypatch.setattr("core.security.sha256_hash", lambda p: "ee" * 32)
    ok, msg = PV.verify_provenance(prov)
    assert ok is False and "uyuşmuyor" in msg


def test_attestation_signer_branch():
    prov = PV.BuildProvenance()
    prov.output_file = "/tmp/cikti.pkg.tar.zst"
    prov.output_sha256 = "ab" * 32
    st = PV.create_attestation(prov, signer_key="x" * 32)
    assert st.predicate["signer"]["keyId"] == "x" * 16


def test_verify_attestation_rejects():
    iyi = NS(_type="https://in-toto.io/Statement/v1",
             predicate_type="https://pkgforge.dev/convert/v1",
             subject=[{"name": "a"}],
             predicate={"builder": {}, "buildType": "t", "metadata": {}})
    ok, _ = PV.verify_attestation(iyi)
    assert ok is True

    kotu_tip = NS(_type="baska", predicate_type="https://x", subject=[{}],
                  predicate={})
    ok, msg = PV.verify_attestation(kotu_tip)
    assert ok is False and "statement tipi" in msg

    kotu_pred = NS(_type="https://in-toto.io/Statement/v1",
                   predicate_type="ftp://x", subject=[{}], predicate={})
    ok, msg = PV.verify_attestation(kotu_pred)
    assert ok is False and "predicate tipi" in msg

    subj_yok = NS(_type="https://in-toto.io/Statement/v1",
                  predicate_type="https://x", subject=[], predicate={})
    ok, msg = PV.verify_attestation(subj_yok)
    assert ok is False and "subject yok" in msg

    eksiko_alan = NS(_type="https://in-toto.io/Statement/v1",
                     predicate_type="https://x", subject=[{}],
                     predicate={"builder": {}})
    ok, msg = PV.verify_attestation(eksiko_alan)
    assert ok is False and "buildType" in msg

def test_diff_summary_version_changes():
    eski = SB.SBOMDocument(); eski.files = []
    yeni = SB.SBOMDocument(); yeni.files = []
    fark = SB.diff_sboms(eski, yeni)
    fark.version_changes = [
        {"dep": "kitaplik", "old": "1.0", "new": "2.0"},
        {"dep": "diger", "old": "3.1", "new": "3.2"},
    ]
    metin = fark.summary()
    assert "Versiyon değişiklikleri" in metin
    assert "kitaplik: 1.0 → 2.0" in metin
