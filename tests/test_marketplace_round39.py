"""Tur-39 — marketplace.py ana govdesi."""
from __future__ import annotations

import hashlib
import urllib.error
from pathlib import Path

import pytest

import core.plugins.marketplace as MP


@pytest.fixture()
def pazar(monkeypatch, tmp_path):
    monkeypatch.setattr(MP, "PLUGIN_DIR", tmp_path / "eklentiler")
    return tmp_path / "eklentiler"


# --- yardimcilar -----------------------------------------------------------------

def test_name_and_https_helpers():
    assert MP.is_valid_plugin_name("demo-1_x") is True
    assert MP.is_valid_plugin_name("") is False
    with pytest.raises(ValueError, match="Geçersiz plugin"):
        MP._validate_plugin_name("Kötü Ad")                        # 47-51
    MP._validate_plugin_name("iyi-ad")

    with pytest.raises(ValueError, match="HTTPS"):
        MP._require_https("http://sunucu/e.py")                    # 57-58
    MP._require_https("https://sunucu/e.py")


def test_user_agent_sha_download_fetch(monkeypatch, tmp_path):
    ua = MP._get_user_agent()                                      # 61-64
    assert "plugin-marketplace" in ua

    dosya = tmp_path / "veri.bin"
    dosya.write_bytes(b"icerik")
    ozet = hashlib.sha256(b"icerik").hexdigest()
    assert MP._sha256_file(dosya) == ozet                          # 67-73

    # _download_file: https zorunlu + icerik yazimi
    hedef = tmp_path / "indirilen.py"
    with pytest.raises(ValueError):
        MP._download_file("http://s/x.py", hedef)                  # 78

    class SahteYanit:
        def __init__(self, *a, **k):
            self._okundu = False

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n=-1):
            if not self._okundu:
                self._okundu = True
                return b"PLUGIN_KODU"
            return b""
    monkeypatch.setattr(MP.urllib.request, "urlopen",
                        lambda req, timeout=30: SahteYanit())
    MP._download_file("https://s/x.py", hedef)                     # 80-81
    assert hedef.read_bytes() == b"PLUGIN_KODU"

    # _fetch_json
    monkeypatch.setattr(MP.urllib.request, "urlopen",
                        lambda req, timeout=10: SahteYanit())
    monkeypatch.setattr(MP.json, "loads",
                        lambda s: {"tag_name": "v9"})
    assert MP._fetch_json("https://s/index.json")["tag_name"] == "v9"


# --- fetch_available_plugins -----------------------------------------------------

def test_fetch_offline_and_error(pazar, monkeypatch):
    assert MP.fetch_available_plugins(offline=True) == []          # 101-103

    def patlak(req, timeout=10):
        raise urllib.error.URLError("ag yok")
    monkeypatch.setattr(MP.urllib.request, "urlopen", patlak)
    assert MP.fetch_available_plugins() == []                      # 106-108


def test_fetch_parse_assets(pazar, monkeypatch):
    veri = {"tag_name": "v2.0",
            "assets": [{"name": "a.py",
                        "browser_download_url": "https://s/a.py"},
                       {"name": "okubeni.txt",
                        "browser_download_url": "https://s/x"}]}
    monkeypatch.setattr(MP, "_fetch_json", lambda url, timeout=10: veri)
    liste = MP.fetch_available_plugins()                           # 111-124
    assert len(liste) == 1 and liste[0]["name"] == "a"
    assert liste[0]["sha256_url"] == "https://s/a.py.sha256"


# --- install_plugin --------------------------------------------------------------

def test_install_already_installed(pazar):
    pazar.mkdir(parents=True)
    (pazar / "mevcut.py").write_text("x")
    yol = MP.install_plugin("mevcut")                              # 158-160
    assert yol.exists()


def test_install_not_found(pazar, monkeypatch):
    monkeypatch.setattr(MP, "fetch_available_plugins", list)
    with pytest.raises(FileNotFoundError, match="bulunamadı|not found"):
        MP.install_plugin("yok-eki")                               # 170-174


