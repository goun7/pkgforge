"""pkgforge core.sbom dal-kesen testleri (LEED) — tar-line ayristirma + dosya-türü + sayaclama.

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (tmp_path + magic-byte dosyalari + monkeypatch;
network/HTTP/DB/subprocess YASAK — dep_resolver stub'landi).

ORTAM-ANATOMI:
- _parse_tv_line(line): _TV_BSDTAR_RE | _TV_GNU_RE -> (perms, size, path) | None
- _detect_file_type(path): magic bytes -> elf/text/binary/""
- _summarize_file_counts(sbom): file_type sayaclari
- _fill_runtime_deps(sbom, tools, *, offline): offline=True -> atla
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, ".")
sys.path.insert(0, "src")
from core.sbom import (  # noqa: E402
    SBOMDocument, _detect_file_type, _fill_runtime_deps, _parse_tv_line,
    _summarize_file_counts,
)

BSD = "-rw-r--r-- 1 root root 1234 Jan 1 12:00 pkg/test.txt"
GNU = "-rw-r--r-- root 1234 2026-01-01 12:00 pkg/test.txt"


# == _parse_tv_line: BSDTAR =============================================================================

def test_bsd_gecerli():
    perms, size, path = _parse_tv_line(BSD)
    assert perms == "-rw-r--r--"
    assert size == 1234
    assert path == "pkg/test.txt"


def test_bsd_dizin():
    perms, size, path = _parse_tv_line("drwxr-xr-x 0 root root 0 Jan 1 12:00 pkg/")
    assert perms == "drwxr-xr-x"
    assert size == 0
    assert path == "pkg/"


def test_bsd_symlink():
    line = "lrwxrwxrwx 1 root root 5 Jan 1 12:00 pkg/link -> real"
    perms, size, path = _parse_tv_line(line)
    assert perms == "lrwxrwxrwx"


def test_bsd_bosluklu_dosya_adi():
    """ORTAM: '(.+)$' greedy — bosluklu isim TAM korunnur."""
    _, _, path = _parse_tv_line("-rw-r--r-- 1 root root 1 Jan 1 12:00 a b c.txt")
    assert path == "a b c.txt"


def test_bsd_buyuk_size():
    _, size, _ = _parse_tv_line("-rw-r--r-- 1 root root 99999999999 Jan 1 12:00 x")
    assert size == 99999999999


def test_bsd_farkli_ay():
    for ay in ["Jan", "Dec", "Jun"]:
        assert _parse_tv_line(f"-rw-r--r-- 1 r r 1 {ay} 1 12:00 x") is not None


def test_bsd_farkli_gun():
    for gun in ["1", "12", "31"]:
        assert _parse_tv_line(f"-rw-r--r-- 1 r r 1 Jan {gun} 12:00 x") is not None


def test_bsd_saat():
    for saat in ["00:00", "12:00", "23:59"]:
        assert _parse_tv_line(f"-rw-r--r-- 1 r r 1 Jan 1 {saat} x") is not None


def test_bsd_eksik_alan_reject():
    assert _parse_tv_line("-rw-r--r-- 1 root root 1234 Jan 1 12:00") is None


def test_bsd_saat_yok_reject():
    assert _parse_tv_line("-rw-r--r-- 1 root root 1234 Jan 1 x") is None


def test_bsd_sayi_olmayan_size_reject():
    assert _parse_tv_line("-rw-r--r-- 1 root root abc Jan 1 12:00 x") is None


def test_bsd_kisa_perms_reject():
    assert _parse_tv_line("-rw- 1 root root 1234 Jan 1 12:00 x") is None


def test_bsd_uzun_isim():
    uzun = "x" * 200
    _, _, path = _parse_tv_line(f"-rw-r--r-- 1 root root 1 Jan 1 12:00 {uzun}")
    assert path == uzun


# == _parse_tv_line: GNU ================================================================================

def test_gnu_gecerli():
    perms, size, path = _parse_tv_line(GNU)
    assert perms == "-rw-r--r--"
    assert size == 1234
    assert path == "pkg/test.txt"


def test_gnu_dizin():
    _, size, _ = _parse_tv_line("drwxr-xr-x root 0 2026-06-15 08:30 pkg/")
    assert size == 0


def test_gnu_symlink():
    assert _parse_tv_line("lrwxrwxrwx root 5 2026-01-01 12:00 l -> r") is not None


def test_gnu_bosluklu_isim():
    _, _, path = _parse_tv_line("-rw-r--r-- root 1 2026-01-01 12:00 a b.txt")
    assert path == "a b.txt"


def test_gnu_tarih():
    for tarih in ["2026-01-01", "1999-12-31", "2100-06-15"]:
        assert _parse_tv_line(f"-rw-r--r-- root 1 {tarih} 12:00 x") is not None


def test_gnu_tarih_sadece_format():
    """ORTAM-OGRENDI: \d{4}-\d{2}-\d{2} SADECE format denetler —
    '2026-13-45' takvim-gecersiz olsa da regex eslesir (calendar
    validation YOK). Quirk characterization pin'lendi."""
    r = _parse_tv_line("-rw-r--r-- root 1 2026-13-45 12:00 x")
    assert r is not None and r[1] == 1


