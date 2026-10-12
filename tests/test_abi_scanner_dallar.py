"""pkgforge core.abi_scanner dal-kesen testleri (LEED) — 4 fonksiyon.

Kapsanan fonksiyonlar: _collect_elf_binaries, _extract_pkg_for_abi,
_get_objcopy, _ldd_missing_libs.

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory — ar/tar/ldd/objcopy CAGRILMADI; safe_run + shutil.which
         MONKEYPATCH ile sahte CompletedProcess donduruldu (gercek komut YOK).
         ELF girdileri tmp_path'te elle yazilir (network YOK).
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, ".")
import core.abi_scanner
from core.abi_scanner import (
    _collect_elf_binaries,
    _extract_pkg_for_abi,
    _get_objcopy,
    _ldd_missing_libs,
)
from core.constants import TIMEOUT_FAST, TIMEOUT_MEDIUM

_ELF_HEADER = b"\x7fELF"


def _cp(stdout: str = "", stderr: str = "", rc: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["fake"], returncode=rc,
                                       stdout=stdout, stderr=stderr)


class _Rec:
    """safe_run cagrilarini kaydeder; siradaki CompletedProcess'i dondurur."""

    def __init__(self, results=()):
        self.results = list(results)
        self.calls = []

    def __call__(self, cmd, *, cwd=None, timeout=120, env=None, input=None, text=None):
        self.calls.append({"cmd": list(cmd), "timeout": timeout, "cwd": cwd})
        if self.results:
            return self.results.pop(0)
        return _cp()


def _write_elf(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_ELF_HEADER + b"\x02\x01\x01\x00" * 4)
    return path


