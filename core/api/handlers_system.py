"""PkgForge sidecar API — delta/export/graph/source/system handlers (F2.2 split from core/api_server.py)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from config import discover_tools
from core.api import transport
from i18n import tr

# ── Faz 1 / A4: delta updater ───────────────────────────────────

def handle_delta_status(params: dict) -> dict:
    from core.delta_updater import get_auto_update_status

    return get_auto_update_status()


def handle_delta_enable(params: dict) -> dict:
    # Enabling the systemd timer requires privilege escalation; the desktop
    # UI triggers pkexec via its own privileged helper in a later phase.
    return {"ok": False, "requires_privilege": True,
            "message": "Delta auto-update etkinleştirme yetkili işlem gerektiriyor (pkexec)"}


def handle_delta_disable(params: dict) -> dict:
    return {"ok": False, "requires_privilege": True,
            "message": "Delta auto-update kapatma yetkili işlem gerektiriyor (pkexec)"}


# ── Faz 1 / A1: export centers ──────────────────────────────────

def handle_export_oci(params: dict) -> dict:
    from core.oci_builder import build_oci_image

    path = transport._require_pkg_file(params)
    tools = discover_tools()
    tag = params.get("tag") or None
    output_file = Path(params["output_file"]) if params.get("output_file") else None

    def _op() -> Any:
        ok, msg, out = build_oci_image(path, tools, tag=tag, output_file=output_file)
        return {"ok": ok, "message": msg, "output_path": str(out) if out else ""}

    transport._run_thread(_op, "event/export_done")
    return {"started": True}


def handle_export_appimage_to_deb(params: dict) -> dict:
    from core.appimage_converter import appimage_to_deb

    appimage = Path(params.get("appimage_path", ""))
    if not appimage.is_file():
        raise FileNotFoundError(f"AppImage not found: {appimage}")
    out_dir = Path(params.get("output_dir", "."))

    def _op() -> Any:
        ok, msg, deb = appimage_to_deb(appimage, out_dir)
        return {"ok": ok, "message": msg, "deb_path": str(deb) if deb else ""}

    transport._run_thread(_op, "event/export_done")
    return {"started": True}


def handle_export_flatpak_list(params: dict) -> list:
    from dataclasses import asdict

    from core.flatpak_converter import list_installed_apps

    return [asdict(app) for app in list_installed_apps()]


def handle_export_flatpak_to_deb(params: dict) -> dict:
    from core.flatpak_converter import flatpak_to_deb

    app_id = params.get("app_id", "")
    if not app_id:
        raise ValueError("app_id is required")
    branch = params.get("branch", "stable")
    out_dir = Path(params.get("output_dir", "."))

    def _op() -> Any:
        ok, msg, deb = flatpak_to_deb(app_id, out_dir, branch=branch)
        return {"ok": ok, "message": msg, "deb_path": str(deb) if deb else ""}

    transport._run_thread(_op, "event/export_done")
    return {"started": True}


# ── Faz 1 / A3: dependency graph ────────────────────────────────

def handle_graph_build(params: dict) -> dict:
    from dataclasses import asdict

    from core.dep_graph import build_dep_graph, build_file_dep_graph

    path = transport._require_pkg_file(params)
    show_files = bool(params.get("files", False))

    def _op() -> Any:
        graph = build_file_dep_graph(path) if show_files else build_dep_graph(path)
        return {
            "root": graph.root,
            "nodes": {name: asdict(node) for name, node in graph.nodes.items()},
            "stats": graph.stats(),
            "mermaid": graph.to_mermaid(),
            "warnings": graph.warnings,
        }

    transport._run_thread(_op, "event/graph_done")
    return {"started": True}


# ── Faz 1 / A5: from-source PKGBUILD ────────────────────────────

def handle_source_generate(params: dict) -> dict:
    import tempfile

    from core.from_source import generate_pkgbuild_from_source
    from core.security import safe_run

    repo_url = params.get("repo_url", "").strip()
    if not repo_url:
        raise ValueError("repo_url is required")
    out_dir = Path(params.get("output_dir", ".")).resolve()

    def _op() -> Any:
        with tempfile.TemporaryDirectory(prefix="pkgforge_src_") as tmpdir:
            tmp = Path(tmpdir)
            transport._event("event/source_progress", {"step": "clone"})
            res = safe_run(["git", "clone", "--depth=1", repo_url, str(tmp / "repo")], timeout=120)
            if res.returncode != 0:
                raise RuntimeError(f"git clone failed: {res.stderr[:200]}")
            repo_dir = tmp / "repo"

            proj_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
            transport._event("event/source_progress", {"step": "detect"})
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

            transport._event("event/source_progress", {"step": "generate"})
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

    transport._run_thread(_op, "event/source_done")
    return {"started": True}


# ── Faz 1 / A6: system tools ────────────────────────────────────

def handle_system_cross_check(params: dict) -> dict:
    from dataclasses import asdict

    from core.cross_check import cross_check_package

    name = params.get("package_name", "")
    if not name:
        raise ValueError("package_name is required")
    local_version = params.get("local_version", "")

    def _op() -> Any:
        return asdict(cross_check_package(name, local_version))

    transport._run_thread(_op, "event/cross_check_done")
    return {"started": True}


def handle_system_snapshot_status(params: dict) -> dict:
    from core.snapshot_cleanup import get_cleanup_status

    return get_cleanup_status()


def handle_system_snapshot_install(params: dict) -> dict:
    """Snapshot temizlik servisini kurar; pkexec ekranda yetki ister."""
    from core.snapshot_cleanup import install_cleanup_service

    max_age = int(params.get("max_age_days", 7))

    def _op() -> Any:
        ok, msg = install_cleanup_service(max_age_days=max_age)
        return {"ok": ok, "message": msg}

    transport._run_thread(_op, "event/snapshot_done")
    return {"started": True}


def handle_system_snapshot_remove(params: dict) -> dict:
    """Snapshot temizlik servisini kaldirir; pkexec ekranda yetki ister."""
    from core.snapshot_cleanup import remove_cleanup_service

    def _op() -> Any:
        ok, msg = remove_cleanup_service()
        return {"ok": ok, "message": msg}

    transport._run_thread(_op, "event/snapshot_done")
    return {"started": True}


def handle_system_open_path(params: dict) -> dict:
    """Dosya yoneticisinde yolun bulundugu klasoru acar (sonuc bandi 'Klasoru Ac')."""
    import subprocess

    path = Path(params.get("path", ""))
    if not path.exists():
        raise FileNotFoundError(tr("api.yol_bulunamadi_path", path=path))
    target = path.parent if path.is_file() else path
    subprocess.Popen(["xdg-open", str(target)],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"ok": True}


def handle_system_install_pkg(params: dict) -> dict:
    """Donusturulmus .pkg.tar.zst paketini pkexec + pacman -U ile kurar.

    Faz 14: rota, konsolide privileged helper'in install-pkg alt-komutuna
    gider — byolenek [pkexec, pacman, ...] zinciri yerine TEK policy action
    (org.pkgforge.install) yetkilendirilir ve helper argüman doğrulaması
    (uzanti/mutlak yol/çapraz-yol) devrede kalır.
    """
    from core.privileged import privileged_install_pkg_argv
    from core.security import safe_run

    pkg = Path(params.get("pkg_path", ""))
    if not pkg.is_file():
        raise FileNotFoundError(tr("api.paket_bulunamadi_pkg", pkg=pkg))
    if ".pkg.tar" not in pkg.name:
        raise ValueError(tr("api.gecersiz_paket_dosyasi_pkg", pkg_name=pkg.name))
    tools = discover_tools()
    if not tools.pkexec or not tools.pacman:
        raise RuntimeError("pkexec veya pacman bulunamadı")

    # Snapshot + kurulum TEK diyalogda (helper --snapshot).
    snap = ""
    try:
        from core.snapshot_manager import detect_backend, snapshot_name
        from i18n import load_setting
        if load_setting("snapshot", True) and detect_backend() != "none":
            from config import extract_package_name
            snap = snapshot_name(extract_package_name(pkg.name))
    except Exception:  # noqa: BLE001
        snap = ""

    def _op() -> Any:
        argv = privileged_install_pkg_argv(tools.pkexec, str(pkg), snapshot=snap)
        res = safe_run(argv, timeout=600)
        if res.returncode == 0:
            return {"ok": True, "message": f"{pkg.name} kuruldu"}
        return {"ok": False, "message": tr("api.kurulum_basarisiz_kod_res", res_returncode=res.returncode)}

    transport._run_thread(_op, "event/install_done")
    return {"started": True}


def handle_system_verify_rollback(params: dict) -> dict:
    from dataclasses import asdict

    from core.rollback_verify import verify_rollback

    def _op() -> Any:
        return asdict(verify_rollback())

    transport._run_thread(_op, "event/system_done")
    return {"started": True}


def handle_system_benchmark(params: dict) -> dict:
    from dataclasses import asdict

    from core.benchmark import run_benchmarks

    quick = bool(params.get("quick", False))

    def _op() -> Any:
        report = run_benchmarks(quick=quick)
        d = asdict(report)
        d["passed"] = report.passed
        return d

    transport._run_thread(_op, "event/bench_done")
    return {"started": True}


# ── Faz 2 / B8: plugin marketplace ──────────────────────────────

