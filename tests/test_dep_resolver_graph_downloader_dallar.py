"""pkgforge dal-kesen testleri (LEED) — dep_resolver + dep_graph + downloader.

Kapsanan fonksiyonlar:
  - core.dep_resolver._check_pacman, _check_pacman_installed (subprocess stub)
  - core.dep_graph._extract_for_graph (subprocess stub)
  - core.downloader._download_filename (saf string)

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory — pacman/tar CAGRILMADI; shutil.which + safe_run
         MONKEYPATCH ile sahte CompletedProcess donduruldu (gercek komut YOK).
"""
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

import pytest

sys.path.insert(0, ".")
import core.dep_graph
import core.dep_resolver
from core.dep_graph import _extract_for_graph
from core.dep_resolver import _check_pacman, _check_pacman_installed
from core.downloader import _download_filename


def _cp(stdout: str = "", stderr: str = "", rc: int = 0) -> subprocess.CompletedProcess:
    """Sahte CompletedProcess (gercek komut calismadi)."""
    return subprocess.CompletedProcess(args=["fake"], returncode=rc,
                                       stdout=stdout, stderr=stderr)


class _Recorder:
    """safe_run cagrilarini kaydeder; siradaki CompletedProcess'i dondurur."""

    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def __call__(self, cmd, *, cwd=None, timeout=120, env=None, input=None, text=None):
        self.calls.append({"cmd": list(cmd), "timeout": timeout, "cwd": cwd})
        if self.results:
            return self.results.pop(0)
        return _cp()


@pytest.fixture()
def fake_pacman(monkeypatch):
    """shutil.which 'pacman' icin sahte yol dondurur (varsayilan)."""
    def _set(path="/usr/bin/pacman"):
        monkeypatch.setattr(shutil, "which", lambda n: path if n == "pacman" else None)
        return path
    return _set


# == _check_pacman =================================================================================

def test_pacman_yoksa_hazir_deger(monkeypatch):
    """ORTAM: pacman kurul degil (which None) -> (False, '') ve komut CALISMADI."""
    monkeypatch.setattr(shutil, "which", lambda n: None)
    rec = _Recorder([_cp()])
    monkeypatch.setattr(core.dep_resolver, "safe_run", rec)
    assert _check_pacman("foo") == (False, "")
    assert rec.calls == []  # which None -> safe_run cagrilmadi bile


def test_pacman_bulundu_versiyon_ile(monkeypatch, fake_pacman):
    """ORTAM: rc 0 + 'Version : 1.2.3' -> (True, '1.2.3')."""
    fake_pacman()
    rec = _Recorder([_cp(stdout="Name      : foo\nVersion : 1.2.3\n")])
    monkeypatch.setattr(core.dep_resolver, "safe_run", rec)
    assert _check_pacman("foo") == (True, "1.2.3")


@pytest.mark.parametrize("line,expected", [
    ("Version : 1.2.3\n", "1.2.3"),
    ("Version :   1.2.3   \n", "1.2.3"),
    ("Version : 1:2.0-1\n", "1:2.0-1"),
    ("Version : 2.0-1\nDescription : x\n", "2.0-1"),
])
def test_pacman_versiyon_ayristirma(monkeypatch, fake_pacman, line, expected):
    """ORTAM: 'Version :' satirindan sonra strip; epoch ':' korunur."""
    fake_pacman()
    monkeypatch.setattr(core.dep_resolver, "safe_run",
                        lambda *a, **k: _cp(stdout=line))
    assert _check_pacman("foo") == (True, expected)


def test_pacman_versiyon_satiri_yoksa_unknown(monkeypatch, fake_pacman):
    """ORTAM: rc 0 ama 'Version' satiri yok -> (True, 'unknown')."""
    fake_pacman()
    monkeypatch.setattr(core.dep_resolver, "safe_run",
                        lambda *a, **k: _cp(stdout="Name : foo\n"))
    assert _check_pacman("foo") == (True, "unknown")


def test_pacman_rc_sifir_degil(monkeypatch, fake_pacman):
    """ORTAM: rc != 0 -> (False, '') (paket repoda yok)."""
    fake_pacman()
    monkeypatch.setattr(core.dep_resolver, "safe_run",
                        lambda *a, **k: _cp(rc=1, stderr="error: not found"))
    assert _check_pacman("nope") == (False, "")


