"""RPC param sozlesmesi kilidi: arayuzun gonderdigi her parametre okunmali.

Olculen bug (2026-10-17, 041e503): handle_pipeline_start 'install' ve
'out_dir' parametrelerini sessizce yutuyordu; arayuz gonderiyordu, sidecar
yok sayiyordu. Bu bir *sinif* haline gelmemeli — yeni bir parametre
eklenip handler'da okunmazsa bu test kirmizi olmali.

Yontem:
1. desktop/src icindeki her call("metot", {...}) cagrisindan gonderilen
   parametre adi seti cikarilir (kisa ve kisa-olmayan yazimlar dahil).
2. core/api/registry.py METHODS'teki handler'in okudugu parametreler
   bulunur: dogrudan params.get/params[...] ve params argumaniyla
   cagrilan yerel yardimcilari da cozerek (cozum dongulerden korunur).
3. Gonderilip okunmayan parametre = SOZLESME IHLALI.

Tarayici bilincli olarak basittir: bir parametrenin gercekten kullanildigini
yalnizca calisan kod gosterir; bu testin amaci sessiz yutmayi bacaklamak,
semantik dogrulamak degil. Yanlis-pozitifler GENERIC_OKUYUCULER karalistesiyle
elenebilir — ama her girdi bir kod incelemesinin sonucu olmali, tatsizdan
karaliste degil.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FE_DIZIN = REPO / "desktop" / "src"

# Handler'lari parametre okuma acisindan dogrudan test dizininden cozmuyoruz:
# registry import'u test ortaminda agir bagimliliklar isteyebilir, bu yuzden
# kaynak metni ayristiriyoruz (ayni yontemDead-surface denetiminde de kullanildi).

# Bilincli karaliste: gonderilir ama handler *butun params*'i generic olarak
# okur (settings.update(params)) ya da degerin okunmasi AST ile gorulemez.
# Her girdi bir inceleme sonucudur; varsayilan olarak BOS kalmalidir.
GENERIC_OKUYUCULAR: set[str] = {
    "settings.set",   # handle_settings_set: settings.update(params) — hepsi okunur
}


# ── 1. arayuz tarafı: call("metot", {...}) gonderilenler ──────────

def _nesne_alani(src: str, basla: int) -> tuple[int, int] | None:
    """src[basla] '{' ise eslesen '}' indeksini doner (string/ciktan kacinir)."""
    if basla >= len(src) or src[basla] != "{":
        return None
    derinlik = 0
    i = basla
    while i < len(src):
        c = src[i]
        if c in "\"'`":
            i += 1
            while i < len(src) and src[i] != c:
                i += 1 if src[i] != "\\" else 2
        elif c == "{":
            derinlik += 1
        elif c == "}":
            derinlik -= 1
            if derinlik == 0:
                return basla, i
        i += 1
    return None


def _alan_adlari(govde: str) -> set[str]:
    """Bir {…} nesne alanindan gonderilen parametre adlarini cikarir."""
    adlar: set[str] = set()
    # normal anahtar: deger
    for m in re.finditer(r"([A-Za-z_$][\w$]*)\s*(?=:)", govde):
        adlar.add(m.group(1))
    # kisa yazim: { paths } veya { id, priority }
    if ":" not in govde:
        for m in re.finditer(r"\b([A-Za-z_$][\w$]*)\b", govde):
            adlar.add(m.group(1))
    return adlar


def arayuz_cagrilari() -> dict[str, set[str]]:
    """desktop/src'teki her call() icin gonderilen parametre setleri."""
    sonuc: dict[str, set[str]] = {}
    for p in FE_DIZIN.rglob("*"):
        if p.suffix not in (".ts", ".tsx"):
            continue
        if "node_modules" in p.parts or "__tests__" in p.parts:
            continue
        src = p.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'\bcall\(\s*"([a-z_.]+)"\s*(?:,\s*)?', src):
            metot = m.group(1)
            i = m.end()
            while i < len(src) and src[i] in " \t\r\n":
                i += 1
            alan = _nesne_alani(src, i)
            if alan is None:
                sonuc.setdefault(metot, set())
                continue
            adlar = _alan_adlari(src[alan[0] + 1:alan[1]])
            sonuc.setdefault(metot, set()).update(adlar)
    return sonuc


# ── 2. taraf tarafı: handler + yardimci okumalari ───────────────

def _kaynak_agaclari() -> dict[str, ast.Module]:
    """core/api + core/http_api altindaki tum .py dosyalari."""
    agaclar: dict[str, ast.Module] = {}
    for kok in (REPO / "core" / "api", REPO / "core" / "http_api"):
        if not kok.is_dir():
            continue
        for p in kok.rglob("*.py"):
            agaclar[p.name] = ast.parse(p.read_text(encoding="utf-8"))
    return agaclar


