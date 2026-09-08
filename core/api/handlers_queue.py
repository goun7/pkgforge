"""PkgForge sidecar API — batch queue/schedule/profile/sync handlers (F2.2 split from core/api_server.py)."""
from __future__ import annotations

import atexit
import logging
import threading
import time
from pathlib import Path
from typing import Any

from core.api import transport
from i18n import load_settings, save_settings, tr

# ── Faz 2 / B6: batch conversion queue ──────────────────────────

_queue_lock = threading.Lock()
_queue_items: dict[str, dict[str, Any]] = {}   # id -> {id, path, status, priority, message}
_queue_seq = 0
_queue_running = False
# Live batch pipelines keyed by item_id (F4.3 honesty fix).
_active_pipelines: dict[str, Any] = {}

# F5.12: durable backing for the queue. Best-effort — a DB failure must never
# break the in-memory hot path.
_queue_store: Any = None
_queue_store_lock = threading.Lock()


def _get_queue_store() -> Any:
    global _queue_store
    with _queue_store_lock:
        if _queue_store is None:
            try:
                from core.queue_store import QueueStore
                _queue_store = QueueStore()
                # Singleton yasam dongusu: process cikisinda baglantiyi kapat
                # (sqlite WAL temizligi + dosya tutamac sizintisini onle).
                atexit.register(_queue_store.close)
            except Exception:  # noqa: BLE001 - persistence is best-effort
                _queue_store = False  # sentinel: tried and failed
        return _queue_store or None


def _persist_item(item: dict[str, Any]) -> None:
    store = _get_queue_store()
    if store is None:
        return
    try:
        store.upsert(item)
    except Exception:  # noqa: BLE001, S110 - best-effort persistence
        pass


def _persist_remove(item_id: str) -> None:
    store = _get_queue_store()
    if store is None:
        return
    try:
        store.remove(item_id)
    except Exception:  # noqa: BLE001, S110 - best-effort persistence
        pass


def _persist_clear(status: str = "") -> None:
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


def _make_pipeline(path: Path, item_id: str, do_install: bool = False) -> Any:
    """Build a ConversionPipeline whose events are tagged with item_id.

    F4.3 honesty: batch is CONVERSION-ONLY by default. The decision gate is
    released via dismiss_install() so no package touches the system unless
    the caller explicitly opted in with do_install=True.
    """
    from PyQt6.QtCore import Qt

    from core.pipeline import ConversionPipeline

    transport._ensure_qapp()
    p = ConversionPipeline()

    # F4.3: slots run DIRECTLY on the emitting thread. Batch dispatcher
    # threads have no Qt event loop; queued delivery would never fire the
    # auto-approve gate and deadlock the item. These lambdas only touch
    # thread-safe state (_event -> write lock, dict under _queue_lock).
    direct = Qt.ConnectionType.DirectConnection

    def _track_finished(result: Any) -> None:
        _active_pipelines.pop(item_id, None)
        _set_item(item_id, status="done" if result.success else "error",
                  message=result.message)

    p.step_changed.connect(
        lambda step, status: transport._event("event/step_changed", {"step": step, "status": status, "item_id": item_id}), type=direct)  # type: ignore[call-arg]
    p.progress.connect(
        lambda v: transport._event("event/progress", {"value": v, "item_id": item_id}), type=direct)  # type: ignore[call-arg]
    p.log_message.connect(
        lambda msg, level: transport._event("event/log", {"message": msg, "level": level, "item_id": item_id}), type=direct)  # type: ignore[call-arg]
    p.compatibility_ready.connect(
        lambda report: transport._event("event/compatibility_ready", {"report": report.to_dict(), "item_id": item_id}), type=direct)  # type: ignore[call-arg]
    if do_install:
        p.compatibility_ready.connect(lambda report: p.approve_install(), type=direct)  # type: ignore[call-arg]
    else:
        pkg_label = Path(path).name
        p._skip_install_message = tr("api.pkg_label_donusturuldu_kurulum", pkg_label=pkg_label)
        p.compatibility_ready.connect(
            lambda report: p.dismiss_install(), type=direct)  # type: ignore[call-arg]
    p.finished.connect(_track_finished, type=direct)  # type: ignore[call-arg]  # type: ignore[call-arg]
    p.finished.connect(
        lambda result: transport._event("event/finished", {
            "success": result.success,
            "message": result.message,
            "output_pkg": str(result.converted_pkg) if result.converted_pkg else "",
            "item_id": item_id,
        }), type=direct)  # type: ignore[call-arg]
    _active_pipelines[item_id] = p
    return p


def _set_item(item_id: str, **fields: object) -> None:
    with _queue_lock:
        if item_id in _queue_items:
            _queue_items[item_id].update(fields)
            _persist_item(_queue_items[item_id])


def handle_queue_add(params: dict[str, Any]) -> dict[str, Any]:
    global _queue_seq
    paths = params.get("paths", [])
    if isinstance(paths, str):
        paths = [paths]
    added = 0
    with _queue_lock:
        for raw in paths:
            path = Path(str(raw))
            if not path.exists():
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


def handle_queue_list(params: dict[str, Any]) -> list[Any]:
    with _queue_lock:
        items = list(_queue_items.values())
    items.sort(key=lambda it: (-it["priority"], it["id"]))
    return items