def test_install_success_with_checksum(pazar, monkeypatch):
    kod = "PLUGIN = 1"
    indirilenler = []

    def sahte_indir(url, dest, timeout=30):
        indirilenler.append(url)
        Path(dest).write_text(kod if not str(dest).endswith(".sha256")
                              else hashlib.sha256(kod.encode()).hexdigest())

    monkeypatch.setattr(MP, "_download_file", sahte_indir)
    monkeypatch.setattr(
        MP, "fetch_available_plugins",
        lambda: [{"name": "iyi", "version": "v1",
                  "download_url": "https://s/iyi.py",
                  "sha256_url": "https://s/iyi.py.sha256"}])
    yol = MP.install_plugin("iyi")                                 # 179-208
    assert yol.read_text() == kod and len(indirilenler) == 2


def test_install_checksum_fail_closed(pazar, monkeypatch):
    def sahte_indir(url, dest, timeout=30):
        Path(dest).write_text("kod")
    monkeypatch.setattr(MP, "_download_file", sahte_indir)

    # checksum dosyasi inerken patlama -> fail-closed RuntimeError
    def yarili(url, dest, timeout=30):
        if str(dest).endswith(".sha256"):
            raise OSError("checksum alinamadi")
        Path(dest).write_text("kod")
    monkeypatch.setattr(MP, "_download_file", yarili)
    monkeypatch.setattr(
        MP, "fetch_available_plugins",
        lambda: [{"name": "kotu", "version": "v1",
                  "download_url": "https://s/kotu.py",
                  "sha256_url": "https://s/kotu.py.sha256"}])
    with pytest.raises(RuntimeError, match="Checksum dosyası alınamadı"):
        MP.install_plugin("kotu")                                  # 191-195

    # checksum uyusmazligi
    monkeypatch.setattr(MP, "_download_file", sahte_indir)
    monkeypatch.setattr(MP, "_sha256_file", lambda p: "farkliozet")
    with pytest.raises(RuntimeError, match="Checksum mismatch"):
        MP.install_plugin("kotu", force=True)                      # 197-201


def test_install_force_overwrites(pazar, monkeypatch):
    pazar.mkdir(parents=True)
    (pazar / "eski.py").write_text("ESKI")
    monkeypatch.setattr(MP, "_download_file",
                        lambda url, dest, timeout=30: Path(dest).write_text("YENI"))
    monkeypatch.setattr(
        MP, "fetch_available_plugins",
        lambda: [{"name": "eski", "version": "v2",
                  "download_url": "https://s/eski.py",
                  "sha256_url": "https://s/eski.py.sha256"}])
    yol = MP.install_plugin("eski", force=True, verify_checksum=False)
    assert yol.read_text() == "YENI"                               # force dali


# --- uninstall / list / update ---------------------------------------------------

def test_uninstall_list_update(pazar, monkeypatch):
    pazar.mkdir(parents=True)
    (pazar / "b.py").write_text("bb")
    (pazar / "_gizli.py").write_text("g")
    (pazar / "a.py").write_text("aaa")

    liste = MP.list_installed_plugins()                            # 241-250
    assert [p["name"] for p in liste] == ["a", "b"]

    assert MP.uninstall_plugin("a") is True                        # 225-228
    assert MP.uninstall_plugin("a") is False                       # 229

    # kurulu degil -> update False
    ok, msg, yol = MP.update_plugin("yok")                         # 264-265
    assert ok is False and "kurulu değil" in msg

    # guncelleme basarisi
    monkeypatch.setattr(MP, "install_plugin",
                        lambda n, force=False: pazar / f"{n}.py")
    ok, msg, yol = MP.update_plugin("b")                           # 268-269
    assert ok is True and yol.name == "b.py"

    # FileNotFoundError ve RuntimeError yollari
    def bulunamadi(n, **k):
        raise FileNotFoundError("pazarda yok")
    def patlak(n, **k):
        raise RuntimeError("indirme coktu")
    monkeypatch.setattr(MP, "install_plugin", bulunamadi)
    ok, msg, _y = MP.update_plugin("b")                            # 270-271
    assert ok is False and "pazarda yok" in msg
    monkeypatch.setattr(MP, "install_plugin", patlak)
    ok, msg, _y = MP.update_plugin("b")                            # 272-273
    assert ok is False and "Güncelleme başarısız" in msg


def test_list_missing_dir(pazar):
    assert MP.list_installed_plugins() == []                       # 238-239