AGACLAR = _kaynak_agaclari()


def _fn_var(name: str) -> ast.Module | None:
    for agac in AGACLAR.values():
        for dugum in ast.walk(agac):
            if isinstance(dugum, ast.FunctionDef) and dugum.name == name:
                return agac
    return None


def okunan_parametreler(fn_adi: str, gorulen: set[str] | None = None) -> set[str] | None:
    """fn_adi'nin okudugu params anahtarlarini doner (yardimcilari cozerek).

    None doner: fonksiyon bulunamadi. params argumani olarak gecmeyen
    yardimcilar cozulmez — bu isteyerek yapilir: _require_pkg_file(params)
    gibi tek-gecisli yardimcilar zaten yakalanir.
    """
    if gorulen is None:
        gorulen = set()
    if fn_adi in gorulen:
        return set()
    gorulen.add(fn_adi)
    agac = _fn_var(fn_adi)
    if agac is None:
        return None
    for dugum in ast.walk(agac):
        if not (isinstance(dugum, ast.FunctionDef) and dugum.name == fn_adi):
            continue
        govde = ast.unparse(dugum)
        anahtarlar: set[str] = set()
        anahtarlar |= set(re.findall(r'\bparams\.get\(\s*["\']([A-Za-z0-9_]+)["\']', govde))
        anahtarlar |= set(re.findall(r'\bparams\[\s*["\']([A-Za-z0-9_]+)["\']\s*\]', govde))
        anahtarlar |= set(re.findall(r'\bparams\.get\(\s*([A-Za-z_][\w]*)\s*\)', govde))
        for cagri in set(re.findall(r'([A-Za-z_][\w]*)\s*\(\s*params\b', govde)):
            alt = okunan_parametreler(cagri, gorulen)
            if alt:
                anahtarlar |= alt
        return anahtarlar
    return None


def _registry_eslemesi() -> dict[str, str]:
    """registry.py METHODS: "metot" -> handler fonksiyon adi."""
    src = (REPO / "core" / "api" / "registry.py").read_text(encoding="utf-8")
    agac = ast.parse(src)
    modul_haritasi: dict[str, str] = {}
    for dugum in ast.walk(agac):
        if isinstance(dugum, ast.ImportFrom) and dugum.module:
            for a in dugum.names:
                modul_haritasi[a.asname or a.name] = dugum.module
    eslesme: dict[str, str] = {}
    for m in re.finditer(r'"([a-z_.]+)"\s*:\s*([A-Za-z_][\w]*)\s*,', src):
        eslesme[m.group(1)] = m.group(2)
    return eslesme


# ── testler ──────────────────────────────────────────────────────

def test_arayuz_her_cagiriyi_gordu():
    """Tarayici hicbir cagriyi kacirmamali: bilinen 53+ metot var."""
    cagrilar = arayuz_cagrilari()
    # 041e503 sonrasi olculen sayi; asagisi bir tarayici kiriligini gosterir.
    assert len(cagrilar) >= 50, f"beklenenden az metot bulundu: {len(cagrilar)}"


def test_soilesozleme_ihlali_yok():
    """Arayuzun gonderdigi her parametre handler'da okunuyor olmali."""
    ihlal = []
    arayuz = arayuz_cagrilari()
    eslesme = _registry_eslemesi()
    for metot, gonderilen in sorted(arayuz.items()):
        if metot in GENERIC_OKUYUCULAR:
            continue
        fn = eslesme.get(metot)
        if fn is None:
            ihlal.append((metot, sorted(gonderilen), "KAYIT YOK"))
            continue
        okunan = okunan_parametreler(fn)
        if okunan is None:
            ihlal.append((metot, sorted(gonderilen), "HANDLER BULUNAMADI"))
            continue
        yutulan = sorted(gonderilen - okunan)
        if yutulan:
            ihlal.append((metot, yutulan, sorted(okunan)))
    assert not ihlal, (
        "Arayuz gonderiyor ama handler okumuyor (sessiz yutma):\n"
        + "\n".join(f"  {m}: gonderilen={g} okunan={o}" for m, g, o in ihlal)
    )


def test_pipeline_start_parametreleri_okunuyor():
    """041e503'un regresyon kilidi: install + out_dir artik okunmali."""
    okunan = okunan_parametreler("handle_pipeline_start")
    assert okunan is not None
    for anahtar in ("path", "install", "out_dir", "mode"):
        assert anahtar in okunan, f"handle_pipeline_start '{anahtar}' okumuyor"