def test_gnu_eksik_saat_reject():
    assert _parse_tv_line("-rw-r--r-- root 1 2026-01-01 x") is None


# == _parse_tv_line: genel ==============================================================================

def test_bos_satir():
    assert _parse_tv_line("") is None


def test_bosluk_satiri():
    assert _parse_tv_line("   ") is None


def test_rastgele_metin():
    assert _parse_tv_line("random text") is None


def test_izin_karakterleri():
    for p in ["----------", "-rwxrwxrwx", "-rw-------", "-r--r--r--"]:
        assert _parse_tv_line(f"{p} 1 root root 1 Jan 1 12:00 x") is not None


def test_donus_tipi():
    r = _parse_tv_line(BSD)
    assert isinstance(r, tuple) and len(r) == 3


@pytest.mark.parametrize("line,beklenen_size", [
    (BSD, 1234), (GNU, 1234),
    ("-rwxrwxrwx 1 r r 42 Jan 1 12:00 a", 42),
    ("-rwxrwxrwx r 42 2026-01-01 12:00 a", 42),
])
def test_size_matrix(line, beklenen_size):
    assert _parse_tv_line(line)[1] == beklenen_size


@pytest.mark.parametrize("line", [
    "", "  ", "abc", "-rw-r--r-- eksik",
    "-rw-r--r-- 1 root root 1 Jan 1 12:00",
    "-rw-r--r-- root 1 2026-01-01",
])
def test_reddedilen_matrix(line):
    assert _parse_tv_line(line) is None


# == _detect_file_type ==================================================================================

def test_elf(tmp_path):
    f = tmp_path / "x.so"
    f.write_bytes(b"\x7fELF\x02\x01\x01\x00")
    assert _detect_file_type(f) == "elf"


def test_elf_tam_4_byte(tmp_path):
    f = tmp_path / "y"
    f.write_bytes(b"\x7fELF")
    assert _detect_file_type(f) == "elf"


def test_shebang(tmp_path):
    f = tmp_path / "script.sh"
    f.write_bytes(b"#!/bin/bash\necho hi\n")
    assert _detect_file_type(f) == "text"


def test_shebang_kisa(tmp_path):
    f = tmp_path / "s"
    f.write_bytes(b"#!")
    assert _detect_file_type(f) == "text"


def test_utf16_le(tmp_path):
    """ORTAM: '<\x00' UTF-16 LE BOM -> text."""
    f = tmp_path / "u16"
    f.write_bytes(b"<\x00h\x00i\x00")
    assert _detect_file_type(f) == "text"


def test_utf8_bom(tmp_path):
    f = tmp_path / "bom"
    f.write_bytes(b"\xef\xbb\xbf# comment\n")
    assert _detect_file_type(f) == "text"


def test_utf32_le_bom(tmp_path):
    """ORTAM: '\xff\xfe\x00' UTF-32 LE BOM -> text."""
    f = tmp_path / "u32"
    f.write_bytes(b"\xff\xfe\x00\x00hi")
    assert _detect_file_type(f) == "text"


def test_binary(tmp_path):
    f = tmp_path / "bin"
    f.write_bytes(b"\x00\x01\x02\x03")
    assert _detect_file_type(f) == "binary"


