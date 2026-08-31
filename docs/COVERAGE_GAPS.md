# Coverage Gap Raporu — Tur-54
## Tarih: 31 Ağustos 2026
## Toplam: %99 (11950 statement, 26 missed)

### Missed Lines Detayı

| Dosya | Stmts | Miss | Cover | Missed Lines | Notlar |
|-------|-------|------|-------|-------------|--------|
| core/benchmark.py | 183 | 4 | 98% | 137, 154, 174, 194 | Benchmark edge-case yolları |
| core/delta_updater.py | 215 | 1 | 99% | 319 | Timer disable error path |
| core/dep_graph.py | 240 | 1 | 99% | 340 | Graph traversal edge case |
| core/doctor.py | 51 | 4 | 92% | 60-65 | Sistem komutu hata yolları |
| core/intake.py | 186 | 1 | 99% | 294 | Metadata extraction fallback |
| core/pipeline.py | 708 | 8 | 99% | 160-161, 413, 458, 525-528 | Multi-step error paths |
| ui/main_window.py | 513 | 6 | 99% | 605-617 | Modal dialog interaction |
| ui/result_dialog.py | 265 | 1 | 99% | 227 | Launch button edge case |

### Değerlendirme
- **core/doctor.py (%92)** en düşük coverage'a sahip modül. Sistem komutlarına bağımlı
  hata yollarını test etmek zordur; `pragma: no cover` veya mock test eklenebilir.
- **ui/main_window.py (605-617)** modal dialog akışı — GUI testlerinde etkileşim
  gerektiren satırlar. Mevcut testler flag-gated olduğu için bu satırlar covered değil.
- **core/pipeline.py (525-528)** multi-step conversion error recovery — nadir tetiklenen
  hata yolu. Integration test ile覆盖 edilebilir.
- Diğer tüm missed line'lar edge-case/error-path kategorisinde ve kabul edilebilir düzeyde.

### Öneriler
1. core/doctor.py için subprocess mock testleri ekle (4 satır → %100)
2. ui/main_window.py modal akış için monkeypatch test ekle (6 satır → %100)  
3. core/pipeline.py error recovery için targeted test ekle (8 satır → %100)
4. Kalanlar için `# pragma: no cover` ile işaretle (kabul edilen risk)
