"""Tur-55 — benchmark kalan dallari (test-only)."""
from __future__ import annotations

import builtins
from types import SimpleNamespace as NS

import core.benchmark as BM

# ── 65-74: bellek olcumu ─────────────────────────────────────────────────────────

def test_get_memory_usage_paths(monkeypatch):
    # gercek /proc okumasi (Linux) — deger doner ya da 0
    deger = BM._get_memory_usage()
    assert deger >= 0

    # OSError yolu (72-73)
    def sahte_open(dosya, *a, **k):
        if "status" in str(dosya):
            raise OSError("yok")
        return builtins.open(dosya, *a, **k)

    monkeypatch.setattr(builtins, "open", sahte_open)
    assert BM._get_memory_usage() == 0                                  # 74

    # ValueError yolu: VmRSS satiri bozuk
    from io import StringIO

    def sahte_open2(dosya, *a, **k):
        if "status" in str(dosya):
            return StringIO("VmRSS: abc def\n")
        return builtins.open(dosya, *a, **k)

    monkeypatch.setattr(builtins, "open", sahte_open2)
    assert BM._get_memory_usage() == 0


# ── 161-163 / 178-180: MIME ve analiz istisna dallari ────────────────────────────

def test_run_benchmarks_mime_and_analysis_errors(monkeypatch, tmp_path):
    test_dosya = tmp_path / "ornek.pkg.tar.zst"
    test_dosya.write_bytes(b"P" * 2048)

    import core.package_analyzer as PA
    import core.security as SEC

    # MIME ValueError (161-163)
    def patlak_mime(dosya, aletler):
        raise ValueError("taniminamayan tur")
    monkeypatch.setattr(SEC, "validate_mime_type", patlak_mime)
    monkeypatch.setattr(SEC, "sha256_hash", lambda p: "a" * 64)

    # analiz Exception (178-180)
    def patlak_analiz(p, t):
        raise RuntimeError("arsiv acilamadi")
    monkeypatch.setattr(PA, "analyze_package", patlak_analiz)

    rapor = BM.run_benchmarks(test_file=test_dosya)
    adlar = {r.name: r for r in rapor.results}
    mime_r = next(v for k, v in adlar.items() if "MIME" in k)
    assert mime_r.passed is False and "Geçersiz MIME" in mime_r.details  # 162-163

    analiz_r = next((v for k, v in adlar.items() if "analizi" in k), None)
    if analiz_r is not None:
        assert analiz_r.passed is False                                  # 179-180


# ── 208-233: xdelta3 benchmark blogu ─────────────────────────────────────────────

def test_run_benchmarks_xdelta3_block(monkeypatch, tmp_path):
    import core.security as SEC
    test_dosya = tmp_path / "buyuk.pkg.tar.zst"
    test_dosya.write_bytes(b"X" * 4096 + b"Y" * 100)

    monkeypatch.setattr(SEC, "validate_mime_type",
                        lambda f, t: "application/octet-stream")
    monkeypatch.setattr(BM.shutil, "which", lambda n: "/usr/bin/xdelta3")
    import core.delta_updater as DU

    # basarili delta (224-232)
    def iyi_delta(eski, yeni, delta):
        delta.write_bytes(b"D" * 64)
        return True
    monkeypatch.setattr(DU, "create_delta", iyi_delta)

    rapor = BM.run_benchmarks(test_file=test_dosya)
    delta_r = next((r for r in rapor.results if "xdelta3" in r.name), None)
    assert delta_r is not None
    assert delta_r.passed is True                                        # 229
    assert "tasarruf" in delta_r.details                                 # 230-232
    assert delta_r.output_size_bytes == 64                               # 228

    # delta dosyasi olusmaz -> output_size 0
    def hicbir_sey(eski, yeni, delta):
        return False
    monkeypatch.setattr(DU, "create_delta", hicbir_sey)
    rapor2 = BM.run_benchmarks(test_file=test_dosya)
    delta_r2 = next(r for r in rapor2.results if "xdelta3" in r.name)
    assert delta_r2.passed is False
    assert delta_r2.output_size_bytes == 0


def test_run_benchmarks_quick_skips_xdelta(monkeypatch, tmp_path):
    import core.security as SEC
    monkeypatch.setattr(SEC, "validate_mime_type",
                        lambda f, t: "application/octet-stream")
    monkeypatch.setattr(SEC, "sha256_hash", lambda p: "b" * 64)
    test_dosya = tmp_path / "hizli.pkg.tar.zst"
    test_dosya.write_bytes(b"Q" * 1024)

    monkeypatch.setattr(BM.shutil, "which",
                        lambda n: "/usr/bin/xdelta3")  # mevcut ama quick atlar
    rapor = BM.run_benchmarks(test_file=test_dosya, quick=True)
    assert all("xdelta3" not in r.name for r in rapor.results)           # 207


# ── BenchmarkReport.passed + summary() ──────────────────────────────────────

def test_report_passed_property_and_summary(monkeypatch, tmp_path):
    import core.package_analyzer as PA
    import core.security as SEC
    monkeypatch.setattr(SEC, "validate_mime_type",
                        lambda f, t: "application/x-pkg")
    monkeypatch.setattr(SEC, "sha256_hash", lambda p: "c" * 64)
    monkeypatch.setattr(PA, "analyze_package",
                        lambda p, t: NS(name="demo", version="1.0"))

    test_dosya = tmp_path / "rapor.pkg.tar.zst"
    test_dosya.write_bytes(b"R" * 512)

    rapor = BM.run_benchmarks(test_file=test_dosya, quick=True)
    assert rapor.passed is True                                      # 48-50
    metin = rapor.summary()                                          # 52-62
    assert "Test" in metin and "Toplam" in metin
    assert "✅" in metin


def test_analysis_success_path(monkeypatch, tmp_path):
    import core.package_analyzer as PA
    import core.security as SEC
    monkeypatch.setattr(SEC, "validate_mime_type",
                        lambda f, t: "application/x-pkg")
    monkeypatch.setattr(SEC, "sha256_hash", lambda p: "d" * 64)
    monkeypatch.setattr(PA, "analyze_package",
                        lambda p, t: NS(name="paket-x", version="2.0"))

    test_dosya = tmp_path / "paket-x.pkg.tar.zst"
    test_dosya.write_bytes(b"P" * 256)
    rapor = BM.run_benchmarks(test_file=test_dosya, quick=True)
    analiz = next(r for r in rapor.results if "analizi" in r.name)
    assert analiz.passed is True and "paket-x 2.0" == analiz.details  # 176-177