def _write_text(path: Path, content: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


# == _collect_elf_binaries =========================================================================

def test_collect_elf_bulunan(tmp_path):
    """ORTAM: ELF header'li dosya toplanir."""
    e = _write_elf(tmp_path / "usr" / "bin" / "app")
    assert _collect_elf_binaries(tmp_path) == [e]


def test_collect_elf_birden_fazla(tmp_path):
    """ORTAM: birden fazla ELF ikilisi sorted olarak doner."""
    a = _write_elf(tmp_path / "usr" / "bin" / "a")
    b = _write_elf(tmp_path / "usr" / "lib" / "b.so")
    assert _collect_elf_binaries(tmp_path) == sorted([a, b])


@pytest.mark.parametrize("ext", [
    ".py", ".txt", ".conf", ".json", ".xml", ".png", ".jpg", ".svg", ".md",
    ".rst", ".html", ".css", ".js", ".ts", ".yaml", ".yml", ".toml", ".ini",
    ".cfg", ".sh", ".bash", ".desktop", ".service",
])
def test_collect_elf_atlanan_uzantilar(tmp_path, ext):
    """ORTAM: bilinen metin/asset uzantilari atlanir (ELF header olsa bile)."""
    p = tmp_path / ("file" + ext)
    p.write_bytes(_ELF_HEADER + b"junk")
    assert _collect_elf_binaries(tmp_path) == []


def test_collect_elf_atlanan_uzanti_buyuk_harf(tmp_path):
    """ORTAM: suffix lower()'a gore karsilastir -> .PY de atlanir."""
    p = tmp_path / "x.PY"
    p.write_bytes(_ELF_HEADER)
    assert _collect_elf_binaries(tmp_path) == []


@pytest.mark.parametrize("name", [".hidden", "_internal", ".dot.so", "_priv"])
def test_collect_elf_atlanan_onekler(tmp_path, name):
    """ORTAM: '.' veya '_' ile baslayan dosyalar atlanir."""
    p = tmp_path / name
    p.write_bytes(_ELF_HEADER)
    assert _collect_elf_binaries(tmp_path) == []


def test_collect_elf_klasor_atlanir(tmp_path):
    """ORTAM: klasorler (is_file False) atlanir."""
    (tmp_path / "subdir").mkdir()
    e = _write_elf(tmp_path / "app")
    assert _collect_elf_binaries(tmp_path) == [e]


def test_collect_elf_bos_klasor(tmp_path):
    """ORTAM: bos agac -> bos liste."""
    assert _collect_elf_binaries(tmp_path) == []


def test_collect_elf_okunamayan_dosya_atlanir(tmp_path):
    """ORTAM: IOError'da _is_elf_binary False doner -> atlanir (crash YOK)."""
    e = _write_elf(tmp_path / "app")

    class _Boom:
        def __init__(self, *a, **k):
            raise PermissionError("yok")

    import builtins
    orig = builtins.open
    builtins.open = _Boom
    try:
        assert _collect_elf_binaries(tmp_path) == []
    finally:
        builtins.open = orig
    assert e.exists()  # dosya yerinde


def test_collect_elf_uzantisiz_elf_alinir(tmp_path):
    """ORTAM: uzantisiz ELF ikilisi toplanir."""
    e = _write_elf(tmp_path / "usr" / "bin" / "tool")
    assert _collect_elf_binaries(tmp_path) == [e]


def test_collect_elf_karisik_icerik(tmp_path):
    """ORTAM: metinler atlanir, ELF'ler alınır."""
    _write_text(tmp_path / "README.md")
    _write_text(tmp_path / "usr/bin/app.py")
    _write_elf(tmp_path / "usr/bin/app")
    _write_elf(tmp_path / "lib/x.so.1")
    r = _collect_elf_binaries(tmp_path)
    assert len(r) == 2
    assert {p.name for p in r} == {"app", "x.so.1"}


# == _extract_pkg_for_abi ===========================================================================

def test_extract_deb_basarisiz_format(tmp_path):
    """ORTAM: .deb/.pkg.tar icermeyen isim -> False (komut CALISMADAN)."""
    rec = _Rec([_cp(rc=0)])
    import core.abi_scanner as mod
    orig = mod.safe_run
    mod.safe_run = rec
    try:
        assert _extract_pkg_for_abi(tmp_path / "p.tar.gz", tmp_path) is False
    finally:
        mod.safe_run = orig
    assert rec.calls == []


def test_extract_pkg_tar_basari(monkeypatch, tmp_path):
    """ORTAM: .pkg.tar.* -> 'tar xf pkg -C tmp' rc 0 -> True."""
    rec = _Rec([_cp(rc=0)])
    monkeypatch.setattr(core.abi_scanner, "safe_run", rec)
    pkg = tmp_path / "p.pkg.tar.zst"
    out = tmp_path / "out"
    out.mkdir()
    assert _extract_pkg_for_abi(pkg, out) is True
    assert rec.calls == [{"cmd": ["tar", "xf", str(pkg), "-C", str(out)],
                          "timeout": TIMEOUT_MEDIUM, "cwd": None}]


def test_extract_pkg_tar_zaman_asimi(monkeypatch, tmp_path):
    """ORTAM: tar timeout=TIMEOUT_MEDIUM (30s) ile cagrilir."""
    rec = _Rec([_cp(rc=0)])
    monkeypatch.setattr(core.abi_scanner, "safe_run", rec)
    _extract_pkg_for_abi(tmp_path / "p.pkg.tar.xz", tmp_path)
    assert rec.calls[0]["timeout"] == TIMEOUT_MEDIUM


@pytest.mark.parametrize("rc", [0, 1, 2])
def test_extract_pkg_tar_returncode_esleri(monkeypatch, tmp_path, rc):
    """ORTAM: pkg.tar yolu returncode'u goz ardi eder -> her zaman True."""
    monkeypatch.setattr(core.abi_scanner, "safe_run", lambda *a, **k: _cp(rc=rc))
    assert _extract_pkg_for_abi(tmp_path / "p.pkg.tar.gz", tmp_path) is True


def test_extract_deb_ar_data_yolu(monkeypatch, tmp_path):
    """ORTAM: .deb -> '/bin/bash -c ar x ... data.tar.*' + tar xf data.tar."""
    rec = _Rec([_cp(rc=0), _cp(rc=0)])
    monkeypatch.setattr(core.abi_scanner, "safe_run", rec)
    pkg = tmp_path / "p.deb"
    out = tmp_path / "out"
    out.mkdir()
    (out / "data.tar.xz").write_bytes(b"x")  # ar ciktisi simule
    assert _extract_pkg_for_abi(pkg, out) is True
    assert len(rec.calls) == 2
    assert rec.calls[0]["cmd"][0] == "/bin/bash"
    assert "ar x" in rec.calls[0]["cmd"][2]
    assert str(pkg) in rec.calls[0]["cmd"][2]
    assert "data.tar.*" in rec.calls[0]["cmd"][2]
    assert rec.calls[0]["cwd"] == str(out)


def test_extract_deb_data_tar_cikarilir(monkeypatch, tmp_path):
    """ORTAM: ar'dan sonra data.tar.* bulunup tar xf ile acilir."""
    rec = _Rec([_cp(rc=0), _cp(rc=0)])
    monkeypatch.setattr(core.abi_scanner, "safe_run", rec)
    out = tmp_path / "out"
    out.mkdir()
    (out / "data.tar.xz").write_bytes(b"x")
    _extract_pkg_for_abi(tmp_path / "p.deb", out)
    assert rec.calls[1]["cmd"][0] == "tar"
    assert rec.calls[1]["cmd"][1] == "xf"
    assert rec.calls[1]["cmd"][2].endswith("data.tar.xz")
    assert not (out / "data.tar.xz").exists()  # cikarildiktan sonra silinir


def test_extract_deb_data_tar_yoksa(monkeypatch, tmp_path):
    """ORTAM: ar sonrasi data.tar bulunamazsa tar xf yapilmaz -> yine True."""
    rec = _Rec([_cp(rc=0)])
    monkeypatch.setattr(core.abi_scanner, "safe_run", rec)
    out = tmp_path / "out"
    out.mkdir()
    assert _extract_pkg_for_abi(tmp_path / "p.deb", out) is True
    assert len(rec.calls) == 1  # sadece ar cagrildi


def test_extract_deb_istisna_false(monkeypatch, tmp_path):
    """ORTAM: ar TimeoutExpired/OSError -> False."""
    def boom(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=1)

    monkeypatch.setattr(core.abi_scanner, "safe_run", boom)
    assert _extract_pkg_for_abi(tmp_path / "p.deb", tmp_path) is False


def test_extract_deb_oserror_false(monkeypatch, tmp_path):
    """ORTAM: ar OSError -> False."""
    def boom(cmd, **kw):
        raise OSError("yok")

    monkeypatch.setattr(core.abi_scanner, "safe_run", boom)
    assert _extract_pkg_for_abi(tmp_path / "p.deb", tmp_path) is False


@pytest.mark.parametrize("name", ["p.pkg.tar.zst", "p.pkg.tar.xz", "p.pkg.tar.gz",
                                  "p.pkg.tar", "x.deb", "y.deb"])
def test_extract_desteklenen_uzantilar(monkeypatch, tmp_path, name):
    """ORTAM: desteklenen uzantilar True doner (komut stub)."""
    monkeypatch.setattr(core.abi_scanner, "safe_run", lambda *a, **k: _cp(rc=0))
    assert _extract_pkg_for_abi(tmp_path / name, tmp_path) is True


# == _get_objcopy ==================================================================================

@pytest.mark.parametrize("which_result,expected", [
    ("/usr/bin/objcopy", "/usr/bin/objcopy"),
    ("/home/u/bin/objcopy", "/home/u/bin/objcopy"),
])
def test_objcopy_bulunur(monkeypatch, which_result, expected):
    """ORTAM: which('objcopy') doluysa o doner."""
    monkeypatch.setattr(shutil, "which", lambda n: which_result if n == "objcopy" else None)
    assert _get_objcopy() == expected


def test_objcopy_yoksa_mutlak_yol(monkeypatch):
    """ORTAM: 'objcopy' PATH'te yoksa '/usr/bin/objcopy' denenir."""
    seq = []

    def fake(n):
        seq.append(n)
        return "/usr/bin/objcopy" if n == "/usr/bin/objcopy" else None

    monkeypatch.setattr(shutil, "which", fake)
    assert _get_objcopy() == "/usr/bin/objcopy"
    assert seq == ["objcopy", "/usr/bin/objcopy"]


def test_objcopy_hic_yoksa_none(monkeypatch):
    """ORTAM: iki deneme de bos -> None."""
    monkeypatch.setattr(shutil, "which", lambda n: None)
    assert _get_objcopy() is None


def test_objcopy_bos_string_none(monkeypatch):
    """ORTAM-OGRENDI: which '' donerse 'or' zinciri '' birakir (None DEGIL)."""
    monkeypatch.setattr(shutil, "which", lambda n: "")
    assert _get_objcopy() == ""


# == _ldd_missing_libs =============================================================================

def test_ldd_yoksa_bos(monkeypatch, tmp_path):
    """ORTAM: ldd kurul degil -> [] (komut calismaz)."""
    monkeypatch.setattr(shutil, "which", lambda n: None)
    rec = _Rec([_cp()])
    monkeypatch.setattr(core.abi_scanner, "safe_run", rec)
    assert _ldd_missing_libs([tmp_path / "a"], tmp_path) == []
    assert rec.calls == []


def test_ldd_elf_yoksa_bos(monkeypatch, tmp_path):
    """ORTAM: elf_files bos -> [] (ldd var olsa bile)."""
    monkeypatch.setattr(shutil, "which", lambda n: "/usr/bin/ldd")
    rec = _Rec([_cp()])
    monkeypatch.setattr(core.abi_scanner, "safe_run", rec)
    assert _ldd_missing_libs([], tmp_path) == []
    assert rec.calls == []


def test_ldd_eksik_yok(monkeypatch, tmp_path):
    """ORTAM: tum kutuphaneler bulundu -> bos liste."""
    monkeypatch.setattr(shutil, "which", lambda n: "/usr/bin/ldd")
    monkeypatch.setattr(core.abi_scanner, "safe_run",
                        lambda *a, **k: _cp(stdout="\tlibc.so.6 => /usr/lib/libc.so.6\n"))
    elf = _write_elf(tmp_path / "app")
    assert _ldd_missing_libs([elf], tmp_path) == []


@pytest.mark.parametrize("line,expected", [
    ("\tlibc.so.6 => not found\n", ("app", "libc.so.6")),
    ("\tlibfoo.so.1 => not found\n", ("app", "libfoo.so.1")),
    ("\tlibc.so.6 => /usr/lib/libc.so.6\n", None),
    ("\tlinux-vdso.so.1 =>  (0x0000)\n", None),
])
def test_ldd_not_found_ayristirma(monkeypatch, tmp_path, line, expected):
    """ORTAM: 'not found' satirindan (rel path, kutuphane) cifti; yoksa bos."""
    monkeypatch.setattr(shutil, "which", lambda n: "/usr/bin/ldd")
    monkeypatch.setattr(core.abi_scanner, "safe_run", lambda *a, **k: _cp(stdout=line))
    elf = _write_elf(tmp_path / "app")
    r = _ldd_missing_libs([elf], tmp_path)
    if expected:
        assert r == [expected]
    else:
        assert r == []


def test_ldd_birden_fazla_eksik(monkeypatch, tmp_path):
    """ORTAM: ayni ikilide birden fazla eksik -> duzlestirilmis cift listesi."""
    monkeypatch.setattr(shutil, "which", lambda n: "/usr/bin/ldd")
    monkeypatch.setattr(core.abi_scanner, "safe_run", lambda *a, **k: _cp(
        stdout="\tlibc.so.6 => not found\n\tlibfoo.so.1 => not found\n"))
    elf = _write_elf(tmp_path / "app")
    assert _ldd_missing_libs([elf], tmp_path) == [
        ("app", "libc.so.6"), ("app", "libfoo.so.1")]


def test_ldd_birden_fazla_ikili(monkeypatch, tmp_path):
    """ORTAM: her ikili kendi ciftlerini uretir (relative path)."""
    a = _write_elf(tmp_path / "usr" / "bin" / "a")
    b = _write_elf(tmp_path / "usr" / "bin" / "b")
    results = iter([
        _cp(stdout="\tliba.so => not found\n"),
        _cp(stdout="\tlibb.so => not found\n"),
    ])
    monkeypatch.setattr(shutil, "which", lambda n: "/usr/bin/ldd")
    monkeypatch.setattr(core.abi_scanner, "safe_run", lambda *a, **k: next(results))
    r = _ldd_missing_libs([a, b], tmp_path)
    assert r == [("usr/bin/a", "liba.so"), ("usr/bin/b", "libb.so")]


def test_ldd_komut_ve_zaman_asimi(monkeypatch, tmp_path):
    """ORTAM: 'ldd <elf>' komutu, timeout=TIMEOUT_FAST (5s)."""
    rec = _Rec([_cp()])
    monkeypatch.setattr(shutil, "which", lambda n: "/usr/bin/ldd")
    monkeypatch.setattr(core.abi_scanner, "safe_run", rec)
    elf = _write_elf(tmp_path / "app")
    _ldd_missing_libs([elf], tmp_path)
    assert rec.calls == [{"cmd": ["/usr/bin/ldd", str(elf)],
                          "timeout": TIMEOUT_FAST, "cwd": None}]


def test_ldd_istisna_atlanir(monkeypatch, tmp_path):
    """ORTAM: TimeoutExpired/OSError -> o ikili atlanir (crash YOK)."""
    def boom(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=1)

    monkeypatch.setattr(shutil, "which", lambda n: "/usr/bin/ldd")
    monkeypatch.setattr(core.abi_scanner, "safe_run", boom)
    elf = _write_elf(tmp_path / "app")
    assert _ldd_missing_libs([elf], tmp_path) == []


def test_ldd_oserror_atlanir(monkeypatch, tmp_path):
    """ORTAM: OSError -> ikili atlanir."""
    def boom(cmd, **kw):
        raise OSError("yok")

    monkeypatch.setattr(shutil, "which", lambda n: "/usr/bin/ldd")
    monkeypatch.setattr(core.abi_scanner, "safe_run", boom)
    elf = _write_elf(tmp_path / "app")
    assert _ldd_missing_libs([elf], tmp_path) == []
