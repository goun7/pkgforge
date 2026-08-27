# Feature Tezgahi Faz 2 — scan-image / attest / publish / snapshot-cleanup

Tarih: 2026-08-27  Durum: ONAYLI (kullanici: 'Hepsini onerdigin sirayla otonom gerceklestir')

## Baglam

Faz 1 (B10) rpm-to-deb / abi-check / audit'i her iki GUI'ye tasimisti. Faz 2, GUI'si
olmayan kalan 4 CLI ozelligini ayni desenle (RPC + PyQt6 + Tauri) tasir. Cekirdek
moduller hazir ve testlidir; sadece RPC kabugu + UI katmani eklenir.

## Kapsamdaki ozellikler ve cekirdek API'leri

1. scan-image  : OCI imaj/arşiv taramasi (trivy/grype/clamscan). CLI mantigi cli.py'de
   inline; test_cli_scan.py onu monkeypatch'ler. Bu yuzden core/malware_scanner.py'ye
   YENI `scan_oci_image(image_path)->dict` eklenir ve RPC onu kullanir; CLI'a dokunulmaz
   (test kirilmaz). CLI-inline ile core arasindaki kucuk duplikasyon, kalite borcu olarak
   mutmut turunda birlestirilebilir.
2. attest      : core.provenance.{find_provenance, load_provenance, create_attestation,
   save_attestation}. Bir paketin provenance kayfindan in-toto/SLSA attestation uretir.
3. publish     : core.aur_publish.{prepare_aur_package, push_to_aur}. AUR paketi hazirlar,
   opsiyonel olarak AUR'a iter.
4. snapshot-cleanup : core.snapshot_cleanup.{get_cleanup_status, install_cleanup_service,
   remove_cleanup_service}. systemd timer servisi kur/kaldir/durum.

## RPC tasarimi (core/api_server.py)

- tools.scan_image      thread'li, event/scan_image_done   params:{image}
- tools.attest          thread'li, event/attest_done       params:{package, key?}
- tools.publish         thread'li, event/publish_done      params:{package, output_dir?, aur_url?}
- tools.snapshot_status SENKRON (hizli, salt-okunur)       params:{}
- tools.snapshot_install thread'li, event/snapshot_done    params:{max_age_days?}
- tools.snapshot_remove  thread'li, event/snapshot_done    params:{}

Faz 1 tutarliligi: dosya-girdili/uzun isler thread'li (_run_thread + event), hizli
salt-okunur durum senkron. snapshot_status senkron (audit gibi); install/remove thread'li.

## GUI tasarimi

- PyQt6: ui/tools_dialog.py'ye 4 yeni sekme (Scan / Attest / Publish / Snapshot).
  Her sekme: girdi satiri + eylem butonu + sonuc alani; run_in_background ile.
- Tauri: desktop/src/pages/Tools.tsx'e 4 yeni kart. scan/attest/publish event'lerle,
  snapshot status senkron call + install/remove butonlari.
- i18n: tools.scan_*, tools.attest_*, tools.publish_*, tools.snapshot_* (tr/en).

## Test plani

- tests/test_api_tools2_round63.py : 6 handler (basari + hata + senkron status).
- tests/test_tools_dialog2_round63.py : 4 yeni sekme (sync run_in_background monkeypatch).
- desktop/src/pages/__tests__/Tools2.test.tsx : 4 yeni kart.
- core/malware_scanner.scan_oci_image icin birim testleri (trivy/grype/clamscan dallari).
- Tam suit %100 / 0 FAILED / rc=0; ruff/mypy/bandit temiz; tsc+vite build temiz.

## Uygulama sirasi

1. core: scan_oci_image + birim testleri
2. api_server: 6 handler + METHODS + test_api_tools2_round63
3. PyQt6: 4 sekme + i18n + test_tools_dialog2_round63
4. Tauri: 4 kart + types + i18n + Tools2.test.tsx + build
5. statik uclu + tam suit + mantiksal commit'ler