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

Yalnizca string-literal anahtarlar denetlenir; `for k in _STEP_KEYS: tr(k)` gibi
dinamik cagrilar da modul duzeyindeki sabit liste/tuple'lardan cozulur. Gercekten
calisma zamaninda uretilen (henuz yok) anahtarlar statik olarak tespit edilemez.
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
    """Dosyadaki tr("<literal>") cagrilarinin anahtarlarini dondurur.

    Dinamik cagrilar da cozulur: `for k in _STEP_KEYS: tr(k)` icin _STEP_KEYS
    modul duzeyinde sabit bir liste/tuple ise uyeleri eklenir — aksi halde bu
    anahtarlar katalogda yoksa hicbir test yakalamazdi.
    """
    agac = ast.parse(dosya.read_text(encoding="utf-8"), filename=str(dosya))

    sabit_listeler: dict[str, set[str]] = {}
    for dugum in getattr(agac, "body", []):
        if isinstance(dugum, ast.Assign) and isinstance(
                dugum.value, (ast.List, ast.Tuple)):
            degerler = {e.value for e in dugum.value.elts
                        if isinstance(e, ast.Constant)
                        and isinstance(e.value, str)}
            if degerler:
                for hede in dugum.targets:
                    if isinstance(hede, ast.Name):
                        sabit_listeler[hede.id] = degerler

    dongu_adlari: dict[str, set[str]] = {}
    for dugum in ast.walk(agac):
        if not isinstance(dugum, ast.For):
            continue
        hedefler = ([dugum.target] if isinstance(dugum.target, ast.Name)
                    else [e for e in getattr(dugum.target, "elts", [])
                          if isinstance(e, ast.Name)])
        if isinstance(dugum.iter, ast.Name):
            kume = sabit_listeler.get(dugum.iter.id)
            if kume:
                for hede in hedefler:
                    dongu_adlari[hede.id] = kume
        elif (isinstance(dugum.iter, ast.Call)
              and getattr(dugum.iter.func, "id", None) == "enumerate"
              and dugum.iter.args and isinstance(dugum.iter.args[0], ast.Name)):
            kume = sabit_listeler.get(dugum.iter.args[0].id)
            if not kume:
                continue
            if isinstance(dugum.target, ast.Tuple) and len(dugum.target.elts) == 2:
                hede = [e for e in dugum.target.elts if isinstance(e, ast.Name)]
                if len(hede) == 2:      # (sirasal, anahtar)
                    dongu_adlari[hede[1].id] = kume
            else:
                for hede in hedefler:
                    dongu_adlari[hede.id] = kume

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
        elif isinstance(ilk, ast.Name):
            bulunan |= dongu_adlari.get(ilk.id, set())
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


def test_yer_tutucu_adlari_tr_imzasina_carmaz():
    """'{key}' sablonu cagri noktasini DUSURURDU: tr(key, **kwargs) cakilamaz.

    `tr("a.b", key="x")` Python'da TypeError dogurur ("multiple values for
    argument 'key'") — ceviri kaydirildiktan sonra polkit doctor probunda bu
    tam olarak oluyordu. Ruff/mypy literal anahtar oldugundan yakalamaz; tek
    gecen yol ya cagrinin gercekten calistirilmasi ya da burada sablon adlarinin
    tr()'nin parametre adleriyle karsilastirilmasi.
    """
    import inspect
    import re
    import string

    from i18n import tr

    korunan = set(inspect.signature(tr).parameters)
    assert "key" in korunan, "tr imzasi degisti; bu testin onemi gozden gecirilmeli"

    def ph(deger: str) -> set[str]:
        try:
            alanlar = {f for _, f, _, _ in string.Formatter().parse(deger) if f}
        except ValueError:
            return set()
        # "{a.b}", "{a[0]}", "{a!r:>{w}}" -> kök ad "a"
        return {re.split(r"[.[:!]", a, maxsplit=1)[0] for a in alanlar}

    for ad, katalog in (("TR", TR), ("EN", EN)):
        for anahtar, deger in katalog.items():
            cubusan = ph(deger) & korunan
            assert not cubusan, (
                f"{ad}:{anahtar} tr() parametre adiyla ayni yer tutucu kullaniyor: "
                f"{sorted(cubusan)} — tr anahtar kelimenin degeri olamaz")

