"""Tur-55 C10: REST API v2 + OpenAPI generator."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # type: ignore[import-not-found]

from core.api_v2 import app, export_openapi


@pytest.fixture
def client():
    return TestClient(app)


def test_version(client):
    r = client.get("/api/v2/version")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "pkgforge"
    assert body["version"] == "2.0.0"
    assert body["api"] == "v2"


def test_doctor_returns_tool_map(client):
    r = client.get("/api/v2/doctor")
    assert r.status_code == 200
    body = r.json()
    assert "ok" in body
    assert "tools" in body
    assert isinstance(body["tools"], dict)
    # Some tools should be detected on a normal dev box.
    for k in ("gpg", "ar", "tar"):
        assert k in body["tools"]


def test_benchmark_runs_and_reports(client):
    r = client.post("/api/v2/benchmark", json={"name": "t", "iterations": 50})
    assert r.status_code == 200
    body = r.json()
    assert body["iterations"] == 50
    assert body["duration_ms"] >= 0
    assert body["per_iter_ms"] >= 0


def test_benchmark_validates_iterations(client):
    r = client.post("/api/v2/benchmark", json={"name": "t", "iterations": 0})
    assert r.status_code == 422  # Pydantic validation


def test_signing_status_shape(client):
    r = client.get("/api/v2/signing/status")
    assert r.status_code == 200
    body = r.json()
    assert "gpg_available" in body
    assert "cosign_available" in body


def test_validate_manifest_ok(client):
    r = client.post("/api/v2/packages/manifests", json={
        "name": "mypkg", "version": "1.2.3", "arch": "amd64",
        "size_bytes": 1024, "sha256": "a" * 64,
        "dependencies": ["libc"], "signed": True,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert body["errors"] == []


def test_validate_manifest_rejects_bad_name(client):
    r = client.post("/api/v2/packages/manifests", json={
        "name": "Bad Name!", "version": "1.0.0", "arch": "amd64",
    })
    assert r.status_code == 422


def test_validate_manifest_rejects_bad_version(client):
    r = client.post("/api/v2/packages/manifests", json={
        "name": "ok", "version": "1.0", "arch": "amd64",
    })
    assert r.status_code == 422


def test_validate_manifest_signed_without_hash(client):
    r = client.post("/api/v2/packages/manifests", json={
        "name": "ok", "version": "1.0.0", "arch": "amd64",
        "signed": True, "sha256": "",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is False
    assert any("sha256" in e for e in body["errors"])


def test_openapi_json_includes_paths(client):
    r = client.get("/api/v2/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert spec["info"]["title"] == "PkgForge REST API v2"
    for path in ("/api/v2/version", "/api/v2/doctor",
                 "/api/v2/benchmark", "/api/v2/signing/status",
                 "/api/v2/packages/manifests"):
        assert path in spec["paths"]


def test_export_openapi_writes_file(tmp_path: Path):
    out = tmp_path / "openapi.json"
    export_openapi(str(out))
    assert out.is_file()
    spec = json.loads(out.read_text(encoding="utf-8"))
    assert spec["openapi"].startswith("3.")
    assert "paths" in spec
