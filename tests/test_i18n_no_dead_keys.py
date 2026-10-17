"""Atil anahtar kilidi: katalogda yazilan ama hicbir yerden cagri noktasi
olmayan i18n anahtarlari birikmesin.

Neden var: 2026-10-16 analizinde TR katalogunda 72, masaustu sozlugunde
(`desktop/src/lib/i18n.ts`) 8 anahtar hicbir yerde gecmiyordu — kullanilmayan
arayuz metinleri sessizce birikiyordu. Parite testleri iki katalogu kendi
icinde karsilastirdigi icin bu sinifi hic yakalayamaz.

Tarama bilincli olarak GENIS (yanlis-pozitif uretmez; "atil" dedigimiz anahtar
gercekten hicbir yerde gecmez):
  - uretim .py dosyalarindaki TUM string sabitleri (tr("k"), ternary dallari,
    sabit anahtar listeleri; tools/ ve scripts/ dahil)
  - f-string cagri on ekleri: tr(f"month.{mm}") -> "month." ailesi canli sayilir
  - masaustu .ts/.tsx dosyalarindaki TUM tirnakli kelimeler (testler dahil;
    anahtarlar `labelKey: "navConvert"` gibi dolayli kullaniliyor)
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from i18n.lang_en import STRINGS as EN
from i18n.lang_tr import STRINGS as TR

REPO = Path(__file__).resolve().parent.parent

# Katalog dosyalari taranmaz: kendi anahtarlarini "kullanim" sayardik.
PY_DIZINLER = ("core", "ui", "i18n", "tools", "scripts")
PY_TEKLI = ("cli.py", "main.py", "config.py")
TS_KATALOG = "desktop/src/lib/i18n.ts"


def _py_dosyalari() -> list[Path]:
    dosyalar: list[Path] = []
    for alt in PY_DIZINLER:
        dizin = REPO / alt
        if dizin.is_dir():
            dosyalar.extend(
                p for p in dizin.rglob("*.py")
                if p.name not in ("lang_tr.py", "lang_en.py")
            )
    dosyalar.extend(REPO / tek for tek in PY_TEKLI)
    return [d for d in dosyalar if d.is_file()]


def _ts_dosyalari() -> list[Path]:
    return [
        p for p in (REPO / "desktop" / "src").rglob("*")
        if p.suffix in (".ts", ".tsx") and p.name != Path(TS_KATALOG).name
    ]


def _tr_icinde_mi(kok: ast.AST, hedef: ast.JoinedStr) -> bool:
    """Hedef f-string bir tr(...) cagrisinin icinde mi?

    tr() cagrisinin herhangi bir argumaninda yer alan JoinedStr'ler dinamik
    anahtar uretiyor sayilir; baska yerlerdeki (degisken atamalari gibi)
    f-string'ler sayilmaz.
    """
    for dugum in ast.walk(kok):
        if isinstance(dugum, ast.Call):
            f = dugum.func
            isim = f.id if isinstance(f, ast.Name) else (
                f.attr if isinstance(f, ast.Attribute) else None)
            if isim == "tr":
                for arg in list(dugum.args) + [
                        kw.value for kw in dugum.keywords]:
                    for alt in ast.walk(arg):
                        if alt is hedef:
                            return True
    return False


def _kullanim() -> tuple[set[str], set[str]]:
    """(kullanimda görülen metinler, dinamik cagri on ekleri)"""
    kullanim: set[str] = set()
    onekler: set[str] = set()
    for dosya in _py_dosyalari():
        agac = ast.parse(dosya.read_text(encoding="utf-8"), filename=str(dosya))
        for dugum in ast.walk(agac):
            if isinstance(dugum, ast.Constant) and isinstance(dugum.value, str):
                kullanim.add(dugum.value)
            elif isinstance(dugum, ast.JoinedStr) and dugum.values:
                # Olculen bug (2026-10-17): her f-string'in on eki i18n on eki
                # sayiliyordu. handlers_queue.py:194'teki `item_id = f"q{seq}"`
                # bir tr() cagrisi degil, ama "q" on eki butun "queue.*"
                # ailesini ("queue.done" gibi) canli gibi gosteriyordu —
                # 5 dead anahtar kilicin altindan sessizce alisti.
                # Simdi yalnizca bir tr(...) cagrisinin ICINDeki f-string
                # on ekleri dinamik anahtar sayiliyor.
                if not _tr_icinde_mi(agac, dugum):
                    continue
                ilk = dugum.values[0]
                if isinstance(ilk, ast.Constant) and isinstance(ilk.value, str):
                    onekler.add(ilk.value)
    for dosya in _ts_dosyalari():
        metin = dosya.read_text(encoding="utf-8", errors="replace")
        kullanim.update(re.findall(r"""["']([\w.]+)["']""", metin))
    return kullanim, onekler


def _atil(katalog: set[str]) -> list[str]:
    kullanim, onekler = _kullanim()
    return sorted(
        k for k in katalog
        if k not in kullanim and not any(k.startswith(o) for o in onekler if o)
    )


def test_tr_katalogunda_atil_anahtar_yok():
    assert _atil(set(TR)) == []


def test_en_katalogunda_atil_anahtar_yok():
    assert _atil(set(EN)) == []


def test_ts_sozlugunde_atil_anahtar_yok():
    metin = (REPO / TS_KATALOG).read_text(encoding="utf-8")
    sozluk_anahtarlari = set(re.findall(r"^\s{4}(\w+):\s*[`\"']", metin, re.MULTILINE))
    # Sozluk bicimi degisirse test sessizce bos kumesle "yesil" kalmasin.
    assert len(sozluk_anahtarlari) > 100, "sozluk bicimi degisti, test guncellenmeli"
    assert _atil(sozluk_anahtarlari) == []


def test_ayni_kullanim_kumesi_anahtar_uretmiyor():
    """Kilic kendisi de bir kullanim uydurmasin: dinamik on ek listesi kisa."""
    _, onekler = _kullanim()
    assert onekler and all(o for o in onekler)


@pytest.mark.parametrize("katalog", [TR, EN], ids=["tr", "en"])
def test_katalog_bos_anahtar_ictirmiyor(katalog: dict[str, str]):
    """Bos anahtar kullanim kumesini "her seyle eslesir" yapmasin."""
    assert "" not in katalog


# --- 2026-10-17: tr() disi f-string on eki kilidi ---------------------------

def test_tr_disi_f_string_on_ek_i18n_canliligi_yanlis_eqlemesin():
    """`f"q{seq}"` gibi tr() disi bir f-string "queue.*" ailesini canli
    gosterMEMELI. 2026-10-17'da `core/api/handlers_queue.py:194`'teki
    `item_id = f"q{_queue_seq}"` yuzunden 5 dead queue.* anahtari kilicin
    altindan gecti (kirmizi kanit: `_tr_icinde_mi` kaldirilinca bu test
    fail verir)."""
    _, onekler = _kullanim()
    assert "q" not in onekler, (
        "tr() cagrisi OLMAYAN bir f-string'in 'q' on eki toplandi — bu 'queue.*' "
        "ailesini yanlis canli gosterir. guard tekrar bozulmus."
    )


def test_tr_icindeki_f_string_on_eki_canli_sayiliyor():
    """`tr(f"month.{mm}")` gibi gercek dinamik kullanim canli kalmali."""
    _, onekler = _kullanim()
    assert "month." in onekler, (
        "stats_wrapped.py'daki tr(f\"month.{int(mm)}\") cagrisi canli bir "
        "anahtar ailesi uretiyor — on ek tespiti bozulmus."
    )


def test_queue_dead_anahtarlar_katalogdan_cikarildi():
    """queue.{item_status,waiting,converting,done,error} anahtarlari
    2026-10-17'de gercekten dead olculup silindi; kataloglara geri
    donerlerse bu test fail verir."""
    for katalog, isim in [(TR, "TR"), (EN, "EN")]:
        for k in ("queue.item_status", "queue.waiting",
                  "queue.converting", "queue.done", "queue.error"):
            assert k not in katalog, (
                f"{isim} katalogunda {k} geri donmus — dead anahtar "
                f"birikmesin.")