def test_pacman_komut_argumanlari(monkeypatch, fake_pacman):
    """ORTAM: komut 'pacman -Si <name>' seklinde gider."""
    path = fake_pacman("/usr/bin/pacman")
    rec = _Recorder([_cp(stdout="Version : 1.0\n")])
    monkeypatch.setattr(core.dep_resolver, "safe_run", rec)
    _check_pacman("mypkg")
    assert rec.calls == [{"cmd": [path, "-Si", "mypkg"], "timeout": 10, "cwd": None}]


def test_pacman_timeout_10(monkeypatch, fake_pacman):
    """ORTAM: safe_run timeout=10 ile cagrılır."""
    fake_pacman()
    rec = _Recorder([_cp()])
    monkeypatch.setattr(core.dep_resolver, "safe_run", rec)
    _check_pacman("x")
    assert rec.calls[0]["timeout"] == 10


@pytest.mark.parametrize("name", ["gcc", "linux", "python-3", "lib32-glibc", "a"])
def test_pacman_isimleri_iletir(monkeypatch, fake_pacman, name):
    """ORTAM: her isim komuta aynen gecer."""
    fake_pacman()
    rec = _Recorder([_cp(stdout="Version : 1\n")])
    monkeypatch.setattr(core.dep_resolver, "safe_run", rec)
    _check_pacman(name)
    assert rec.calls[0]["cmd"][2] == name


# == _check_pacman_installed =======================================================================

def test_pacman_installed_yoksa(monkeypatch):
    """ORTAM: pacman yok -> (False, '')."""
    monkeypatch.setattr(shutil, "which", lambda n: None)
    monkeypatch.setattr(core.dep_resolver, "safe_run",
                        lambda *a, **k: _cp(stdout="Version : 1\n"))
    assert _check_pacman_installed("foo") == (False, "")


def test_pacman_installed_versiyon_ile(monkeypatch, fake_pacman):
    """ORTAM: rc 0 + Version -> (True, versiyon)."""
    fake_pacman()
    monkeypatch.setattr(core.dep_resolver, "safe_run",
                        lambda *a, **k: _cp(stdout="Version : 5.6.7\n"))
    assert _check_pacman_installed("foo") == (True, "5.6.7")


def test_pacman_installed_unknown(monkeypatch, fake_pacman):
    """ORTAM: rc 0 + Version satiri yok -> (True, 'unknown')."""
    fake_pacman()
    monkeypatch.setattr(core.dep_resolver, "safe_run",
                        lambda *a, **k: _cp(stdout="Name : foo\n"))
    assert _check_pacman_installed("foo") == (True, "unknown")


def test_pacman_installed_degil(monkeypatch, fake_pacman):
    """ORTAM: rc != 0 -> (False, '') (kurulu degil)."""
    fake_pacman()
    monkeypatch.setattr(core.dep_resolver, "safe_run",
                        lambda *a, **k: _cp(rc=1, stderr="not installed"))
    assert _check_pacman_installed("nope") == (False, "")


def test_pacman_installed_komut_Qi(monkeypatch, fake_pacman):
    """ORTAM: komut 'pacman -Qi <name>' (repo -Si DEGIL)."""
    path = fake_pacman()
    rec = _Recorder([_cp(stdout="Version : 1\n")])
    monkeypatch.setattr(core.dep_resolver, "safe_run", rec)
    _check_pacman_installed("mypkg")
    assert rec.calls[0]["cmd"] == [path, "-Qi", "mypkg"]


# == _extract_for_graph ============================================================================

def test_extract_basarili(monkeypatch, tmp_path):
    """ORTAM: tar rc 0 -> True."""
    rec = _Recorder([_cp(rc=0)])
    monkeypatch.setattr(core.dep_graph, "safe_run", rec)
    assert _extract_for_graph(tmp_path / "p.pkg.tar.zst", tmp_path) is True


def test_extract_basarisiz(monkeypatch, tmp_path):
    """ORTAM: tar rc != 0 -> False (format desteklenmiyor)."""
    rec = _Recorder([_cp(rc=2, stderr="tar: hata")])
    monkeypatch.setattr(core.dep_graph, "safe_run", rec)
    assert _extract_for_graph(tmp_path / "p.pkg.tar.zst", tmp_path) is False


