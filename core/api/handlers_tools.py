"""PkgForge sidecar API — dbus/rehearse/tools/fleet handlers (F2.2 split from core/api_server.py)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.api import transport
from i18n import load_settings, save_settings


# -- C1: D-Bus service bridge ------------------------------------
def handle_dbus_set_policy(params: dict[str, Any]) -> dict[str, Any]:
    s = load_settings()
    s["dbus_allow_mutations"] = bool(params.get("allow_mutations", False))
    save_settings(s)
    return {"ok": True, "allow_mutations": s["dbus_allow_mutations"]}


def handle_dbus_start(params: dict[str, Any]) -> dict[str, Any]:
    from core.dbus_service import start_default

    # Quick op (spawns its own serve thread); result/error via done event.
    transport._run_thread(start_default, "event/dbus_done")
    return {"started": True}


def handle_install_rehearse(params: dict[str, Any]) -> dict[str, Any]:
    """F5.14: konteyner ici kurulum provasi (dosya-liste diffi)."""
    from core.install_rehearsal import rehearse_install

    path = params.get("package_path", "")
    if not path:
        raise ValueError("package_path gerekli")
    return rehearse_install(Path(path))


def handle_tools_rpm_to_deb(params: dict[str, Any]) -> dict[str, Any]:
    """Feature Tezgahi: RPM -> DEB donusumu (CLI rpm-to-deb karsiligi)."""
    from core.rpm_to_deb_converter import is_rpm_to_deb_available, rpm_to_deb

    rpm_path = Path(params.get("rpm", ""))
    if not rpm_path.is_file():
        raise FileNotFoundError(f"RPM bulunamadi: {rpm_path}")
    out_raw = params.get("output_dir", "")
    out_dir = Path(out_raw) if out_raw else Path.cwd()

    def _op() -> Any:
        if not is_rpm_to_deb_available():
            return {"ok": False,
                    "message": "rpm2cpio veya dpkg-deb bulunamadi",
                    "deb_path": None}
        ok, msg, deb_path = rpm_to_deb(rpm_path, out_dir)
        return {"ok": ok, "message": msg,
                "deb_path": str(deb_path) if deb_path else None}

    transport._run_thread(_op, "event/rpm_to_deb_done")
    return {"started": True}


def handle_tools_abi_check(params: dict[str, Any]) -> dict[str, Any]:
    """Feature Tezgahi: ABI/sembol uyumluluk taramasi (CLI abi-check)."""
    from dataclasses import asdict

    from core.abi_scanner import check_abi_compatibility

    pkg_path = Path(params.get("package", ""))
    if not pkg_path.is_file():
        raise FileNotFoundError(f"Paket bulunamadi: {pkg_path}")

    def _op() -> Any:
        report = check_abi_compatibility(pkg_path)
        d = asdict(report)
        d["passed"] = report.passed
        d["error_count"] = report.error_count
        d["summary"] = report.summary()
        return d

    transport._run_thread(_op, "event/abi_check_done")
    return {"started": True}


def handle_tools_audit(params: dict[str, Any]) -> dict[str, Any]:
    """Feature Tezgahi: gecmis denetim izi (CLI audit karsiligi)."""
    from dataclasses import asdict

    from core.history_db import HistoryDB

    limit = int(params.get("limit", 100))
    date_from = params.get("date_from") or None
    date_to = params.get("date_to") or None

    records = HistoryDB().get_history(limit=limit)
    if date_from or date_to:
        filtered = []
        for r in records:
            if date_from and r.timestamp < date_from:
                continue
            if date_to and r.timestamp > date_to:
                continue
            filtered.append(r)
        records = filtered

    status_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    for r in records:
        status_counts[r.status] = status_counts.get(r.status, 0) + 1
        type_counts[r.package_type] = type_counts.get(r.package_type, 0) + 1

    integrity_issues = 0
    for r in records:
        if r.output_pkg and not Path(r.output_pkg).exists():
            integrity_issues += 1
        if r.backup_pkg and not Path(r.backup_pkg).exists():
            integrity_issues += 1

    anomalies = 0
    name_counts: dict[str, int] = {}
    for r in records:
        name_counts[r.package_name] = name_counts.get(r.package_name, 0) + 1
    for count in name_counts.values():
        if count > 3:
            anomalies += 1

    return {
        "total": len(records),
        "status_counts": status_counts,
        "type_counts": type_counts,
        "integrity_issues": integrity_issues,
        "anomalies": anomalies,
        "records": [asdict(r) for r in records],
    }


def handle_tools_scan_image(params: dict[str, Any]) -> dict[str, Any]:
    """Feature Tezgahi Faz 2: OCI imaj/arşiv taramasi (CLI scan-image)."""
    from core.malware_scanner import scan_oci_image

    image_path = Path(params.get("image", ""))
    if not image_path.exists():
        raise FileNotFoundError(f"Goruntu bulunamadi: {image_path}")

    def _op() -> Any:
        return scan_oci_image(image_path)

    transport._run_thread(_op, "event/scan_image_done")
    return {"started": True}


def handle_tools_attest(params: dict[str, Any]) -> dict[str, Any]:
    """Feature Tezgahi Faz 2: SLSA/in-toto attestation (CLI attest)."""
    from core.provenance import (
        create_attestation,
        find_provenance,
        load_provenance,
        save_attestation,
    )

    pkg_path = Path(params.get("package", ""))
    if not pkg_path.is_file():
        raise FileNotFoundError(f"Paket bulunamadi: {pkg_path}")
    signer_key = params.get("key", "") or ""

    def _op() -> Any:
        prov_path = find_provenance(pkg_path)
        if not prov_path:
            return {"ok": False,
                    "error": "Provenance kaydi bulunamadi (once convert calistirin)"}
        prov = load_provenance(prov_path)
        if not prov:
            return {"ok": False, "error": f"Provenance yuklenemedi: {prov_path}"}
        attestation = create_attestation(prov, signer_key=signer_key)
        att_path = save_attestation(
            attestation, pkg_path.parent / f"{pkg_path.name}.attestation.json")
        subject_name = ""
        if attestation.subject:
            subject_name = attestation.subject[0].get("name", "")
        return {
            "ok": True,
            "attestation_path": str(att_path),
            "statement_type": attestation._type,
            "predicate_type": attestation.predicate_type,
            "subject": subject_name,
            "builder": attestation.predicate.get("builder", {}).get("id", ""),
            "build_id": attestation.predicate.get(
                "metadata", {}).get("buildInvocationId", ""),
        }

    transport._run_thread(_op, "event/attest_done")
    return {"started": True}


def handle_tools_publish(params: dict[str, Any]) -> dict[str, Any]:
    """Feature Tezgahi Faz 2: AUR paketi hazirla/yayinla (CLI publish)."""
    from core.aur_publish import prepare_aur_package, push_to_aur

    pkg_path = Path(params.get("package", ""))
    if not pkg_path.is_file():
        raise FileNotFoundError(f"Paket bulunamadi: {pkg_path}")
    out_raw = params.get("output_dir", "")
    out_dir = Path(out_raw) if out_raw else Path.cwd()
    aur_url = params.get("aur_url", "") or ""

    def _op() -> Any:
        ok, msg, aur_pkg = prepare_aur_package(pkg_path, out_dir)
        if not ok or not aur_pkg:
            return {"ok": False, "message": msg}
        result = {
            "ok": True,
            "message": msg,
            "pkgbuild": str(aur_pkg.pkgbuild),
            "srcinfo": str(aur_pkg.srcinfo),
            "name": aur_pkg.name,
            "version": aur_pkg.version,
            "pushed": False,
            "push_message": "",
        }
        if aur_url:
            ok2, msg2 = push_to_aur(aur_pkg.pkgbuild.parent, aur_url)
            result["pushed"] = ok2
            result["push_message"] = msg2
            if not ok2:
                result["ok"] = False
        return result

    transport._run_thread(_op, "event/publish_done")
    return {"started": True}


def handle_tools_snapshot_status(params: dict[str, Any]) -> dict[str, Any]:
    """Feature Tezgahi Faz 2: snapshot-cleanup servis durumu (senkron)."""
    from core.snapshot_cleanup import get_cleanup_status

    return get_cleanup_status()


def handle_tools_snapshot_install(params: dict[str, Any]) -> dict[str, Any]:
    """Feature Tezgahi Faz 2: snapshot-cleanup servisi kur (CLI --install)."""
    from core.snapshot_cleanup import install_cleanup_service

    max_age = int(params.get("max_age_days", 7))

    def _op() -> Any:
        ok, msg = install_cleanup_service(max_age_days=max_age)
        return {"ok": ok, "message": msg}

    transport._run_thread(_op, "event/snapshot_done")
    return {"started": True}


def handle_tools_snapshot_remove(params: dict[str, Any]) -> dict[str, Any]:
    """Feature Tezgahi Faz 2: snapshot-cleanup servisini kaldir (CLI --remove)."""
    from core.snapshot_cleanup import remove_cleanup_service

    def _op() -> Any:
        ok, msg = remove_cleanup_service()
        return {"ok": ok, "message": msg}

    transport._run_thread(_op, "event/snapshot_done")
    return {"started": True}


def handle_fleet_status(params: dict[str, Any]) -> dict[str, Any]:
    """Fleet konsolu: tek-cagri agregasyon (senkron, salt-okunur)."""
    from core.fleet import get_fleet_status

    return get_fleet_status()
