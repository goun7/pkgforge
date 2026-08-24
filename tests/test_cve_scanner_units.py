"""Coverage itmesi — core/cve_scanner.py OSV tarama dallari."""
from __future__ import annotations

import urllib.error

import core.cve_scanner as CS


def test_empty_deps(monkeypatch):
    monkeypatch.setattr(CS, "_query_osv",
                        lambda dep, timeout=10: (_ for _ in ()).throw(
                            AssertionError("cagrilmamali")))
    out = CS.scan_dependencies([])
    assert out["deps_scanned"] == 0 and out["count"] == 0
    out2 = CS.scan_dependencies(["", "  "])
    assert out2["deps_scanned"] == 0


def test_offline_mode(monkeypatch):
    monkeypatch.setattr(CS, "_query_osv",
                        lambda dep, timeout=10: [])
    out = CS.scan_dependencies(["openssl"], offline=True)
    assert out["offline"] is True and out["deps_scanned"] == 1


def test_vuln_found_with_db_severity(monkeypatch):
    raw = [{"id": "GHSA-1", "summary": "kotu",
            "database_specific": {"severity": "HIGH"}}]
    monkeypatch.setattr(CS, "_query_osv", lambda dep, timeout=10: raw)
    out = CS.scan_dependencies(["openssl"])
    assert out["count"] == 1
    v = out["vulns"][0]
    assert v["severity"] == "HIGH" and v["affected_dep"] == "openssl"


dedup_id = "GHSA-DUP"


def test_dedup_same_vuln_across_deps(monkeypatch):
    monkeypatch.setattr(CS, "_query_osv",
                        lambda dep, timeout=10: [
                            {"id": dedup_id, "summary": "s"}])
    out = CS.scan_dependencies(["a", "b"])
    assert out["count"] == 1
    assert out["vulns"][0]["affected_dep"] == "a"


def test_severity_fallbacks(monkeypatch):
    monkeypatch.setattr(CS, "_query_osv", lambda dep, timeout=10: [
        {"id": "V1", "severity": [{"type": "CVSS_V3"}]},
        {"id": "V2"},
    ])
    out = CS.scan_dependencies(["x"])
    sev = {v["id"]: v["severity"] for v in out["vulns"]}
    assert sev["V1"] == "CVSS_V3"
    assert sev["V2"] == "UNKNOWN"


def test_all_network_errors_mark_offline(monkeypatch):
    def fail(dep, timeout=10):
        raise urllib.error.URLError("yok")
    monkeypatch.setattr(CS, "_query_osv", fail)
    out = CS.scan_dependencies(["a", "b"])
    assert out["offline"] is True and out["count"] == 0
