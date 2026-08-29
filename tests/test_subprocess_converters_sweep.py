"""Coverage itmesi — core/subprocess_converters.py DEB/RPM akislari."""
from __future__ import annotations

import io
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import core.subprocess_converters as SC


def _araclar():
    return NS(ar="/usr/bin/ar", bsdtar="/usr/bin/bsdtar",
              makepkg="/usr/bin/makepkg",
              rpm2cpio="/usr/bin/rpm2cpio")


def _meta(**kw):
    taban = {"name": "Demo App!", "version": "2:1.0-1deb", "arch_mapped": "",
             "description": None, "url": None,
             "depends": ["libc6", "libgtk"]}
    taban.update(kw)
    return NS(**taban)


class _Kayit:
    def __init__(self):
        self.satirlar = []
        self.bitisler = []

    def bagla(self, conv):
        conv.output_line.connect(lambda m: self.satirlar.append(m))
        conv.finished.connect(lambda ok, msg, p: self.bitisler.append((ok, msg, p)))


def _guvenlik_modulu(escape=None, hatalar=None, uyarilar=None):
    return NS(
        check_symlink_attacks=lambda d: (escape or []),
        check_dangerous_files=lambda d: ((hatalar or []), (uyarilar or [])),
        build_sandbox_cmd=lambda cmd, cwd, tools: (cmd[0], cmd[1:]),
    )


def _popen_sahte(satir=("derleniyor",), rc=0, yaz=None):
    def sahte(cmd, **kw):
        if yaz and "env" in kw:
            hedef = Path(kw["env"]["PKGDEST"])
            hedef.mkdir(parents=True, exist_ok=True)
            (hedef / yaz).write_bytes(b"paket")
        out = iter([s + "\n" for s in satir])
        return NS(stdout=out, stderr=b"", pid=1,
                  wait=lambda timeout=None: None,
                  communicate=lambda timeout=None: (b"", b""),
                  returncode=rc)
    return sahte


def _temel_yamalar(monkeypatch, *, guvenlik, popen_rc=0, popen_yaz=None,
                   cozulen=("gtk3",), analiz_hata=None, meta=None):
    analiz = None if meta is not None else (
        (lambda p, t: (_ for _ in ()).throw(RuntimeError("analiz patladi")))
        if analiz_hata else (lambda p, t: _meta()))
    gercek_pa = __import__("core.package_analyzer",
                           fromlist=["PackageMetadata"])
    monkeypatch.setitem(sys.modules, "core.package_analyzer",
                        NS(analyze_package=analiz
                           or (lambda p, t: meta),
                           PackageMetadata=gercek_pa.PackageMetadata))
    monkeypatch.setitem(sys.modules, "core.security", guvenlik)
    monkeypatch.setitem(sys.modules, "core.dep_resolver",
                        NS(resolve_runtime_dependencies=lambda *a, **k:
                           list(cozulen)))
    monkeypatch.setattr(SC, "subprocess",
                        NS(Popen=_popen_sahte(rc=popen_rc, yaz=popen_yaz),
                           PIPE=-1, STDOUT=-2))


# --- Signal ---------------------------------------------------------------------

def test_signal_connect_emit_disconnect():
    s = SC.Signal()
    alinan = []
    def dinle(*a):
        alinan.append(a)
    s.connect(dinle)
    s.emit("x", 1)
    s.disconnect(dinle)
    s.emit("y")
    assert alinan == [("x", 1)]


# --- DEB ------------------------------------------------------------------------

def test_deb_symlink_attack_aborts(monkeypatch, tmp_path):
    conv = SC.NativeDebConverterSubprocess(_araclar())
    kayit = _Kayit(); kayit.bagla(conv)
    monkeypatch.setattr(conv, "_extract_data_tar", lambda p, d: None)
    _temel_yamalar(monkeypatch,
                   guvenlik=_guvenlik_modulu(escape=["../kotu"]))
    conv._do_convert(tmp_path / "x.deb", tmp_path)
    ok, msg, _p = kayit.bitisler[-1]
    assert ok is False and "symlink" in msg


def test_deb_dangerous_file_aborts(monkeypatch, tmp_path):
    conv = SC.NativeDebConverterSubprocess(_araclar())
    kayit = _Kayit(); kayit.bagla(conv)
    monkeypatch.setattr(conv, "_extract_data_tar", lambda p, d: None)
    _temel_yamalar(monkeypatch,
                   guvenlik=_guvenlik_modulu(hatalar=["etc/passwd"],
                                             uyarilar=["buyuk dosya"]))
    conv._do_convert(tmp_path / "x.deb", tmp_path)
    ok, msg, _p = kayit.bitisler[-1]
    assert ok is False and "tehlikeli" in msg
    assert any("⚠" in s for s in kayit.satirlar)


