"""PkgForge sidecar API — pipeline + history handlers (F2.2 split from core/api_server.py)."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from core.api import transport


def handle_pipeline_start(params: dict[str, Any]) -> dict[str, Any]:
    from core import intake
    from core.pipeline import ConversionPipeline

    path = Path(params.get("path", ""))
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    # Universal intake: accept every type; an optional 'mode' resolves an
    # ambiguous tarball (source_tarball / binary_tarball / ...).
    mode = params.get("mode") or None
    forced = None
    if mode:
        try:
            forced = intake.FileType(mode).value
        except ValueError:
            raise ValueError(f"Unknown mode: {mode}")
    ir = intake.classify(path)
    if ir.ambiguous and not forced:
        raise ValueError(
            "Ambiguous file type; pass mode='source_tarball' or mode='binary_tarball'")
    transport._ensure_qapp()
    transport._pipeline = ConversionPipeline()
    transport._pipeline.step_changed.connect(
        lambda step, status: transport._event("event/step_changed", {"step": step, "status": status}))
    transport._pipeline.progress.connect(
        lambda v: transport._event("event/progress", {"value": v}))
    transport._pipeline.log_message.connect(
        lambda msg, level: transport._event("event/log", {"message": msg, "level": level}))
    transport._pipeline.compatibility_ready.connect(
        lambda report: transport._event("event/compatibility_ready", {"report": report.to_dict()}))
    transport._pipeline.finished.connect(
        lambda result: transport._event("event/finished", {
            "success": result.success,
            "message": result.message,
            "output_pkg": str(result.converted_pkg) if result.converted_pkg else "",
        }))
    transport._pipeline.stage(path, forced)
    # run on a worker thread so stdin keeps being read
    threading.Thread(target=transport._pipeline.run_staged, daemon=True).start()
    return {"started": True}


def handle_pipeline_cancel(params: dict[str, Any]) -> dict[str, Any]:
    if transport._pipeline:
        transport._pipeline.cancel()
    return {"ok": True}


def handle_pipeline_approve(params: dict[str, Any]) -> dict[str, Any]:
    if transport._pipeline:
        transport._pipeline.approve_install()
    return {"ok": True}


def handle_pipeline_dismiss(params: dict[str, Any]) -> dict[str, Any]:
    if transport._pipeline:
        transport._pipeline.dismiss_install(params.get("message", ""))
    return {"ok": True}


def handle_history_uninstall(params: dict[str, Any]) -> dict[str, Any]:
    from core.security import is_valid_package_name

    name = params.get("name", "")
    if not is_valid_package_name(name):
        raise ValueError(f"Invalid package name: {name}")
    # Actual pacman -R requires privilege escalation; the desktop UI
    # triggers pkexec via its own privileged helper in a later phase.
    return {"ok": True, "requires_privilege": True, "package": name}


def handle_history_rollback(params: dict[str, Any]) -> dict[str, Any]:
    from core.history_db import HistoryDB
    from core.security import is_valid_package_name

    name = params.get("name", "")
    if not is_valid_package_name(name):
        raise ValueError(f"Invalid package name: {name}")
    db = HistoryDB()
    records = db.get_records_for_package(name)
    backups = [r for r in records if r.backup_pkg and Path(r.backup_pkg).is_file()]
    if not backups:
        raise FileNotFoundError(f"No backup found for {name}")
    return {"ok": True, "requires_privilege": True, "backup": backups[0].backup_pkg}


def handle_history_clear(params: dict[str, Any]) -> dict[str, Any]:
    from core.history_db import HistoryDB

    db = HistoryDB()
    db.clear_history()
    return {"ok": True}


def handle_history_restore(params: dict[str, Any]) -> dict[str, Any]:
    """Faz 9 (5.7): undo of history.clear — re-insert saved records."""
    from core.history_db import HistoryDB

    records = params.get("records") or []
    if not isinstance(records, list):
        raise TypeError("records bir liste olmalı")
    db = HistoryDB()
    restored = db.restore_records(records)
    return {"ok": True, "restored": restored}
