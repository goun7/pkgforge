"""PkgForge sidecar API — security panel handlers (F2.2 split from core/api_server.py)."""
from __future__ import annotations

from pathlib import Path

from config import discover_tools
from core.api import transport


def handle_security_verify(params):
    from dataclasses import asdict

    from core.package_signing import verify_signature

    path = transport._require_pkg_file(params)
    return asdict(verify_signature(path))


def handle_security_keys(params):
    from core.package_signing import list_keys

    return list_keys()


def handle_security_sigstore_status(params):
    from core.sigstore import get_sigstore_status

    return get_sigstore_status()


def handle_security_provenance(params):
    from core.provenance import find_provenance, load_provenance

    path = Path(params.get("pkg_path", ""))
    prov_path = find_provenance(path)
    if prov_path is None:
        return None
    prov = load_provenance(prov_path)
    return prov.to_dict() if prov else None


def _run_security_thread(fn, event_name="event/security_done"):
    """Backwards-compatible alias for security ops."""
    transport._run_security_thread(fn, event_name)


def handle_security_sign(params):
    from core.package_signing import sign_package

    path = transport._require_pkg_file(params)
    key_path = Path(params["key_path"]) if params.get("key_path") else None
    passphrase = params.get("passphrase", "")

    def _op():
        ok, msg = sign_package(path, key_path=key_path, passphrase=passphrase)
        return {"ok": ok, "message": msg}

    _run_security_thread(_op)
    return {"started": True}


def handle_security_sbom(params):
    from core.sbom import generate_sbom

    path = transport._require_pkg_file(params)
    include_hashes = bool(params.get("include_hashes", True))
    tools = discover_tools()

    def _op():
        doc = generate_sbom(path, tools, include_hashes=include_hashes)
        return doc.to_dict()

    _run_security_thread(_op)
    return {"started": True}


def handle_security_quality(params):
    from dataclasses import asdict

    from core.quality_score import score_package

    path = transport._require_pkg_file(params)
    tools = discover_tools()

    def _op():
        report = score_package(path, tools)
        d = asdict(report)
        d["passed"] = report.passed
        return d

    _run_security_thread(_op)
    return {"started": True}


def handle_security_provenance_create(params):
    from core.provenance import create_provenance, save_provenance

    source_file = Path(params.get("source_file", ""))
    output_file = Path(params.get("output_file", ""))
    if not source_file.is_file():
        raise FileNotFoundError(f"Source not found: {source_file}")

    def _op():
        prov = create_provenance(
            source_file=source_file,
            output_file=output_file,
            source_type=params.get("source_type", ""),
            source_url=params.get("source_url", ""),
        )
        save_path = Path(str(output_file) + ".provenance.json")
        save_provenance(prov, save_path)
        return prov.to_dict()

    _run_security_thread(_op)
    return {"started": True}


def handle_security_cve_scan(params):
    from core.cve_scanner import scan_package

    pkg_path = transport._require_pkg_file(params)
    tools = discover_tools()

    def _op():
        return scan_package(pkg_path, tools)

    _run_security_thread(_op)
    return {"started": True}

