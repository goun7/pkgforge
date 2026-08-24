"""PkgForge — JSON-RPC 2.0 sidecar over stdio.

Framing: one JSON object per line on stdin/stdout. Logs go to stderr ONLY.
This module wraps the existing core modules; it adds NO new business logic.
"""
from __future__ import annotations

import json
import logging
import queue
import sys
import threading
import time
from collections import deque
from pathlib import Path

from config import APP_VERSION, discover_tools
from core import http_assets

# F5.11: stateless meta handler'lar router paketine tasindi; facade olarak
# buradan import edilip METHODS'a kaydedilir (testler degismez).
from core.http_api.meta import (
    handle_app_doctor,
    handle_app_version,
    handle_policy_evaluate,
    handle_policy_get,
    handle_policy_set,
    handle_settings_get,
    handle_settings_set,
    handle_stats_wrapped,
    handle_system_health,
    handle_tools_status,
)
from i18n import load_settings, save_settings

_write_lock = threading.Lock()

# Pipeline state (single conversion at a time, matching the GUI model)
_pipeline = None

# When True (HTTP/LAN mode) push events have no stdio channel to ride on,
# so _event() suppresses them instead of polluting the server's stdout.
_http_mode = False

# F5.23: SSE (Server-Sent Events) event bus for the HTTP dashboard. A ring
# buffer keeps recent events for late subscribers; each connected /events
# client gets its own queue. Publishing is best-effort and never blocks the
# conversion pipeline.
_sse_lock = threading.Lock()
_sse_history: deque = deque(maxlen=100)
_sse_subscribers: list = []


def _sse_publish(method, params):
    """Broadcast a push event to SSE subscribers + the ring buffer."""
    payload = {"method": method, "params": params}
    with _sse_lock:
        _sse_history.append(payload)
        for q in _sse_subscribers:
            try:
                q.put_nowait(payload)
            except Exception:  # noqa: BLE001, S110 - full/dead subscriber
                pass


def _sse_subscribe():
    q = queue.Queue(maxsize=256)
    with _sse_lock:
        _sse_subscribers.append(q)
    return q


def _sse_unsubscribe(q):
    with _sse_lock:
        if q in _sse_subscribers:
            _sse_subscribers.remove(q)


def _send(obj: dict) -> None:
    with _write_lock:
        sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def _result(req_id, result):
    _send({"jsonrpc": "2.0", "id": req_id, "result": result})


def _error(req_id, code, message):
    _send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def _event(method, params):
    if _http_mode:
        # F5.23: no stdio channel in HTTP mode; broadcast over SSE instead.
        _sse_publish(method, params)
        return
    _send({"jsonrpc": "2.0", "method": method, "params": params})


def _ensure_qapp():
    from PyQt6.QtCore import QCoreApplication

    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


def handle_pipeline_start(params):
    global _pipeline
    from core.pipeline import ConversionPipeline

    path = Path(params.get("path", ""))
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    if path.suffix.lower() not in (".deb", ".rpm"):
        raise ValueError(f"Unsupported file type: {path.suffix}")
    _ensure_qapp()
    _pipeline = ConversionPipeline()
    _pipeline.step_changed.connect(
        lambda step, status: _event("event/step_changed", {"step": step, "status": status}))
    _pipeline.progress.connect(
        lambda v: _event("event/progress", {"value": v}))
    _pipeline.log_message.connect(
        lambda msg, level: _event("event/log", {"message": msg, "level": level}))
    _pipeline.compatibility_ready.connect(
        lambda report: _event("event/compatibility_ready", {"report": report.to_dict()}))
    _pipeline.finished.connect(
        lambda result: _event("event/finished", {
            "success": result.success,
            "message": result.message,
            "output_pkg": str(result.converted_pkg) if result.converted_pkg else "",
        }))
    _pipeline.stage(path)
    # run on a worker thread so stdin keeps being read
    threading.Thread(target=_pipeline.run_staged, daemon=True).start()
    return {"started": True}


def handle_pipeline_cancel(params):
    if _pipeline:
        _pipeline.cancel()
    return {"ok": True}


def handle_pipeline_approve(params):
    if _pipeline:
        _pipeline.approve_install()
    return {"ok": True}


def handle_pipeline_dismiss(params):
    if _pipeline:
        _pipeline.dismiss_install(params.get("message", ""))
    return {"ok": True}


def handle_history_list(params):
    from core.history_db import HistoryDB

    db = HistoryDB()
    records = db.get_history(limit=int(params.get("limit", 100)))
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp,
            "package_name": r.package_name,
            "package_type": r.package_type,
            "status": r.status,
            "original_file": r.original_file,
            "source_url": r.source_url or "",
        }
        for r in records
    ]


def handle_history_uninstall(params):
    from core.security import is_valid_package_name

    name = params.get("name", "")
    if not is_valid_package_name(name):
        raise ValueError(f"Invalid package name: {name}")
    # Actual pacman -R requires privilege escalation; the desktop UI
    # triggers pkexec via its own privileged helper in a later phase.
    return {"ok": True, "requires_privilege": True, "package": name}


def handle_history_rollback(params):
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


def handle_history_clear(params):
    from core.history_db import HistoryDB

    db = HistoryDB()
    db.clear_history()
    return {"ok": True}


# ── Faz 1 / A2: security panel ──────────────────────────────────

def _require_pkg_file(params) -> Path:
    """Resolve and validate a package path param, raising if missing."""
    path = Path(params.get("pkg_path", ""))
    if not path.is_file():
        raise FileNotFoundError(f"Package not found: {path}")
    return path


def handle_security_verify(params):
    from dataclasses import asdict

    from core.package_signing import verify_signature

    path = _require_pkg_file(params)
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