def test_bos_dosya(tmp_path):
    """ORTAM: 0 byte -> magic=b'' -> 'binary'."""
    f = tmp_path / "empty"
    f.write_bytes(b"")
    assert _detect_file_type(f) == "binary"


def test_kisa_binary(tmp_path):
    f = tmp_path / "short"
    f.write_bytes(b"\x00")
    assert _detect_file_type(f) == "binary"


def test_dosya_yok():
    """ORTAM: OSError -> ''."""
    assert _detect_file_type(Path("/yok/boyle/dosya")) == ""


def test_dizin(tmp_path):
    """ORTAM: dizin okuma -> OSError/IsADirectoryError -> ''."""
    assert _detect_file_type(tmp_path) == ""


def test_elf_uzun(tmp_path):
    f = tmp_path / "big.so"
    f.write_bytes(b"\x7fELF" + b"\x00" * 1000)
    assert _detect_file_type(f) == "elf"


def test_stabil(tmp_path):
    f = tmp_path / "x"
    f.write_bytes(b"\x7fELF")
    assert _detect_file_type(f) == _detect_file_type(f)


@pytest.mark.parametrize("magic,beklenen", [
    (b"\x7fELF", "elf"),
    (b"#!", "text"),
    (b"<\x00", "text"),
    (b"\xef\xbb\xbf", "text"),
    (b"\xff\xfe\x00", "text"),
    (b"ABCD", "binary"),
    (b"", "binary"),
])
def test_magic_matrix(tmp_path, magic, beklenen):
    f = tmp_path / "m"
    f.write_bytes(magic)
    assert _detect_file_type(f) == beklenen


# == _summarize_file_counts =============================================================================

class _F:
    def __init__(self, t):
        self.file_type = t


def _doc(*tipler):
    d = SBOMDocument()
    d.files = [_F(t) for t in tipler]
    _summarize_file_counts(d)
    return d


def test_hepsi_sifir():
    d = _doc()
    assert (d.elf_count, d.text_count, d.symlink_count, d.dir_count) == (0, 0, 0, 0)


def test_elf_sayisi():
    assert _doc("elf", "elf", "elf").elf_count == 3


def test_text_sayisi():
    assert _doc("text", "text").text_count == 2


def test_symlink_sayisi():
    assert _doc("symlink").symlink_count == 1


def test_dizin_sayisi():
    assert _doc("directory", "directory", "directory", "directory").dir_count == 4


def test_karisik():
    d = _doc("elf", "text", "text", "symlink", "directory", "elf")
    assert (d.elf_count, d.text_count, d.symlink_count, d.dir_count) == (2, 2, 1, 1)


def test_bilinmeyen_tip_sayanlar_artmaz():
    """ORTAM: 'binary' sayaclardan HICBIRINE girmez."""
    d = _doc("binary", "binary", "binary")
    assert (d.elf_count, d.text_count, d.symlink_count, d.dir_count) == (0, 0, 0, 0)


def test_bos_files():
    d = SBOMDocument()
    d.files = []
    _summarize_file_counts(d)
    assert d.elf_count == 0


def test_uygulama_idempotent():
    d = _doc("elf")
    once = (d.elf_count, d.text_count, d.symlink_count, d.dir_count)
    _summarize_file_counts(d)
    assert (d.elf_count, d.text_count, d.symlink_count, d.dir_count) == once


def test_toplam_files_ile_uyumlu():
    tipler = ["elf", "text", "symlink", "directory", "binary"]
    d = _doc(*tipler)
    assert d.elf_count + d.text_count + d.symlink_count + d.dir_count <= len(tipler)


@pytest.mark.parametrize("tip,sayac", [
    ("elf", "elf_count"), ("text", "text_count"),
    ("symlink", "symlink_count"), ("directory", "dir_count"),
])
def test_sayac_matrix(tip, sayac):
    d = _doc(tip, tip, tip, tip, tip)
    assert getattr(d, sayac) == 5
    for diger in ("elf_count", "text_count", "symlink_count", "dir_count"):
        if diger != sayac:
            assert getattr(d, diger) == 0


# == _fill_runtime_deps =================================================================================

class _Tools:
    pass


