# -*- coding: utf-8 -*-
"""Dal-kesen (branch-cutting) unit testler — ``core.dep_resolver._parse_dep_string``.

Hedef: ``pkgforge/core/dep_resolver.py:63`` module-level ``_parse_dep_string`` (13 satır).
'dep_str' → (name, version_constraint) ayrıştırmasının TÜM dalları kesilir:

  B1  dep_str.strip()                         — baş/son boşluk-yiyici
  B2-B6  op in [">=","<=",">","<=","<","="]   — operatör-arama döngüsü (5 dal)
  B7  len(parts) == 2                         — split-sonucu-iki-parça (her-zaman-doğru)
  B8  parts[0].strip() truthy                 — isim-boş-değil-kontrolü
  B9  return dep_str, ""                      — operatör-yok-fallback'i

Ek-kesimler: operatör-önceliği (döngü-sırası > konum), sadece-ilk-split
(maxsplit=1), iç-boşluk-korunması, unicode isimler, ve girdi-türü sınırları.

Disiplin (görev-kuralları):
  • SADECE YENİ DOSYA — production'a DOKUNULMADI.
  • Saf in-memory; dış ağ/HTTP/DB/pacman/AUR çağrısı YOK (sadece string-mantık).
"""

import pytest

from core.dep_resolver import _parse_dep_string


# ──────────────────────── B9: operatör-YOK fallback-dalı ────────────────────────
@pytest.mark.parametrize("dep", ["foo", "libfoo", "pkg-name", "pkg_name", "linux"])
def test_plain_name_no_operator(dep):
    """Operatör-yok: isim-olduğu-gibi, sürüm-kısıtı boş-döner (B9)."""
    name, ver = _parse_dep_string(dep)
    assert (name, ver) == (dep, "")


# ──────────────────── B2-B6: beş operatörün her biri eşleşince ────────────────────
@pytest.mark.parametrize("op", [">=", "<=", ">", "<", "="])
def test_each_operator_parsed(op):
    """Her operatör bulununca (name, op+version) döner; operatör KORUNUR."""
    name, ver = _parse_dep_string("foo" + op + "2.0")
    assert name == "foo"
    assert ver == op + "2.0"


# ──────────────────────────── B1: strip() dalı ────────────────────────────
@pytest.mark.parametrize("dep", ["  foo>=2.0", "foo>=2.0  ", "\tfoo>=2.0\t",
                                 " \n foo >= 2.0 \n "])
def test_outer_whitespace_stripped(dep):
    """Baş/son boşluk (tab/newline dahil) yenir ama operatör-kararını-bozmaz."""
    assert _parse_dep_string(dep) == ("foo", ">=2.0")


@pytest.mark.parametrize("dep,expected", [
    ("foo  bar>=2", ("foo  bar", ">=2")),      # iç-boşluk KORUNUR
    ("foo\tbar>=2", ("foo\tbar", ">=2")),      # iç-tab KORUNUR
])
def test_internal_whitespace_preserved(dep, expected):
    """SINIR: strip() SADECE baş/son-u-yer; iç-boşluk-isimde-kalır."""
    assert _parse_dep_string(dep) == expected


@pytest.mark.parametrize("dep,expected", [
    ("foo >=  2.0", ("foo", ">=2.0")),
    ("foo >= 2.0  ", ("foo", ">=2.0")),
    ("foo>=   2.0  ", ("foo", ">=2.0")),
])
def test_version_part_is_stripped(dep, expected):
    """Sürüm-kısmının baş/son boşluğu da-yenir (parts[1].strip())."""
    assert _parse_dep_string(dep) == expected


def test_version_inner_content_preserved():
    """SINIR: sürümün İÇ-boşluğu/sonrası aynen-kalır — yalnız-baş/son-strip."""
    assert _parse_dep_string("foo >= 2.0 : baz") == ("foo", ">=2.0 : baz")


# ──────────────── ÖNCELİK: döngü-sırası > string-içi-konum ────────────────
@pytest.mark.parametrize("dep,expected", [
    ("foo<>=2.0", ("foo<", ">=2.0")),    # "<" daha-sol-da-AMA ">=" döngüde-önce
    ("a>b<=1", ("a>b", "<=1")),          # "<=" döngüde-önce-olmasa-da "> 'dan-önce
    ("a>=b<=c", ("a", ">=b<=c")),        # ilk-eşleşen-operatör-çoklu-kalıbı
])
def test_operator_precedence_is_loop_order(dep, expected):
    """SINIR: operatör-önceliği string-içi-KONUMA-göre-değil,
    [">=","<=",">","<","="] döngü-SIRASINA-göredir (belge-değeri)."""
    assert _parse_dep_string(dep) == expected


@pytest.mark.parametrize("dep,expected", [
    ("foo>=1<2", ("foo", ">=1<2")),
    ("a=b=c", ("a", "=b=c")),
    ("x>1>2", ("x", ">1>2")),
])
def test_only_first_split_applies(dep, expected):
    """SINIR: split(op, 1) — SADECE ilk-operatör-bölünür; gerisi sürümde-kalır."""
    assert _parse_dep_string(dep) == expected