def _run_thread(fn, event_name):
    """Run a blocking op on a daemon thread, emitting a done event.

    The done event carries {"ok": True, "result": ...} on success or
    {"ok": False, "error": str} on failure. Used by all long-running
    Faz 1 handlers (export, graph, source, system).
    """

    def _worker():
        try:
            result = fn()
            _event(event_name, {"ok": True, "result": result})
        except Exception as exc:  # noqa: BLE001
            _event(event_name, {"ok": False, "error": str(exc)})

    threading.Thread(target=_worker, daemon=True).start()


def _run_security_thread(fn, event_name="event/security_done"):
    """Backwards-compatible alias for security ops."""
    _run_thread(fn, event_name)


def handle_security_sign(params):
    from core.package_signing import sign_package

    path = _require_pkg_file(params)
    key_path = Path(params["key_path"]) if params.get("key_path") else None
    passphrase = params.get("passphrase", "")

    def _op():
        ok, msg = sign_package(path, key_path=key_path, passphrase=passphrase)
        return {"ok": ok, "message": msg}

    _run_security_thread(_op)
    return {"started": True}


def handle_security_sbom(params):
    from core.sbom import generate_sbom

    path = _require_pkg_file(params)
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

    path = _require_pkg_file(params)
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

    pkg_path = _require_pkg_file(params)
    tools = discover_tools()

    def _op():
        return scan_package(pkg_path, tools)

    _run_security_thread(_op)
    return {"started": True}


# ── Faz 1 / A4: delta updater ───────────────────────────────────

def handle_delta_status(params):
    from core.delta_updater import get_auto_update_status

    return get_auto_update_status()


def handle_delta_enable(params):
    # Enabling the systemd timer requires privilege escalation; the desktop
    # UI triggers pkexec via its own privileged helper in a later phase.
    return {"ok": False, "requires_privilege": True,
            "message": "Delta auto-update etkinleştirme yetkili işlem gerektiriyor (pkexec)"}


def handle_delta_disable(params):
    return {"ok": False, "requires_privilege": True,
            "message": "Delta auto-update kapatma yetkili işlem gerektiriyor (pkexec)"}


# ── Faz 1 / A1: export centers ──────────────────────────────────

def handle_export_oci(params):
    from core.oci_builder import build_oci_image

    path = _require_pkg_file(params)
    tools = discover_tools()
    tag = params.get("tag") or None
    output_file = Path(params["output_file"]) if params.get("output_file") else None

    def _op():
        ok, msg, out = build_oci_image(path, tools, tag=tag, output_file=output_file)
        return {"ok": ok, "message": msg, "output_path": str(out) if out else ""}

    _run_thread(_op, "event/export_done")
    return {"started": True}


def handle_export_appimage_to_deb(params):
    from core.appimage_converter import appimage_to_deb

    appimage = Path(params.get("appimage_path", ""))
    if not appimage.is_file():
        raise FileNotFoundError(f"AppImage not found: {appimage}")
    out_dir = Path(params.get("output_dir", "."))

    def _op():
        ok, msg, deb = appimage_to_deb(appimage, out_dir)
        return {"ok": ok, "message": msg, "deb_path": str(deb) if deb else ""}

    _run_thread(_op, "event/export_done")
    return {"started": True}


def handle_export_flatpak_list(params):
    from dataclasses import asdict

    from core.flatpak_converter import list_installed_apps

    return [asdict(app) for app in list_installed_apps()]


def handle_export_flatpak_to_deb(params):
    from core.flatpak_converter import flatpak_to_deb

    app_id = params.get("app_id", "")
    if not app_id:
        raise ValueError("app_id is required")
    branch = params.get("branch", "stable")
    out_dir = Path(params.get("output_dir", "."))

    def _op():
        ok, msg, deb = flatpak_to_deb(app_id, out_dir, branch=branch)
        return {"ok": ok, "message": msg, "deb_path": str(deb) if deb else ""}

    _run_thread(_op, "event/export_done")
    return {"started": True}


# ── Faz 1 / A3: dependency graph ────────────────────────────────

def handle_graph_build(params):
    from dataclasses import asdict

    from core.dep_graph import build_dep_graph, build_file_dep_graph

    path = _require_pkg_file(params)
    show_files = bool(params.get("files", False))

    def _op():
        graph = build_file_dep_graph(path) if show_files else build_dep_graph(path)
        return {
            "root": graph.root,
            "nodes": {name: asdict(node) for name, node in graph.nodes.items()},
            "stats": graph.stats(),
            "mermaid": graph.to_mermaid(),
            "warnings": graph.warnings,
        }

    _run_thread(_op, "event/graph_done")
    return {"started": True}


# ── Faz 1 / A5: from-source PKGBUILD ────────────────────────────

