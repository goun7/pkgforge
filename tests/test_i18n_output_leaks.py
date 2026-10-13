"""CLI/cekirdek ciktilarinin iki dilde de gercekten cevrildigini kanitlayan kilidler.

Neden var: EN modunda calistirildiginda `doctor`, `list`, `audit`, `wrapped`,
`snapshot-cleanup --status`, `delta status` ve `serve --help` ciktilarinda Turkce
satirlar kaliyordu (gercek komut calistirmalarinda olculdu). Ceviri kismen
yapildigi icin mevcut parite testi (TR ile EN'yi kendi arasinda karsilastirir)
bu class'i yakalayamiyor: anahtar kataloglarda var, ama kod henuz ham literali
bastiriyor. Bu dosya o boslugu kapatir ve geriye donusu engeller.
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

import cli as cli_mod
import main as main_mod
from i18n import _load_language_module, tr

REPO = pathlib.Path(__file__).resolve().parent.parent
TURKCE_HARF = re.compile(r"[çğıöşüÇĞİÖŞÜ]")


@pytest.fixture(autouse=True)
def _tr_dili():
    """Testler arasi dil sizintisini engeller."""
    from i18n import init_language

    init_language("tr")
    yield
    init_language("tr")


def _iki_dil(anahtar: str, **kwargs: object) -> tuple[str, str]:
    from i18n import init_language

    init_language("tr")
    tr_ciktisi = tr(anahtar, **kwargs)
    init_language("en")
    en_ciktisi = tr(anahtar, **kwargs)
    return tr_ciktisi, en_ciktisi


# --- ay adlari: core/stats_wrapped.py artik kataloga bakiyor -----------------

def test_oniki_ay_katiligi_iki_dilde_de_var() -> None:
    tr_harita = _load_language_module("tr")
    en_harita = _load_language_module("en")
    for ay in range(1, 13):
        anahtar = f"month.{ay}"
        assert tr_harita.get(anahtar), f"{anahtar} TR katalogda yok"
        assert en_harita.get(anahtar), f"{anahtar} EN katalogda yok"


def test_busiest_month_dile_gore_cevrilir() -> None:
    from core.stats_wrapped import _month_label

    from i18n import init_language

    init_language("tr")
    assert _month_label("08") == "Agustos"      # eski davranisla baytbayt
    init_language("en")
    assert _month_label("08") == "August"


def test_ay_etiketi_rakam_degilse_oldugu_gibi_kalir() -> None:
    from core.stats_wrapped import _month_label

    assert _month_label("abc") == "abc"
    assert _month_label("13") == "13"


# --- tablo basliklari: TR'de Ingilizce, EN'de Turkce classi ------------------

def test_tablo_basliklari_eski_genislikleri_koruyor() -> None:
    from i18n import init_language

    init_language("tr")
    # Eski `audit` satiriyla baytbayt ayni olmali.
    assert cli_mod._table_headers((4, 20, 20, 6, 12, 0)) == (
        "ID   Tarih                Paket                Tür    Durum        "
        "Orijinal Dosya")
    init_language("en")
    baslik = cli_mod._table_headers((4, 20, 20, 6, 10, 0))
    assert "Tarih" not in baslik and "Paket" not in baslik
    assert baslik.startswith("ID   Date")


def test_tablo_basliginda_alti_etiket_var() -> None:
    from i18n import init_language

    for dil in ("tr", "en"):
        init_language(dil)
        assert len(tr("cli.history_table_headers").split(",")) == 6


# --- doctor ayrintilari -------------------------------------------------------

def test_keyring_detayi_iki_dilde_de_var() -> None:
    tr_d, en_d = _iki_dil("doctor.keyring_yok")
    assert tr_d == "Secret Service yok (anahtarlik devre disi)"
    assert "yok" not in en_d and en_d


def test_doktor_baslik_satirlari_cevrili() -> None:
    tr_d, en_d = _iki_dil("cli.doctor_depolama", profil="default",
                          config="/x")
    assert tr_d == "Depolama — profil: default, config: /x"
    assert en_d == "Storage — profile: default, config: /x"

    tr_d, en_d = _iki_dil("cli.doctor_eksik_zorunlu", items="debtap")
    assert tr_d == "Eksik zorunlu: debtap"
    assert en_d == "Missing required: debtap"


def test_polkit_detayleri_placeholder_ile_doluyor() -> None:
    tr_d, en_d = _iki_dil("doctor.polkit_exec_path_yok",
                          polkit_key="org.freedesktop.policykit.exec.path")
    assert "'org.freedesktop.policykit.exec.path'" in tr_d
    assert "'org.freedesktop.policykit.exec.path'" in en_d
    assert "{polkit_key}" not in en_d


def test_keyring_probu_cekirdekte_ceviriye_bagli() -> None:
    from unittest import mock

    import core.doctor as doctor

    from i18n import init_language

    with mock.patch("core.secrets_store.available", return_value=False):
        init_language("en")
        assert "yok" not in doctor._check_keyring()["detail"]
        init_language("tr")
        assert doctor._check_keyring()["detail"] == (
            "Secret Service yok (anahtarlik devre disi)")


# --- main.py: program ciktilari ---------------------------------------------

def test_schedule_run_ozeti_eski_ciktiyla_ayni() -> None:
    tr_d, _ = _iki_dil("main.schedule_run_ozet", ran=True, gorev="convert",
                       sonuc=True, detay="ok")
    # Eski: print("calisti:", ..., "| gorev:", ..., "| sonuc:", ..., "|", detay)
    assert tr_d == "calisti: True | gorev: convert | sonuc: True | ok"


def test_check_deps_etiketleri_dile_gore() -> None:
    tr_d, en_d = _iki_dil("deps.gerekli")
    assert (tr_d, en_d) == ("GEREKLİ", "REQUIRED")
    tr_d, en_d = _iki_dil("deps.istege_bagli")
    assert (tr_d, en_d) == ("İsteğe bağlı", "optional")


def test_schedule_install_satiri_cevrili() -> None:
    tr_d, en_d = _iki_dil("main.schedule_install_tamam", enable=True)
    assert tr_d == "kurulum tamam. etkinlestirme: True"
    assert en_d == "install complete. enabled: True"


# --- ratchet: kodda ham Turkce basma yasağı ----------------------------------

def _print_sabitleri(yol: pathlib.Path) -> list[tuple[int, str]]:
    """print(...) cagrilarindaki koda gomulu metinler (tr() anahtarlari degil)."""
    agac = ast.parse(yol.read_text(encoding="utf-8"))
    bulunan: list[tuple[int, str]] = []
    for dugum in ast.walk(agac):
        if not isinstance(dugum, ast.Call):
            continue
        ad = getattr(dugum.func, "id", None) or getattr(dugum.func, "attr", None)
        if ad != "print":
            continue
        anahtarlar = {
            id(a) for c in ast.walk(dugum) if isinstance(c, ast.Call)
            and (getattr(c.func, "id", None) or getattr(c.func, "attr", None)) == "tr"
            for a in c.args if isinstance(a, ast.Constant)
        }
        for sabit in ast.walk(dugum):
            if (isinstance(sabit, ast.Constant) and isinstance(sabit.value, str)
                    and id(sabit) not in anahtarlar):
                bulunan.append((sabit.lineno, sabit.value))
    return bulunan


# ASCIIyle yazilmis Turkce kelimeler: diacritic taramasi bunlari gormez.
_ASCII_TURKCE = re.compile(
    r"\b(kaynak|cikti|girdi|paket|dosya|durum|tarih|sayisi|adet|liste|listesi|"
    r"islem|kontrol|kurulu|aktif|analiz|uyari|hata|basarili|basarisiz|tamam|"
    r"toplam|maks|derinlik|agac|secenek|gorev|zaman|aralik|onizle|yazma|goster|"
    r"indiriliyor|kaydedildi|bulunamadi|gerekli|edildi|edilemedi|yayinda|"
    r"calistir|calisti|sonuc|etkinlestirme|eksik|zorunlu|opsiyonel|"
    r"bagimlilik|cozumleme|anomal|tespit|uyumsuzluk|sistem|gecmis|kayit|ozet|"
    r"tur|yil|gore|igin)\b",
    re.IGNORECASE)


@pytest.mark.parametrize("dosya", ["cli.py", "main.py"])
def test_print_cagrilarinda_ham_turkce_metin_yok(dosya: str) -> None:
    """EN modunda Turkce satir basan tek kaynak ham literaldi; ratchet.

    `tr(...)` ile alinmis metinler buradan gecmez; yalnizca koda gomulu
    kelimeler denetlenir. Emoji/kisa etiket (ID, D-Bus) muaf.
    """
    suclu = [(satir, deger) for satir, deger in _print_sabitleri(REPO / dosya)
             if TURKCE_HARF.search(deger) or _ASCII_TURKCE.search(deger)]
    assert not suclu, f"{dosya}: {suclu[:5]}"


@pytest.mark.parametrize("dosya", ["cli.py", "main.py"])
def test_argparse_help_literalleri_tr_ile_alinmis(dosya: str) -> None:
    """help="..." sabiti yardim ekranina dil fark etmeksizin ayni basilir."""
    agac = ast.parse((REPO / dosya).read_text(encoding="utf-8"))
    suclu = [
        (dugum.lineno, kw.value.value)
        for dugum in ast.walk(agac) if isinstance(dugum, ast.Call)
        for kw in dugum.keywords
        if kw.arg == "help" and isinstance(kw.value, ast.Constant)
        and isinstance(kw.value.value, str)
    ]
    assert not suclu, f"{dosya}: {suclu[:5]}"


def test_main_hata_sablonu_doldurulabiliyor() -> None:
    """Bu modulun kendi kullandigi yardimci: tr(...) kwargs adlari test edilsin."""
    _, en_d = _iki_dil("main.hata", mesaj="boom")
    assert en_d == "error: boom"
    assert main_mod.tr is not None
