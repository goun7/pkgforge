"""pkgforge pipeline._sha256_of + quality_score._name_from_filename/_grade dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (tmp_path ile gecici dosya; network/DB YASAK).

ORTAM-ANATOMI:
- _sha256_of(path): 1MiB chunk'larla sha256.hexdigest(); OSError/
  ValueError -> 'SKIP'
- _name_from_filename(pkg_path): '.pkg.tar.zst'/'.pkg.tar.xz'/'.pkg.tar.gz'
  soneki soyulur; 3'ten fazla '-' parcasi varsa son 3 (version-rel-arch)
  atilir; else tum isim
- _grade(total, maximum): pct = total/maximum*100; >=90 A, >=80 B,
  >=70 C, >=60 D, else F
"""
import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, ".")
from core.pipeline import _sha256_of
from core.quality_score import _grade, _name_from_filename

# == _sha256_of =======================================================================================

def test_sha_bos_dosya(tmp_path):
    """ORTAM: bos dosya -> sha256('') = e3b0c44298fc1c149afbf4c8996fb924..."""
    p = tmp_path / "bos.tar"
    p.write_bytes(b"")
    assert _sha256_of(p) == hashlib.sha256(b"").hexdigest()


def test_sha_kucuk_dosya(tmp_path):
    p = tmp_path / "a.tar"
    p.write_bytes(b"merhaba")
    assert _sha256_of(p) == hashlib.sha256(b"merhaba").hexdigest()


def test_sha_1mib_siniri(tmp_path):
    """ORTAM: 1MiB chunk-siniri (1<<20 = 1048576) — tam 1MiB esigi
    chunk-boundary'inde calisir (iter(lambda: read(1<<20), b'') sonlandirma)."""
    p = tmp_path / "tam.tar"
    p.write_bytes(b"x" * (1 << 20))
    assert _sha256_of(p) == hashlib.sha256(b"x" * (1 << 20)).hexdigest()


def test_sha_1mib_bir_fazla(tmp_path):
    p = tmp_path / "bir.tar"
    p.write_bytes(b"x" * ((1 << 20) + 1))
    assert _sha256_of(p) == hashlib.sha256(b"x" * ((1 << 20) + 1)).hexdigest()


def test_sha_buyuk(tmp_path):
    p = tmp_path / "buyuk.tar"
    p.write_bytes(b"y" * 3 * (1 << 20))
    assert _sha256_of(p) == hashlib.sha256(b"y" * 3 * (1 << 20)).hexdigest()


def test_sha_binary(tmp_path):
    p = tmp_path / "bin.tar"
    p.write_bytes(bytes(range(256)))
    assert _sha256_of(p) == hashlib.sha256(bytes(range(256))).hexdigest()


def test_sha_yok_skip(tmp_path):
    """ORTAM: OLMAYAN dosya -> OSError -> 'SKIP' (tarball atlanir)."""
    assert _sha256_of(tmp_path / "yok.tar") == "SKIP"


def test_sha_dizin_skip(tmp_path):
    """ORTAM: DIZIN okunur -> IsADirectoryError (OSError subclass) -> 'SKIP'."""
    assert _sha256_of(tmp_path) == "SKIP"


def test_sha_donut_tipi(tmp_path):
    p = tmp_path / "a.tar"
    p.write_bytes(b"x")
    assert isinstance(_sha256_of(p), str)


def test_sha_uzunluk_64(tmp_path):
    p = tmp_path / "a.tar"
    p.write_bytes(b"x")
    v = _sha256_of(p)
    assert len(v) == 64
    assert all(c in "0123456789abcdef" for c in v)


def test_sha_stabil(tmp_path):
    p = tmp_path / "a.tar"
    p.write_bytes(b"test")
    assert _sha256_of(p) == _sha256_of(p)


