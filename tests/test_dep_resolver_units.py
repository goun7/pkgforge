"""Coverage itmesi — core/dep_resolver.py saf fonksiyonlar."""
from __future__ import annotations

from core.dep_resolver import (
    DepStatus,
    ResolveReport,
    _parse_dep_string,
    install_aur_packages,
    is_elf_file,
    parse_needed_sonames,
    parse_objdump_sonames,
    resolve_dependencies,
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


def _ns(code, out="", err=""):
    from types import SimpleNamespace as NS
    return NS(returncode=code, stdout=out, stderr=err)

def test_pacman_guards(monkeypatch):
    import core.dep_resolver as DR
    monkeypatch.setattr(DR.shutil, "which", lambda n: None)
    assert DR._check_pacman("x") == (False, "")
    assert DR._check_pacman_installed("x") == (False, "")
    assert DR._aur_helper() is None

    paths = {"pacman": "/p", "paru": "/paru"}
    monkeypatch.setattr(DR.shutil, "which", lambda n: paths.get(n))
    monkeypatch.setattr(DR, "safe_run", lambda c, timeout=None: _ns(0, out="Version : 1.2"))
    ok, ver = DR._check_pacman("x")
    assert ok is True and ver == "1.2"
    ok2, ver2 = DR._check_pacman_installed("x")
    assert ok2 is True and ver2 == "1.2"
    assert DR._aur_helper() == "paru"

def test_resolve_chain(monkeypatch):
    import core.dep_resolver as DR
    state = {"mode": "installed"}

    def fake_pacman(cmd, timeout=None):
        if cmd[1] == "-Qi":
            return _ns(0 if state["mode"] == "installed" else 1, out="Version : 9.9")
        return _ns(0 if state["mode"] == "repo" else 1, out="Version : 8.8")
    monkeypatch.setattr(DR.shutil, "which", lambda n: "/p")
    monkeypatch.setattr(DR, "safe_run", fake_pacman)

    r1 = resolve_dependencies(["gtk3"])
    assert r1.resolved_count == 1 and r1.deps[0].source == "pacman (installed)"

    state["mode"] = "repo"
    r2 = resolve_dependencies(["gtk3"], include_installed=False)
    assert r2.deps[0].source == "pacman (official)"

    state["mode"] = "none"
    monkeypatch.setattr(DR, "_check_aur", lambda n: (True, "3.1"))
    r3 = resolve_dependencies(["sadece-aur"], include_installed=False)
    d = r3.deps[0]
    assert d.source == "aur" and d.aur_package == "sadece-aur" and d.resolved

    monkeypatch.setattr(DR, "_check_aur", lambda n: (False, ""))
    r4 = resolve_dependencies(["yok1", "virtual/ozel", "yok2"], include_installed=False)
    assert r4.missing_count == 2 and r4.all_resolved is False
    assert len(r4.deps) == 2  # virtual atlandi

def test_check_aur_cache_and_helper(monkeypatch):
    import core.dep_resolver as DR
    class FakeCache:
        def get_or_fetch(self, kind, name, fn):
            return {"resultcount": 1, "results": [{"Name": name, "Version": "5.0"}]}
    monkeypatch.setattr("core.offline_cache.get_cache", lambda: FakeCache())
    ok, ver = DR._check_aur("demo")
    assert ok is True and ver == "5.0"

    def bad_cache():
        raise RuntimeError("ag yok")
    monkeypatch.setattr("core.offline_cache.get_cache", bad_cache)
    monkeypatch.setattr(DR.shutil, "which", lambda n: None)
    assert DR._check_aur("demo") == (False, "")

    monkeypatch.setattr(DR.shutil, "which", lambda n: "/usr/bin/yay")
    monkeypatch.setattr(DR, "safe_run", lambda c, timeout=None: _ns(0, out="Repo : aur" + chr(10) + "Version : 7"))
    ok3, ver3 = DR._check_aur("demo2")
    assert ok3 is True and ver3 == "7"

def test_install_aur_packages(monkeypatch):
    import core.dep_resolver as DR
    monkeypatch.setattr(DR, "_aur_helper", lambda: None)
    ok, msg = install_aur_packages(["a"])
    assert ok is False and "bulunamad" in msg

    seen = []
    monkeypatch.setattr(DR, "_aur_helper", lambda: "paru")
    monkeypatch.setattr(DR, "safe_run", lambda c, timeout=None: seen.append(c) or _ns(0))
    ok2, msg2 = install_aur_packages(["a", "b"])
    assert ok2 is True and "2 paket kuruldu" in msg2
    assert "--needed" in seen[0]

    monkeypatch.setattr(DR, "safe_run", lambda c, timeout=None: _ns(1, err="hata"))
    ok3, msg3 = install_aur_packages(["c"], aur_helper="yay")
    assert ok3 is False and "başarısız" in msg3