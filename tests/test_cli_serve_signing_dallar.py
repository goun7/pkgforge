"""pkgforge cli._cmd_serve_api + _cmd_signing_setup dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory — uvicorn runner MONKEYPATCH (gercek sunucu YOK),
         signing-wizard ortam statusu MONKEYPATCH (gercek gpg/cosign YOK),
         OpenAPI export ciktisi tmp_path'e yazilir (network YOK).
"""
import argparse
import json
import re
import sys

import pytest

sys.path.insert(0, ".")
import core.api_v2
import core.signing_wizard as sw
from cli import _cmd_serve_api, _cmd_signing_setup

# == yardimcilar ===================================================================================

def _ns(**kw) -> argparse.Namespace:
    """args.Namespace — _cmd_* fonksiyonlari getattr ile okur, eksik attr default."""
    return argparse.Namespace(**kw)


@pytest.fixture()
def serve_calls(monkeypatch):
    """core.api_v2.run MONKEYPATCH — gercek uvicorn sunucu KALKMADI."""
    calls: list[dict] = []

    def _fake_run(host="127.0.0.1", port=8899):
        calls.append({"host": host, "port": port})

    monkeypatch.setattr(core.api_v2, "run", _fake_run)
    return calls


@pytest.fixture()
def env(monkeypatch):
    """core.signing_wizard._env_status MONKEYPATCH — gpg/cosign durumu enjekte."""
    holder: dict[str, dict] = {}

    def _fake_status():
        return holder.get("payload", {
            "gpg": {"available": True, "path": "/usr/bin/gpg"},
            "sigstore": {"cosign_available": False, "cosign_version": ""},
        })

    monkeypatch.setattr(sw, "_env_status", _fake_status)
    holder["payload"] = None  # None -> default (gpg var) kullanilmaz; setter bekler
    return holder


@pytest.fixture()
def env_status(env, monkeypatch):
    """env payload'ini parametre olarak enjekte et."""
    def _set(payload):
        monkeypatch.setattr(sw, "_env_status", lambda: payload)
        return payload
    return _set


# == _cmd_serve_api: sunucu-baslatma dallari ========================================================

def test_serve_varsayilan_host_ve_port(serve_calls, capsys):
    """ORTAM: args bos -> host 127.0.0.1, port 8899."""
    rc = _cmd_serve_api(_ns())
    assert rc == 0
    assert serve_calls == [{"host": "127.0.0.1", "port": 8899}]


def test_serve_banner_uruleri_varsayilan(serve_calls, capsys):
    """ORTAM: banner 3 URL de 127.0.0.1:8899 icerir."""
    _cmd_serve_api(_ns())
    out = capsys.readouterr().out
    assert "🚀 PkgForge API v2: http://127.0.0.1:8899" in out
    assert "• Docs:   http://127.0.0.1:8899/docs" in out
    assert "• Schema: http://127.0.0.1:8899/api/v2/openapi.json" in out


@pytest.mark.parametrize("host,port", [
    ("localhost", 7000),
    ("127.0.0.1", 8899),
    ("::1", 9000),
])
def test_serve_ozel_host_port(serve_calls, capsys, host, port):
    """ORTAM: host/port args'ten gelir, banner'a ve run()'a aynen gecer.

    Routable adresler (0.0.0.0, 192.168.x) burada listelenMEZ: api_v2 kimlik
    dogrulamasi olmadigi icin artik reddediliyor — davranis kilitleri
    tests/test_api_v2_bind_guard.py icinde.
    """
    rc = _cmd_serve_api(_ns(host=host, port=port))
    assert rc == 0
    assert serve_calls == [{"host": host, "port": port}]
    out = capsys.readouterr().out
    assert f"http://{host}:{port}" in out
    assert f"http://{host}:{port}/docs" in out
    assert f"http://{host}:{port}/api/v2/openapi.json" in out


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.10"])
def test_serve_routable_host_redededilir(serve_calls, capsys, host):
    """GUVENLIK SOZLESMESI: routable bind rc=1, run() cagrilmaz, banner yok."""
    rc = _cmd_serve_api(_ns(host=host, port=9100))
    assert rc == 1
    assert serve_calls == []
    assert "🚀" not in capsys.readouterr().out