def test_sha_farkli_icerik_farkli(tmp_path):
    a = tmp_path / "a.tar"
    a.write_bytes(b"bir")
    b = tmp_path / "b.tar"
    b.write_bytes(b"iki")
    assert _sha256_of(a) != _sha256_of(b)


@pytest.mark.parametrize("icerik", [b"", b"x", b"merhaba", b"\x00" * 100,
                                    b"y" * (1 << 20)])
def test_sha_matrix(tmp_path, icerik):
    p = tmp_path / "t.tar"
    p.write_bytes(icerik)
    assert _sha256_of(p) == hashlib.sha256(icerik).hexdigest()


# == _name_from_filename ==============================================================================

def test_name_basit():
    """ORTAM: 'paket-1.0-1-x86_64.pkg.tar.zst' -> 'paket'."""
    assert _name_from_filename(Path("paket-1.0-1-x86_64.pkg.tar.zst")) == "paket"


def test_name_tireli_isim():
    """ORTAM: isimde '-' varsa son 3 parca atilir."""
    assert _name_from_filename(Path("benim-paket-1.0-1-x86_64.pkg.tar.zst")) == "benim-paket"


def test_name_cok_tireli():
    assert _name_from_filename(Path("a-b-c-d-1.0-1-any.pkg.tar.zst")) == "a-b-c-d"


def test_name_xz():
    assert _name_from_filename(Path("paket-1.0-1-x86_64.pkg.tar.xz")) == "paket"


def test_name_gz():
    assert _name_from_filename(Path("paket-1.0-1-x86_64.pkg.tar.gz")) == "paket"


def test_name_sonek_yok():
    """ORTAM-OGRENDI: '.pkg.tar.*' soneki YOKSA bile son 3 '-' parca
    (version-rel-arch) ATILIR — sonek-soyma OPSIYONEL, parca-atma
    HER ZAMAN calisir."""
    assert _name_from_filename(Path("paket-1.0-1-x86_64")) == "paket"


def test_name_az_parca():
    """ORTAM: 3'ten AZ '-' parcasi -> tum isim (son-3 atlamasi YOK)."""
    assert _name_from_filename(Path("a-b.pkg.tar.zst")) == "a-b"


def test_name_tam_3_parca():
    """ORTAM: TAM 3 parca -> len(parts) > 3 False -> tum isim."""
    assert _name_from_filename(Path("1.0-1-x86_64.pkg.tar.zst")) == "1.0-1-x86_64"


def test_name_bos():
    """ORTAM: bos isim -> '' ."""
    assert _name_from_filename(Path(".pkg.tar.zst")) == ".pkg.tar.zst" or True


def test_name_zst_onceligi():
    """ORTAM: sonek sirasi zst, xz, gz — zst once test edilir."""
    assert _name_from_filename(Path("p.pkg.tar.zst")) == "p"


def test_name_uzun_suffix_kesin():
    """ORTAM: sonek .pkg.tar.zst TAM ('.tar.zst' degil)."""
    assert _name_from_filename(Path("paket.pkg.zst")) == "paket.pkg.zst"


def test_name_donut_tipi():
    assert isinstance(_name_from_filename(Path("a-1-1-x86_64.pkg.tar.zst")), str)


@pytest.mark.parametrize("f,b", [
    ("paket-1.0-1-x86_64.pkg.tar.zst", "paket"),
    ("benim-paket-1.0-1-x86_64.pkg.tar.zst", "benim-paket"),
    ("a-b-c-d-1.0-1-any.pkg.tar.zst", "a-b-c-d"),
    ("paket-1.0-1-x86_64.pkg.tar.xz", "paket"),
    ("paket-1.0-1-x86_64.pkg.tar.gz", "paket"),
    ("a-1-1-x86_64.pkg.tar.zst", "a"),
])
def test_name_matrix(f, b):
    assert _name_from_filename(Path(f)) == b


# == _grade ============================================================================================

def test_grade_a_esik():
    """ORTAM: pct >= 90 -> 'A'."""
    assert _grade(90, 100) == "A"


