"""Coverage itmesi - aur_checker: RPC akislari, arama ve surum karsilastirma."""
from __future__ import annotations

import json

import pytest

import core.aur_checker as AC


class FakeResp:
    def __init__(self, payload: bytes = b"", exc: Exception | None = None):
        self._payload = payload
        self._exc = exc

    def __enter__(self):
        if self._exc is not None:
            raise self._exc
        return self

    def read(self) -> bytes:
        return self._payload

    def __exit__(self, *a):
        return False


def _rpc(results=None, resultcount=None):
    return {
        "resultcount": resultcount if resultcount is not None else len(results or []),
        "results": results or [],
    }


# --- check_aur -----------------------------------------------------------------

def test_check_empty_name_error():
    r = AC.check_aur("")
    assert r.status == "error" and "Boş" in r.detail


def test_check_offline_short_circuit():
    r = AC.check_aur("gtk3", offline=True)
    assert r.status == "error" and "Çevrimdışı" in r.detail


def test_check_not_found(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=0: FakeResp(json.dumps(_rpc()).encode()))
    assert AC.check_aur("yokpak").status == "not_found"


def _pkg(ver, ood=False, last_mod=1700000000):
    # AUR RPC eski olmayan paketlerde OutOfDate anahtarini hic gondermez;
    # modul 'is not None' ile baktigi icin bayrak yoksa anahtari koyma.
    p = {"Name": "demo", "Version": ver, "LastModified": last_mod}
    if ood:
        p["OutOfDate"] = 1700000000
    return p


@pytest.mark.parametrize("aur_ver,local,expected", [
    ("2.0.0", "1.0.0", "found_newer"),
    ("0.9.0", "1.0.0", "found_older"),
])
def test_check_version_branches(monkeypatch, aur_ver, local, expected):
    monkeypatch.setattr("shutil.which", lambda n: None)  # saf python karsilastirma
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=0: FakeResp(json.dumps(_rpc([_pkg(aur_ver)])).encode()))
    r = AC.check_aur("demo", local_version=local)
    assert r.status == expected and r.aur_version == aur_ver


def test_check_out_of_date_flag_wins(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: None)
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=0: FakeResp(json.dumps(_rpc([_pkg("0.1", ood=True)])).encode()))
    r = AC.check_aur("demo", local_version="9.9")
    assert r.status == "out_of_date" and r.out_of_date is True


def test_check_url_error_mapped(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=0: FakeResp(exc=__import__("urllib.error",
                                                        fromlist=["URLError"]).URLError("ag yok")))
    r = AC.check_aur("demo")
    assert r.status == "error" and "ag yok" in r.detail


def test_check_bad_json_mapped(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=0: FakeResp(b"{bozuk"))
    r = AC.check_aur("demo")
    assert r.status == "error"


def test_check_missing_results_key_mapped(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=0: FakeResp(json.dumps({"resultcount": 1}).encode()))
    r = AC.check_aur("demo")
    assert r.status == "error"


# --- search_aur ----------------------------------------------------------------

def test_search_empty_and_offline():
    assert AC.search_aur("") == []
    assert AC.search_aur("  ") == []
    assert AC.search_aur("gtk", offline=True) == []


def test_search_sorted_by_votes(monkeypatch):
    data = _rpc([
        {"Name": "azoy", "Version": "1", "NumVotes": 3},
        {"Name": "cokoy", "Version": "2", "NumVotes": 99,
         "Description": "populer", "URLPath": "/cokoy"},
    ])
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=0: FakeResp(json.dumps(data).encode()))
    out = AC.search_aur("oy")
    assert [o["name"] for o in out] == ["cokoy", "azoy"]
    assert out[0]["num_votes"] == 99 and out[0]["url_path"] == "/cokoy"


def test_search_url_error_returns_empty(monkeypatch):
    import urllib.error
    def boom(req, timeout=0):
        raise urllib.error.URLError("yasak")
    monkeypatch.setattr("urllib.request.urlopen", boom)
    assert AC.search_aur("gtk") == []


def test_search_bad_json_returns_empty(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=0: FakeResp(b"[bozuk"))
    assert AC.search_aur("gtk") == []


# --- _version_compare ----------------------------------------------------------

def test_version_compare_with_vercmp_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/vercmp")
    monkeypatch.setattr("core.security.safe_run",
                        lambda cmd, timeout=0: NS(returncode=0, stdout="1\n"))
    assert AC._version_compare("2.0", "1.0") == 1


def test_version_compare_vercmp_rc_nonzero_falls_back(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/vercmp")
    monkeypatch.setattr("core.security.safe_run",
                        lambda cmd, timeout=0: NS(returncode=2, stdout=""))
    assert AC._version_compare("2.0", "1.0") > 0


def test_version_compare_vercmp_crash_falls_back(monkeypatch):
    import subprocess

    def boom(cmd, timeout=0):
        raise subprocess.TimeoutExpired("vercmp", 5)
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/vercmp")
    monkeypatch.setattr("core.security.safe_run", boom)
    assert AC._version_compare("1.0", "1.0") == 0


def test_version_compare_python_semantics():
    assert AC._version_compare("1.10", "1.9") > 0      # sayısal karşılaştırma
    assert AC._version_compare("3:1.0", "1.0") > 0     # epoch öncelikli
    assert AC._version_compare("1.0-2", "1.0") == 0    # rel kırpılır
    assert AC._version_compare("1.0", "1.0.1") < 0     # uzunluk farkı


from types import SimpleNamespace as NS