def test_deb_happy_path(monkeypatch, tmp_path):
    conv = SC.NativeDebConverterSubprocess(_araclar())
    kayit = _Kayit(); kayit.bagla(conv)
    monkeypatch.setattr(conv, "_extract_data_tar", lambda p, d: None)
    _temel_yamalar(monkeypatch,
                   guvenlik=_guvenlik_modulu(uyarilar=["kocaman"]),
                   popen_rc=0, popen_yaz="demo-app-1.0-1-x.pkg.tar.zst")
    conv._do_convert(tmp_path / "x.deb", tmp_path)
    ok, _msg, paket = kayit.bitisler[-1]
    assert ok is True and paket is not None
    assert (tmp_path / "native_build" / "PKGBUILD").is_file()


def test_deb_makepkg_failure(monkeypatch, tmp_path):
    conv = SC.NativeDebConverterSubprocess(_araclar())
    kayit = _Kayit(); kayit.bagla(conv)
    monkeypatch.setattr(conv, "_extract_data_tar", lambda p, d: None)
    _temel_yamalar(monkeypatch, guvenlik=_guvenlik_modulu(),
                   popen_rc=2)
    conv._do_convert(tmp_path / "x.deb", tmp_path)
    ok, msg, _p = kayit.bitisler[-1]
    assert ok is False and "makepkg başarısız" in msg


def test_deb_no_pkg_found(monkeypatch, tmp_path):
    conv = SC.NativeDebConverterSubprocess(_araclar())
    kayit = _Kayit(); kayit.bagla(conv)
    monkeypatch.setattr(conv, "_extract_data_tar", lambda p, d: None)
    _temel_yamalar(monkeypatch, guvenlik=_guvenlik_modulu(),
                   popen_rc=0)                      # hic paket yazilmadi
    conv._do_convert(tmp_path / "x.deb", tmp_path)
    ok, msg, _p = kayit.bitisler[-1]
    assert ok is False and "bulunamadı" in msg


def test_deb_analyzer_exception(monkeypatch, tmp_path):
    conv = SC.NativeDebConverterSubprocess(_araclar())
    kayit = _Kayit(); kayit.bagla(conv)
    _temel_yamalar(monkeypatch, guvenlik=_guvenlik_modulu(),
                   analiz_hata=True)
    conv._do_convert(tmp_path / "x.deb", tmp_path)
    ok, msg, _p = kayit.bitisler[-1]
    assert ok is False and "Dönüşüm hatası" in msg


# --- DEB yardimcilari -----------------------------------------------------------

def test_deb_extract_data_tar_listing_and_missing(monkeypatch, tmp_path):
    conv = SC.NativeDebConverterSubprocess(_araclar())

    def sahte_popen(cmd, **kw):
        if "ar" in str(cmd[0]) and cmd[1] == "p":
            return NS(stdout=io.BytesIO(b"akis"), stderr=b"",
                      wait=lambda timeout=None: None,
                      communicate=lambda timeout=None: (b"", b""),
                      returncode=0, pid=2)
        return NS(stdout=io.BytesIO(), stderr=b"",
                  communicate=lambda timeout=None: (b"", b""),
                  returncode=0, pid=3)
    monkeypatch.setattr(SC, "subprocess",
                        NS(Popen=sahte_popen, PIPE=-1))
    monkeypatch.setattr(SC, "safe_run",
                        lambda cmd, timeout=0: NS(returncode=0,
                                                  stdout="data.tar.xz\ncontrol.tar.gz\n"))
    conv._extract_data_tar(tmp_path / "a.deb", tmp_path)

    monkeypatch.setattr(SC, "safe_run",
                        lambda cmd, timeout=0: NS(returncode=0, stdout="sadece-control\n"))
    with pytest.raises(RuntimeError, match="data.tar"):
        conv._extract_data_tar(tmp_path / "a.deb", tmp_path)


