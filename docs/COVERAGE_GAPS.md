# Coverage Durumu — S3 (ölçülen, gerekçeli)

Tarih: 2026-09-07 · Toplam: %99 (12 769 ifade, 46 eksik)
Yöntem: `pytest tests/ --cov=core --cov=ui --cov=i18n`.
Eski Tur-54 raporu (`%99, 26 eksik`) emeklidir — kod o zamandan beri büyüdü.

## Kapatılanlar (S3)

privileged validasyon matrisi · streaming rapor/header/split-join kenarları ·
workspace bozuk-TOML/çözüm dalları · api_v2 manifest çapraz-kontrol ·
safe_run boş-komut · epoch iki yön · benchmark yok-dosya guard'ları ·
shebang kenarları (+ölü ValueError dalı silindi) · SSRF fail-closed sıkılaştırma ·
cloud bozuk-db · signing chmod-hatası · delta/dep_graph/installer/intake/
cleanup beklenen-hata dalları · handlers_system snapshot başarı+fallback ·
pipeline sha/cancel/temp dalları · subprocess thread-spawn · result/tools
dialog dalları · doctor polkit 3 dal · dep_graph ldd · workspace cwd/root ·
cloud kötü-üye · signing rationale · rpm çıkarma hata dalları · compat
pacman-yok guard'ları · streaming kısa-okuma · snapshot başarı dalı.

## Bilinçli kabul listesi (kapatılmayacak — gerekçesiyle)

| Dosya: satırlar | Neden kabul |
|---|---|
| `snapshot_manager.py` 29 satır | Gerçek btrfs/zfs + root + pkexec ister; CI/dev makinede yıkıcı |
| `package_analyzer.py` 270-284 | `rpm2archive` fallback yalnızca ubuntu rpm derlemesinde çalışır (Arch'ta ölü dal; CI matrix'i kapsar) |
| `api_v2.py` 139-142, 193-194 | Gerçek `cosign` binary'si + bloklayan `run()` server'ı |
| `compatibility_checker.py` 216, 305 | `pacman` yokluğu — non-Arch'ta hep açık (guard'ların kendisi testli) |
| `streaming_extensions.py` 192 | Savunma-ölü: döngü koşulu `need>0` garantiler (`pragma: no cover` gerekçeli) |
| `ui/main_window.py` 608-620 | Onaylı-kurulum modal sorusu — flag-gated (açmak event-loop kilitler) |
| `ui/history_dialog.py` 324 | Modal hata kutusu |

## Skip'ler (4)

- `rpm_to_deb` guard dalı: iki araç da kuruluysa erişilemez (doğru davranış)
- `secrets_store` live: yerelde Secret Service yok (CI `keyring-live` kapsar)
- `sync_backends` age ×2: `age` CLI kurulu değil (kabul)
- `.rpm` fixture skibi KAPANDI — `utest/fixtures` yedeğiyle canlı