def handle_source_generate(params):
    import tempfile

    from core.from_source import generate_pkgbuild_from_source
    from core.security import safe_run

    repo_url = params.get("repo_url", "").strip()
    if not repo_url:
        raise ValueError("repo_url is required")
    out_dir = Path(params.get("output_dir", ".")).resolve()

    def _op():
        with tempfile.TemporaryDirectory(prefix="pkgforge_src_") as tmpdir:
            tmp = Path(tmpdir)
            _event("event/source_progress", {"step": "clone"})
            res = safe_run(["git", "clone", "--depth=1", repo_url, str(tmp / "repo")], timeout=120)
            if res.returncode != 0:
                raise RuntimeError(f"git clone failed: {res.stderr[:200]}")
            repo_dir = tmp / "repo"

            proj_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
            _event("event/source_progress", {"step": "detect"})
            build_system = "unknown"
            if (repo_dir / "CMakeLists.txt").exists():
                build_system = "cmake"
            elif (repo_dir / "meson.build").exists():
                build_system = "meson"
            elif (repo_dir / "Cargo.toml").exists():
                build_system = "cargo"
            elif (repo_dir / "configure").exists():
                build_system = "autotools"
            elif (repo_dir / "Makefile").exists() or (repo_dir / "makefile").exists():
                build_system = "make"
            elif (repo_dir / "setup.py").exists():
                build_system = "python"

            _event("event/source_progress", {"step": "generate"})
            content = generate_pkgbuild_from_source(proj_name, repo_url, build_system, repo_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            pkgbuild_path = out_dir / f"PKGBUILD-{proj_name}"
            pkgbuild_path.write_text(content, encoding="utf-8")
            return {
                "ok": True,
                "proj_name": proj_name,
                "build_system": build_system,
                "pkgbuild_path": str(pkgbuild_path),
                "pkgbuild_content": content,
            }

    _run_thread(_op, "event/source_done")
    return {"started": True}


# ── Faz 1 / A6: system tools ────────────────────────────────────

def handle_system_cross_check(params):
    from dataclasses import asdict

    from core.cross_check import cross_check_package

    name = params.get("package_name", "")
    if not name:
        raise ValueError("package_name is required")
    local_version = params.get("local_version", "")

    def _op():
        return asdict(cross_check_package(name, local_version))

    _run_thread(_op, "event/cross_check_done")
    return {"started": True}


def handle_system_snapshot_status(params):
    from core.snapshot_cleanup import get_cleanup_status

    return get_cleanup_status()


def handle_system_snapshot_install(params):
    return {"ok": False, "requires_privilege": True,
            "message": "Snapshot temizlik servisi kurulumu yetkili işlem gerektiriyor (pkexec)"}


def handle_system_snapshot_remove(params):
    return {"ok": False, "requires_privilege": True,
            "message": "Snapshot temizlik servisi kaldırma yetkili işlem gerektiriyor (pkexec)"}


def handle_system_verify_rollback(params):
    from dataclasses import asdict

    from core.rollback_verify import verify_rollback

    def _op():
        return asdict(verify_rollback())

    _run_thread(_op, "event/system_done")
    return {"started": True}


def handle_system_benchmark(params):
    from dataclasses import asdict

    from core.benchmark import run_benchmarks

    quick = bool(params.get("quick", False))

    def _op():
        report = run_benchmarks(quick=quick)
        d = asdict(report)
        d["passed"] = report.passed
        return d

    _run_thread(_op, "event/bench_done")
    return {"started": True}


# ── Faz 2 / B8: plugin marketplace ──────────────────────────────

def handle_plugin_list(params):
    from core.plugins.marketplace import list_installed_plugins

    return list_installed_plugins()


def handle_plugin_available(params):
    from core.plugins.marketplace import fetch_available_plugins

    offline = bool(params.get("offline", False))
    return fetch_available_plugins(offline=offline)


def handle_plugin_install(params):
    from core.plugins import reload_plugins
    from core.plugins.marketplace import install_plugin

    name = params.get("name", "")
    version = params.get("version", "latest")
    force = bool(params.get("force", False))

    def _op():
        path = install_plugin(name, version=version, force=force)
        reload_plugins()
        return {"ok": True, "path": str(path)}

    _run_thread(_op, "event/plugin_done")
    return {"started": True}


def handle_plugin_uninstall(params):
    from core.plugins import reload_plugins
    from core.plugins.marketplace import is_valid_plugin_name, uninstall_plugin

    name = params.get("name", "")
    if not is_valid_plugin_name(name):
        raise ValueError(f"Invalid plugin name: {name}")
    removed = uninstall_plugin(name)
    if not removed:
        raise FileNotFoundError(f"Plugin not found: {name}")
    reload_plugins()
    return {"ok": True}


def handle_plugin_update(params):
    from core.plugins import reload_plugins
    from core.plugins.marketplace import update_plugin

    name = params.get("name", "")

    def _op():
        ok, msg, _path = update_plugin(name)
        if ok:
            reload_plugins()
        return {"ok": ok, "message": msg}

    _run_thread(_op, "event/plugin_done")
    return {"started": True}


def handle_plugin_audit(params):
    from core.plugins.marketplace import audit_plugins

    return audit_plugins()


# ── Faz 2 / B5: package comparison ──────────────────────────────

def handle_compare_diff(params):
    from core.sbom import diff_sboms, generate_sbom

    old_path = Path(params.get("old_path", ""))
    new_path = Path(params.get("new_path", ""))
    if not old_path.is_file():
        raise FileNotFoundError(f"Old package not found: {old_path}")
    if not new_path.is_file():
        raise FileNotFoundError(f"New package not found: {new_path}")
    tools = discover_tools()

    def _op():
        old_sbom = generate_sbom(old_path, tools, include_hashes=True)
        new_sbom = generate_sbom(new_path, tools, include_hashes=True)
        diff = diff_sboms(old_sbom, new_sbom)
        return diff.to_dict()

    _run_thread(_op, "event/compare_done")
    return {"started": True}


# ── Faz 2 / B1: AUR browser ─────────────────────────────────────

_AUR_NAME_RE = __import__("re").compile(r"^[A-Za-z0-9@._+-]+$")


def _validate_aur_name(name: str) -> None:
    if not name or not _AUR_NAME_RE.match(name) or len(name) > 255:
        raise ValueError(f"Invalid AUR package name: {name!r}")


def handle_aur_search(params):
    from core.aur_checker import search_aur

    query = str(params.get("query", ""))
    limit = int(params.get("limit", 25))

    def _op():
        return search_aur(query, limit=limit)

    _run_thread(_op, "event/aur_search_done")
    return {"started": True}


def handle_aur_info(params):
    from dataclasses import asdict

    from core.aur_checker import check_aur

    name = str(params.get("name", ""))
    _validate_aur_name(name)

    def _op():
        return asdict(check_aur(name))

    _run_thread(_op, "event/aur_info_done")
    return {"started": True}


def handle_aur_build(params):
    import shutil
    import subprocess as _sp
    import tempfile

    name = str(params.get("name", ""))
    install = bool(params.get("install", False))
    _validate_aur_name(name)

    def _op():
        _event("event/aur_build_progress", {"name": name, "step": "clone"})
        workdir = Path(tempfile.mkdtemp(prefix=f"pkgforge-aur-{name}-"))
        clone_url = f"https://aur.archlinux.org/{name}.git"
        r = _sp.run(
            ["git", "clone", "--depth=1", clone_url, str(workdir / name)],
            capture_output=True, text=True, timeout=180, check=False,
        )
        if r.returncode != 0:
            raise RuntimeError(f"git clone başarısız: {r.stderr.strip()[:300]}")

        _event("event/aur_build_progress", {"name": name, "step": "build"})
        cmd = ["makepkg", "-f", "--noconfirm"]
        if install and shutil.which("pacman"):
            cmd = ["makepkg", "-si", "--noconfirm"]
        b = _sp.run(
            cmd, capture_output=True, text=True, timeout=3600,
            cwd=str(workdir / name), check=False,
        )
        if b.returncode != 0:
            raise RuntimeError(f"makepkg başarısız: {b.stderr.strip()[-300:]}")

        built = sorted((workdir / name).glob("*.pkg.tar.zst"))
        if not built:
            raise RuntimeError("makepkg tamamlandı ama paket dosyası bulunamadı")
        return {"name": name, "pkg_path": str(built[-1]), "installed": install}

    _run_thread(_op, "event/aur_build_done")
    return {"started": True}


# ── Faz 2 / B6: batch conversion queue ──────────────────────────

_queue_lock = threading.Lock()
_queue_items: dict = {}   # id -> {id, path, status, priority, message}
_queue_seq = 0
_queue_running = False
# Live batch pipelines keyed by item_id (F4.3 honesty fix).
_active_pipelines: dict = {}

# F5.12: durable backing for the queue. Best-effort — a DB failure must never
# break the in-memory hot path.
_queue_store = None
_queue_store_lock = threading.Lock()


def _get_queue_store():
    global _queue_store
    with _queue_store_lock:
        if _queue_store is None:
            try:
                from core.queue_store import QueueStore
                _queue_store = QueueStore()
            except Exception:  # noqa: BLE001 - persistence is best-effort
                _queue_store = False  # sentinel: tried and failed
        return _queue_store or None


def _persist_item(item) -> None:
    store = _get_queue_store()
    if store is None:
        return
    try:
        store.upsert(item)
    except Exception:  # noqa: BLE001, S110 - best-effort persistence
        pass


def _persist_remove(item_id) -> None:
    store = _get_queue_store()
    if store is None:
        return
    try:
        store.remove(item_id)
    except Exception:  # noqa: BLE001, S110 - best-effort persistence
        pass


def _persist_clear(status="") -> None:
    store = _get_queue_store()
    if store is None:
        return
    try:
        store.clear(status)
    except Exception:  # noqa: BLE001, S110 - best-effort persistence
        pass


def restore_queue() -> int:
    """Reload pending queue items from the durable store (F5.12).

    Called on startup. Items are coerced to 'pending' and the id sequence is
    advanced past them so new additions do not collide. Returns the count.
    """
    global _queue_seq
    store = _get_queue_store()
    if store is None:
        return 0
    try:
        items = store.load_restorable()
    except Exception:  # noqa: BLE001
        return 0
    restored = 0
    with _queue_lock:
        for item in items:
            if item["id"] in _queue_items:
                continue
            _queue_items[item["id"]] = item
            restored += 1
            iid = item["id"]
            if iid.startswith("q") and iid[1:].isdigit():
                _queue_seq = max(_queue_seq, int(iid[1:]))
    return restored


def _make_pipeline(path, item_id, do_install=False):
    """Build a ConversionPipeline whose events are tagged with item_id.

    F4.3 honesty: batch is CONVERSION-ONLY by default. The decision gate is
    released via dismiss_install() so no package touches the system unless
    the caller explicitly opted in with do_install=True.
    """
    from PyQt6.QtCore import Qt

    from core.pipeline import ConversionPipeline

    _ensure_qapp()
    p = ConversionPipeline()

    # F4.3: slots run DIRECTLY on the emitting thread. Batch dispatcher
    # threads have no Qt event loop; queued delivery would never fire the
    # auto-approve gate and deadlock the item. These lambdas only touch
    # thread-safe state (_event -> write lock, dict under _queue_lock).
    direct = Qt.ConnectionType.DirectConnection

    def _track_finished(result):
        _active_pipelines.pop(item_id, None)
        _set_item(item_id, status="done" if result.success else "error",
                  message=result.message)

    p.step_changed.connect(
        lambda step, status: _event("event/step_changed", {"step": step, "status": status, "item_id": item_id}), type=direct)
    p.progress.connect(
        lambda v: _event("event/progress", {"value": v, "item_id": item_id}), type=direct)
    p.log_message.connect(
        lambda msg, level: _event("event/log", {"message": msg, "level": level, "item_id": item_id}), type=direct)
    p.compatibility_ready.connect(
        lambda report: _event("event/compatibility_ready", {"report": report.to_dict(), "item_id": item_id}), type=direct)
    if do_install:
        p.compatibility_ready.connect(lambda report: p.approve_install(), type=direct)
    else:
        pkg_label = Path(path).name
        p._skip_install_message = f"{pkg_label} dönüştürüldü (kurulum atlandı)"
        p.compatibility_ready.connect(
            lambda report: p.dismiss_install(), type=direct)
    p.finished.connect(_track_finished, type=direct)
    p.finished.connect(
        lambda result: _event("event/finished", {
            "success": result.success,
            "message": result.message,
            "output_pkg": str(result.converted_pkg) if result.converted_pkg else "",
            "item_id": item_id,
        }), type=direct)
    _active_pipelines[item_id] = p
    return p


def _set_item(item_id, **fields):
    with _queue_lock:
        if item_id in _queue_items:
            _queue_items[item_id].update(fields)
            _persist_item(_queue_items[item_id])


def handle_queue_add(params):
    global _queue_seq
    paths = params.get("paths", [])
    if isinstance(paths, str):
        paths = [paths]
    added = 0
    with _queue_lock:
        for raw in paths:
            path = Path(str(raw))
            if not path.is_file():
                continue
            if path.suffix.lower() not in (".deb", ".rpm"):
                continue
            _queue_seq += 1
            item_id = f"q{_queue_seq}"
            _queue_items[item_id] = {
                "id": item_id,
                "path": str(path),
                "name": path.name,
                "status": "pending",
                "priority": int(params.get("priority", 0)),
                "message": "",
            }
            _persist_item(_queue_items[item_id])
            added += 1
    return {"added": added}


def handle_queue_list(params):
    with _queue_lock:
        items = list(_queue_items.values())
    items.sort(key=lambda it: (-it["priority"], it["id"]))
    return items


def handle_queue_priority(params):
    item_id = params.get("id", "")
    with _queue_lock:
        if item_id not in _queue_items:
            raise KeyError(f"Queue item not found: {item_id}")
        _queue_items[item_id]["priority"] = int(params.get("priority", 0))
        _persist_item(_queue_items[item_id])
    return {"ok": True}


def handle_queue_remove(params):
    item_id = params.get("id", "")
    with _queue_lock:
        _queue_items.pop(item_id, None)
    _persist_remove(item_id)
    return {"ok": True}


def handle_queue_clear(params):
    status = params.get("status", "")
    with _queue_lock:
        if not status:
            _queue_items.clear()
        else:
            for k in [k for k, v in _queue_items.items() if v["status"] == status]:
                del _queue_items[k]
    _persist_clear(status)
    return {"ok": True}


def _queue_dispatch(parallel, do_install=False):
    """Worker: process pending queue items by priority until none remain."""
    global _queue_running
    parallel = max(1, min(4, int(parallel)))
    if do_install:
        # pacman's database lock makes concurrent installs race; serialize.
        parallel = 1
    try:
        while True:
            with _queue_lock:
                pending = [it for it in _queue_items.values() if it["status"] == "pending"]
            if not pending:
                break
            pending.sort(key=lambda it: (-it["priority"], it["id"]))
            batch = pending[: max(1, parallel)]
            threads = []
            for it in batch:
                _set_item(it["id"], status="running", message="")
                p = _make_pipeline(Path(it["path"]), it["id"], do_install=do_install)
                p.stage(Path(it["path"]))
                t = threading.Thread(target=p.run_staged, daemon=True)
                t.start()
                threads.append(t)
            for t in threads:
                t.join()
    finally:
        _queue_running = False
        _event("event/queue_done", {"ok": True})


def handle_queue_cancel(params):
    """Cancel one (item_id) or all running batch pipelines."""
    item_id = str(params.get("item_id", "")).strip()
    with _queue_lock:
        targets = [(iid, pl) for iid, pl in _active_pipelines.items()
                   if not item_id or iid == item_id]
    cancelled = 0
    for _iid, pl in targets:
        try:
            pl.cancel()
            cancelled += 1
        except Exception as exc:  # noqa: BLE001 - keep cancelling the rest
            logging.getLogger(__name__).warning("queue cancel failed: %s", exc)
    return {"cancelled": cancelled}


def handle_queue_start(params):
    global _queue_running
    do_install = bool(params.get("install", False))
    parallel = max(1, min(4, int(params.get("parallel", 1))))
    if do_install:
        parallel = 1
    with _queue_lock:
        has_pending = any(it["status"] == "pending" for it in _queue_items.values())
    if not has_pending:
        return {"started": False, "reason": "no pending items"}
    if _queue_running:
        return {"started": False, "reason": "already running"}
    _queue_running = True
    threading.Thread(target=_queue_dispatch, args=(parallel, do_install),
                       daemon=True).start()
    return {"started": True}


# ── Faz 2 / B3: scheduled tasks ─────────────────────────────────

_scheduler_started = False


def _schedule_state():
    from core.scheduler import state as sched_state

    return sched_state()


def handle_schedule_get(params):
    st = _schedule_state()
    next_run = ""
    if st["enabled"]:
        try:
            if st["last_run"]:
                last = time.mktime(time.strptime(st["last_run"], "%Y-%m-%d %H:%M:%S"))
                next_run = time.strftime("%Y-%m-%d %H:%M:%S",
                                         time.localtime(last + st["interval_hours"] * 3600))
            else:
                next_run = time.strftime("%Y-%m-%d %H:%M:%S",
                                         time.localtime(time.time() + st["interval_hours"] * 3600))
        except (ValueError, OverflowError, OSError):
            next_run = ""
    st["next_run"] = next_run
    return st


def handle_schedule_set(params):
    s = load_settings()
    if "enabled" in params:
        s["schedule_enabled"] = bool(params["enabled"])
    if "interval_hours" in params:
        s["schedule_interval_hours"] = max(1.0, float(params["interval_hours"]))
    if "task" in params:
        s["schedule_task"] = str(params["task"])
    save_settings(s)
    return {"ok": True}


def _scheduler_tick():
    """Daemon loop: run the scheduled task when its interval elapses."""
    while True:
        try:
            st = _schedule_state()
            if st["enabled"]:
                due = True
                if st["last_run"]:
                    try:
                        last = time.mktime(time.strptime(st["last_run"], "%Y-%m-%d %H:%M:%S"))
                        due = (time.time() - last) >= st["interval_hours"] * 3600
                    except (ValueError, OverflowError, OSError):
                        due = True
                if due:
                    now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                    s = load_settings()
                    s["schedule_last_run"] = now
                    save_settings(s)
                    _event("event/schedule_ran", {"task": st["task"], "at": now})
        except Exception as exc:  # noqa: BLE001
            _event("event/schedule_ran", {"task": "", "error": str(exc)})
        time.sleep(60)


def _ensure_scheduler():
    global _scheduler_started
    if not _scheduler_started:
        _scheduler_started = True
        threading.Thread(target=_scheduler_tick, daemon=True).start()


# -- C2: multi-profile management -------------------------------
def handle_profile_list(params):
    from core.profiles import list_profiles

    return list_profiles()


def handle_profile_current(params):
    from core.profiles import current_profile

    return {"name": current_profile()}


def _profile_name(params) -> str:
    return str(params.get("name", "")).strip()


def handle_profile_create(params):
    from core.profiles import create_profile

    return create_profile(_profile_name(params))


def handle_profile_switch(params):
    from core.profiles import switch_profile

    result = switch_profile(_profile_name(params))
    # Rebind cached UI state (language) to the new profile settings.
    try:
        from i18n import init_language

        init_language()
    except Exception as exc:  # noqa: BLE001 - cosmetic; never fail the switch
        logging.getLogger(__name__).debug("init_language after switch failed: %s", exc)
    return result


def handle_profile_delete(params):
    from core.profiles import delete_profile

    return delete_profile(_profile_name(params))


# -- C3: backup & cloud sync ------------------------------------
def handle_sync_export(params):
    from core.cloud_sync import export_backup

    output = str(params.get("output_path", "")).strip()
    return export_backup(output or None)


def handle_sync_import(params):
    from core.cloud_sync import import_backup

    return import_backup(str(params.get("backup_path", "")))


def handle_schedule_timer_install(params):
    """Install systemd user timer units (dry_run preview by default)."""
    from core.scheduler import install_timer

    return install_timer(
        interval_hours=params.get("interval_hours"),
        dry_run=bool(params.get("dry_run", True)))


def handle_schedule_run(params):
    """Run the scheduled task immediately (force unless told otherwise)."""
    from core.scheduler import run_due

    return run_due(force=bool(params.get("force", False)))


def handle_sync_config(params):
    s = load_settings()
    if "sync_url" in params:
        s["sync_url"] = str(params["sync_url"]).strip()
    if "sync_username" in params:
        s["sync_username"] = str(params["sync_username"]).strip()

    stored_in = "settings"
    warning = ""
    if params.get("sync_password"):
        secret = str(params["sync_password"])
        user = s.get("sync_username", "")
        from core.secrets_store import available, webdav_store

        if user and available():
            try:
                webdav_store(str(user)).set_secret(secret)
                stored_in = "keyring"
                s.pop("sync_password", None)  # migrate off plaintext
            except Exception as exc:  # noqa: BLE001 - fallback to settings
                warning = f"Anahtarlık kullanılamadı: {exc}"
                s["sync_password"] = secret
        else:
            s["sync_password"] = secret
            if not user:
                warning = "Anahtarlik icin kullanici adi gerekli"

    save_settings(s)
    out = {"ok": True, "password_stored": stored_in}
    if warning:
        out["warning"] = warning
    return out


def handle_sync_push(params):
    from core.cloud_sync import webdav_push

    _run_thread(webdav_push, "event/sync_done")
    return {"started": True}


def handle_sync_pull(params):
    from core.cloud_sync import webdav_pull

    _run_thread(webdav_pull, "event/sync_done")
    return {"started": True}


# -- C1: D-Bus service bridge ------------------------------------
def handle_dbus_status(params):
    from core.dbus_service import service_status

    return service_status()


def handle_dbus_set_policy(params):
    s = load_settings()
    s["dbus_allow_mutations"] = bool(params.get("allow_mutations", False))
    save_settings(s)
    return {"ok": True, "allow_mutations": s["dbus_allow_mutations"]}


def handle_dbus_start(params):
    from core.dbus_service import start_default

    # Quick op (spawns its own serve thread); result/error via done event.
    _run_thread(start_default, "event/dbus_done")
    return {"started": True}


METHODS = {
    "app.version": handle_app_version,
    "app.doctor": handle_app_doctor,
    "tools.status": handle_tools_status,
    "settings.get": handle_settings_get,
    "settings.set": handle_settings_set,
    "pipeline.start": handle_pipeline_start,
    "pipeline.cancel": handle_pipeline_cancel,
    "pipeline.approve": handle_pipeline_approve,
    "pipeline.dismiss": handle_pipeline_dismiss,
    "history.list": handle_history_list,
    "history.uninstall": handle_history_uninstall,
    "history.rollback": handle_history_rollback,
    "history.clear": handle_history_clear,
    # Faz 1 / A2: security panel
    "security.verify": handle_security_verify,
    "security.sign": handle_security_sign,
    "security.keys": handle_security_keys,
    "security.sbom": handle_security_sbom,
    "security.quality": handle_security_quality,
    "security.provenance": handle_security_provenance,
    "security.provenance_create": handle_security_provenance_create,
    "security.sigstore_status": handle_security_sigstore_status,
    "security.cve_scan": handle_security_cve_scan,
    # Faz 1 / A4: delta updater
    "delta.status": handle_delta_status,
    "delta.enable": handle_delta_enable,
    "delta.disable": handle_delta_disable,
    # Faz 1 / A1: export centers
    "export.oci": handle_export_oci,
    "export.appimage_to_deb": handle_export_appimage_to_deb,
    "export.flatpak_list": handle_export_flatpak_list,
    "export.flatpak_to_deb": handle_export_flatpak_to_deb,
    # Faz 1 / A3: dependency graph
    "graph.build": handle_graph_build,
    # Faz 1 / A5: from-source
    "source.generate": handle_source_generate,
    # Faz 1 / A6: system tools
    "system.health": handle_system_health,
    "stats.wrapped": handle_stats_wrapped,
    "policy.evaluate": handle_policy_evaluate,
    "policy.get": handle_policy_get,
    "policy.set": handle_policy_set,
    "system.cross_check": handle_system_cross_check,
    "system.snapshot_status": handle_system_snapshot_status,
    "system.snapshot_install": handle_system_snapshot_install,
    "system.snapshot_remove": handle_system_snapshot_remove,
    "system.verify_rollback": handle_system_verify_rollback,
    "system.benchmark": handle_system_benchmark,
    # Faz 2 / B8: plugin marketplace
    "plugin.list": handle_plugin_list,
    "plugin.available": handle_plugin_available,
    "plugin.install": handle_plugin_install,
    "plugin.uninstall": handle_plugin_uninstall,
    "plugin.update": handle_plugin_update,
    "plugin.audit": handle_plugin_audit,
    # Faz 2 / B5: package comparison
    "compare.diff": handle_compare_diff,
    # Faz 2 / B1: AUR browser
    "aur.search": handle_aur_search,
    "aur.info": handle_aur_info,
    "aur.build": handle_aur_build,
    # Faz 2 / B6: batch conversion queue
    "queue.add": handle_queue_add,
    "queue.list": handle_queue_list,
    "queue.priority": handle_queue_priority,
    "queue.remove": handle_queue_remove,
    "queue.clear": handle_queue_clear,
    "queue.start": handle_queue_start,
    "queue.cancel": handle_queue_cancel,
    # Faz 2 / B3: scheduled tasks
    "schedule.get": handle_schedule_get,
    "schedule.set": handle_schedule_set,
    "profile.list": handle_profile_list,
    "profile.current": handle_profile_current,
    "profile.create": handle_profile_create,
    "profile.switch": handle_profile_switch,
    "profile.delete": handle_profile_delete,
    "sync.export": handle_sync_export,
    "sync.import": handle_sync_import,
    "sync.config": handle_sync_config,
    "schedule.timer_install": handle_schedule_timer_install,
    "schedule.run": handle_schedule_run,
    "sync.push": handle_sync_push,
    "sync.pull": handle_sync_pull,
    "dbus.status": handle_dbus_status,
    "dbus.start": handle_dbus_start,
    "dbus.set_policy": handle_dbus_set_policy,
}


def _dispatch(msg: dict) -> dict:
    """Dispatch one JSON-RPC request and return the response object.

    Returns the response dict (never raises) so both the stdio loop and the
    HTTP server can serialize it. Push events are emitted via _event().
    """
    req_id = msg.get("id")
    method = msg.get("method", "")
    params = msg.get("params") or {}
    handler = METHODS.get(method)
    if handler is None:
        return {"jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}}
    try:
        return {"jsonrpc": "2.0", "id": req_id, "result": handler(params)}
    except Exception as exc:  # noqa: BLE001 — report, never crash the loop
        return {"jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32000, "message": str(exc)}}


def serve() -> None:
    """Run the sidecar main loop (blocking).

    Non-blocking stdin reads interleaved with Qt event processing so
    pipeline signals (emitted from the worker thread) are delivered and
    approve/dismiss requests reach a pipeline blocked in _wait_for_decision.
    """
    import select

    app = _ensure_qapp()
    _ensure_scheduler()
    restore_queue()
    while True:
        app.processEvents()
        try:
            ready, _, _ = select.select([sys.stdin], [], [], 0.05)
        except (OSError, ValueError):
            break  # stdin closed
        if not ready:
            continue
        line = sys.stdin.readline()
        if not line:
            break  # stdin closed — parent exited
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            _error(None, -32700, "Parse error")
            continue
        _send(_dispatch(msg))


# HTTP hardening limits (F4.2).
_HTTP_MAX_BODY = 1_048_576  # 1 MiB request body ceiling
_HTTP_RATE_LIMIT = 60  # requests per minute per client IP
# Methods a read-only token may call; everything else needs the operator token.
# F5.1: single source of truth lives in core/capabilities.py.
from core.capabilities import http_reader_methods as _http_reader_methods

_READ_METHODS = _http_reader_methods()
_http_rate: dict[str, deque] = {}


def _rate_limited(ip: str, now: float) -> bool:
    """Sliding-window limiter: True when this client exceeded the cap."""
    # F5.2a: bounded memory — sweep empty per-IP buckets when map balloons.
    if len(_http_rate) > 4096:
        for stale in [k for k, v in _http_rate.items() if not v]:
            del _http_rate[stale]
    hits = _http_rate.setdefault(ip, deque())
    while hits and now - hits[0] > 60:
        hits.popleft()
    if len(hits) >= _HTTP_RATE_LIMIT:
        return True
    hits.append(now)
    return False


def _resolve_client_ip(socket_ip: str, xff_header: str,
                       trusted_proxy: bool) -> str:
    """Pick the client IP used for rate limiting (F5.2b).

    X-Forwarded-For is honoured ONLY when the operator explicitly trusts an
    upstream (TLS-terminating) proxy; otherwise the header is attacker-
    controlled and would let anyone dodge the per-IP rate limit.
    """
    if trusted_proxy and xff_header:
        return xff_header.split(",")[0].strip() or socket_ip
    return socket_ip


def build_openapi_schema() -> dict:
    """Minimal OpenAPI 3 description of the JSON-RPC surface (F4.8).

    Method names and doc summaries are public metadata by design; executing
    methods still requires the operator/read tokens enforced in do_POST.
    """
    paths: dict = {}
    for name in sorted(METHODS):
        handler = METHODS[name]
        doc = (getattr(handler, "__doc__", None) or "").strip()
        summary = doc.splitlines()[0] if doc else "JSON-RPC metodu: " + name
        paths["/rpc/" + name] = {
            "post": {
                "operationId": name.replace(".", "_"),
                "summary": summary,
                "tags": [name.split(".")[0]],
                "requestBody": {
                    "required": False,
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {
                            "params": {"type": "object",
                                       "additionalProperties": True},
                        },
                    }}}},
                "responses": {
                    "200": {"description": "JSON-RPC yanıtı"},
                    "401": {"description": "token gerekli"},
                    "403": {"description": "okuma yetkisi yok"},
                    "429": {"description": "hız limiti"},
                },
            }
        }
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "PkgForge API",
            "version": APP_VERSION,
            "description": ("JSON-RPC yüzeyi. Yazma işlemleri operator "
                            "token, salt-okuma metodları read-token ile "
                            "açılır."),
        },
        "servers": [{"url": "/"}],
        "paths": paths,
    }