@pytest.mark.parametrize("attr", ["host", "port"])
def test_serve_none_attr_defaulta_doner(serve_calls, attr):
    """ORTAM: host=None veya port=None -> default (None or kisa-devre)."""
    rc = _cmd_serve_api(_ns(**{attr: None}))
    assert rc == 0
    assert serve_calls == [{"host": "127.0.0.1", "port": 8899}]


@pytest.mark.parametrize("port_str,expected", [
    ("9100", 9100),
    ("0", 0),
    ("65535", 65535),
    ("  8080  ", 8080),
])
def test_serve_port_string_inte_doner(serve_calls, port_str, expected):
    """ORTAM: port string -> int(...) coercion."""
    rc = _cmd_serve_api(_ns(port=port_str))
    assert rc == 0
    assert serve_calls[0]["port"] == expected


@pytest.mark.parametrize("bad_port", ["abc", "88.99", "0x100", "12abc", "1e3", "  "])
def test_serve_port_gecersiz_string_valueerror(serve_calls, bad_port):
    """ORTAM: int() ceviremeyen port -> ValueError (uretim davranisi)."""
    with pytest.raises(ValueError):
        _cmd_serve_api(_ns(port=bad_port))
    assert serve_calls == []


def test_serve_port_bos_string_defaulta_doner(serve_calls):
    """ORTAM-OGRENDI: port='' falsy -> 'or 8899' kisa-devre -> 8899 (ValueError DEGIL)."""
    rc = _cmd_serve_api(_ns(port=""))
    assert rc == 0
    assert serve_calls[0]["port"] == 8899


def test_serve_run_argumanlari_anahtarlarla(serve_calls):
    """ORTAM: run() host= ve port= anahtar argumanlariyla cagrilir.

    Loopback adresi kullanilir: amac arguman ismi tasimasi, bind politikasi degil.
    """
    _cmd_serve_api(_ns(host="127.0.0.1", port=1234))
    assert serve_calls[0] == {"host": "127.0.0.1", "port": 1234}


def test_serve_export_openapi_yoksa_run_cagrilir(serve_calls):
    """ORTAM: export_openapi attr yok -> serve yolu."""
    _cmd_serve_api(_ns())
    assert len(serve_calls) == 1


# == _cmd_serve_api: --export-openapi dallari ======================================================

def test_export_openapi_dosyaya_yazar(tmp_path, serve_calls, capsys):
    """ORTAM: export_openapi=hedef -> spec JSON yazilir, rc 0, run CAGRILMAZ."""
    out_file = tmp_path / "openapi.json"
    rc = _cmd_serve_api(_ns(export_openapi=str(out_file)))
    assert rc == 0
    assert serve_calls == []  # sunucu baslamadi
    assert out_file.exists()
    spec = json.loads(out_file.read_text(encoding="utf-8"))
    assert "openapi" in spec
    assert "info" in spec
    assert "paths" in spec
    assert isinstance(spec["paths"], dict)
    assert f"📦 OpenAPI → {out_file}" in capsys.readouterr().out


def test_export_openapi_parent_dizin_olusturmaz(tmp_path, serve_calls):
    """ORTAM-OGRENDI: export_openapi plain open() kullanir — parent dizini
    OLUSTURMAZ; yoksa FileNotFoundError (mkdir YOK, signing save'ten farkli)."""
    target = tmp_path / "a" / "b" / "openapi.json"
    with pytest.raises(FileNotFoundError):
        _cmd_serve_api(_ns(export_openapi=str(target)))
    assert not target.exists()
    assert not (tmp_path / "a").exists()
    assert serve_calls == []


def test_export_openapi_gecerli_yolu_dondurur(tmp_path, capsys):
    """ORTAM: yazilan mesaj tam dosya yolunu icerir."""
    target = tmp_path / "spec.json"
    _cmd_serve_api(_ns(export_openapi=str(target)))
    out = capsys.readouterr().out
    assert str(target) in out
    assert "openapi.json" not in out  # bizim dosya adimiz spec.json


@pytest.mark.parametrize("falsy", [None, "", False])
def test_export_openapi_falsy_ise_serve_yolu(serve_calls, falsy):
    """ORTAM: export_openapi falsy (None/''/False) -> sunucu yolu."""
    rc = _cmd_serve_api(_ns(export_openapi=falsy))
    assert rc == 0
    assert len(serve_calls) == 1


# == _cmd_serve_api: ImportError dalı ==============================================================

