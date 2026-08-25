"""Coverage itmesi - quality_score: not bantlari ve tum yedek dallari."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import core.quality_score as QS
from core.quality_score import QualityCheck, QualityReport


def _pkg(tmp_path):
    p = tmp_path / "demo-1.0-1-x86_64.pkg.tar.zst"
    p.write_bytes(b"x" * 2048)
    return p


def _info(extra=None):
    base = {"pkgname": "demo", "pkgver": "1.0", "desc": "Uzun aciklama",
            "license": "GPL", "url": "https://demo.example"}
    base.update(extra or {})
    return base


class BadInfo(dict):
    """Belirtilen anahtarda get() ile patlayan sahte PKGINFO."""
    def __init__(self, bad_key):
        super().__init__()
        self._bad = bad_key

    def get(self, k, default=None):
        if k == self._bad:
            raise RuntimeError("okunamadi")
        return super().get(k, default)


# --- ozet not bantlari ---------------------------------------------------------

@pytest.mark.parametrize("score,text", [
    (92, "Mükemmel"),
    (80, "İyi"),
    (65, "Kabul edilebilir"),
    (45, "Düşük"),
    (10, "Kötü"),
])
def test_summary_grade_bands(score, text):
    r = QualityReport()
    r.total_score = score
    out = r.summary()
    assert text in out


# --- _read_pkginfo -------------------------------------------------------------

def test_read_pkginfo_parses_pairs(tmp_path, monkeypatch):
    body = "pkgname = demo\npkgver = 1.0\nbozuk-satir"
    monkeypatch.setattr(QS, "safe_run",
                        lambda cmd, timeout=0: NS(returncode=0, stdout=body))
    info = QS._read_pkginfo(tmp_path / "x.pkg.tar.zst")
    assert info["pkgname"] == "demo" and info["pkgver"] == "1.0"


def test_read_pkginfo_rc_fail_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(QS, "safe_run",
                        lambda cmd, timeout=0: NS(returncode=1, stdout=""))
    assert QS._read_pkginfo(tmp_path / "x.pkg.tar.zst") == {}


def test_read_pkginfo_exception_swallowed(tmp_path, monkeypatch):
    def boom(cmd, timeout=0):
        raise OSError("tar yok")
    monkeypatch.setattr(QS, "safe_run", boom)
    assert QS._read_pkginfo(tmp_path / "x.pkg.tar.zst") == {}


# --- yardimci: score_package'i sahtelerle sur ----------------------------------

def _drive(tmp_path, monkeypatch, *, info=None, safe=None, abi="pass",
           deps_report=None, dep_raise=False, machine=None):
    pkg = _pkg(tmp_path)
    monkeypatch.setattr(QS, "_read_pkginfo", lambda p: info if info is not None else _info())
    if safe is None:
        safe = lambda cmd, timeout=0: NS(returncode=0,
                                         stdout="usr/bin/a\netc/b\n")
    monkeypatch.setattr(QS, "safe_run", safe)

    if abi == "raise":
        def bad_abi(p):
            raise RuntimeError("abi yok")
        monkeypatch.setattr("core.abi_scanner.check_abi_compatibility", bad_abi)
    else:
        result = (NS(passed=True, error_count=0, binary_count=3)
                  if abi == "pass"
                  else NS(passed=False, error_count=2, binary_count=5))
        monkeypatch.setattr("core.abi_scanner.check_abi_compatibility",
                            lambda p: result)

    if dep_raise:
        def bad_deps(*a, **k):
            raise RuntimeError("cozulemedi")
        monkeypatch.setattr("core.dep_resolver.resolve_dependencies", bad_deps)
    elif deps_report is not None:
        monkeypatch.setattr("core.dep_resolver.resolve_dependencies",
                            lambda d, include_installed=True: deps_report)

    if machine is not None:
        import platform
        monkeypatch.setattr(platform, "machine", lambda: machine)
    return QS.score_package(pkg, NS())


def _check(report, name):
    for c in report.checks:
        if c.name == name:
            return c
    raise AssertionError(f"kontrol yok: {name}")


# --- guvenlik kontrolleri ------------------------------------------------------

def test_abi_fail_scores_partial(tmp_path, monkeypatch):
    rep = _drive(tmp_path, monkeypatch, abi="fail")
    c = _check(rep, "ABI Uyumluluğu")
    assert c.passed is False and c.score == 6 and "2 uyumsuzluk" in c.detail


def test_abi_crash_swallowed(tmp_path, monkeypatch):
    rep = _drive(tmp_path, monkeypatch, abi="raise")
    assert rep.checks  # akis yasa disi durmadan devam eder


def test_path_traversal_tar_fail_partial_credit(tmp_path, monkeypatch):
    rep = _drive(tmp_path, monkeypatch,
                 safe=lambda cmd, timeout=0: NS(returncode=1, stdout=""))
    c = _check(rep, "Path Traversal")
    assert c.score == 3 and "alınamadı" in c.detail


def test_path_traversal_offending_zeroes(tmp_path, monkeypatch):
    rep = _drive(
        tmp_path, monkeypatch,
        safe=lambda cmd, timeout=0: NS(returncode=0,
                                       stdout="../kötü/usr/x\netc/y"))
    c = _check(rep, "Path Traversal")
    assert c.passed is False and c.score == 0 and "1 ihlal" in c.detail


def test_path_traversal_crash_fallback(tmp_path, monkeypatch):
    def boom(cmd, timeout=0):
        raise OSError("tar patladi")
    rep = _drive(tmp_path, monkeypatch, safe=boom)
    c = _check(rep, "Path Traversal")
    assert c.detail == "Kontrol başarısız"


# --- uyumluluk -----------------------------------------------------------------

def test_deps_resolved_ratio_scores(tmp_path, monkeypatch):
    rr = NS(resolved_count=1, total=2, all_resolved=False)
    rep = _drive(tmp_path, monkeypatch,
                 info=_info({"depend": "gtk3"}),
                 deps_report=rr)
    c = _check(rep, "Bağımlılık Çözümleme")
    assert c.score == 7 and c.passed is False


def test_deps_none_gives_default_credit(tmp_path, monkeypatch):
    rep = _drive(tmp_path, monkeypatch)
    c = _check(rep, "Bağımlılık Çözümleme")
    assert c.score == 10 and c.passed is True


def test_deps_crash_fallback(tmp_path, monkeypatch):
    rep = _drive(tmp_path, monkeypatch, dep_raise=True,
                 info=_info({"depend": "gtk3"}))
    c = _check(rep, "Bağımlılık Çözümleme")
    assert c.score == 8 and c.detail == "Kontrol başarısız"


def test_arch_mismatch_zero_and_unknown(tmp_path, monkeypatch):
    rep = _drive(tmp_path, monkeypatch, info=_info({"arch": "aarch64"}),
                 machine="x86_64")
    c = _check(rep, "Mimari Uyumluluğu")
    assert c.passed is False and c.score == 0

    rep2 = _drive(tmp_path, monkeypatch, info=_info(), machine="x86_64")
    c2 = _check(rep2, "Mimari Uyumluluğu")
    assert c2.passed is True  # any/paket mimarisi bilinmiyor dalı


def test_arch_crash_fallback(tmp_path, monkeypatch):
    import platform

    def boom():
        raise RuntimeError("makine yok")
    monkeypatch.setattr(platform, "machine", boom)
    rep = _drive(tmp_path, monkeypatch, machine=None)
    c = _check(rep, "Mimari Uyumluluğu")
    assert c.score == 5


# --- metadata okunamadi fallbackleri -------------------------------------------

def test_metadata_version_read_failure(tmp_path, monkeypatch):
    rep = _drive(tmp_path, monkeypatch, info=BadInfo("pkgver"))
    c = _check(rep, "Sürüm")
    assert c.passed is False and c.score == 0 and c.detail == "Okunamadı"


def test_metadata_desc_read_failure(tmp_path, monkeypatch):
    rep = _drive(tmp_path, monkeypatch, info=BadInfo("desc"))
    c = _check(rep, "Açıklama")
    assert c.score == 0


def test_metadata_license_read_failure(tmp_path, monkeypatch):
    rep = _drive(tmp_path, monkeypatch, info=BadInfo("license"))
    c = _check(rep, "Lisans")
    assert c.passed is False


def test_metadata_url_read_failure(tmp_path, monkeypatch):
    rep = _drive(tmp_path, monkeypatch, info=BadInfo("url"))
    c = _check(rep, "Web Sitesi")
    assert c.detail == "Okunamadı"


def test_metadata_missing_values_partial(tmp_path, monkeypatch):
    # pkgname bos -> dosya adindan turetilir ("demo") ve ad kontrolu GECER
    rep = _drive(tmp_path, monkeypatch, info={"pkgname": ""})
    name_c = _check(rep, "Paket Adı")
    assert name_c.passed is True and name_c.detail == "demo"
    assert _check(rep, "Sürüm").passed is False
    assert _check(rep, "Lisans").passed is False


def test_summary_lists_categories_and_icons():
    r = QualityReport()
    r.total_score = 95
    r.checks.append(QualityCheck(name="ABI Uyumluluğu", category="security",
                                 passed=True, score=10, max_score=10,
                                 detail="temiz"))
    r.checks.append(QualityCheck(name="Sürüm", category="metadata",
                                 passed=False, score=0, max_score=5,
                                 detail="yok"))
    out = r.summary()
    assert "[SECURITY]" in out and "[METADATA]" in out
    assert "✅ ABI Uyumluluğu" in out and "❌ Sürüm" in out


def test_name_from_filename_variants():
    assert QS._name_from_filename(Path("demo.pkg.tar.zst")) == "demo"
    assert QS._name_from_filename(Path("a-b-c.pkg.tar.xz")) == "a-b-c"
    assert QS._name_from_filename(Path("sadecead")) == "sadecead"
    assert QS._name_from_filename(
        Path("gtk3-3.24.42-1-x86_64.pkg.tar.gz")) == "gtk3"


# --- boyut bantlari ------------------------------------------------------------

def test_size_band_medium_500mb(tmp_path, monkeypatch):
    def fake_stat(self, **kw):
        return NS(st_size=300 * 1024 * 1024)
    monkeypatch.setattr(type(_pkg(tmp_path)), "stat", fake_stat)
    rep = _drive(tmp_path, monkeypatch)
    c = _check(rep, "Paket Boyutu")
    assert c.score == 7 and c.passed is True


def test_size_band_huge_2gb_fails(tmp_path, monkeypatch):
    def fake_stat(self, **kw):
        return NS(st_size=2 * 1024 * 1024 * 1024)
    monkeypatch.setattr(type(_pkg(tmp_path)), "stat", fake_stat)
    rep = _drive(tmp_path, monkeypatch)
    c = _check(rep, "Paket Boyutu")
    assert c.score == 1 and c.passed is False


def _file_count_case(count, rc=0):
    def safe(cmd, timeout=0):
        if cmd[:2] == ["tar", "xf"]:
            return NS(returncode=0, stdout="")
        if rc != 0:
            return NS(returncode=rc, stdout="")
        return NS(returncode=0, stdout="\n".join(f"f{i}" for i in range(count)))
    return safe


def test_file_count_bands(tmp_path, monkeypatch):
    for count, expected in ((999, 10), (4999, 7), (25000, 1)):
        rep = _drive(tmp_path, monkeypatch, safe=_file_count_case(count))
        c = _check(rep, "Dosya Sayısı")
        assert c.score == expected, count


def test_file_count_tar_fail_neutral(tmp_path, monkeypatch):
    rep = _drive(tmp_path, monkeypatch, safe=_file_count_case(0, rc=1))
    c = _check(rep, "Dosya Sayısı")
    assert c.score == 5 and "Sayılamadı" in c.detail


def test_compression_ratio_branch(tmp_path, monkeypatch):
    rep = _drive(tmp_path, monkeypatch,
                 safe=_file_count_case(50))  # kucuk liste -> dusuk oran
    c = _check(rep, "Sıkıştırma Oranı")
    assert c.max_score == 5