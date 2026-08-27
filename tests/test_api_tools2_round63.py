"""Tur-63 — Feature Tezgahi Faz 2 RPC handlerlari.

tools.scan_image / attest / publish / snapshot_status / snapshot_install /
snapshot_remove.
"""
from __future__ import annotations

import pytest

import core.api_server as AS


@pytest.fixture()
def senkron(monkeypatch):
    """_run_thread'i senkrona cevir, olaylari kaydet."""
    kayit = []

    def sahte(fn, event_name="event/security_done"):
        try:
            sonuc = fn()
            kayit.append((event_name, {"ok": True, "sonuc": sonuc}))
        except Exception as exc:  # noqa: BLE001
            kayit.append((event_name, {"ok": False, "hata": str(exc)}))

    monkeypatch.setattr(AS, "_run_thread", sahte)
    return kayit


# ── tools.scan_image ────────────────────────────────────────────
def test_scan_image_success(senkron, tmp_path, monkeypatch):
    img = tmp_path / "img.tar"
    img.write_bytes(b"x")
    import core.malware_scanner as MS
    monkeypatch.setattr(MS, "scan_oci_image",
                        lambda p: {"clean": True, "findings": [], "detail": "temiz"})
    yanit = AS.handle_tools_scan_image({"image": str(img)})
    assert yanit == {"started": True}
    assert senkron[0][0] == "event/scan_image_done"
    assert senkron[0][1]["sonuc"]["clean"] is True


def test_scan_image_missing(senkron):
    with pytest.raises(FileNotFoundError):
        AS.handle_tools_scan_image({"image": "/yok/img.tar"})


# ── tools.attest ────────────────────────────────────────────────
class _FakeAtt:
    _type = "https://in-toto.io/Statement/v1"
    predicate_type = "https://pkgforge.app/attestation/v1"
    subject = [{"name": "p.pkg.tar.zst"}]
    predicate = {"builder": {"id": "pkgforge"},
                 "metadata": {"buildInvocationId": "b1"}}


def test_attest_success(senkron, tmp_path, monkeypatch):
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"x")
    import core.provenance as PR
    monkeypatch.setattr(PR, "find_provenance", lambda p: tmp_path / "p.prov.json")
    monkeypatch.setattr(PR, "load_provenance", lambda p: object())
    monkeypatch.setattr(PR, "create_attestation",
                        lambda prov, signer_key="": _FakeAtt())
    monkeypatch.setattr(PR, "save_attestation",
                        lambda att, path: path)
    yanit = AS.handle_tools_attest({"package": str(pkg)})
    assert yanit == {"started": True}
    sonuc = senkron[0][1]["sonuc"]
    assert sonuc["ok"] is True
    assert sonuc["subject"] == "p.pkg.tar.zst"
    assert sonuc["builder"] == "pkgforge"
    assert sonuc["attestation_path"].endswith(".attestation.json")


def test_attest_missing_pkg(senkron):
    with pytest.raises(FileNotFoundError):
        AS.handle_tools_attest({"package": "/yok/p.pkg.tar.zst"})


def test_attest_no_provenance(senkron, tmp_path, monkeypatch):
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"x")
    import core.provenance as PR
    monkeypatch.setattr(PR, "find_provenance", lambda p: None)
    AS.handle_tools_attest({"package": str(pkg)})
    assert senkron[0][1]["sonuc"]["ok"] is False


def test_attest_load_fails(senkron, tmp_path, monkeypatch):
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"x")
    import core.provenance as PR
    monkeypatch.setattr(PR, "find_provenance", lambda p: tmp_path / "p.prov.json")
    monkeypatch.setattr(PR, "load_provenance", lambda p: None)
    AS.handle_tools_attest({"package": str(pkg)})
    assert senkron[0][1]["sonuc"]["ok"] is False


# ── tools.publish ───────────────────────────────────────────────
class _FakeAUR:
    def __init__(self, tmp_path):
        self.pkgbuild = tmp_path / "aur" / "PKGBUILD"
        self.srcinfo = tmp_path / "aur" / ".SRCINFO"
        self.name = "p-bin"
        self.version = "1.0.0"