def test_import_error_rc2_ve_stderr(monkeypatch, capsys, serve_calls):
    """ORTAM: core.api_v2 import edilemezse rc 2 + stderr'de kurulum mesaji."""
    monkeypatch.setitem(sys.modules, "core.api_v2", None)
    rc = _cmd_serve_api(_ns())
    assert rc == 2
    err = capsys.readouterr().err
    assert "REST API bagimlilklari kurulu degil" in err
    assert "pip install 'pkgforge[api]'" in err
    assert serve_calls == []


def test_import_error_stdout_bos(monkeypatch, capsys):
    """ORTAM: import hatasinda banner stdout'a YAZILMAZ."""
    monkeypatch.setitem(sys.modules, "core.api_v2", None)
    _cmd_serve_api(_ns())
    assert capsys.readouterr().out == ""


def test_import_error_export_yolu_da_engellenir(monkeypatch, tmp_path, serve_calls):
    """ORTAM: import hatasi export dalindan once gelir -> rc 2, dosya YAZILMAZ."""
    monkeypatch.setitem(sys.modules, "core.api_v2", None)
    target = tmp_path / "x.json"
    rc = _cmd_serve_api(_ns(export_openapi=str(target)))
    assert rc == 2
    assert not target.exists()
    assert serve_calls == []


# == _cmd_signing_setup: yontem-secim dallari =======================================================

def test_signing_setup_varsayilan_rc0(capsys):
    """ORTAM: args bos -> rc 0."""
    rc = _cmd_signing_setup(_ns())
    assert rc == 0


def test_signing_setup_method_none_autoa_doner(env_status, capsys):
    """ORTAM: method=None -> 'auto' (None or kisa-devre)."""
    env_status({"gpg": {"available": True, "path": "/usr/bin/gpg"},
                "sigstore": {"cosign_available": False, "cosign_version": ""}})
    _cmd_signing_setup(_ns(method=None))
    out = capsys.readouterr().out
    assert "📋  Yöntem: pgp" in out


@pytest.mark.parametrize("env_payload,expected", [
    ({"gpg": {"available": True, "path": "/usr/bin/gpg"},
      "sigstore": {"cosign_available": False, "cosign_version": ""}}, "pgp"),
    ({"gpg": {"available": False, "path": ""},
      "sigstore": {"cosign_available": True, "cosign_version": "2.2.0"}}, "sigstore"),
    ({"gpg": {"available": False, "path": ""},
      "sigstore": {"cosign_available": False, "cosign_version": ""}}, "skip"),
])
def test_signing_setup_auto_orama_gore_secer(env_status, capsys, env_payload, expected):
    """ORTAM: auto -> gpg varsa pgp, cosign varsa sigstore, yoksa skip."""
    env_status(env_payload)
    _cmd_signing_setup(_ns(method="auto"))
    out = capsys.readouterr().out
    assert f"📋  Yöntem: {expected}" in out


@pytest.mark.parametrize("method", ["pgp", "sigstore", "skip"])
@pytest.mark.parametrize("gpg_avail", [True, False])
def test_signing_setup_acik_method_oramdan_bagimsiz(env_status, capsys, method, gpg_avail):
    """ORTAM: acik method her zaman ortamdan bagimsiz secilir."""
    env_status({"gpg": {"available": gpg_avail, "path": "/usr/bin/gpg" if gpg_avail else ""},
                "sigstore": {"cosign_available": not gpg_avail,
                             "cosign_version": "2.2.0" if not gpg_avail else ""}})
    _cmd_signing_setup(_ns(method=method))
    assert f"📋  Yöntem: {method}" in capsys.readouterr().out


@pytest.mark.parametrize("bad", ["bogus", "GPG", "pgp ", "cosign", "PGP", "none"])
def test_signing_setup_gecersiz_method_valueerror(env_status, bad):
    """ORTAM: bilinmeyen method -> ValueError (uretim davranisi)."""
    env_status({"gpg": {"available": True, "path": "/usr/bin/gpg"},
                "sigstore": {"cosign_available": False, "cosign_version": ""}})
    with pytest.raises(ValueError):
        _cmd_signing_setup(_ns(method=bad))


