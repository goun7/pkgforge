# Feature Tezgahi — kalan CLI ozelliklerini GUI'lere tasima (Faz 5)

Tarih: 2026-08-27  Durum: ONAYLI (kullanici: 'Her birini planlayip otonom olarak tamamla')

## Baglam

PkgForge CLI (main.py + cli.py) ~30 alt komut sunar. Sidecar (core/api_server.py)
bunlarin cogunu JSON-RPC olarak halihazirda acar (pipeline, history, security,
export, graph, source, system, plugin, compare, aur, queue, schedule, profile, sync).
Ancak asagidaki CLI komutlarinin RPC karsiligi YOKTUR ve dolayisiyla hicbir GUI'de
(PyQt6 ya da Tauri) erisilemez:

- audit          (gecmis denetim izi: ozet, butunluk, anomali)
- rpm-to-deb     (RPM'den DEB'ye donusum)
- abi-check      (ABI/sembol uyumluluk taramasi)
- scan-image     (OCI goruntu CVE taramasi; harici arac bagimli)
- attest         (sigstore attestasyonu)
- publish        (AUR yayinlama; kimlik bilgisi gerektirir)
- check-updates  (guncelleme izleme; watch dongusu)

## Kapsam (bu alt sistem)

Uc temiz, kendi-icine kapali, yuksek degerli ozellik her iki GUI'ye tasinir:

1. rpm-to-deb   -> RPC tools.rpm_to_deb
2. abi-check    -> RPC tools.abi_check
3. audit        -> RPC tools.audit

Kapsam disi (gelecek is, ayri alt sistemler): scan-image, attest, publish,
check-updates. Nedenleri: harici arac/kimlik bilgisi bagimliligi, uzun suren
surecler veya watch dongusu; GUI degeri/effort orani bu turde daha dusuk.

## Tasarim — RPC katmani (core/api_server.py)

Uc yeni handler ve METHODS kaydi. Ad alani olarak mevcut 'tools.status' ile
tutarli bicimde 'tools.*' kullanilir.

### tools.rpm_to_deb
  params : { rpm: str, output_dir: str? }
  donen  : { ok: bool, message: str, deb_path: str | None }
  mantik : core.rpm_to_deb_converter.is_rpm_to_deb_available() kontrolu;
           yoksa ok=False + acik mesaj. Varsa rpm_to_deb(rpm, out_dir) cagrisi.
           Dosya yoksa FileNotFoundError.

### tools.abi_check
  params : { package: str }
  donen  : { passed, error_count, binary_count, checked_symbols,
             mismatches: [{binary,symbol,required_version,available_version,
             library,severity}], missing_libs: [[binary,lib]],
             namcap_available, namcap_results: [{severity,tag,message,file}],
             summary: str }
  mantik : core.abi_scanner.check_abi_compatibility(pkg) -> ABIScanReport;
           dataclass alanlari JSON'a serilestirilir. Dosya yoksa FileNotFoundError.

### tools.audit
  params : { date_from: str?, date_to: str?, limit: int? (varsayilan 100) }
  donen  : { total, status_counts: {str:int}, type_counts: {str:int},
             integrity_issues: int, anomalies: int, records: [HistoryRecord...] }
  mantik : HistoryDB().get_history(limit); tarih araligi filtresi; durum/tur
           sayaclari; butunluk (output_pkg/backup_pkg var mi) ve anomali
           (yineleyen donusum, hizli kurulum) tespiti. Salt-okunur, guvenli.

## Tasarim — Tauri frontend (desktop/src)

Yeni sayfa: pages/Tools.tsx. Sidebar'a 'Tools' (Wrench ikonu) eklenir.
Sayfa uc kart icerir (mevcut Card/Button/Badge/Toast bilesenleri kullanilir):

1. RPM to DEB   : dosya secici + donustur butonu + sonuc (ok/message/deb_path)
2. ABI Check    : dosya secici + tara butonu + rapor (passed, sayac, mismatch listesi)
3. Audit Trail  : yukle butonu + tarih filtresi + ozet rozetleri + kayit tablosu
                  + butunluk/anomali ozeti

lib/types.ts'ye AbiReport, AuditReport, RpmToDebResult tipleri eklenir.
i18n (lib/lang.ts) 'tools.*' anahtarlari eklenir (tr/en).

## Tasarim — PyQt6 (ui/)

Yeni diyalog: ui/tools_dialog.py — ToolsDialog(QDialog) uc sekme (QTabWidget):
RPM to DEB, ABI Check, Audit. MainWindow'a bir 'Araclar' butonu eklenir ve
bu diyaloğu acar. Her sekme ilgili core fonksiyonunu BackgroundWorker ile
senkron/arka planda calistirir ve sonucu gosterir. i18n (lang_tr/lang_en)
'tools.*' anahtarlari eklenir.

## Test plani (%100 kapsama zorunlu)

- tests/test_api_tools_round62.py : uc handler'in basari/hata/eksik-dosya/
  arac-yok dallari; METHODS kaydi doğrulama.
- PyQt6 ToolsDialog icin birim testleri (offscreen): sekme varligi, buton
  davranislari (mock core fonksiyonlari).
- Tauri Tools.tsx icin vitest testi (call mock): uc kart render, yukleme/
  hata durumlar.
- Mevcut tam suit %100 / 0 FAILED / rc=0 korunur; ruff/mypy/bandit temiz.

## Uygulama sirasi

1. RPC handlerlari + api testleri (backend temeli, her iki GUI'nin ortak kapisi)
2. PyQt6 ToolsDialog + main_window butonu + i18n + testler
3. Tauri Tools.tsx + Sidebar + types + i18n + vitest + build
4. Statik kontroller + tam suit + mantiksal commit'ler