def serve_http(port: int = 8765, token: str = "", host: str = "127.0.0.1",
               read_token: str = "", insecure_http_lan: bool = False,
               trusted_proxy: bool = False) -> None:
    """Run the JSON-RPC API over HTTP for LAN remote management (B7/F4.2).

    POST / accepts a single JSON-RPC 2.0 request and returns the response.
    Requests must carry "Authorization: Bearer <token>" (operator scope) or
    the optional *read_token* (read-only method subset). Binding to a
    non-loopback address without an operator token is refused at startup.
    Push events are suppressed in this mode (no stdio channel).
    """
    global _http_mode
    import hmac
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    loopback = host in ("127.0.0.1", "localhost", "::1")
    if not loopback and not token:
        raise ValueError(
            "Non-loopback bind requires --token "
            "(LAN erisimi kimlik dogrulamasiz acilamaz)")
    # F5.2b: no TLS support — plain HTTP on a routable address is only
    # allowed behind an explicit opt-in, or in front of a TLS-terminating
    # reverse proxy (use --trusted-proxy so X-Forwarded-For is honoured).
    if not loopback and not insecure_http_lan:
        raise ValueError(
            "Non-loopback HTTP requires --insecure-http-lan "
            "(TLS yok; acik HTTP LAN erisimi icin riski bilincli onaylayin "
            " ya da onde TLS sonlandiran bir reverse proxy kullanin)")

    _http_mode = True
    _ensure_qapp()
    _ensure_scheduler()
    restore_queue()

    class Handler(BaseHTTPRequestHandler):
        def _reply(self, code: int, obj: dict) -> None:
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _scope(self) -> str | None:
            """Return operator/reader for this request, else None."""
            auth = self.headers.get("Authorization", "")
            if token and hmac.compare_digest(auth, f"Bearer {token}"):
                return "operator"
            if read_token and hmac.compare_digest(auth, f"Bearer {read_token}"):
                return "reader"
            return None

        def _client_ip(self) -> str:
            """Client address for rate limiting.

            F5.2b: only honour X-Forwarded-For when the operator explicitly
            trusts an upstream proxy; otherwise the header is attacker-controlled.
            """
            return _resolve_client_ip(
                self.client_address[0],
                self.headers.get("X-Forwarded-For", ""),
                trusted_proxy)

        def _raw(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _sse_write(self, ev: dict) -> None:
            data = json.dumps(ev, ensure_ascii=False)
            self.wfile.write(f"event: message\ndata: {data}\n\n".encode())
            self.wfile.flush()

        def _sse_stream(self) -> None:
            """F5.23: stream push events as Server-Sent Events."""
            q = _sse_subscribe()
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                # Replay recent history so late clients catch up.
                with _sse_lock:
                    history = list(_sse_history)
                for ev in history:
                    self._sse_write(ev)
                # Stream new events until the client disconnects.
                while True:
                    try:
                        ev = q.get(timeout=15)
                    except queue.Empty:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                        continue
                    self._sse_write(ev)
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                _sse_unsubscribe(q)

        def do_GET(self) -> None:
            if self.path == "/health":
                self._reply(200, {"ok": True, "service": "pkgforge-http",
                                  "version": APP_VERSION})
            elif self.path == "/openapi.json":
                self._raw(200, json.dumps(build_openapi_schema()).encode(),
                          "application/json")
            elif self.path == "/docs":
                self._raw(200, http_assets.docs_html(),
                          "text/html; charset=utf-8")
            elif self.path in ("/", "/index.html"):
                self._raw(200, http_assets.dashboard_html(),
                          "text/html; charset=utf-8")
            elif self.path == "/assets/swagger/swagger-ui.css":
                self._raw(200, http_assets.swagger_css(), "text/css")
            elif self.path == "/assets/swagger/swagger-ui-bundle.js":
                self._raw(200, http_assets.swagger_bundle_js(),
                          "application/javascript")
            elif self.path == "/events":
                # F5.23: SSE canli olay akisi (reader ya da operator token).
                if self._scope() is None:
                    self._reply(401, {"error": "Unauthorized"})
                    return
                self._sse_stream()
            else:
                self._reply(404, {"error": "not found"})

        def do_POST(self) -> None:
            client_ip = self._client_ip()
            if _rate_limited(client_ip, time.time()):
                self._reply(429, {"jsonrpc": "2.0", "id": None,
                                  "error": {"code": -32000,
                                            "message": "Rate limit exceeded"}})
                return
            scope = self._scope()
            if scope is None:
                self._reply(401, {"jsonrpc": "2.0", "id": None,
                                  "error": {"code": -32000, "message": "Unauthorized"}})
                return
            length = int(self.headers.get("Content-Length", 0))
            if length > _HTTP_MAX_BODY:
                self._reply(413, {"jsonrpc": "2.0", "id": None,
                                  "error": {"code": -32000,
                                            "message": "Request body too large"}})
                return
            raw = self.rfile.read(length) if length else b""
            try:
                msg = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._reply(400, {"jsonrpc": "2.0", "id": None,
                                  "error": {"code": -32700, "message": "Parse error"}})
                return
            if scope == "reader" and msg.get("method") not in _READ_METHODS:
                self._reply(403, {"jsonrpc": "2.0", "id": msg.get("id"),
                                  "error": {"code": -32000,
                                            "message": "Read-only token"}})
                return
            self._reply(200, _dispatch(msg))

        def log_message(self, fmt, *args) -> None:
            pass  # silence per-request logging

    server = ThreadingHTTPServer((host, port), Handler)
    sys.stderr.write(f"[http] JSON-RPC dinleniyor: http://{host}:{port}/\n")
    sys.stderr.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
