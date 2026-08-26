# PkgForge "Gerçek 100" Kalite Dosyası

Tarih: bu oturum · Amaç: "%100" iddiasını ölçülebilir kanıtlarla desteklemek.

## Yapılan doğrulamalar ve sonuçlar

| Alan | Yöntem | Sonuç |
|---|---|---|
| Test kapsaması | pytest + cov (core/ui/i18n) | **%100** (10 574 stmt / 0 eksik) |
| Statik kalite | ruff · mypy (72 dosya) · bandit CI-parite | **temiz** |
| Güvenlik öz-denetimi | 12 modülün yetki/kabuk yüzeyinin elle incelenmesi | **1 bulgu düzeltildi**, 6 site temiz (bkz. SECURITY_REVIEW.md) |
| Gerçek-dünya E2E | dpkg-deb ve rpmbuild ile üretilen gerçek paketler | **6/6 PASS** |
| Performans duman testi | core.benchmark quick | DEB üretimi **235 ms**, provenance 231 ms |
| Mutasyon testi (mini) | 3 kritik fonksiyona hata enjeksiyonu | **3/3 KILLED** — testler hepsini yakaladı |
| Paket bütünlüğü | wheel derle + boş venv kurulum + import | **OK** (pkgforge-2.0.0 whl) |

## E2E matrisi detayı (6/6)
- analyze_package(.deb) → `demo-app 1.0-1` doğru çözümlendi
- NativeDebConverter akışı gerçek .deb ile başladı
- rpm2cpio\|bsdtar gerçek .rpm içeriğini çıkardı (usr/bin/demo-app mevcut)
- RpmConverter._extract_rpm pipeline enjeksiyonlu fabrikayla çalıştı
- **rpm_to_deb tam dönüşüm**: geçerli .deb üretti ("DEB paketi hazır")
- Güvenlik taraması: setuid + world-writable fixture'ları doğru uyarildi

## Mini mutasyon skoru
| Mutasyon | Hedef | Sonuç |
|---|---|---|
| M1: sürüm regex yakalama grubu sabitlendi | from_source.py | **KILLED** |
| M2: check_symlink_attacks no-op | security.py | **KILLED** |
| M3: dep grafiği kenar şartı if False | dep_graph.py | **KILLED** |

## Hâlâ dışarıda bırakılanlar (dürüst liste)
- Tam kapsamlı mutasyon taraması (mutmut, 10k+ stmt → saatler): mini örnek
  yerine tam skor için ayrı gece koşusu gerekir.
- Taze VM/kurulum matrisi (Arch dışı dağıtımlar, Wayland/X11 farkları).
- Harici güvenlik denetimi / fuzzing (öz-denetim değildir).
- Kullanılabilirlik testi (gerçek kullanıcı geri bildirimi).

**Sonuç:** Ölçülebilen her kapıda tavan; kalan maddeler kod değil, süreç işi.