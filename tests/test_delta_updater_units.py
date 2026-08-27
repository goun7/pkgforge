"""Coverage itmesi — core/delta_updater.py delta + oto-guncelleme akislari."""
from __future__ import annotations

from types import SimpleNamespace

import core.delta_updater as DU


def _ns(code, out=""):
    return SimpleNamespace(returncode=code, stdout=out, stderr="")


def test_xdelta_availability(monkeypatch):
    monkeypatch.setattr(DU.shutil, "which", lambda n: None)
    assert DU.is_xdelta3_available() is False


def test_create_delta_guards(monkeypatch, tmp_path):
    monkeypatch.setattr(DU.shutil, "which", lambda n: None)
    assert DU.create_delta(tmp_path / "a", tmp_path / "b",
                           tmp_path / "d") is False
    monkeypatch.setattr(DU.shutil, "which", lambda n: "/usr/bin/xdelta3")
    assert DU.create_delta(tmp_path / "yok", tmp_path / "b",
                           tmp_path / "d") is False


def test_create_delta_success_and_failure(monkeypatch, tmp_path):
    old = tmp_path / "eski.deb"
    new = tmp_path / "yeni.deb"
    delta = tmp_path / "fark.xdelta"
    old.write_bytes(b"AAAA")
    new.write_bytes(b"BBBB")
    delta.write_bytes(b"D")
    monkeypatch.setattr(DU.shutil, "which", lambda n: "/usr/bin/x3")
    monkeypatch.setattr(DU, "safe_run", lambda cmd, timeout=None: _ns(0))
    assert DU.create_delta(old, new, delta) is True
    monkeypatch.setattr(DU, "safe_run", lambda cmd, timeout=None: _ns(2))
    assert DU.create_delta(old, new, delta) is False


def test_apply_delta_paths(monkeypatch, tmp_path):
    old = tmp_path / "eski.deb"
    dlt = tmp_path / "fark.xdelta"
    out = tmp_path / "cikti.deb"
    old.write_bytes(b"A")
    dlt.write_bytes(b"D")
    monkeypatch.setattr(DU.shutil, "which", lambda n: "/usr/bin/x3")
    monkeypatch.setattr(DU, "safe_run", lambda cmd, timeout=None: _ns(0))
    assert DU.apply_delta(old, dlt, out) is True
    monkeypatch.setattr(DU.shutil, "which", lambda n: None)
    assert DU.apply_delta(old, dlt, out) is False


def test_apply_delta_sha256_verification(monkeypatch, tmp_path):
    import hashlib
    old = tmp_path / "eski.deb"; old.write_bytes(b"A")
    dlt = tmp_path / "fark.xdelta"; dlt.write_bytes(b"D")
    out = tmp_path / "cikti.deb"
    monkeypatch.setattr(DU.shutil, "which", lambda n: "/usr/bin/x3")
    icerik = b"YENI-ICERIK"
    beklenen = hashlib.sha256(icerik).hexdigest()

    def fake_run(cmd, timeout=None):
        out.write_bytes(icerik)          # xdelta3 ciktiyi uretmis gibi
        return _ns(0)
    monkeypatch.setattr(DU, "safe_run", fake_run)

    # Eslesen hash -> True, dosya korunur (buyuk/kucuk harf duyarsiz)
    assert DU.apply_delta(old, dlt, out, expected_sha256=beklenen) is True
    assert out.is_file()
    assert DU.apply_delta(old, dlt, out, expected_sha256=beklenen.upper()) is True

    # Eslesmeyen hash -> False, cikti silinir
    assert DU.apply_delta(old, dlt, out, expected_sha256="0" * 64) is False
    assert not out.exists()


def test_download_with_delta_bad_hash_falls_back(monkeypatch, tmp_path):
    from pathlib import Path
    old = tmp_path / "eski.deb"; old.write_bytes(b"A")
    dest = tmp_path / "yeni.deb"
    monkeypatch.setattr(DU.shutil, "which", lambda n: "/usr/bin/x3")

    def fake_dl(url, parent, require_https=True):
        if url.endswith(".xdelta"):
            (parent / "delta.xdelta").write_bytes(b"D")
            return parent / "delta.xdelta"
        dest.write_bytes(b"TAM")
        return dest
    monkeypatch.setattr("core.downloader.download_package", fake_dl)

    def fake_run(cmd, timeout=None):
        Path(cmd[-1]).write_bytes(b"BOZUK-CIKTI")
        return _ns(0)
    monkeypatch.setattr(DU, "safe_run", fake_run)

    got, used = DU.download_with_delta("https://x/yeni.deb", dest, old,
                                       expected_sha256="f" * 64)
    assert used is False                                  # hash tutmadi
    assert got == dest and dest.read_bytes() == b"TAM"    # tam indirme


def test_find_local_previous_picks_newest(tmp_path):
    eski = tmp_path / "demo-1.0-1-x86_64.pkg.tar.zst"
    yeni = tmp_path / "demo-2.0-1-x86_64.pkg.tar.zst"
    diger = tmp_path / "baska-1.0-1-x86_64.pkg.tar.zst"
    imza = tmp_path / "demo-3.0-1-x86_64.pkg.tar.zst.sig"
    for i, p in enumerate((eski, yeni, diger, imza)):
        p.write_bytes(b"x")
        import os as _os
        _os.utime(p, (1000 + i * 10, 1000 + i * 10))
    got = DU.find_local_previous("demo", pkg_dir=tmp_path)
    assert got == yeni
    bos = tmp_path / "bos"
    bos.mkdir()
    assert DU.find_local_previous("demo", pkg_dir=bos) is None


