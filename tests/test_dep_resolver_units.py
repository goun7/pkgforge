"""Coverage itmesi — core/dep_resolver.py saf fonksiyonlar."""
from __future__ import annotations

from core.dep_resolver import (
    DepStatus,
    ResolveReport,
    _parse_dep_string,
    is_elf_file,
    parse_needed_sonames,
    parse_objdump_sonames,
)


def test_parse_dep_string_operators():
    assert _parse_dep_string("foo>=2.0") == ("foo", ">=2.0")
    assert _parse_dep_string("bar<=1") == ("bar", "<=1")
    assert _parse_dep_string("baz>3") == ("baz", ">3")
    assert _parse_dep_string("q<2") == ("q", "<2")
    assert _parse_dep_string("w=5") == ("w", "=5")


def test_parse_dep_string_plain_and_spaces():
    assert _parse_dep_string("sade") == ("sade", "")
    assert _parse_dep_string("  bosluk>=9  ") == ("bosluk", ">=9")


def test_parse_needed_sonames_readelf():
    out = chr(10).join([
        "Dynamic Section at 0x0 contains 2 entries:",
        " 0x01 (NEEDED)             Shared library: [libfoo.so.1]",
        " 0x01 (NEEDED)             Shared library: [libbar.so.2]",
    ])
    assert parse_needed_sonames(out) == ["libfoo.so.1", "libbar.so.2"]


def test_parse_objdump_sonames():
    out = chr(10).join([
        "              Version References:",
        "  NEEDED               libone.so.0",
        "  NEEDED               libtwo.so.3",
    ])
    assert parse_objdump_sonames(out) == ["libone.so.0", "libtwo.so.3"]


def test_is_elf_file(tmp_path):
    p = tmp_path / "bin"
    p.write_bytes(bytes([0x7F]) + b"ELF" + b"\x02\x01")
    assert is_elf_file(p) is True
    t = tmp_path / "txt"
    t.write_bytes(b"plain text")
    assert is_elf_file(t) is False
    assert is_elf_file(tmp_path / "yok") is False


def test_resolve_report_summary_with_missing():
    ok = DepStatus(name="a", resolved=True)
    bad = DepStatus(name="b", resolved=False, required_version=">=2",
                    source="aur")
    rep = ResolveReport(deps=[ok, bad], all_resolved=False, total=2,
                        resolved_count=1, missing_count=1)
    s = rep.summary()
    assert "Toplam bağımlılık: 2" in s
    assert "Eksik:             1" in s
    assert "b>=2" in s and "aur" in s


def test_resolve_report_summary_clean():
    rep = ResolveReport(total=1, resolved_count=1, missing_count=0)
    s = rep.summary()
    assert "Eksik bağımlılıklar" not in s