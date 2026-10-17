"""Tauri 2 ACL regression guard: webview olay ulaşımının önkoşulları.

Ölçülen geçmiş (2026-10-16 → 10-17): "Rust→JS özel olaylar webview'a
ulaşmıyor" bulgusu bir ürün hatası değildi; deneme kabuğunda iki koşul
eksikti: (1) `window.__TAURI__` yalnızca `withGlobalTauri: true` durumunda
enjekte edilir, (2) `listen()` aslında bir IPC komutudur
(`invoke("plugin:event|listen")`) ve `core:event` ACL yetkisi olmadan
`Command plugin:event|listen not allowed by ACL` ile reddedilir.

Üretim yapılandırması bu ikisinin doğru halini taşır: JS modül import'u
kullanır (global nesneye ihtiyaç duymaz) ve `core:default` →
`core:event:default` → `allow-listen` yetki zinciri capabilities'te mevcuttur.
Bu testler, birinin yanlışlıkla `core:default`'u capabilities listesinden
çıkarması veya frontend'i global Tauri nesnesine dayalı bir çağrıya
kaydırması durumunda düşer — çünkü her iki değişiklik de olayların
webview'e ulaşmasını sessizce kırar (10-16'daki gibi).
"""

import json
from pathlib import Path

_KOK = Path(__file__).resolve().parents[1]
_TAURI_DIZINI = _KOK / "desktop" / "src-tauri"


def _capability_izinleri() -> list[str]:
    dosya = _TAURI_DIZINI / "capabilities" / "default.json"
    assert dosya.is_file(), f"capability dosyasi yok: {dosya}"
    veri = json.loads(dosya.read_text())
    izinler = veri.get("permissions", [])
    return [p if isinstance(p, str) else str(p.get("identifier", ""))
            for p in izinler]


def _acl_manifesti() -> dict:
    dosya = _TAURI_DIZINI / "gen" / "schemas" / "acl-manifests.json"
    assert dosya.is_file(), (
        "acl-manifests.json yok — once `cargo build` (tauri-build) calistirilmali")
    return json.loads(dosya.read_text())


def test_capabilities_core_default_icerir():
    """core:default -> core:event:default -> allow-listen zinciri.

    Bu zincir olmadan `listen()` ACL reddi alir: 2026-10-17'de capabilities'siz
    bir deneme kabugunda birebir olculen davranis
    ("Command plugin:event|listen not allowed by ACL").
    """
    izinler = _capability_izinleri()
    assert "core:default" in izinler, (
        f"capabilities/default.json 'core:default' icermiyor; bu, webview'in "
        f"tum event/* dinleyicilerini ACL redleriyle sessizce kirar. "
        f"Mevcut izinler: {izinler}")


def test_acl_manifesti_event_listen_izinli():
    """Compiled ACL'de core:event:default altinda allow-listen olmalidir."""
    manifest = _acl_manifesti()
    core_event = manifest.get("core:event")
    assert core_event is not None, "acl-manifests.json'da 'core:event' yok"
    varsayilan = core_event.get("default_permission", {})
    alt_izinler = varsayilan.get("permissions", [])
    assert "allow-listen" in alt_izinler, (
        f"core:event default izinleri allow-listen icermiyor: {alt_izinler}")
    assert "allow-unlisten" in alt_izinler, (
        f"core:event default izinleri allow-unlisten icermiyor: {alt_izinler}")


def test_on_yuz_global_tauri_kullanmiyor():
    """Ön yüz modül import'u (`@tauri-apps/api`) kullanmalıdır.

    Tauri 2'de `window.__TAURI__` ancak `app.withGlobalTauri: true` durumunda
    vardır; üretim yapılandırması bu alanı kullanmaz. Eğer arayüz global
    nesneye başvurursa JS sessizce ölür (10-16'da olculen ilk yanılgı).
    """
    kaynak = _KOK / "desktop" / "src"
    assert kaynak.is_dir(), f"on yuz kaynak dizini yok: {kaynak}"
    sorunlu: list[str] = []
    for dosya in kaynak.rglob("*.ts*"):
        metin = dosya.read_text(errors="ignore")
        # Yalnizca gerçek erişimler; yorum/belge içindeki geçişler sayılmaz.
        for satir_no, satir in enumerate(metin.splitlines(), start=1):
            kirpik = satir.split("//")[0]
            # Cok satirli yorum satiri (basinda '*' veya sonunda '*/'):
            # icindeki gecisler belge amacli, kod degil.
            if ("*" in kirpik and
                    (kirpik.lstrip().startswith("*") or kirpik.rstrip().endswith("*/"))):
                continue
            if "window.__TAURI__" in kirpik:
                sorunlu.append(f"{dosya.name}:{satir_no}: {satir.strip()}")
    assert sorunlu == [], (
        "On yuz window.__TAURI__ globaline basvuruyor; bu nesne yalnizca "
        "withGlobalTauri:true durumunda vardir ve üretim kabugunda sessiz "
        "olumle sonuclanir. Yerine @tauri-apps/api modul import'u "
        f"kullanilmali: {sorunlu[:3]}")


def test_tauri_conf_global_tauri_alani_yok():
    """withGlobalTauri bilinçle kapalıdır; eklersek test düşer.

    Üretim JS'i modül import'u kullandığından bu alan gerekmez; ama
    bilinçsiz bir değişiklikte global nesneye dayalı kodun çalıştığı
    sanılmasın diye bu sözleşme sabit kalır.
    """
    dosya = _TAURI_DIZINI / "tauri.conf.json"
    veri = json.loads(dosya.read_text())
    app = veri.get("app", {})
    assert "withGlobalTauri" not in app, (
        "tauri.conf.json app.withGlobalTauri tanimli; üretim sözleşmesi "
        "modul import'u (global nesne degil) oldugu için bu alan "
        "kaldirilmali.")
