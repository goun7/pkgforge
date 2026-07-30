"""PkgForge — Headless Command Line Interface (CLI).

Provides full headless operation without Qt GUI for package conversion, URL downloading,
lifecycle management (list, remove, rollback), update checks, and GUI invocation.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

from config import ToolPaths, discover_tools
from core.downloader import download_package
from core.history_db import HistoryDB
from core.security import safe_run, is_valid_package_name
from core.upstream_tracker import check_all_installed_updates
from i18n import tr, load_setting

log = logging.getLogger(__name__)

# ANSI Color Codes for Terminal Output
GREEN = "\033[32m"
RED = "\033[31m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
RESET = "\033[0m"


def run_cli(args: argparse.Namespace) -> int:
    """Execute CLI commands based on parsed arguments."""
    command = args.command

    if command == "convert":
        return _cmd_convert(args)
    elif command == "list":
        return _cmd_list(args)
    elif command == "remove":
        return _cmd_remove(args)
    elif command == "rollback":
        return _cmd_rollback(args)
    elif command == "check-updates":
        return _cmd_check_updates(args)
    else:
        print(tr("cli.invalid_cmd"))
        return 1


def _cmd_convert(args: argparse.Namespace) -> int:
    """Handle `pkgforge convert <file_or_url>`."""
    target = args.target
    print(tr("cli.converting").format(target=target))

    tools = discover_tools()
    missing = tools.missing_required
    if missing:
        print(tr("cli.missing_tools").format(tools=", ".join(missing)))
        return 1

    # Check if target is URL or local file
    file_path: Path
    if target.startswith("http://") or target.startswith("https://"):
        print(tr("cli.downloading_url").format(target=target))
        try:
            file_path = download_package(
                target, require_https=not load_setting("allow_insecure_http", False)
            )
            print(tr("cli.download_complete").format(name=file_path.name))
        except Exception as exc:
            print(tr("cli.download_error").format(error=str(exc)))
            return 1
    else:
        file_path = Path(target).resolve()
        if not file_path.is_file():
            print(tr("cli.file_not_found").format(path=file_path))
            return 1

    # Run conversion via NativeDebConverter or RpmConverter
    out_dir = Path(args.output_dir).resolve() if args.output_dir else file_path.parent
    is_deb = file_path.suffix.lower() == ".deb"

    if is_deb:
        from core.native_deb_converter import NativeDebConverter
        converter = NativeDebConverter(tools)
    else:
        from core.rpm_converter import RpmConverter
        from core.package_analyzer import analyze_package
        meta = analyze_package(file_path, tools)
        converter = RpmConverter(tools)  # type: ignore

    print(tr("cli.starting_conversion").format(name=file_path.name))
    success = False
    msg = ""
    pkg_path = None

    def on_line(line: str):
        print(f"  {line}")

    def on_done(succ: bool, message: str, pkg: object):
        nonlocal success, msg, pkg_path
        success = succ
        msg = message
        pkg_path = pkg

    converter.output_line.connect(on_line)
    converter.finished.connect(on_done)

    from PyQt6.QtCore import QCoreApplication, QEventLoop
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)

    loop = QEventLoop()
    converter.finished.connect(lambda: loop.quit())

    if is_deb:
        converter.convert(file_path, out_dir)
    else:
        converter.convert(file_path, out_dir, meta)  # type: ignore

    loop.exec()

    if not success or not pkg_path:
        print(tr("cli.conversion_failed").format(msg=msg))
        return 1

    print(tr("cli.conversion_success").format(pkg=pkg_path))

    # Compatibility grade + "what will change" preview (best-effort, never fatal)
    try:
        from core.package_analyzer import analyze_package
        from core.compatibility_checker import run_compatibility_checks

        preview_meta = analyze_package(file_path, tools)
        report = run_compatibility_checks(
            Path(pkg_path), preview_meta.file_list, preview_meta.depends, tools
        )
        print(tr("cli.grade").format(grade=report.grade, overall=report.overall.value))
        preview_files = [f for f in preview_meta.file_list if not f.endswith("/")]
        if preview_files:
            print(tr("cli.files_preview").format(count=len(preview_files)))
            for f in preview_files[:10]:
                print(f"    {f}")
    except Exception as exc:
        log.debug("Uyumluluk önizleme atlandı: %s", exc)

    # Backup converted package in HistoryDB
    db = HistoryDB()
    backup_path = db.backup_package(Path(pkg_path))

    db.add_record(
        package_name=file_path.stem.split("_")[0].split("-")[0],
        original_file=file_path.name,
        package_type="deb" if is_deb else "rpm",
        sha256="",
        status="success",
        output_pkg=str(pkg_path),
        source_url=target if target.startswith("http") else "",
        backup_pkg=str(backup_path) if backup_path else "",
        details=msg,
    )

    # Auto-install if requested (dry-run disables installation entirely)
    dry_run = getattr(args, "dry_run", False) or load_setting("dry_run", False)
    if args.install and dry_run:
        print(tr("cli.dry_run_note"))
    elif args.install:
        if not getattr(args, "yes", False):
            print(tr("cli.confirm_install").format(name=pkg_path.name))
            try:
                answer = input("[y/N] ").strip().lower()
            except EOFError:
                answer = ""
            if answer not in ("y", "yes", "e", "evet"):
                print(tr("cli.install_cancelled"))
                return 0
        print(tr("cli.installing_pkg").format(name=pkg_path.name))
        pkexec = tools.pkexec or "pkexec"
        pacman = tools.pacman or "pacman"

        res = safe_run([pkexec, pacman, "-U", "--noconfirm", "--", str(pkg_path)], timeout=120)
        if res.returncode == 0:
            print(tr("cli.install_success").format(name=pkg_path.name))
        else:
            print(tr("cli.install_failed").format(error=res.stderr))
            return 1

    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    """Handle `pkgforge list`."""
    db = HistoryDB()
    records = db.get_history(limit=30)
    print(tr("cli.list_title") + "\n")

    if not records:
        print(tr("cli.list_empty"))
        return 0

    print(f"{'ID':<4} {'Date':<20} {'Package':<20} {'Type':<6} {'Status':<10} {'Original File'}")
    print("-" * 80)
    for r in records:
        print(f"{r.id:<4} {r.timestamp:<20} {r.package_name:<20} {r.package_type:<6} {r.status:<10} {r.original_file}")
    return 0


def _cmd_remove(args: argparse.Namespace) -> int:
    """Handle `pkgforge remove <package>`."""
    pkg_name = args.package
    if not is_valid_package_name(pkg_name):
        print(tr("cli.invalid_pkg_name").format(name=pkg_name))
        return 1
    print(tr("cli.removing_pkg").format(name=pkg_name))

    tools = discover_tools()
    pkexec = tools.pkexec or "pkexec"
    pacman = tools.pacman or "pacman"

    res = safe_run([pkexec, pacman, "-R", "--noconfirm", "--", pkg_name], timeout=60)
    if res.returncode == 0:
        print(tr("cli.remove_success").format(name=pkg_name))
        return 0
    else:
        print(tr("cli.remove_failed").format(error=res.stderr))
        return 1


def _cmd_rollback(args: argparse.Namespace) -> int:
    """Handle `pkgforge rollback <package>`."""
    pkg_name = args.package
    if not is_valid_package_name(pkg_name):
        print(tr("cli.invalid_pkg_name").format(name=pkg_name))
        return 1
    print(tr("cli.rolling_back").format(name=pkg_name))

    db = HistoryDB()
    records = db.get_records_for_package(pkg_name)
    backups = [r for r in records if r.backup_pkg and Path(r.backup_pkg).is_file()]

    if not backups:
        print(tr("cli.no_backup_found").format(name=pkg_name))
        return 1

    target_backup = Path(backups[0].backup_pkg)
    print(tr("cli.installing_backup").format(name=target_backup.name))

    tools = discover_tools()
    pkexec = tools.pkexec or "pkexec"
    pacman = tools.pacman or "pacman"

    res = safe_run([pkexec, pacman, "-U", "--noconfirm", "--", str(target_backup)], timeout=120)
    if res.returncode == 0:
        print(tr("cli.rollback_success").format(name=pkg_name))
        return 0
    else:
        print(tr("cli.rollback_failed").format(error=res.stderr))
        return 1


def _cmd_check_updates(args: argparse.Namespace) -> int:
    """Handle `pkgforge check-updates`."""
    print(tr("cli.checking_updates") + "\n")
    results = check_all_installed_updates()

    if not results:
        print(tr("cli.no_url_pkgs"))
        return 0

    for r in results:
        status_icon = "🟢" if r.has_update else "⚪"
        print(f"  {status_icon} {r.package_name:<20} | {r.detail}")
    return 0
