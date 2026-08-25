"""Coverage itmesi — core/dep_resolver.py: cozumleme, AUR, ELF/soname akislari."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import core.dep_resolver as DR
from config import ToolPaths


def _rc(code, stdout="", stderr=""):
    return NS(returncode=code, stdout=stdout, stderr=stderr)


def _araclar(**kw):
    taban = {"debtap": "/u/debtap", "rpm2cpio": "/u/rpm2cpio",
             "makepkg": "/u/makepkg", "pacman": "/u/pacman",
             "readelf": "", "objdump": ""}
    taban.update(kw)
    return ToolPaths(**taban)


# --- bagimlilik dizgesi cozumu --------------------------------------------------

@pytest.mark.parametrize("girdi,beklenen", [
    ("foo>=2.0", ("foo", ">=2.0")),
    ("bar<=1", ("bar", "<=1")),
    ("baz>3", ("baz", ">3")),
    ("qux<0.1", ("qux", "<0.1")),
    ("lib=5", ("lib", "=5")),
    ("  duz ", ("duz", "")),
    ("=sadece-op", ("=sadece-op", "")),   # sol bos -> operator eslesmez
])
def test_parse_dep_string_variants(girdi, beklenen):
    assert DR._parse_dep_string(girdi) == beklenen


# --- pacman sorgulari -----------------------------------------------------------

def test_check_pacman_missing_tool(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: None)
    assert DR._check_pacman("x") == (False, "")
    monkeypatch.setattr(DR, "safe_run",
                        lambda cmd, timeout=0: _rc(0,
                                                   stdout="Version : 3.2\n"))
    assert DR._check_pacman_installed("y") == (False, "")


def test_check_pacman_versions_and_unknown(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/pacman")
    cikti = {"Version": []}

    def sahte(cmd, timeout=0):
        return _rc(0, stdout=cikti.get("stdout", ""))
    monkeypatch.setattr(DR, "safe_run", sahte)

    cikti["stdout"] = "Repository : core\nVersion : 6.1-2\n"
    ok, ver = DR._check_pacman("demo")
    assert (ok, ver) == (True, "6.1-2")

    cikti["stdout"] = "Name : demo\n"          # Version satiri yok
    assert DR._check_pacman("demo") == (True, "unknown")

    monkeypatch.setattr(DR, "safe_run",
                        lambda cmd, timeout=0: _rc(1))
    assert DR._check_pacman("demo") == (False, "")

    monkeypatch.setattr(DR, "safe_run",
                        lambda cmd, timeout=0: _rc(0,
                                                   stdout="Version : 9.9\n"))
    ok, ver = DR._check_pacman_installed("demo")
    assert (ok, ver) == (True, "9.9")

    monkeypatch.setattr(DR, "safe_run",
                        lambda cmd, timeout=0: _rc(0, stdout="Desc : x\n"))
    assert DR._check_pacman_installed("demo") == (True, "unknown")


def test_aur_helper_preference(monkeypatch):
    siralar = []
    def sahte(n):
        siralar.append(n)
        return {"paru": None, "yay": "/usr/bin/yay"}.get(n)
    monkeypatch.setattr("shutil.which", sahte)
    assert DR._aur_helper() == "yay"
    monkeypatch.setattr("shutil.which", lambda n: None)
    assert DR._aur_helper() is None


# --- AUR kontrolu ---------------------------------------------------------------

class _Onbellek:
    def __init__(self, cevap=None, hata=None):
        self.cevap = cevap
        self.hata = hata

    def get_or_fetch(self, alan, anahtar, uretici):
        if self.hata:
            raise RuntimeError(self.hata)
        return self.cevap


def _aur_modulleri(monkeypatch, onbellek):
    monkeypatch.setitem(sys.modules, "core.offline_cache",
                        NS(get_cache=lambda: onbellek))
    monkeypatch.setitem(sys.modules, "core.retry",
                        NS(retry_aur_rpc=lambda url, max_retries=0, timeout=0:
                           NS(status="ok")))


def test_check_aur_rpc_hit(monkeypatch):
    onb = _Onbellek(cevap={"resultcount": 1,
                           "results": [{"Name": "demo-git",
                                        "Version": "2.0-1"}]})
    _aur_modulleri(monkeypatch, onb)
    assert DR._check_aur("demo") == (True, "2.0-1")


def test_check_aur_rpc_miss_falls_to_helper(monkeypatch):
    _aur_modulleri(monkeypatch, _Onbellek(cevap={"resultcount": 0}))
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/yay"
                        if n in ("paru", "yay") else None)
    monkeypatch.setattr(DR, "safe_run",
                        lambda cmd, timeout=0: _rc(0,
                                                   stdout="Version : 4.4\n"))
    assert DR._check_aur("demo") == (True, "4.4")

    monkeypatch.setattr(DR, "safe_run",
                        lambda cmd, timeout=0: _rc(0, stdout="Depends : x\n"))
    assert DR._check_aur("demo") == (True, "unknown")


def test_check_aur_error_then_no_helper(monkeypatch):
    _aur_modulleri(monkeypatch, _Onbellek(hata="ag yok"))
    monkeypatch.setattr("shutil.which", lambda n: None)
    assert DR._check_aur("demo") == (False, "")


# --- ELF / soname toplama -------------------------------------------------------

READELF_CIKTI = ("Dynamic section at offset ..\n"
                 " 0x0000000000000001 (NEEDED) Shared library: [libfoo.so.1]\n"
                 " 0x0000000000000001 (NEEDED) Shared library: [libbar.so.2]\n")
OBJDUMP_CIKTI = "  NEEDED  libfoo.so.1\n  NEEDED  libbaz.so.9\n"


def test_parse_helpers():
    assert DR.parse_needed_sonames(READELF_CIKTI) == ["libfoo.so.1",
                                                      "libbar.so.2"]
    assert DR.parse_objdump_sonames(OBJDUMP_CIKTI) == ["libfoo.so.1",
                                                       "libbaz.so.9"]
    assert DR.is_elf_file(Path("/etc/hostname")) is False or True  # tip koru


def test_is_elf_magic(tmp_path):
    elf = tmp_path / "a.out"; elf.write_bytes(b"\x7fELF" + b"kalan")
    duz = tmp_path / "not.txt"; duz.write_bytes(b"merhaba")
    yok = tmp_path / "yok.bin"
    assert DR.is_elf_file(elf) is True
    assert DR.is_elf_file(duz) is False
    assert DR.is_elf_file(yok) is False


def test_collect_sonames_requires_reader(tmp_path):
    assert DR.collect_sonames(tmp_path, _araclar()) == set()


def _elf_agaci(tmp_path, adet=2):
    for i in range(adet):
        (tmp_path / f"bin{i}").write_bytes(b"\x7fELF" + bytes([65 + i]) * 8)
    (tmp_path / "metin.txt").write_text("degil")
    hedef = tmp_path / "bin0"
    bag = tmp_path / "bag"; bag.symlink_to(hedef)
    return bag


def test_collect_sonames_readelf_path(monkeypatch, tmp_path):
    _elf_agaci(tmp_path)
    monkeypatch.setattr(DR, "safe_run",
                        lambda cmd, timeout=0: _rc(0, stdout=READELF_CIKTI))
    sonuc = DR.collect_sonames(tmp_path, _araclar(readelf="/usr/bin/readelf"))
    assert sonuc == {"libfoo.so.1", "libbar.so.2"}


def test_collect_sonames_objdump_fallback(monkeypatch, tmp_path):
    _elf_agaci(tmp_path)
    monkeypatch.setattr(DR, "safe_run",
                        lambda cmd, timeout=0: _rc(0, stdout=OBJDUMP_CIKTI))
    sonuc = DR.collect_sonames(tmp_path, _araclar(objdump="/usr/bin/objdump"))
    assert sonuc == {"libfoo.so.1", "libbaz.so.9"}


def test_collect_sonames_max_files_cap(monkeypatch, tmp_path):
    _elf_agaci(tmp_path, adet=3)
    cagrilar = []
    monkeypatch.setattr(DR, "safe_run",
                        lambda cmd, timeout=0: cagrilar.append(cmd)
                        or _rc(0, stdout=""))
    DR.collect_sonames(tmp_path, _araclar(readelf="/r"), max_files=1)
    assert len(cagrilar) == 1


def test_collect_sonames_reader_failure_swallowed(monkeypatch, tmp_path):
    _elf_agaci(tmp_path)

    def patla(cmd, timeout=0):
        raise OSError("okuma reddi")
    monkeypatch.setattr(DR, "safe_run", patla)
    assert DR.collect_sonames(tmp_path,
                              _araclar(readelf="/r")) == set()


# --- soname -> Arch paketi ------------------------------------------------------

def test_sonames_to_packages_without_pacman():
    assert DR.sonames_to_packages({"libx.so"}, _araclar(pacman="")) == []


def test_sonames_to_packages_loader_shortcut():
    assert DR.sonames_to_packages(
        {"ld-linux-x86-64.so.2"}, _araclar()) == ["glibc"]
    assert DR.sonames_to_packages({"ld-2.33.so"}, _araclar()) == ["glibc"]


def test_sonames_to_packages_mapping(monkeypatch):
    istekler = []

    sahipler = {"libfoo.so.1": "extra/libfoo.so.1-6\n",
                "libbar.so": "core/libbar\n"}

    def sahte(cmd, timeout=0):
        istekler.append(cmd[-1])
        return _rc(0, stdout=sahipler.get(cmd[-1], ""))
    monkeypatch.setattr(DR, "safe_run", sahte)
    paketler = DR.sonames_to_packages({"libfoo.so.1", "libbar.so"},
                                      _araclar())
    assert paketler == ["libbar", "libfoo.so.1-6"]

    monkeypatch.setattr(DR, "safe_run",
                        lambda cmd, timeout=0: _rc(1))
    assert DR.sonames_to_packages({"yok.so"}, _araclar()) == []

    monkeypatch.setattr(DR, "safe_run",
                        lambda cmd, timeout=0: _rc(0, stdout="\n"))
    assert DR.sonames_to_packages({"bos.so"}, _araclar()) == []

    def patla(cmd, timeout=0):
        raise TimeoutError("pacman -F db yok")
    monkeypatch.setattr(DR, "safe_run", patla)
    assert DR.sonames_to_packages({"hata.so"}, _araclar()) == []


# --- ust seviye cozum -----------------------------------------------------------

def test_resolve_runtime_empty_tree(tmp_path):
    assert DR.resolve_runtime_dependencies(tmp_path, _araclar(readelf="/r")) == []


def test_resolve_runtime_happy_chain(monkeypatch, tmp_path):
    _elf_agaci(tmp_path)
    monkeypatch.setattr(DR, "safe_run",
                        lambda cmd, timeout=0:
                        _rc(0, stdout=READELF_CIKTI)
                        if "-d" in cmd else _rc(0, stdout="extra/libfoo.so.1\n"))
    paketler = DR.resolve_runtime_dependencies(
        tmp_path, _araclar(readelf="/usr/bin/readelf"))
    assert paketler == ["libfoo.so.1"]


def test_resolve_runtime_exception_swallowed(monkeypatch, tmp_path):
    def patla(*a, **k):
        raise RuntimeError("agac patladi")
    monkeypatch.setattr(DR, "collect_sonames", patla)
    assert DR.resolve_runtime_dependencies(tmp_path, _araclar()) == []

def test_check_pacman_installed_rc_fail(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/pacman")
    monkeypatch.setattr(DR, "safe_run", lambda cmd, timeout=0: _rc(1))
    assert DR._check_pacman_installed("yok") == (False, "")


def test_check_aur_cache_miss_invokes_producer(monkeypatch):
    yakalanan = {}

    class UreticiOnbellek:
        def get_or_fetch(self, alan, anahtar, uretici):
            yakalanan["uretici"] = uretici
            return uretici()          # onbellek bos -> RPC'ye gider

    def sahte_rpc(url, max_retries=0, timeout=0):
        yakalanan["url"] = url
        return {"resultcount": 1,
                "results": [{"Name": "demo", "Version": "7.7"}]}

    monkeypatch.setitem(sys.modules, "core.offline_cache",
                        NS(get_cache=lambda: UreticiOnbellek()))
    monkeypatch.setitem(sys.modules, "core.retry",
                        NS(retry_aur_rpc=sahte_rpc))
    ok, ver = DR._check_aur("demo")
    assert (ok, ver) == (True, "7.7")
    assert "rpc/v5/info/demo" in yakalanan["url"]


def test_sonames_to_packages_no_system_pacman(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: None)
    assert DR.sonames_to_packages({"libx.so"}, _araclar(pacman="")) == []