def test_extract_komut_ve_zaman_asimi(monkeypatch, tmp_path):
    """ORTAM: 'tar xf <pkg> -C <tmp>' komutu, timeout=30."""
    pkg = tmp_path / "p.pkg.tar.zst"
    out = tmp_path / "out"
    out.mkdir()
    rec = _Recorder([_cp(rc=0)])
    monkeypatch.setattr(core.dep_graph, "safe_run", rec)
    _extract_for_graph(pkg, out)
    assert rec.calls == [{"cmd": ["tar", "xf", str(pkg), "-C", str(out)],
                          "timeout": 30, "cwd": None}]


@pytest.mark.parametrize("rc", [0, 1, 2, 127])
def test_extract_returncode_esleri(monkeypatch, tmp_path, rc):
    """ORTAM: returncode 0 -> True, digerleri -> False."""
    monkeypatch.setattr(core.dep_graph, "safe_run", lambda *a, **k: _cp(rc=rc))
    assert _extract_for_graph(tmp_path / "x", tmp_path) is (rc == 0)


# == _download_filename ============================================================================

@pytest.mark.parametrize("url,path,expected", [
    ("https://e.com/p/foo.deb", "/p/foo.deb", "foo.deb"),
    ("https://e.com/a/b/c.rpm", "/a/b/c.rpm", "c.rpm"),
    ("http://h/dl/package-1.0.pkg.tar.zst", "/dl/package-1.0.pkg.tar.zst",
     "package-1.0.pkg.tar.zst"),
    ("https://e.com/f.pkg.tar.zst?sig=x", "/f.pkg.tar.zst", "f.pkg.tar.zst"),
    ("https://e.com/dir/", "/dir/", "downloaded_package.rpm"),
    ("https://e.com/", "/", "downloaded_package.rpm"),
    ("https://e.com/deb/", "/deb/", "downloaded_package.deb"),
    ("https://e.com/DEB/PKG", "/DEB/PKG", "downloaded_package.deb"),
    ("https://e.com/rpm/pkg", "/rpm/pkg", "downloaded_package.rpm"),
    ("https://e.com/x", "/x", "downloaded_package.rpm"),
    ("https://e.com/debian/pkg.deb", "/debian/pkg.deb", "pkg.deb"),
])
def test_download_filename(url, path, expected):
    """ORTAM: path basename; bos/yazisizsa url'de 'deb' varsa .deb yoksa .rpm."""
    parsed = urllib.parse.urlparse(url)
    assert parsed.path == path
    assert _download_filename(url, parsed) == expected


def test_download_filename_query_yol_degil(monkeypatch):
    """ORTAM: sadece parsed.path kullanilir; query ?sonra yok sayilir."""
    parsed = urllib.parse.urlparse("https://e.com/a.deb?download=1&x=2")
    assert _download_filename("https://e.com/a.deb?download=1&x=2", parsed) == "a.deb"


def test_download_filename_varsayilan_deb_uzantisiyla():
    """ORTAM: varsayilan .deb dosya adi '.' icerir (uzanti vardir)."""
    parsed = urllib.parse.urlparse("https://e.com/deb/")
    name = _download_filename("https://e.com/deb/", parsed)
    assert name == "downloaded_package.deb"
    assert "." in name


def test_download_filename_varsayilan_rpm_uzantisiyla():
    """ORTAM: varsayilan .rpm dosya adi '.' icerir."""
    parsed = urllib.parse.urlparse("https://e.com/x")
    name = _download_filename("https://e.com/x", parsed)
    assert name == "downloaded_package.rpm"
    assert "." in name


@pytest.mark.parametrize("url", [
    "https://e.com/deb", "https://e.com/DEB", "https://e.com/?deb=1",
    "https://debian.org/x", "https://e.com/debian",
])
def test_download_filename_deb_kelimesi(url):
    """ORTAM: url'de 'deb' (buyuk/kucuk) geciyorsa .deb varsayilani."""
    parsed = urllib.parse.urlparse(url)
    name = _download_filename(url, parsed)
    if not Path(parsed.path).name or "." not in Path(parsed.path).name:
        assert name == "downloaded_package.deb"