def test_offline_atlar():
    """ORTAM: offline=True -> dep_resolver import EDILMEZ."""
    d = SBOMDocument()
    d.dependencies = []
    _fill_runtime_deps(d, _Tools(), offline=True)
    assert d.dependencies == []


def test_offline_dep_resolver_cagrilmaz(monkeypatch):
    """ORTAM-OGRENDI: offline modda core.dep_resolver yuklenmez (agir modul)."""
    import builtins
    gercek = builtins.__import__
    cagrilan = []

    def sahte_import(isim, *a, **kw):
        if "dep_resolver" in str(isim):
            cagrilan.append(isim)
        return gercek(isim, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", sahte_import)
    d = SBOMDocument()
    _fill_runtime_deps(d, _Tools(), offline=True)
    assert cagrilan == []


def test_online_stub(monkeypatch):
    """ORTAM: offline=False -> resolve_runtime_dependencies cagrilir."""
    import core.sbom as sbom_mod
    cagri = {"n": 0, "arg": None}

    def sahte_resolve(kok, tools):
        cagri["n"] += 1
        cagri["arg"] = (kok, tools)
        return ["libfoo.so"]

    monkeypatch.setitem(sys.modules, "core.dep_resolver",
                        type("M", (), {"resolve_runtime_dependencies": sahte_resolve}))
    d = SBOMDocument()
    d.dependencies = []
    _fill_runtime_deps(d, _Tools(), offline=False)
    assert cagri["n"] == 1
    assert d.dependencies == ["libfoo.so"]


def test_online_hata_yutulur(monkeypatch):
    """ORTAM-OGRENDI: dep_resolver exception -> log.debug, sessiz yutulur
    (noqa: BLE001) — SBOM uretimi durmaz."""
    def sahte_resolve(kok, tools):
        raise RuntimeError("patladi")

    monkeypatch.setitem(sys.modules, "core.dep_resolver",
                        type("M", (), {"resolve_runtime_dependencies": sahte_resolve}))
    d = SBOMDocument()
    onceki = list(d.dependencies) if hasattr(d, "dependencies") else None
    _fill_runtime_deps(d, _Tools(), offline=False)
    assert onceki is None or d.dependencies == onceki


def test_online_import_hatasi_yutulur(monkeypatch):
    """ORTAM: dep_resolver import basarisiz -> yutulur."""
    def sahte_resolve(kok, tools):
        raise ImportError("yok")

    monkeypatch.setitem(sys.modules, "core.dep_resolver",
                        type("M", (), {"resolve_runtime_dependencies": sahte_resolve}))
    d = SBOMDocument()
    _fill_runtime_deps(d, _Tools(), offline=False)
    # hata yutuldu, exception yayilmadi


def test_online_kok_dizini(monkeypatch):
    """ORTAM: resolve_runtime_dependencies(Path('/'), tools) — kok her zaman '/'."""
    gorulen = {}

    def sahte_resolve(kok, tools):
        gorulen["kok"] = kok
        return []

    monkeypatch.setitem(sys.modules, "core.dep_resolver",
                        type("M", (), {"resolve_runtime_dependencies": sahte_resolve}))
    d = SBOMDocument()
    _fill_runtime_deps(d, _Tools(), offline=False)
    assert gorulen["kok"] == Path("/")


def test_tools_aktarilir(monkeypatch):
    gorulen = {}

    def sahte_resolve(kok, tools):
        gorulen["tools"] = tools
        return []

    tp = _Tools()
    monkeypatch.setitem(sys.modules, "core.dep_resolver",
                        type("M", (), {"resolve_runtime_dependencies": sahte_resolve}))
    d = SBOMDocument()
    _fill_runtime_deps(d, tp, offline=False)
    assert gorulen["tools"] is tp


@pytest.mark.parametrize("offline", [True, True, False, False])
def test_offline_matrix(monkeypatch, offline):
    sayac = {"n": 0}

    def sahte_resolve(kok, tools):
        sayac["n"] += 1
        return []

    monkeypatch.setitem(sys.modules, "core.dep_resolver",
                        type("M", (), {"resolve_runtime_dependencies": sahte_resolve}))
    _fill_runtime_deps(SBOMDocument(), _Tools(), offline=offline)
    assert sayac["n"] == (0 if offline else 1)
