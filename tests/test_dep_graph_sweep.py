"""Coverage itmesi — core/dep_graph.py: grafik cizimi ve kurucular."""
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import core.dep_graph as DG
from core.dep_graph import DepGraph, DepNode


def _rc(code, stdout="", stderr=""):
    return NS(returncode=code, stdout=stdout, stderr=stderr)


def _hangi_secici(harita):
    def sahte(ad):
        return harita.get(ad)
    return sahte


# --- grafik sinifi --------------------------------------------------------------

def test_add_edge_creates_and_dedups():
    g = DepGraph()
    g.add_edge("app", "liba")
    g.add_edge("app", "liba")          # tekrar -> dup yok
    g.add_edge("app", "libb")
    assert g.nodes["app"].deps == ["liba", "libb"]
    assert g.nodes["liba"].needed_by == ["app"]
    assert set(g.nodes) == {"app", "liba", "libb"}


def test_to_mermaid_shapes_and_sanitizing():
    g = DepGraph(root="my.app")
    g.nodes["my.app"] = DepNode(name="my.app", version="1.0",
                                is_installed=True, deps=["lib-x/y"])
    g.nodes["lib-x/y"] = DepNode(name="lib-x/y")
    metin = g.to_mermaid()
    assert 'graph TD' in metin
    assert 'my_app["my.app v1.0"]' in metin          # kurulu -> koseli
    assert 'lib_x_y{{"lib-x/y"}}' in metin            # eksik -> suslu
    assert "my_app --> lib_x_y" in metin


def test_to_ascii_markers_and_cycles():
    g = DepGraph(root="app")
    g.nodes["app"] = DepNode(name="app", deps=["liba", "libb"],
                             is_installed=True)
    g.nodes["liba"] = DepNode(name="liba", version="2", deps=["app"])
    g.nodes["libb"] = DepNode(name="libb")
    metin = g.to_ascii()
    assert "app" in metin and "liba v2" in metin
    assert "(circular ref ↑)" in metin                # dongu isaretli
    assert "MISSING" in metin                          # libb kurulusuz

    bos = DepGraph()
    assert "MISSING" in bos.to_ascii()   # bos graf yer-tutucu

    koksu = DepGraph()
    koksu.add_edge("tek", "cocos")
    assert koksu.to_ascii().startswith("└── tek")


def test_stats_counts():
    g = DepGraph(root="r")
    g.nodes["r"] = DepNode(name="r", is_installed=True,
                           deps=["a", "b"])
    g.nodes["a"] = DepNode(name="a", is_installed=True, deps=["c"])
    g.nodes["b"] = DepNode(name="b", is_foreign=True)
    g.nodes["c"] = DepNode(name="c")
    s = g.stats()
    assert s["total"] == 4 and s["installed"] == 2
    assert s["missing"] == 2 and s["foreign"] == 1
    assert s["max_depth"] == 3                        # r->a->c


def test_max_depth_guards():
    g = DepGraph()
    assert g._max_depth() == 0
    g.root = "yok"
    assert g._max_depth() == 0


# --- yardimcilar ----------------------------------------------------------------

@pytest.mark.parametrize("girdi,beklenen", [
    ("gtk3>=3.24", "gtk3"),
    ("python<3.13", "python"),
    ("ffmpeg=2:7.0", "ffmpeg"),
    ("duz-paket", "duz-paket"),
    (" bos ", "bos"),
])
def test_parse_dep_name(girdi, beklenen):
    assert DG._parse_dep_name(girdi) == beklenen


def test_is_elf_binary_magic_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda n: None)
    elf = tmp_path / "a"; elf.write_bytes(b"\x7fELFgeri")
    duz = tmp_path / "b"; duz.write_bytes(b"merhaba")
    assert DG._is_elf_binary(elf) is True
    assert DG._is_elf_binary(duz) is False
    assert DG._is_elf_binary(tmp_path / "yok") is False