# ──────────────── B8: operatör-var-AMA-isim-boş (parts[0] falsy) ────────────────
@pytest.mark.parametrize("dep", [">2.0", "<2.0", "=2.0"])
def test_leading_single_char_operator_falls_back(dep):
    """SINIR: '>2.0' gibi tek-karakter-operatörle-başlayan girdi — o operatörün
    dalı isim-boş-verir, sonra başka-operatör-eşleşmez → (tüm-string, '') fallback."""
    assert _parse_dep_string(dep) == (dep, "")


@pytest.mark.parametrize("dep,expected", [(">2.0", (">2.0", "")),
                                          ("<2.0", ("<2.0", "")),
                                          ("=2.0", ("=2.0", ""))])
def test_leading_operator_never_produces_empty_name(dep, expected):
    """B8 koruması: operatör-önekli girdilerde isim ASLA boş-dönmez."""
    name, _ = _parse_dep_string(dep)
    assert name != ""
    assert _parse_dep_string(dep) == expected


@pytest.mark.parametrize("dep,expected", [(">=", (">", "=")),
                                          ("<=", ("<", "=")),
                                          (">=2.0", (">", "=2.0")),
                                          ("<=2.0", ("<", "=2.0"))])
def test_two_char_operator_falls_through_to_equals_branch(dep, expected):
    """SINIR (tuzaq): '>=2.0' — '>=' dalı isim-boş-verip-atlanır, '<=' ve '>'
    da-boş-verir, EN-SON '=' dalı '>=' içinden-bölünür → ('>', '=2.0').
    Yani iki-karakterli-operatör-önceliği BEKLENEN-sonucu-VERMEZ; operatörün
    'gövdesi' isim-sanılır. Dokümante-bug-benzeri-davranış."""
    assert _parse_dep_string(dep) == expected


@pytest.mark.parametrize("dep", [">", "<", "="])
def test_bare_single_char_operator_returns_itself_as_name(dep):
    """Yalnız-tek-karakter-operatör → dal-isimsiz → fallback: (kendisi, '')."""
    assert _parse_dep_string(dep) == (dep, "")


# ───────────────────────── Boş/whitespace girdi-dalları ─────────────────────────
@pytest.mark.parametrize("dep", ["", " ", "   ", "\t\n "])
def test_empty_and_whitespace_only(dep):
    """Boş veya tamamen-boşluk girdi → ('', '') döner."""
    assert _parse_dep_string(dep) == ("", "")


@pytest.mark.parametrize("dep,expected", [("foo>=", ("foo", ">=")),
                                          ("pkg=", ("pkg", "="))])
def test_operator_with_empty_version(dep, expected):
    """SINIR: isim-var-AMA operatörden-sonra-sürüm-yok → (name, op) döner."""
    assert _parse_dep_string(dep) == expected


# ───────────────────── Unicode & gerçek-dünya Arch biçimleri ─────────────────────
@pytest.mark.parametrize("dep,expected", [
    ("paket adı>=1.0", ("paket adı", ">=1.0")),      # Türkçe-isim + iç-boşluk
    ("kütüphane=2", ("kütüphane", "=2")),            # unicode-isim, '=' operatör
    ("paket>=1,0", ("paket", ">=1,0")),              # virgül-sürüm koruması
])
def test_unicode_dep_names(dep, expected):
    """Unicode (Türkçe) isimler düzgün-ayrıştırılır — hiçbir-karakter-düşmez."""
    assert _parse_dep_string(dep) == expected


@pytest.mark.parametrize("dep,expected", [
    ("pkg>=1:2", ("pkg", ">=1:2")),                  # Arch epoch
    ("pkg>=1.2.3-1", ("pkg", ">=1.2.3-1")),          # tam pkgver-pkgrel
])
def test_real_arch_version_forms(dep, expected):
    """Gerçek Arch sürüm-biçimleri (epoch/rel) sürüm-kısmında aynen-kalır."""
    assert _parse_dep_string(dep) == expected


# ─────────────────────────── Production sınırları ───────────────────────────
@pytest.mark.parametrize("bad,exc", [(123, AttributeError), (None, AttributeError),
                                     (1.5, AttributeError)])
def test_non_string_input_raises(bad, exc):
    """SINIR: str-dışı girdi — .strip() yok → AttributeError (str-zorunlu)."""
    with pytest.raises(exc):
        _parse_dep_string(bad)


def test_bytes_input_raises_typeerror():
    """SINIR: bytes girdi — .strip() çalışır-AMA 'op in bytes' → TypeError
    (bytes ile str-operatör-karşılaştırılamaz)."""
    with pytest.raises(TypeError):
        _parse_dep_string(b"foo>=1")


@pytest.mark.parametrize("dep", ["foo", "foo>=2.0", ">=2.0"])
def test_return_is_two_tuple_of_str(dep):
    """Sözleşme: dönüş (str, str) tuple'ı — her-zaman-2-eleman."""
    result = _parse_dep_string(dep)
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert all(isinstance(part, str) for part in result)


@pytest.mark.parametrize("dep", ["foo>=2.0", "libx>=1", "pkg<2"])
def test_result_is_reconstructable(dep):
    """name + version tekrar-birleştirilince strip()-sonrası girdiye-eşittir."""
    name, ver = _parse_dep_string(dep)
    assert name + ver == dep.strip()
