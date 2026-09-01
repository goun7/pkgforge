"""Tur-55 C10: PkgForge REST API v2 (FastAPI + Pydantic + OpenAPI).

Mevcut core/api_server.py (JSON-RPC / QT) ile çakışmaz. Bu modül
HTTP tabanlı bir REST + OpenAPI yüzeyi sağlar:
  - /api/v2/version
  - /api/v2/doctor
  - /api/v2/benchmark
  - /api/v2/signing/status
  - /api/v2/packages/manifests (POST validate)
  - /api/v2/openapi.json (auto-generated)
  - /api/v2/docs (Swagger UI)

CLI: `pkgforge serve-api --port 8899`
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from i18n import tr

app = FastAPI(
    title="PkgForge REST API v2",
    version="2.0.0",
    description=tr("api.v2_description"),
    contact={"name": "PkgForge", "url": "https://github.com/goun7/pkgforge"},
    license_info={"name": "MIT"},
)


# ---- Pydantic models ------------------------------------------------------

class VersionResponse(BaseModel):
    name: str = Field(default="pkgforge")
    version: str = Field(default="2.0.0")
    api: str = Field(default="v2")


class DoctorResponse(BaseModel):
    ok: bool
    issues: list[str] = Field(default_factory=list)
    tools: dict[str, bool] = Field(default_factory=dict)


class BenchmarkRequest(BaseModel):
    name: str = Field(default="default", max_length=64)
    iterations: int = Field(default=100, ge=1, le=10_000)


class BenchmarkResponse(BaseModel):
    name: str
    iterations: int
    duration_ms: float
    per_iter_ms: float


class SigningStatusResponse(BaseModel):
    gpg_available: bool
    gpg_path: str = ""
    cosign_available: bool = False
    cosign_version: str = ""


class PackageManifestRequest(BaseModel):
    name: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9._+-]*$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+([-+][A-Za-z0-9.]+)?$")
    arch: str = Field(pattern=r"^(amd64|arm64|i386|any)$")
    size_bytes: int = Field(ge=0, default=0)
    sha256: str = Field(default="", pattern=r"^([a-f0-9]{64})?$")
    dependencies: list[str] = Field(default_factory=list)
    signed: bool = False


class PackageManifestResponse(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    manifest: PackageManifestRequest


# ---- Routes ---------------------------------------------------------------

@app.get("/api/v2/version", response_model=VersionResponse, tags=["meta"])
async def version() -> VersionResponse:
    return VersionResponse()


@app.get("/api/v2/doctor", response_model=DoctorResponse, tags=["diagnostics"])
async def doctor() -> DoctorResponse:
    """Run doctor checks and return a structured result.

    C10 deliberately runs a lightweight subset synchronously (not the
    full CLI doctor) to keep latency low for HTTP callers. The full
    `pkgforge doctor --json` is recommended for deep diagnostics.
    """
    import shutil
    tools = {}
    for name in ("gpg", "cosign", "ar", "tar", "zstd", "rpm", "dpkg"):
        tools[name] = shutil.which(name) is not None
    issues = [n for n, ok in tools.items() if not ok]
    return DoctorResponse(
        ok=len(issues) == 0,
        issues=issues,
        tools=tools,
    )


@app.post("/api/v2/benchmark", response_model=BenchmarkResponse, tags=["perf"])
async def benchmark(req: BenchmarkRequest) -> BenchmarkResponse:
    """Run a quick CPU-bound benchmark (sha256 over random bytes)."""
    import hashlib
    import time as _time
    chunk = os.urandom(64 * 1024)
    t0 = _time.perf_counter()
    for _ in range(req.iterations):
        hashlib.sha256(chunk).hexdigest()
    elapsed_ms = (_time.perf_counter() - t0) * 1000.0
    return BenchmarkResponse(
        name=req.name,
        iterations=req.iterations,
        duration_ms=elapsed_ms,
        per_iter_ms=elapsed_ms / req.iterations,
    )


@app.get("/api/v2/signing/status",
         response_model=SigningStatusResponse,
         tags=["signing"])
async def signing_status() -> SigningStatusResponse:
    import shutil
    gpg = shutil.which("gpg")
    cosign = shutil.which("cosign")
    cosign_version = ""
    if cosign:
        from core.security import safe_run
        res = safe_run([cosign, "version"], timeout=5)
        out = res.stdout if isinstance(res.stdout, str) else res.stdout.decode("utf-8", errors="replace")
        cosign_version = out.strip().split("\n")[0] if out else ""
    return SigningStatusResponse(
        gpg_available=bool(gpg),
        gpg_path=gpg or "",
        cosign_available=bool(cosign),
        cosign_version=cosign_version,
    )


@app.post("/api/v2/packages/manifests",
          response_model=PackageManifestResponse,
          tags=["packages"])
async def validate_manifest(req: PackageManifestRequest) -> PackageManifestResponse:
    """Validate a package manifest against the shared schema."""
    errors: list[str] = []
    # Cross-field checks (Pydantic handles per-field).
    if req.size_bytes < 0:
        errors.append("size_bytes must be non-negative")
    if req.signed and not req.sha256:
        errors.append("signed=true requires sha256")
    if req.arch not in {"amd64", "arm64", "i386", "any"}:
        errors.append(f"unsupported arch: {req.arch}")
    return PackageManifestResponse(
        valid=len(errors) == 0,
        errors=errors,
        manifest=req,
    )


@app.get("/api/v2/openapi.json", tags=["meta"], include_in_schema=False)
async def openapi_json() -> dict[str, Any]:
    return app.openapi()


# ---- OpenAPI generation to disk -------------------------------------------

def export_openapi(target_path: str) -> str:
    """Dump the auto-generated OpenAPI spec to a JSON file.

    CI bunu `openapi.json` artifact olarak yayınlar; desktop/ tarafı
    aynı şemadan TS tiplerini generate edebilir.
    """
    import json as _json
    spec = app.openapi()
    with open(target_path, "w", encoding="utf-8") as f:
        _json.dump(spec, f, indent=2, ensure_ascii=False)
    return target_path


def run(host: str = "127.0.0.1", port: int = 8899) -> None:
    """Standalone uvicorn runner (CLI entrypoint)."""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")