def test_signing_setup_bos_method_autoa_doner(env_status, capsys):
    """ORTAM-OGRENDI: method='' falsy -> 'or "auto"' kisa-devre -> auto (ValueError DEGIL)."""
    env_status({"gpg": {"available": True, "path": "/usr/bin/gpg"},
                "sigstore": {"cosign_available": False, "cosign_version": ""}})
    _cmd_signing_setup(_ns(method=""))
    assert "📋  Yöntem: pgp" in capsys.readouterr().out


# == _cmd_signing_setup: render cikti dallari =======================================================

def test_signing_setup_render_yapi(env_status, capsys):
    """ORTAM: cikti welcome + Araclar + Yontem + adimlar + done icerir."""
    env_status({"gpg": {"available": True, "path": "/usr/bin/gpg"},
                "sigstore": {"cosign_available": False, "cosign_version": ""}})
    _cmd_signing_setup(_ns())
    out = capsys.readouterr().out
    assert "🪄" in out
    assert "🔧  Araçlar:" in out
    assert "   • gpg: ✅ /usr/bin/gpg" in out
    assert "   • cosign: ❌" in out
    assert "📋  Yöntem: pgp" in out
    assert "✅" in out


@pytest.mark.parametrize("gpg_avail,gpg_path,mark", [
    (True, "/usr/bin/gpg", "✅"),
    (False, "", "❌"),
])
def test_signing_setup_gpg_isareti_orama_gore(env_status, capsys, gpg_avail, gpg_path, mark):
    """ORTAM: gpg available -> ✅/❌ isareti ve path."""
    env_status({"gpg": {"available": gpg_avail, "path": gpg_path},
                "sigstore": {"cosign_available": False, "cosign_version": ""}})
    _cmd_signing_setup(_ns())
    out = capsys.readouterr().out
    assert f"   • gpg: {mark} {gpg_path}" in out


@pytest.mark.parametrize("cosign,version,mark", [
    (True, "2.2.0", "✅"),
    (False, "", "❌"),
])
def test_signing_setup_cosign_isareti_orama_gore(env_status, capsys, cosign, version, mark):
    """ORTAM: cosign available -> ✅/❌ + version."""
    env_status({"gpg": {"available": False, "path": ""},
                "sigstore": {"cosign_available": cosign, "cosign_version": version}})
    _cmd_signing_setup(_ns(method="sigstore"))
    out = capsys.readouterr().out
    assert f"   • cosign: {mark} {version}" in out


@pytest.mark.parametrize("method,needle", [
    ("pgp", "gpg --full-generate-key"),
    ("pgp", "gpg --armor --export <KEY_ID> > pkgforge.pub"),
    ("sigstore", "cosign login ghcr.io"),
    ("sigstore", "cosign sign-blob --yes"),
    ("skip", "# nothing to do — packages will not be signed"),
])
def test_signing_setup_adim_komutlari(env_status, capsys, method, needle):
    """ORTAM: her yontem kendi adim komutlarini basar."""
    env_status({"gpg": {"available": True, "path": "/usr/bin/gpg"},
                "sigstore": {"cosign_available": True, "cosign_version": "2.2.0"}})
    _cmd_signing_setup(_ns(method=method))
    assert needle in capsys.readouterr().out


@pytest.mark.parametrize("method,expected_count", [("pgp", 4), ("sigstore", 4), ("skip", 1)])
def test_signing_setup_adim_sayilari(env_status, capsys, method, expected_count):
    """ORTAM: pgp/sigstore 4 adim, skip 1 adim."""
    env_status({"gpg": {"available": True, "path": "/usr/bin/gpg"},
                "sigstore": {"cosign_available": True, "cosign_version": "2.2.0"}})
    _cmd_signing_setup(_ns(method=method))
    out = capsys.readouterr().out
    adimlar = [ln for ln in out.splitlines() if re.match(r"^\s*\d+\.\s", ln)]
    assert len(adimlar) == expected_count


# == _cmd_signing_setup: --save-config dallari ======================================================

def test_signing_setup_save_yazmaz_default(env_status, capsys, tmp_path):
    """ORTAM: save_config yok -> 'JSON config' blogu YAZILMAZ."""
    env_status({"gpg": {"available": True, "path": "/usr/bin/gpg"},
                "sigstore": {"cosign_available": False, "cosign_version": ""}})
    _cmd_signing_setup(_ns())
    out = capsys.readouterr().out
    assert "JSON config:" not in out