def test_is_elf_binary_via_file_cmd(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which",
                        _hangi_secici({"file": "/usr/bin/file"}))

    def sahte(cmd, timeout=0):
        hedef = Path(cmd[-1]).name
        if hedef.startswith("e"):
            return _rc(0, stdout="ELF 64-bit LSB shared object")
        return _rc(0, stdout="POSIX shell script")
    monkeypatch.setattr(DG, "safe_run", sahte)

    e = tmp_path / "elfbin"; e.write_bytes(b"x")
    d = tmp_path / "diger"; d.write_bytes(b"x")
    assert DG._is_elf_binary(e) is True
    assert DG._is_elf_binary(d) is False

    def patla(cmd, timeout=0):
        raise subprocess.TimeoutExpired(cmd, 5)
    monkeypatch.setattr(DG, "safe_run", patla)
    assert DG._is_elf_binary(e) is False


# --- pacman tabanli graf --------------------------------------------------------

def _pacman_haritasi(cevaplar):
    """cmd['-Qi'/'-Si'][paket] -> (rc, stdout) tablosundan safe_run uretir."""
    def sahte(cmd, timeout=0):
        anahtar = cmd[1]
        paket = cmd[2] if len(cmd) > 2 else ""
        cevap = cevaplar.get((anahtar, paket))
        if cevap is None:
            return _rc(1)
        return _rc(cevap[0], stdout=cevap[1])
    return sahte


def test_build_graph_without_pacman(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: None)
    g = DG.build_dep_graph(Path("/x/demo.pkg.tar.zst"))
    assert any("pacman bulunamadı" in w for w in g.warnings)


def test_build_graph_not_installed_plain(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which",
                        _hangi_secici({"pacman": "/usr/bin/pacman"}))
    monkeypatch.setattr(DG, "safe_run",
                        lambda cmd, timeout=0: _rc(1))
    g = DG.build_dep_graph(tmp_path / "demo-1-1-x.pkg.tar.zst")
    assert g.root == "demo"
    assert any("kurulu değil" in w for w in g.warnings)


def test_build_graph_not_installed_pkginfo_delegate(monkeypatch, tmp_path):
    f = tmp_path / "demo-1-1-x.pkg.tar.zst"
    f.write_bytes(b"sahte-arsiv")
    monkeypatch.setattr("shutil.which",
                        _hangi_secici({"pacman": "/usr/bin/pacman"}))
    monkeypatch.setattr(DG, "safe_run",
                        lambda cmd, timeout=0: _rc(1))
    yakalanan = {}

    def sahte_pkginfo(path, graph):
        yakalanan["path"] = path
        graph.add_edge("demo", "libz")
        return graph
    monkeypatch.setattr(DG, "_build_from_pkginfo", sahte_pkginfo)
    g = DG.build_dep_graph(f)
    assert yakalanan["path"] == f
    assert "libz" in g.nodes


QI_ROOT = ("Name : demo\nVersion : 1.0-1\n"
           "Depends On : gtk3>=3.24 libsndfile\n  libx11 libxcb=None\n"
           "Description : Deneme araci\n")
QI_DEP = "Version : 3.24-5\nDescription : Grafik kutuphanesi\n"


def test_build_graph_full_parse(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which",
                        _hangi_secici({"pacman": "/usr/bin/pacman"}))
    tablo = {
        ("-Qi", "demo"): (0, QI_ROOT),
        ("-Qi", "gtk3"): (0, QI_DEP),
        ("-Qi", "libsndfile"): (1, ""),
        ("-Si", "libsndfile"): (0, "Repo : extra\n"),
        ("-Qi", "libx11"): (1, ""),
        ("-Si", "libx11"): (1, ""),
        ("-Qi", "libxcb"): (0, QI_DEP),
    }
    monkeypatch.setattr(DG, "safe_run", _pacman_haritasi(tablo))
    g = DG.build_dep_graph(
        tmp_path / "demo-1.0-1-x86_64.pkg.tar.zst")

    assert g.root == "demo"
    kok = g.nodes["demo"]
    assert kok.version == "1.0-1" and kok.is_installed
    assert set(kok.deps) == {"gtk3", "libsndfile",
                             "libx11", "libxcb"}
    gtk = g.nodes["gtk3"]
    assert gtk.is_installed
    assert gtk.version == "3.24-5 — Grafik kutuphanesi"
    snd = g.nodes["libsndfile"]
    assert not snd.is_installed and not snd.is_foreign  # repoda, kurulu degil
    x11 = g.nodes["libx11"]
    assert x11.is_foreign                                # hicbir yerde yok
    xcb = g.nodes["libxcb"]
    assert xcb.is_installed                              # devam satiri


