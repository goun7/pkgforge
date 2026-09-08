"""PkgForge sidecar API — plugin/compare/AUR handlers (F2.2 split from core/api_server.py)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from config import discover_tools
from core.api import transport
from i18n import tr


def handle_plugin_install(params: dict[str, Any]) -> dict[str, Any]:
    from core.plugins import reload_plugins
    from core.plugins.marketplace import install_plugin

    name = params.get("name", "")
    version = params.get("version", "latest")
    force = bool(params.get("force", False))

    def _op() -> Any:
        path = install_plugin(name, version=version, force=force)
        reload_plugins()
        return {"ok": True, "path": str(path)}

    transport._run_thread(_op, "event/plugin_done")
    return {"started": True}


def handle_plugin_uninstall(params: dict[str, Any]) -> dict[str, Any]:
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


def handle_plugin_update(params: dict[str, Any]) -> dict[str, Any]:
    from core.plugins import reload_plugins
    from core.plugins.marketplace import update_plugin

    name = params.get("name", "")

    def _op() -> Any:
        ok, msg, _path = update_plugin(name)
        if ok:
            reload_plugins()
        return {"ok": ok, "message": msg}

    transport._run_thread(_op, "event/plugin_done")
    return {"started": True}


# ── Faz 2 / B5: package comparison ──────────────────────────────

def handle_compare_diff(params: dict[str, Any]) -> dict[str, Any]:
    from core.sbom import diff_sboms, generate_sbom

    old_path = Path(params.get("old_path", ""))
    new_path = Path(params.get("new_path", ""))
    if not old_path.is_file():
        raise FileNotFoundError(f"Old package not found: {old_path}")
    if not new_path.is_file():
        raise FileNotFoundError(f"New package not found: {new_path}")
    tools = discover_tools()

    def _op() -> Any:
        old_sbom = generate_sbom(old_path, tools, include_hashes=True)
        new_sbom = generate_sbom(new_path, tools, include_hashes=True)
        diff = diff_sboms(old_sbom, new_sbom)
        return diff.to_dict()

    transport._run_thread(_op, "event/compare_done")
    return {"started": True}


# ── Faz 2 / B1: AUR browser ─────────────────────────────────────

_AUR_NAME_RE = __import__("re").compile(r"^[A-Za-z0-9][A-Za-z0-9@._+-]*$")


def _validate_aur_name(name: str) -> None:
    # First character must be alphanumeric: rejects "", "-bas", ".nokta" and,
    # critically, "." / ".." path segments before the name reaches
    # tempfile.mkdtemp(prefix=f"pkgforge-aur-{name}-") and the clone URL.
    if not name or not _AUR_NAME_RE.match(name) or len(name) > 255:
        raise ValueError(f"Invalid AUR package name: {name!r}")


def handle_aur_search(params: dict[str, Any]) -> dict[str, Any]:
    from core.aur_checker import search_aur

    query = str(params.get("query", ""))
    limit = int(params.get("limit", 25))

    def _op() -> Any:
        return search_aur(query, limit=limit)

    transport._run_thread(_op, "event/aur_search_done")
    return {"started": True}


def handle_aur_info(params: dict[str, Any]) -> dict[str, Any]:
    from dataclasses import asdict

    from core.aur_checker import check_aur

    name = str(params.get("name", ""))
    _validate_aur_name(name)

    def _op() -> Any:
        return asdict(check_aur(name))

    transport._run_thread(_op, "event/aur_info_done")
    return {"started": True}


def handle_aur_build(params: dict[str, Any]) -> dict[str, Any]:
    import subprocess as _sp
    import tempfile

    name = str(params.get("name", ""))
    _validate_aur_name(name)

    def _op() -> Any:
        transport._event("event/aur_build_progress", {"name": name, "step": "clone"})
        workdir = Path(tempfile.mkdtemp(prefix=f"pkgforge-aur-{name}-"))
        clone_url = f"https://aur.archlinux.org/{name}.git"
        r = _sp.run(
            ["git", "clone", "--depth=1", clone_url, str(workdir / name)],
            capture_output=True, text=True, timeout=180, check=False,
        )
        if r.returncode != 0:
            raise RuntimeError(tr("api.git_clone_basarisiz_var0", var0=r.stderr.strip()[:300]))

        transport._event("event/aur_build_progress", {"name": name, "step": "build"})
        # Security: build-only. makepkg -si would run arbitrary AUR PKGBUILD
        # code with privileged install hooks; installation must go through
        # the consolidated polkit helper (install-pkg) instead.
        cmd = ["makepkg", "-f", "--noconfirm"]
        b = _sp.run(
            cmd, capture_output=True, text=True, timeout=3600,
            cwd=str(workdir / name), check=False,
        )
        if b.returncode != 0:
            raise RuntimeError(tr("api.makepkg_basarisiz_var0", var0=b.stderr.strip()[-300:]))

        built = sorted((workdir / name).glob("*.pkg.tar.zst"))
        if not built:
            raise RuntimeError("makepkg tamamlandı ama paket dosyası bulunamadı")
        # Build-only handler: install is never attempted here (SEC).
        return {"name": name, "pkg_path": str(built[-1]), "installed": False}

    transport._run_thread(_op, "event/aur_build_done")
    return {"started": True}
