"""Tur-36 — plugins/__init__, deb eklentisi ve abi_scanner kalanlari."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import core.plugins as PL
import core.plugins.deb_plugin as DP


class OrnekEklenti(PL.ConverterPlugin):
    name = "ornek"
    extensions = (".deb",)
    priority = 5
    category = "converter"
    description = "deneme"
    author = "ben"
    version = "1.0"

    def is_available(self, tools):
        return True

    def convert(self, input_path, output_dir, tools, **kwargs):
        return True, "tamam", None


def test_register_and_list(monkeypatch):
    monkeypatch.setattr(PL, "_REGISTRY", {})
    PL.register_plugin(OrnekEklenti)
    assert "ornek" in PL._REGISTRY                                 # 88-90

    with pytest.raises(TypeError):
        PL.register_plugin(dict)                                   # 85-86

    liste = PL.list_plugins()                                      # 202-217
    assert liste[0]["name"] == "ornek"
    assert PL.list_plugins(category="security") == []              # 205-206


def test_load_plugins_builtin_and_marketplace(monkeypatch, tmp_path):
    # dahili modul yukleme hatalarina dayanikli
    sonuc = PL.load_plugins()                                      # 104-112
    assert isinstance(sonuc, dict)

    # pazaryeri dizini: boş ve dolumu
    sahte_mp = NS(PLUGIN_DIR=tmp_path)
    monkeypatch.setitem(sys.modules, "core.plugins.marketplace", sahte_mp)
    assert PL.load_plugins() is not None                           # 116-117

    (tmp_path / "_gizli.py").write_text("")
    (tmp_path / "pazar.py").write_text(
        "NAME = 'pazar'\n"
        "def register(module_registry):\n"
        "    module_registry['pazar'] = None\n")
    assert PL.load_plugins() is not None                           # 118-132

    # ImportError yolu
    monkeypatch.delitem(sys.modules, "core.plugins.marketplace",
                        raising=False)
    gercek_import = __import__

    def kirik_import(name, *a, **k):
        if name.endswith("plugins.marketplace") and "marketplace" in name:
            raise ImportError("yok")
        return gercek_import(name, *a, **k)
    monkeypatch.setitem(sys.modules, "core.plugins.marketplace", None)
    # marketplace modulu yokken de sessizce devam etmeli
    monkeypatch.setitem(sys.modules, "core.plugins.marketplace", None)
    PL.load_plugins()                                              # 133-134


def test_reload_plugins(monkeypatch):
    monkeypatch.setattr(PL, "_REGISTRY", {"eski": object})
    PL.reload_plugins()                                            # 230-232
    assert "eski" not in PL._REGISTRY


def test_sighup_handler(monkeypatch):
    import signal

    kurulan = {}
    def sahte_signal(sig, fn):
        kurilan_kayit = kurilan.setdefault  # noqa: F841
        kurilan[sig] = fn
    kurilan = kurulan
    monkeypatch.setattr(signal, "signal", sahte_signal)
    PL._setup_sighup_handler()                                     # 252-253
    handler = kurilan.get(signal.SIGHUP)

    # tetikle: basarili yeniden yukleme ve istisna yolu
    monkeypatch.setattr(PL, "reload_plugins", lambda: {"a": 1})
    handler(signal.SIGHUP, None)                                   # 244-247

    def patlak():
        raise RuntimeError("yeniden yukleme yok")
    monkeypatch.setattr(PL, "reload_plugins", patlak)
    handler(signal.SIGHUP, None)                                   # 248-249

    # ana-thread hatasi sessizce yutulur
    def patlak_signal(sig, fn):
        raise ValueError("ana thread degil")
    monkeypatch.setattr(signal, "signal", patlak_signal)
    PL._setup_sighup_handler()                                     # 254-255


# --- deb_plugin ------------------------------------------------------------------

class SahteSignal:
    def __init__(self):
        self.abone = None
        self.ikinci = None

    def connect(self, fn, **k):
        if self.abone is None or self.ikinci is not None:
            self.abone = self.abone or fn
        else:
            pass
        if self.abone is None:
            self.abone = fn
        else:
            self.ikinci = fn

    def disconnect(self, fn):
        raise TypeError("bağlantı yok")

    def emit(self, *a):
        for f in filter(None, (self.abone, self.ikinci)):
            f(*a)


def test_deb_plugin_success_flow(monkeypatch, tmp_path):
    class SahteDonusturucu:
        def __init__(self, tools):
            self.finished = SahteSignal()

        def convert(self, inp, out):
            self.finished.emit(True, "hazir", "/cikti.deb")

    monkeypatch.setitem(sys.modules, "core.subprocess_converters",
                        NS(NativeDebConverterSubprocess=SahteDonusturucu))
    eklenti = DP.DebConverterPlugin()
    ok, msg, _cikti = eklenti.convert(tmp_path / "giris.deb", tmp_path,
                                      NS(makepkg="makepkg",
                                         bsdtar="bsdtar"))
    assert ok is True and msg == "hazir"                           # 45-81


def test_deb_plugin_failure_paths(monkeypatch, tmp_path):
    # convert icinde istisna -> genel yakalama
    class Patlak:
        def __init__(self, tools):
            self.finished = SahteSignal()

        def convert(self, inp, out):
            raise RuntimeError("donusum coktu")

    monkeypatch.setitem(sys.modules, "core.subprocess_converters",
                        NS(NativeDebConverterSubprocess=Patlak))
    eklenti = DP.DebConverterPlugin()
    ok, msg, _cikti = eklenti.convert(tmp_path / "g.deb", tmp_path,
                                      NS(makepkg="m", bsdtar="b"))
    assert ok is False and "Dönüşüm hatası" in msg                 # 85-87

    # import yok
    monkeypatch.setitem(sys.modules, "core.subprocess_converters", None)
    ok, msg, _cikti = DP.DebConverterPlugin().convert(
        tmp_path / "g.deb", tmp_path, NS(makepkg="m", bsdtar="b"))
    assert ok is False and "mevcut değil" in msg                   # 83-84

# --- ek dilim: _register_module, pazaryeri hatasi, rpm eklentisi ------------------

def test_register_module_variants():
    kayit = {}

    class IyiEklenti(PL.ConverterPlugin):
        name = "iyi"
        extensions = (".iyi",)

        def is_available(self, tools):
            return True

        def convert(self, *a, **k):
            return True, "ok", None

    sahte_modul = NS(IyiEklenti=IyiEklenti, yardimci=lambda: 1)
    PL._register_module(sahte_modul, kayit)                        # 162-175
    assert "iyi" in kayit


def test_marketplace_broken_file(monkeypatch, tmp_path):
    (tmp_path / "kirik.py").write_text("raise RuntimeError('bozuk eklenti')\n")
    monkeypatch.setitem(sys.modules, "core.plugins.marketplace",
                        NS(PLUGIN_DIR=tmp_path))
    sonuc = PL.load_plugins()                                      # 131-132
    assert isinstance(sonuc, dict)


def test_rpm_plugin_paths(monkeypatch, tmp_path):
    import core.plugins.rpm_to_deb_plugin as RP

    # alien yok
    monkeypatch.setattr(RP.shutil, "which", lambda n: None)
    ok, msg, _c = RP.RpmToDebConverter().convert(tmp_path / "x.rpm",
                                                 tmp_path, NS())
    assert ok is False and "alien bulunamad" in msg                # 52-54

    monkeypatch.setattr(RP.shutil, "which", lambda n: "/usr/bin/alien")

    # alien hata kodu
    monkeypatch.setattr(RP, "safe_run",
                        lambda cmd, **k: NS(returncode=2, stdout="",
                                            stderr="paket bozuk"))
    cikti = tmp_path / "cikti"
    ok, msg, _c = RP.RpmToDebConverter().convert(tmp_path / "x.rpm",
                                                 cikti, NS())
    assert ok is False and "alien başarısız" in msg                # 64-66

    # deb uretilmedi
    monkeypatch.setattr(RP, "safe_run",
                        lambda cmd, **k: NS(returncode=0, stdout="",
                                            stderr=""))
    ok, msg, _c = RP.RpmToDebConverter().convert(tmp_path / "x.rpm",
                                                 cikti, NS())
    assert ok is False and "oluşturulamadı" in msg                 # 69-71

    # basari: cwd'ye .deb dusen alien
    def ureten(cmd, **k):
        Path(k["cwd"], "x-1.0.deb").write_bytes(b"D")
        return NS(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(RP, "safe_run", ureten)
    ok, msg, yol = RP.RpmToDebConverter().convert(tmp_path / "x.rpm",
                                                  cikti, NS())
    assert ok is True and yol.name == "x-1.0.deb"                  # 73-75