def test_build_from_pkginfo_parses_fields(monkeypatch, tmp_path):
    f = tmp_path / "demo-1-1-x.pkg.tar.zst"
    f.write_bytes(b"x")
    pkginfo = ("pkgname = demo\npkgver = 2.5-1\n"
               "depend = gtk3>=3.24\ndepend = libpng\n")
    monkeypatch.setattr(DG, "safe_run",
                        lambda cmd, timeout=0: _rc(0, stdout=pkginfo))
    g = DG._build_from_pkginfo(f, DepGraph())
    assert g.root == "demo"
    assert g.nodes["demo"].version == "2.5-1"
    assert set(g.nodes["demo"].deps) == {"gtk3", "libpng"}


def test_build_from_pkginfo_failures_swallowed(monkeypatch, tmp_path):
    f = tmp_path / "demo.pkg.tar.zst"; f.write_bytes(b"x")

    monkeypatch.setattr(DG, "safe_run",
                        lambda cmd, timeout=0: _rc(1))
    g = DG._build_from_pkginfo(f, DepGraph())
    assert g.nodes == {}

    def patla(cmd, timeout=0):
        raise subprocess.TimeoutExpired(cmd, 30)
    monkeypatch.setattr(DG, "safe_run", patla)
    assert DG._build_from_pkginfo(f, DepGraph()).nodes == {}


# --- dosya/ldd tabanli graf -----------------------------------------------------

LDD_CIKTI = (
    "\tlinux-vdso.so.1 (0x00007ff)\n"
    "\tlibfoo.so.1 => /usr/lib/libfoo.so.1 (0x00007fe)\n"
    "\tlibmiss.so.2 => not found\n"
    "\tld-linux-x86-64.so.2 => /usr/lib/ld.so (0x7fd)\n"
)


def test_file_graph_missing_file(tmp_path):
    g = DG.build_file_dep_graph(tmp_path / "yok-1-1-x.pkg.tar.zst")
    assert any("Dosya bulunamadı" in w for w in g.warnings)


def test_file_graph_extract_failure(monkeypatch, tmp_path):
    f = tmp_path / "demo-1-1-x.pkg.tar.zst"; f.write_bytes(b"x")
    monkeypatch.setattr(DG, "safe_run",
                        lambda cmd, timeout=0: _rc(2, stderr="bozuk"))
    g = DG.build_file_dep_graph(f)
    assert any("çıkarılamadı" in w for w in g.warnings)


def test_file_graph_no_ldd(monkeypatch, tmp_path):
    f = tmp_path / "demo-1-1-x.pkg.tar.zst"; f.write_bytes(b"x")

    def sahte_tar(cmd, timeout=0):
        hedef = Path(cmd[-1])
        (hedef / "app").write_bytes(b"\x7fELFx")
        return _rc(0)
    monkeypatch.setattr(DG, "safe_run", sahte_tar)
    monkeypatch.setattr("shutil.which", lambda n: None)   # file de ldd de yok
    g = DG.build_file_dep_graph(f)
    assert any("ldd bulunamadı" in w for w in g.warnings)


def test_file_graph_full_flow(monkeypatch, tmp_path):
    f = tmp_path / "demo-1-1-x.pkg.tar.zst"; f.write_bytes(b"x")

    def sahte(cmd, timeout=0):
        if cmd[0] == "tar":
            hedef = Path(cmd[-1])
            (hedef / "usr" / "bin").mkdir(parents=True, exist_ok=True)
            (hedef / "usr" / "bin" / "demo").write_bytes(b"\x7fELFbin")
            (hedef / "usr" / "share" / "doc").mkdir(parents=True,
                                                    exist_ok=True)
            (hedef / "usr" / "share" / "doc" / "README.md").write_text("ok")
            (hedef / "usr" / "bin" / ".gizli").write_bytes(b"\x7fELFx")
            return _rc(0)
        if str(cmd[0]).endswith("ldd"):
            return _rc(0, stdout=LDD_CIKTI)
        return _rc(0, stdout="")
    monkeypatch.setattr(DG, "safe_run", sahte)
    monkeypatch.setattr("shutil.which",
                        _hangi_secici({"ldd": "/usr/bin/ldd"}))  # file yok

    g = DG.build_file_dep_graph(f)
    assert g.root == "demo"
    assert g.warnings == []                               # ELF bulundu
    kenar = g.nodes["usr/bin/demo"].deps
    assert "libfoo.so.1" in kenar and "libmiss.so.2" in kenar
    assert "linux-vdso.so.1" not in kenar
    assert g.nodes["libfoo.so.1"].is_installed is True
    assert g.nodes["libmiss.so.2"].is_installed is False