def test_signing_setup_save_json_dosyasi(env_status, capsys, tmp_path):
    """ORTAM: save_config -> JSON config blogu + geccerli dosya.

    ORTAM-OGRENDI: dosyadaki 'config_path' BOS'tur — _write_persist result'a
    config_path ATANMADAN ONCE yazilir; atama sonrasi olur (hafizadaki result
    ile basilan JSON blogu DOGRU yolu tasir, dosya bos kaydedilir).
    """
    env_status({"gpg": {"available": True, "path": "/usr/bin/gpg"},
                "sigstore": {"cosign_available": False, "cosign_version": ""}})
    target = tmp_path / "cfg.json"
    rc = _cmd_signing_setup(_ns(save_config=str(target)))
    assert rc == 0
    assert target.exists()
    data = json.loads(target.read_text(encoding="utf-8"))
    assert set(data.keys()) == {"method", "tools_available", "steps", "config_path"}
    assert data["method"] == "pgp"
    assert data["config_path"] == ""  # yazim sirasi quirk'i (yukarida)
    out = capsys.readouterr().out
    assert "JSON config:" in out
    # stdout'taki JSON blogu hafizadaki (atanmis) result -> yol ile
    assert f'"config_path": "{target}"' in out


def test_signing_setup_save_parent_dizin_olusturur(env_status, tmp_path):
    """ORTAM: hedef parent dizini yoksa olusturulur."""
    env_status({"gpg": {"available": True, "path": "/usr/bin/gpg"},
                "sigstore": {"cosign_available": False, "cosign_version": ""}})
    target = tmp_path / "x" / "y" / "cfg.json"
    _cmd_signing_setup(_ns(save_config=str(target)))
    assert target.exists()


def test_signing_setup_save_path_str_olmali(env_status, capsys, tmp_path):
    """ORTAM: save_config Path de olabilir (Path(save_path))."""
    env_status({"gpg": {"available": True, "path": "/usr/bin/gpg"},
                "sigstore": {"cosign_available": False, "cosign_version": ""}})
    target = tmp_path / "p.json"
    _cmd_signing_setup(_ns(save_config=target))
    assert target.exists()


@pytest.mark.parametrize("method", ["pgp", "sigstore", "skip"])
def test_signing_setup_save_ve_method_birlikte(env_status, tmp_path, method):
    """ORTAM: save + acik method -> dosyada o method yazar."""
    env_status({"gpg": {"available": True, "path": "/usr/bin/gpg"},
                "sigstore": {"cosign_available": True, "cosign_version": "2.2.0"}})
    target = tmp_path / "m.json"
    _cmd_signing_setup(_ns(method=method, save_config=str(target)))
    assert json.loads(target.read_text(encoding="utf-8"))["method"] == method


def test_signing_setup_save_render_kayit_mesaji(env_status, capsys, tmp_path):
    """ORTAM: kaydedilince render'a 'Yapılandırma kaydedildi' gelir."""
    env_status({"gpg": {"available": True, "path": "/usr/bin/gpg"},
                "sigstore": {"cosign_available": False, "cosign_version": ""}})
    target = tmp_path / "k.json"
    _cmd_signing_setup(_ns(save_config=str(target)))
    out = capsys.readouterr().out
    assert "Yapılandırma kaydedildi" in out
    assert str(target) in out


def test_signing_setup_kayitsiz_render_kayit_yok(env_status, capsys):
    """ORTAM: save yoksa render'da kayit mesaji YOK."""
    env_status({"gpg": {"available": True, "path": "/usr/bin/gpg"},
                "sigstore": {"cosign_available": False, "cosign_version": ""}})
    _cmd_signing_setup(_ns())
    assert "Yapılandırma kaydedildi" not in capsys.readouterr().out


def test_signing_setup_json_blogu_to_dict_ile_uyusur(env_status, capsys, tmp_path):
    """ORTAM: basilan JSON blogu dosyadaki JSON ile ayni icerige sahip."""
    env_status({"gpg": {"available": True, "path": "/usr/bin/gpg"},
                "sigstore": {"cosign_available": False, "cosign_version": ""}})
    target = tmp_path / "sync.json"
    _cmd_signing_setup(_ns(save_config=str(target)))
    out = capsys.readouterr().out
    # stdout'taki JSON blogu dosyadaki degerle ayni method'u tasir
    assert '"method": "pgp"' in out
    assert json.loads(target.read_text(encoding="utf-8"))["method"] == "pgp"
