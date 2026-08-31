# F-String i18n Borcu — Takip Kartı
## Tarih: 2026-08-31 · Tur-54
## Toplam: 221 f-string (38 dosya) — henüz dönüştürülmedi

### Durum
- **Tamamlanan i18n:** 78 plain/%-style log mesajı (Tur-53, .spec-work/i18n-batches/transform.py) → 545/545 parity
- **Kalan borç:** 221 Türkçe f-string (örn. raise ValueError(f"Dosya bulunamadı: {path}"))
- **Envanter:** .spec-work/fstring-inventory.json (satır numaraları + metinler)
- **Neden beklemede:** Batch subagent'lar model kısıtlaması nedeniyle düştü; manuel dönüşüm 221 string × karmaşık expression → çok yüksek çaba/gotur

### En Yoğun Dosyalar (top 10)
| Dosya | Adet | Örnek |
|-------|------|-------|
| core/pipeline.py | 17 | f"Uyumsuz mimari: {meta.arch} → ..." |
| core/native_deb_converter.py | 13 | f"DEB dosyası bulunamadı: {deb_path}" |
| core/delta_updater.py | 12 | f"Otomatik güncelleme etkinleştirildi ..." |
| core/oci_builder.py | 11 | f"Paket dosyası bulunamadı: {pkg_path}" |
| core/subprocess_converters.py | 11 | f"ar başarısız (kod: {n}): ..." |
| core/rpm_converter.py | 10 | f"  PKGBUILD yazıldı: {path}" |
| core/security.py | 9 | f"Dosya boyutu büyük: {size_mb:.0f} MB" |
| core/installer.py | 9 | f"Kurulum hatası: {error}" |
| core/snapshot_manager.py | 9 | f"ZFS snapshot geri yükleme: ..." |
| core/api_server.py | 8 | f"Paket bulunamadı: {pkg}" |

### Dönüşüm Şablonu
```python
# Önce:
raise ValueError(f"Dosya bulunamadı: {path}")

# Sonra:
raise ValueError(tr("security.file_not_found", path=path))
# lang_tr.py: "security.file_not_found": "Dosya bulunamadı: {path}"
# lang_en.py: "security.file_not_found": "File not found: {path}"
```

### Önerilen Yaklaşım (sonraki tur)
1. Her dosya için f-string'leri expression karmaşıklığına göre sırala (basit {var} önce)
2. Basit olanları mekanik script ile dönüştür (transform.py'nin f-string versiyonu)
3. Karmaşık expression'lar ({len(x)}, {a.b}, {func()}) için manuel review
4. Her batch sonrası: ruff --fix + py_compile + parity check

### Öncelik
- **Yüksek:** raise/ValueError/RuntimeError mesajları (kullanıcıya gösterilen hatalar)
- **Orta:** log/print f-string'leri (debug/geliştirici mesajları)
- **Düşük:** internal f-string'ler (sadece debug için)