def test_deb_extract_data_tar_ar_and_tar_failures(monkeypatch, tmp_path):
    """ar/tar başarısızlık yolları RuntimeError'a düşmeli (Faz 12)."""
    conv = SC.NativeDebConverterSubprocess(_araclar())

    def _sahte(rc_ar, rc_tar):
        def sahte(cmd, **kw):
            if "ar" in str(cmd[0]) and cmd[1] == "p":
                return NS(stdout=io.BytesIO(b""), stderr=io.BytesIO(b"ar hatasi"),
                          wait=lambda timeout=None: None,
                          communicate=lambda timeout=None: (b"", b""),
                          returncode=rc_ar, pid=2)
            return NS(stdout=io.BytesIO(), stderr=b"",
                      wait=lambda timeout=None: None,
                      communicate=lambda timeout=None: (b"", b"tar hatasi"),
                      returncode=rc_tar, pid=3)
        return sahte

    monkeypatch.setattr(SC, "safe_run",
                        lambda cmd, timeout=0: NS(returncode=0,
                                                  stdout="data.tar.xz\n"))
    monkeypatch.setattr(SC, "subprocess",
                        NS(Popen=_sahte(3, 0), PIPE=-1))
    with pytest.raises(RuntimeError, match="ar başarısız"):
        conv._extract_data_tar(tmp_path / "a.deb", tmp_path)

    monkeypatch.setattr(SC, "subprocess",
                        NS(Popen=_sahte(0, 4), PIPE=-1))
    with pytest.raises(RuntimeError, match="İçerik çıkarılamadı"):
        conv._extract_data_tar(tmp_path / "a.deb", tmp_path)


def test_deb_generate_pkgbuild_sanitization():
    conv = SC.NativeDebConverterSubprocess(_araclar())
    metin = conv._generate_pkgbuild(_meta(), ["gtk3", "libgl"])
    assert "pkgname='demo-app'" in metin
    assert "pkgver='1.0'" in metin                    # epoch + deb revduzeltme
    assert "arch=('x86_64')" in metin                 # bos -> varsayilan
    assert "'gtk3' 'libgl'" in metin
    assert "converted from DEB" in metin              # aciklama dususu

    ozel = conv._generate_pkgbuild(_meta(name="Ozel^Paket", version="3.1"),
                                   [])
    assert "pkgname='ozel-paket'" in ozel
    assert "pkgver='3.1'" in ozel
    assert "depends=()" in ozel


# --- RPM ------------------------------------------------------------------------

def test_rpm_extraction_failure(monkeypatch, tmp_path):
    conv = SC.RpmConverterSubprocess(_araclar())
    kayit = _Kayit(); kayit.bagla(conv)
    _temel_yamalar(monkeypatch, guvenlik=_guvenlik_modulu(),
                   popen_rc=3, meta=_meta())
    conv._do_convert(tmp_path / "x.rpm", tmp_path)
    ok, msg, _p = kayit.bitisler[-1]
    assert ok is False and "RPM çıkarma başarısız" in msg


def test_rpm_security_branches(monkeypatch, tmp_path):
    for beklenen_msg, guv in [
        ("symlink", _guvenlik_modulu(escape=["/kacis"])),
        ("tehlikeli", _guvenlik_modulu(hatalar=["usr/bin/kotu"])),
    ]:
        conv = SC.RpmConverterSubprocess(_araclar())
        kayit = _Kayit(); kayit.bagla(conv)
        _temel_yamalar(monkeypatch, guvenlik=guv, meta=_meta())
        # cikarma basarili olsun; sonrasinda guvenlik durur
        monkeypatch.setattr(SC, "subprocess",
                            NS(Popen=_popen_sahte(rc=0), PIPE=-1, STDOUT=-2))
        conv._do_convert(tmp_path / "x.rpm", tmp_path)
        ok, msg, _p = kayit.bitisler[-1]
        assert ok is False and beklenen_msg in msg


def test_rpm_happy_path_with_rename(monkeypatch, tmp_path):
    conv = SC.RpmConverterSubprocess(_araclar())
    kayit = _Kayit(); kayit.bagla(conv)
    _temel_yamalar(monkeypatch, guvenlik=_guvenlik_modulu(),
                   popen_rc=0, popen_yaz="demo-1.0-x.pkg.tar.zst",
                   meta=_meta(version="1.0"))
    conv._do_convert(tmp_path / "x.rpm", tmp_path)
    ok, _msg, paket = kayit.bitisler[-1]
    assert ok is True, kayit.bitisler
    assert paket is not None
    assert (tmp_path / "build" / "PKGBUILD").is_file()
    assert (tmp_path / "build" / "src").is_dir()      # pkg_root yeniden adlandi


def test_rpm_analyze_exception(monkeypatch, tmp_path):
    conv = SC.RpmConverterSubprocess(_araclar())
    kayit = _Kayit(); kayit.bagla(conv)
    _temel_yamalar(monkeypatch, guvenlik=_guvenlik_modulu(),
                   analiz_hata=True)
    conv._do_convert(tmp_path / "x.rpm", tmp_path)
    ok, msg, _p = kayit.bitisler[-1]
    assert ok is False and "Dönüşüm hatası" in msg