def handle_queue_priority(params: dict[str, Any]) -> dict[str, Any]:
    item_id = params.get("id", "")
    with _queue_lock:
        if item_id not in _queue_items:
            raise KeyError(f"Queue item not found: {item_id}")
        _queue_items[item_id]["priority"] = int(params.get("priority", 0))
        _persist_item(_queue_items[item_id])
    return {"ok": True}


def handle_queue_remove(params: dict[str, Any]) -> dict[str, Any]:
    item_id = params.get("id", "")
    with _queue_lock:
        _queue_items.pop(item_id, None)
    _persist_remove(item_id)
    return {"ok": True}


def handle_queue_clear(params: dict[str, Any]) -> dict[str, Any]:
    status = params.get("status", "")
    with _queue_lock:
        if not status:
            _queue_items.clear()
        else:
            for k in [k for k, v in _queue_items.items() if v["status"] == status]:
                del _queue_items[k]
    _persist_clear(status)
    return {"ok": True}


def _queue_dispatch(parallel: int, do_install: bool = False) -> None:
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
        transport._event("event/queue_done", {"ok": True})


def handle_queue_cancel(params: dict[str, Any]) -> dict[str, Any]:
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


def handle_queue_start(params: dict[str, Any]) -> dict[str, Any]:
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


def _schedule_state() -> dict[str, Any]:
    from core.scheduler import state as sched_state

    return sched_state()


def handle_schedule_get(params: dict[str, Any]) -> dict[str, Any]:
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


def handle_schedule_set(params: dict[str, Any]) -> dict[str, Any]:
    s = load_settings()
    if "enabled" in params:
        s["schedule_enabled"] = bool(params["enabled"])
    if "interval_hours" in params:
        s["schedule_interval_hours"] = max(1.0, float(params["interval_hours"]))
    if "task" in params:
        s["schedule_task"] = str(params["task"])
    save_settings(s)
    return {"ok": True}


def _scheduler_tick() -> None:
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
                    transport._event("event/schedule_ran", {"task": st["task"], "at": now})
        except Exception as exc:  # noqa: BLE001
            transport._event("event/schedule_ran", {"task": "", "error": str(exc)})
        time.sleep(60)


def _ensure_scheduler() -> None:
    global _scheduler_started
    if not _scheduler_started:
        _scheduler_started = True
        threading.Thread(target=_scheduler_tick, daemon=True).start()


# -- C2: multi-profile management -------------------------------
def _profile_name(params: dict[str, Any]) -> str:
    return str(params.get("name", "")).strip()


def handle_profile_create(params: dict[str, Any]) -> dict[str, Any]:
    from core.profiles import create_profile

    return create_profile(_profile_name(params))


def handle_profile_switch(params: dict[str, Any]) -> dict[str, Any]:
    from core.profiles import switch_profile

    result = switch_profile(_profile_name(params))
    # Rebind cached UI state (language) to the new profile settings.
    try:
        from i18n import init_language

        init_language()
    except Exception as exc:  # noqa: BLE001 - cosmetic; never fail the switch
        logging.getLogger(__name__).debug("init_language after switch failed: %s", exc)
    return result


def handle_profile_delete(params: dict[str, Any]) -> dict[str, Any]:
    from core.profiles import delete_profile

    return delete_profile(_profile_name(params))


# -- C3: backup & cloud sync ------------------------------------
def handle_sync_export(params: dict[str, Any]) -> dict[str, Any]:
    from core.cloud_sync import export_backup

    output = str(params.get("output_path", "")).strip()
    return export_backup(output or None)


def handle_sync_import(params: dict[str, Any]) -> dict[str, Any]:
    from core.cloud_sync import import_backup

    return import_backup(str(params.get("backup_path", "")))


def handle_schedule_timer_install(params: dict[str, Any]) -> dict[str, Any]:
    """Install systemd user timer units (dry_run preview by default)."""
    from core.scheduler import install_timer

    return install_timer(
        interval_hours=params.get("interval_hours"),
        dry_run=bool(params.get("dry_run", True)))


def handle_schedule_run(params: dict[str, Any]) -> dict[str, Any]:
    """Run the scheduled task immediately (force unless told otherwise)."""
    from core.scheduler import run_due

    return run_due(force=bool(params.get("force", False)))


def handle_sync_config(params: dict[str, Any]) -> dict[str, Any]:
    s = load_settings()
    if "sync_url" in params:
        s["sync_url"] = str(params["sync_url"]).strip()
    if "sync_username" in params:
        s["sync_username"] = str(params["sync_username"]).strip()

    stored_in = "unchanged"
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
            except Exception as exc:  # noqa: BLE001 - never store plaintext
                warning = tr("api.anahtarlik_kullanilamadi_exc", exc=exc)
                stored_in = "rejected"
        elif not user:
            stored_in = "rejected"
            warning = "Anahtarlik icin kullanici adi gerekli"
        else:
            stored_in = "rejected"
            warning = ("Plaintext password storage is disabled. Enable a "
                       "Secret Service (gnome-keyring/kwalletd) and retry.")

    save_settings(s)
    out = {"ok": True, "password_stored": stored_in}
    if warning:
        out["warning"] = warning
    return out


def handle_sync_push(params: dict[str, Any]) -> dict[str, Any]:
    from core.cloud_sync import webdav_push

    transport._run_thread(webdav_push, "event/sync_done")
    return {"started": True}


def handle_sync_pull(params: dict[str, Any]) -> dict[str, Any]:
    from core.cloud_sync import webdav_pull

    transport._run_thread(webdav_pull, "event/sync_done")
    return {"started": True}