def test_download_full_when_no_old(monkeypatch, tmp_path):
    calls = {}

    def fake_dl(url, parent, require_https=True):
        calls["url"] = url
        return parent / "sonuc.deb"
    monkeypatch.setattr("core.downloader.download_package", fake_dl)
    got, used = DU.download_with_delta("https://x/p.deb",
                                       tmp_path / "p.deb")
    assert used is False and got.name == "sonuc.deb"
    assert calls["url"] == "https://x/p.deb"


def test_download_with_delta_success(monkeypatch, tmp_path):
    old = tmp_path / "eski.deb"
    old.write_bytes(b"A")
    dest = tmp_path / "yeni.deb"
    monkeypatch.setattr(DU.shutil, "which", lambda n: "/usr/bin/x3")

    def fake_dl(url, parent, require_https=True):
        if url.endswith(".xdelta"):
            (parent / "delta.xdelta").write_bytes(b"D")
            return parent / "delta.xdelta"
        dest.write_bytes(b"B")
        return dest
    monkeypatch.setattr("core.downloader.download_package", fake_dl)
    seen = []

    def fake_apply(old_f, d_f, out_f, **kwargs):
        seen.append(str(d_f.name))
        out_f.write_bytes(b"B")
        return True
    monkeypatch.setattr(DU, "apply_delta", fake_apply)
    got, used = DU.download_with_delta("https://x/yeni.deb", dest, old)
    assert used is True and got == dest and seen == ["delta.xdelta"]


def test_download_delta_fallback_on_error(monkeypatch, tmp_path):
    old = tmp_path / "eski.deb"
    old.write_bytes(b"A")
    dest = tmp_path / "yeni.deb"
    monkeypatch.setattr(DU.shutil, "which", lambda n: "/usr/bin/x3")

    def fake_dl(url, parent, require_https=True):
        if url.endswith(".xdelta"):
            raise RuntimeError("404")
        dest.write_bytes(b"B")
        return dest
    monkeypatch.setattr("core.downloader.download_package", fake_dl)
    got, used = DU.download_with_delta("https://x/yeni.deb", dest, old)
    assert used is False and got == dest


def test_install_auto_update_success(monkeypatch):
    monkeypatch.setattr("os.path.isfile", lambda p: True)
    monkeypatch.setattr("core.security.safe_run",
                        lambda argv, timeout=None, input=None, **kw: _ns(0))
    ok, msg = DU.install_auto_update(interval_hours=12)
    assert ok is True and "kuruldu" in msg and "12" in msg


def test_install_auto_update_script_rejected(monkeypatch):
    monkeypatch.setattr("os.path.isfile", lambda p: True)
    monkeypatch.setattr("core.security.safe_run",
                        lambda argv, timeout=None, input=None, **kw: _ns(1))
    ok, msg = DU.install_auto_update()
    assert ok is False and "Script dosyası yazılamadı" in msg


def test_install_and_remove_without_systemd(monkeypatch):
    monkeypatch.setattr("os.path.isfile", lambda p: False)
    ok, msg = DU.install_auto_update()
    assert ok is False and "systemctl bulunamadı" in msg
    ok2, msg2 = DU.remove_auto_update()
    assert ok2 is False and msg2 == "systemctl bulunamadı"


def test_remove_auto_update_success(monkeypatch):
    monkeypatch.setattr("os.path.isfile", lambda p: True)
    seen = []

    def fake_run(argv, timeout=None, **kw):
        seen.append(list(argv))
        return _ns(0)
    monkeypatch.setattr("core.security.safe_run", fake_run)
    ok, msg = DU.remove_auto_update()
    assert ok is True and "kaldırıldı" in msg
    assert any("daemon-reload" in c for c in seen)


def _patch_systemctl_queries(monkeypatch, enabled, active, show_out):
    def fake_run(argv, timeout=None, input=None, **kw):
        op = argv[1] if len(argv) > 1 else ""
        if op == "is-enabled":
            return _ns(enabled)
        if op == "is-active":
            return _ns(active)
        if op == "show":
            return _ns(0, out=show_out)
        return _ns(0)
    monkeypatch.setattr("core.security.safe_run", fake_run)


def test_status_matrix(monkeypatch):
    monkeypatch.setattr("os.path.isfile", lambda p: False)
    st = DU.get_auto_update_status()
    assert st["installed"] is False
    assert st["experimental"] is True and st["xdelta3_available"] is False

    monkeypatch.setattr("os.path.isfile", lambda p: True)
    _patch_systemctl_queries(monkeypatch, 0, 0, "NextElapseUSecRealtime=x")
    monkeypatch.setattr(DU.shutil, "which", lambda n: "/usr/bin/x3")
    st2 = DU.get_auto_update_status()
    assert st2["installed"] is True and st2["active"] is True
    assert st2["next_run"] == "x"


def test_enable_disable_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(DU.shutil, "which", lambda n: None)
    ok, msg = DU.enable_auto_update()
    assert ok is False and "systemctl bulunamadı" in msg

    monkeypatch.setattr(DU.shutil, "which",
                        lambda n: "/usr/bin/systemctl")
    ok2, msg2 = DU.enable_auto_update()
    assert ok2 is False and "bulunamadı" in msg2

    def ok_run(argv, timeout=None, **kw):
        return _ns(0)
    monkeypatch.setattr("core.security.safe_run", ok_run)
    ok3, _msg3 = DU.disable_auto_update()
    assert ok3 is True

    def bad_run(argv, timeout=None, **kw):
        op = argv[1] if len(argv) > 1 else ""
        return _ns(1) if op == "disable" else _ns(0)
    monkeypatch.setattr("core.security.safe_run", bad_run)
    ok4, msg4 = DU.disable_auto_update()
    assert ok4 is False and "devre dışı bırakılamadı" in msg4