def test_rpm_generate_pkgbuild_dep_fallback(monkeypatch):
    import config
    monkeypatch.setattr(config, "RPM_DEP_MAP",
                        {"libgtk": "gtk3"}, raising=False)
    monkeypatch.setitem(sys.modules, "core.dep_resolver",
                        NS(resolve_runtime_dependencies=lambda *a, **k: []))
    conv = SC.RpmConverterSubprocess(_araclar())
    metin = conv._generate_pkgbuild(_meta(depends=["libgtk", "bilinmeyen"]),
                                    Path("/nonexistent-src"))
    assert "'gtk3'" in metin                          # eslemeden geldi
    assert "bilinmeyen" not in metin

    monkeypatch.setitem(sys.modules, "core.dep_resolver",
                        NS(resolve_runtime_dependencies=lambda *a, **k:
                           ["cozumlu-dep"]))
    cozulmus = conv._generate_pkgbuild(_meta(depends=[]),
                                       Path("/nonexistent-src"))
    assert "'cozumlu-dep'" in cozulmus

def test_cancel_flags_both_converters():
    d = SC.NativeDebConverterSubprocess(_araclar())
    r = SC.RpmConverterSubprocess(_araclar())
    d.cancel(); r.cancel()
    assert d._cancelled and r._cancelled


def test_rpm_warnings_emitted(monkeypatch, tmp_path):
    conv = SC.RpmConverterSubprocess(_araclar())
    kayit = _Kayit(); kayit.bagla(conv)
    _temel_yamalar(monkeypatch,
                   guvenlik=_guvenlik_modulu(uyarilar=["dev dosya"]),
                   meta=_meta())
    conv._do_convert(tmp_path / "x.rpm", tmp_path)
    assert any("⚠" in s for s in kayit.satirlar)


def test_rpm_pkg_dir_vanished_fallback_src(monkeypatch, tmp_path):
    conv = SC.RpmConverterSubprocess(_araclar())
    kayit = _Kayit(); kayit.bagla(conv)

    def dizini_sil(_d):                       # guvenlik asamasinda kaybolur
        import shutil
        shutil.rmtree(tmp_path / "pkg_root", ignore_errors=True)
        return []
    guv = NS(check_symlink_attacks=dizini_sil,
             check_dangerous_files=lambda d: ([], []),
             build_sandbox_cmd=lambda cmd, cwd, t: (cmd[0], cmd[1:]))
    _temel_yamalar(monkeypatch, guvenlik=guv,
                   popen_rc=0, popen_yaz="demo-1.0-x.pkg.tar.zst",
                   meta=_meta(version="1.0"))
    conv._do_convert(tmp_path / "x.rpm", tmp_path)
    ok, _m, _p = kayit.bitisler[-1]
    assert ok is True and (tmp_path / "build" / "src").is_dir()


def _kademeli_popen(ilk_rc, sonraki_rc=0, yaz=None):
    cagri = {"n": 0}
    def sahte(cmd, **kw):
        cagri["n"] += 1
        rc = ilk_rc if cagri["n"] == 1 else sonraki_rc
        if yaz and "env" in kw and cagri["n"] > 1:
            hedef = Path(kw["env"]["PKGDEST"])
            hedef.mkdir(parents=True, exist_ok=True)
            (hedef / yaz).write_bytes(b"paket")
        return NS(stdout=iter(["ok\n"]), stderr=b"", pid=cagri["n"],
                  wait=lambda timeout=None: None,
                  communicate=lambda timeout=None: (b"", b""),
                  returncode=rc)
    return sahte


def test_rpm_makepkg_failure_staged(monkeypatch, tmp_path):
    conv = SC.RpmConverterSubprocess(_araclar())
    kayit = _Kayit(); kayit.bagla(conv)
    _temel_yamalar(monkeypatch, guvenlik=_guvenlik_modulu(), meta=_meta())
    monkeypatch.setattr(SC, "subprocess",
                        NS(Popen=_kademeli_popen(ilk_rc=0, sonraki_rc=5),
                           PIPE=-1, STDOUT=-2))
    conv._do_convert(tmp_path / "x.rpm", tmp_path)
    ok, msg, _p = kayit.bitisler[-1]
    assert ok is False and "makepkg başarısız" in msg


def test_rpm_no_pkg_found_after_success(monkeypatch, tmp_path):
    conv = SC.RpmConverterSubprocess(_araclar())
    kayit = _Kayit(); kayit.bagla(conv)
    _temel_yamalar(monkeypatch, guvenlik=_guvenlik_modulu(),
                   popen_rc=0, meta=_meta())          # paket yazilmaz
    conv._do_convert(tmp_path / "x.rpm", tmp_path)
    ok, msg, _p = kayit.bitisler[-1]
    assert ok is False and "bulunamadı" in msg