def test_publish_success_no_push(senkron, tmp_path, monkeypatch):
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"x")
    import core.aur_publish as AP
    monkeypatch.setattr(AP, "prepare_aur_package",
                        lambda p, o: (True, "hazir", _FakeAUR(tmp_path)))
    yanit = AS.handle_tools_publish({"package": str(pkg)})
    assert yanit == {"started": True}
    sonuc = senkron[0][1]["sonuc"]
    assert sonuc["ok"] is True and sonuc["pushed"] is False
    assert sonuc["name"] == "p-bin"


def test_publish_missing_pkg(senkron):
    with pytest.raises(FileNotFoundError):
        AS.handle_tools_publish({"package": "/yok/p.pkg.tar.zst"})


def test_publish_prepare_fails(senkron, tmp_path, monkeypatch):
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"x")
    import core.aur_publish as AP
    monkeypatch.setattr(AP, "prepare_aur_package",
                        lambda p, o: (False, "hata", None))
    AS.handle_tools_publish({"package": str(pkg)})
    assert senkron[0][1]["sonuc"]["ok"] is False


def test_publish_with_push_success(senkron, tmp_path, monkeypatch):
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"x")
    import core.aur_publish as AP
    monkeypatch.setattr(AP, "prepare_aur_package",
                        lambda p, o: (True, "hazir", _FakeAUR(tmp_path)))
    monkeypatch.setattr(AP, "push_to_aur", lambda d, u: (True, "itildi"))
    AS.handle_tools_publish({"package": str(pkg),
                             "aur_url": "ssh://aur@aur.archlinux.org/p-bin.git"})
    sonuc = senkron[0][1]["sonuc"]
    assert sonuc["ok"] is True and sonuc["pushed"] is True


def test_publish_with_push_fails(senkron, tmp_path, monkeypatch):
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"x")
    import core.aur_publish as AP
    monkeypatch.setattr(AP, "prepare_aur_package",
                        lambda p, o: (True, "hazir", _FakeAUR(tmp_path)))
    monkeypatch.setattr(AP, "push_to_aur", lambda d, u: (False, "itilemedi"))
    AS.handle_tools_publish({"package": str(pkg), "aur_url": "ssh://x"})
    sonuc = senkron[0][1]["sonuc"]
    assert sonuc["ok"] is False and sonuc["pushed"] is False


# ── tools.snapshot_* ────────────────────────────────────────────
def test_snapshot_status_sync(monkeypatch):
    import core.snapshot_cleanup as SC
    monkeypatch.setattr(SC, "get_cleanup_status",
                        lambda: {"installed": True, "active": True,
                                 "next_run": "yarin", "last_run": ""})
    yanit = AS.handle_tools_snapshot_status({})
    assert yanit["installed"] is True and yanit["next_run"] == "yarin"


def test_snapshot_install_success(senkron, monkeypatch):
    import core.snapshot_cleanup as SC
    monkeypatch.setattr(SC, "install_cleanup_service",
                        lambda max_age_days=7: (True, "kuruldu"))
    yanit = AS.handle_tools_snapshot_install({"max_age_days": 14})
    assert yanit == {"started": True}
    assert senkron[0][1]["sonuc"] == {"ok": True, "message": "kuruldu"}


def test_snapshot_remove_success(senkron, monkeypatch):
    import core.snapshot_cleanup as SC
    monkeypatch.setattr(SC, "remove_cleanup_service",
                        lambda: (True, "kaldirildi"))
    yanit = AS.handle_tools_snapshot_remove({})
    assert yanit == {"started": True}
    assert senkron[0][1]["sonuc"] == {"ok": True, "message": "kaldirildi"}


def test_methods_registered():
    for m in ("tools.scan_image", "tools.attest", "tools.publish",
              "tools.snapshot_status", "tools.snapshot_install",
              "tools.snapshot_remove"):
        assert m in AS.METHODS
