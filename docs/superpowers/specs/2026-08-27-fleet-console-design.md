# Fleet / Kurumsal Konsol (Alan D — stratejik bahis)

Tarih: 2026-08-27  Durum: ONAYLI (kullanici: 'Hepsini onerdigin sirayla otonom gerceklestir')

## Baglam

F5.18 fleet sync backends (webdav/git/rclone-s3 + age sifreleme) ve F5.19 politika
motoru hazir. Bu alt sistem, o yapitaslarini tek bir 'Fleet Konsolu'nda birlestirip
coklu-makine yonetiminin GUI yuzunu acar. Open Core gelir modelinin (Asama 3: ekip/
kurumsal politika profilleri + bulut senkron backend) teknik temelidir.

## Kapsam

1. core/fleet.py (YENI modul): get_fleet_status() tek-cagri agregasyonu:
   - backends: webdav(configured/available), git(available=git binary), rclone-s3(available)
   - age_available, backend_names
   - profiles (cloud_sync._profile_names)
   - sync_configured (settings sync_url)
   - history_count (HistoryDB kayit sayisi)
   - policy_level (policy_engine.policy_from_settings)
   Tum disa-bagimli dallar (which, DB, settings) test edilebilir/monkeypatch'li; hata
   durumunda guvenli varsayilanlar (bos list/0) doner, asla patlamaz.

2. RPC: fleet.status (SENKRON, salt-okunur agregasyon; audit gibi).

3. Tauri Fleet sayfasi (birincil UI): backend kartlari + age rozet + profil listesi +
   policy seviyesi + history/node sayisi + senkron eylemleri (sync.push/pull/export
   yeniden kullanilir). Sidebar'a Server iconlu 'Fleet' nav + App rotasi.

4. PyQt6 FleetDialog (ikincil UI): fleet.status ozetini gosteren basit dialog +
   MainWindow header'a Fleet butonu.

## Test plani

- tests/test_fleet_round64.py : get_fleet_status (tam dallanma + guvenli varsayilanlar).
- tests/test_api_fleet_round64.py : fleet.status handler.
- tests/test_fleet_dialog_round64.py : PyQt6 FleetDialog (offscreen).
- desktop/src/pages/__tests__/Fleet.test.tsx : Fleet sayfasi.
- Tam suit %100 / 0 FAILED / rc=0; ruff/mypy/bandit; tsc+vite build temiz.

## Uygulama sirasi

1. core/fleet.py + birim testleri
2. api_server fleet.status + METHODS + handler testi
3. PyQt6 FleetDialog + MainWindow butonu + i18n + test
4. Tauri Fleet sayfasi + Sidebar/App + types + test + build
5. statik uclu + tam suit + commit + push