def test_file_graph_ldd_crash_continues(monkeypatch, tmp_path):
    f = tmp_path / "demo-1-1-x.pkg.tar.zst"; f.write_bytes(b"x")
    sayac = {"n": 0}

    def sahte(cmd, timeout=0):
        if cmd[0] == "tar":
            hedef = Path(cmd[-1])
            (hedef / "a").write_bytes(b"\x7fELFa")
            (hedef / "b").write_bytes(b"\x7fELFb")
            return _rc(0)
        if str(cmd[0]).endswith("ldd"):
            sayac["n"] += 1
            if sayac["n"] == 1:
                raise subprocess.TimeoutExpired(cmd, 5)
            return _rc(1, stdout="\tlibz.so => /lib/z.so (0x1)\n")
        return _rc(0, stdout="")
    monkeypatch.setattr(DG, "safe_run", sahte)
    monkeypatch.setattr("shutil.which",
                        _hangi_secici({"ldd": "/usr/bin/ldd"}))
    g = DG.build_file_dep_graph(f)
    assert "libz.so" in g.nodes                            # ikinci ikili kurtardi


def test_file_graph_no_elf_warning(monkeypatch, tmp_path):
    f = tmp_path / "demo-1-1-x.pkg.tar.zst"; f.write_bytes(b"x")

    def sahte(cmd, timeout=0):
        if cmd[0] == "tar":
            hedef = Path(cmd[-1])
            (hedef / "belge.txt").write_text("metin")
            return _rc(0)
        return _rc(0, stdout="")
    monkeypatch.setattr(DG, "safe_run", sahte)
    monkeypatch.setattr("shutil.which",
                        _hangi_secici({"ldd": "/usr/bin/ldd"}))
    g = DG.build_file_dep_graph(f)
    assert any("ELF dosyası bulunamadı" in w for w in g.warnings)

def test_max_depth_unknown_dep_name_stops():
    g = DepGraph(root="r")
    g.nodes["r"] = DepNode(name="r", is_installed=True,
                           deps=["hayalet"])     # dugum yok
    assert g._max_depth() == 1


def test_build_graph_depends_none_branch(monkeypatch, tmp_path):
    qi = "Name : tek\nVersion : 1\nDepends On : None\n"
    monkeypatch.setattr("shutil.which",
                        _hangi_secici({"pacman": "/usr/bin/pacman"}))
    monkeypatch.setattr(DG, "safe_run",
                        _pacman_haritasi({("-Qi", "tek"): (0, qi)}))
    g = DG.build_dep_graph(tmp_path / "tek-1-1-x.pkg.tar.zst")
    assert g.nodes["tek"].deps == []


def test_file_graph_raw_tar_branch(monkeypatch, tmp_path):
    f = tmp_path / "demo_1.0_amd64.deb"      # .pkg.tar disi -> ayni tar yolu
    f.write_bytes(b"x")

    def sahte(cmd, timeout=0):
        if str(cmd[0]).endswith("tar"):
            hedef = Path(cmd[-1])
            (hedef / "app").write_bytes(b"\x7fELFa")
            (hedef / "alt_dizil").write_bytes(b"\x7fELFb")   # alt cizgi atlanir
            (hedef / "veri").write_bytes(b"elf-degil")        # sihir yok -> 365
            return _rc(0)
        if str(cmd[0]).endswith("ldd"):
            return _rc(0,
                       stdout="\tlibq.so => /lib/q.so (0x2)\n"
                              "\ttuhaf.so => /a => /b (0x3)\n")
        return _rc(0, stdout="")
    monkeypatch.setattr(DG, "safe_run", sahte)
    monkeypatch.setattr("shutil.which",
                        _hangi_secici({"ldd": "/usr/bin/ldd"}))
    g = DG.build_file_dep_graph(f)
    assert "app" in g.nodes and "libq.so" in g.nodes
    assert "tuhaf.so" not in g.nodes            # iki ok -> satir atlandi