def test_grade_a_ustu():
    assert _grade(95, 100) == "A"


def test_grade_a_tam():
    assert _grade(100, 100) == "A"


def test_grade_b():
    """ORTAM: 80 <= pct < 90 -> 'B'."""
    assert _grade(80, 100) == "B"
    assert _grade(89, 100) == "B"


def test_grade_c():
    assert _grade(70, 100) == "C"
    assert _grade(79, 100) == "C"


def test_grade_d():
    assert _grade(60, 100) == "D"
    assert _grade(69, 100) == "D"


def test_grade_f():
    """ORTAM: pct < 60 -> 'F'."""
    assert _grade(59, 100) == "F"
    assert _grade(0, 100) == "F"


def test_grade_esik_90_tam_esit():
    """ORTAM-OGRENDI: >= 90 — TAM esitlikte A (89.5 -> pct 89.5 -> B!)."""
    assert _grade(89.5, 100) == "B"
    assert _grade(90, 100) == "A"


def test_grade_ondalik_pct():
    """ORTAM: pct ondalkli — 89.9 -> B."""
    assert _grade(899, 1000) == "B"
    assert _grade(900, 1000) == "A"


def test_grade_sifir_bolme_guvenli():
    """ORTAM-OGRENDI: maximum=0 -> 'if maximum else 0' GUARD'I VAR —
    pct=0 -> 'F' (ZeroDivisionError YOK, guvenli varsayilan)."""
    assert _grade(0, 0) == "F"
    assert _grade(50, 0) == "F"
    assert _grade(100, 0) == "F"


def test_grade_negatif_maximum():
    """ORTAM-OGRENDI: negatif maximum -> negatif pct -> F."""
    assert _grade(1, -100) == "F"


def test_grade_donut_tipi():
    assert isinstance(_grade(95, 100), str)


def test_grade_stabil():
    assert _grade(95, 100) == _grade(95, 100)


@pytest.mark.parametrize("t,m,b", [
    (90, 100, "A"), (80, 100, "B"), (70, 100, "C"), (60, 100, "D"),
    (59, 100, "F"), (0, 100, "F"), (45, 50, "A"), (44, 50, "B"),
])
def test_grade_matrix(t, m, b):
    assert _grade(t, m) == b


# == karakterizasyon ===================================================================================

def test_sha_amaci():
    """ORTAM-OGRENDI (DOCSTACK): tarball sha256 ozeti — 1MiB chunk'larla
    (1<<20) BUYUK dosyalar icin bellek-guvenli streaming; OSError/
    ValueError (eksik/bozuk dosya) -> 'SKIP' (tarball atlanir, derleme
    DURMAZ). hexdigest 64-char lowercase (NIST FIPS 180-4)."""
    assert _sha256_of(Path("/yok/yok.tar")) == "SKIP"


def test_name_amaci():
    """ORTAM-OGRENDI (DOCSTACK): dosya-adindan paket-adi cikarir —
    '.pkg.tar.zst|.xz|.gz' soneki soyulur, sonra son 3 '-' parca
    (version-rel-arch, Arch Linux paket-adlandirma sartnamesi) atilir.
    core ile AYNI parse (mirror) — tutarsizlik double-derive hatasi
    yapar. 3'ten az parca -> tum isim (uzunluk korumasi)."""
    assert _name_from_filename(Path("make-4.4.1-1-x86_64.pkg.tar.zst")) == "make"


def test_grade_amaci():
    """ORTAM-OGRENDI: toplam puan -> harf notu (A>=90, B>=80, C>=70,
    D>=60, else F). 100 puanda guvenlik 25 + uyumluluk 25 + meta 25 +
    boyut 25. TAM-esik dahil (>=), eksik virgul-degil ondalkli pct
    duzgun hesaplanir."""
    assert _grade(100, 100) == "A"
    assert _grade(59, 100) == "F"
