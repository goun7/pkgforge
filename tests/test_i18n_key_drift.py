"""i18n anahtar surusum kilidi: uretim kodundaki her tr() anahtari katalogda olmali.

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.

Neden var: uc anahtar hicbir katalogda YOKTU ve kod cagri noktalarinda ham
anahtar metni olarak kullaniciza siziyordu:
  main.py:300      --branch help -> "cli.arg_flatpak_branch"
  cli.py:258       "cli.auto_compat_preview_skipped"
  cli.py:275       "cli.auto_dep_resolve_skipped"
Bunlar yardim ekraninda/standart hatada gorunur; dil parite testi
(test_i18n_parity.py) TR ve EN'yi KENDI ARALARINDA karsilastirdigi icin
iki katalogda da EKSIK olan anahtari hicbir zaman yakalamadi. Yani eksiklik,
mevcut testin kapsama sinirindan dogal olarak firardi — bu test o boslugu kapatir.

Yalnizca string-literal anahtarlar denetlenir; dinamik uretilen anahtarlar
(ui/step_progress.py) statik olarak tespit edilemez ve bilerek disarda birakilir.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from i18n.lang_en import STRINGS as EN
from i18n.lang_tr import STRINGS as TR

REPO = Path(__file__).resolve().parent.parent

# Denetlenecek uretim alanlari (testler kasitli disarda)
URETIM = ["core", "ui", "i18n", "cli.py", "main.py", "config.py"]


def _tr_anahtarlari(dosya: Path) -> set[str]:
    """Dosyadaki tr("<literal>") cagrilarinin anahtarlarini dondurur."""
    agac = ast.parse(dosya.read_text(encoding="utf-8"), filename=str(dosya))
    bulunan: set[str] = set()
    for dugum in ast.walk(agac):
        if not isinstance(dugum, ast.Call):
            continue
        f = dugum.func
        ad = getattr(f, "id", None) or getattr(f, "attr", None)
        if ad != "tr" or not dugum.args:
            continue
        ilk = dugum.args[0]
        if isinstance(ilk, ast.Constant) and isinstance(ilk.value, str):
            bulunan.add(ilk.value)
    return bulunan


def _tum_kaynaklar() -> list[Path]:
    yollar: list[Path] = []
    for parca in URETIM:
        hedef = REPO / parca
        if hedef.is_file():
            yollar.append(hedef)
        elif hedef.is_dir():
            yollar.extend(sorted(p for p in hedef.rglob("*.py")
                                 if "__pycache__" not in p.parts))
    return yollar


ALL = sorted({k for p in _tum_kaynaklar() for k in _tr_anahtarlari(p)})


def test_en_anahtar_bulundugu():
    """Kaynak taramasi bir sey bulmali; bos tarama testin kendisi korur."""
    assert len(ALL) > 500, f"beklenmedik kadar az anahtar tarandi: {len(ALL)}"


@pytest.mark.parametrize("anahtar", ALL)
def test_anahtar_TR_katalogunda_var(anahtar):
    assert anahtar in TR, f"{anahtar} lang_tr.py icinde yok"


@pytest.mark.parametrize("anahtar", ALL)
def test_anahtar_EN_katalogunda_var(anahtar):
    assert anahtar in EN, f"{anahtar} lang_en.py icinde yok"


@pytest.mark.parametrize("anahtar", ALL)
def test_anahtar_yer_tutuculari_TR_EN_ayni(anahtar):
    """Ayni placeholder seti: yoksa bir dil .format ile patlar ya da bos basar."""
    import string

    def ph(deger: str) -> set[str]:
        try:
            return {f for _, f, _, _ in string.Formatter().parse(deger) if f}
        except ValueError:
            return set()

    if anahtar in TR and anahtar in EN:
        assert ph(TR[anahtar]) == ph(EN[anahtar]), anahtar


def test_kataloglarda_kontrol_karakteri_yok():
    """'{\\x01:\\x02}' bozulmasi tekrar girerse buradan yakalanir."""
    for ad, katalog in (("TR", TR), ("EN", EN)):
        for anahtar, deger in katalog.items():
            kontrol = [c for c in deger if ord(c) < 32 and c != "\n"]
            assert not kontrol, f"{ad}:{anahtar} kontrol karakterleri {kontrol}"


def test_konumlu_sablon_kwargs_ile_caburmaz(monkeypatch):
    """IndexError tr()'den KACIYORDU: '{}' + kwargs -> format patlar.

    Cok yerel hata: coklu hata yakalanmiyor diye ceviri sozlugunun bozuk bir
    kaydi bir CLI komutunu dusururdu (bozuk `\\1` sablonlarinda bu neredeyse
    oluyordu; tr()'de sessiz yutma vardi ama IndexError eksikti).
    """
    import i18n

    monkeypatch.setattr(i18n, "_strings", {
        "a": "konumlu {}", "b": "ad {ad}", "c": "bozuk {", "d": "eksik {yok}"})
    monkeypatch.setattr(i18n, "_current_lang", "tr")
    assert i18n.tr("a", ad=1) == "konumlu {}"     # caburmaz, ham metni birakir
    assert i18n.tr("b", ad="x") == "ad x"          # normal dolma
    assert i18n.tr("c", ad=1) == "bozuk {"         # ValueError yutuluyor
    assert i18n.tr("d", ad=1) == "eksik {yok}"     # KeyError yutuluyor


def test_EN_katalogunda_turkce_karakter_kalmamali():
    """Ingilizce modda Turkce metin gorunmesi class'i kapanis kilidi.

    Katalogdaki EN degerleri bir makine cevirisi gecisinde yari Turkce kalmisti
    ("Package filesı not found", "signature datatabanı", "dataficationsı
    failed") — Ingilizce arayuz kullanicisi icin bu, cevirinin hic olmamasindan
    daha kotu. 127 kayit duzeltildi; bu test bir daha sizmasini engeller.
    """
    import re

    turkce = re.compile(r"[çğıöşüÇĞİÖŞÜ]")
    sikayetli = sorted(k for k, v in EN.items() if turkce.search(v))
    assert not sikayetli, (
        f"lang_en.py icinde {len(sikayetli)} degerde Turkce harf var: "
        f"{sikayetli[:6]}")
