#!/usr/bin/env python3
"""PkgForge — Application entry point.

Converts .deb and .rpm packages to Arch Linux packages and installs
them with full security checks and a modern PyQt6 interface.

Usage:
    python main.py                      # Launch GUI
    python main.py --file a.deb b.rpm   # Launch with pre-selected files
    python main.py --lang en            # Launch in English
    python main.py --check-deps         # Check system dependencies
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pkgforge")


# ── Dependency checker ───────────────────────────────────────────

# (tool_name, package_name, required?)
SYSTEM_DEPS: list[tuple[str, str, bool]] = [
    ("pacman", "pacman", True),
    ("makepkg", "pacman", True),
    ("fakeroot", "fakeroot", True),
    ("file", "file", True),
    ("pkexec", "polkit", True),
    ("bsdtar", "libarchive", True),
    ("namcap", "namcap", False),
    ("bwrap", "bubblewrap", False),
    ("gpg", "gnupg", False),
    ("ldd", "glibc", True),
    ("ar", "binutils", False),
    ("clamscan", "clamav", False),
    ("debtap", "debtap (AUR)", False),
    ("rpm2cpio", "rpm-tools", False),
    ("distrobox", "distrobox", False),
    ("rsvg-convert", "librsvg", False),
]


def check_dependencies(install: bool = False) -> bool:
    """Check and optionally install system dependencies.

    Returns True if all required dependencies are met.
    """
    missing_required: list[tuple[str, str]] = []
    missing_optional: list[tuple[str, str]] = []

    print("🔍 PkgForge — Sistem bağımlılıkları kontrol ediliyor...\n")

    for tool, pkg, required in SYSTEM_DEPS:
        found = shutil.which(tool)
        status = "✓" if found else ("✗" if required else "○")
        label = "GEREKLİ" if required else "İsteğe bağlı"
        color = "\033[32m" if found else ("\033[31m" if required else "\033[33m")
        print(f"  {color}{status}\033[0m  {tool:<16s} ({pkg}) [{label}]")

        if not found:
            if required:
                missing_required.append((tool, pkg))
            else:
                missing_optional.append((tool, pkg))

    print()

    if not missing_required and not missing_optional:
        print("✅ Tüm bağımlılıklar mevcut!\n")
        return True

    if missing_required:
        print(f"❌ {len(missing_required)} gerekli bağımlılık eksik:")
        for tool, pkg in missing_required:
            print(f"   • {tool} ({pkg})")

    if missing_optional:
        print(f"\n⚠️  {len(missing_optional)} isteğe bağlı bağımlılık eksik:")
        for tool, pkg in missing_optional:
            print(f"   • {tool} ({pkg})")

    if install and (missing_required or missing_optional):
        print()
        # Separate pacman and AUR packages
        pacman_pkgs = []
        aur_pkgs = []

        all_missing = missing_required + (missing_optional if install else [])
        for tool, pkg in all_missing:
            if "(AUR)" in pkg:
                aur_pkgs.append(pkg.replace(" (AUR)", ""))
            else:
                pacman_pkgs.append(pkg)

        # Deduplicate
        pacman_pkgs = list(dict.fromkeys(pacman_pkgs))
        aur_pkgs = list(dict.fromkeys(aur_pkgs))

        if pacman_pkgs:
            cmd = ["sudo", "pacman", "-S", "--needed", "--noconfirm"] + pacman_pkgs
            print(f"📦 Pacman ile kuruluyor: {' '.join(pacman_pkgs)}")
            result = subprocess.run(cmd)
            if result.returncode != 0:
                print("❌ Pacman kurulumu başarısız!")
                return False

        if aur_pkgs:
            aur_helper = shutil.which("paru") or shutil.which("yay")
            if aur_helper:
                cmd = [aur_helper, "-S", "--needed", "--noconfirm"] + aur_pkgs
                print(f"📦 AUR ile kuruluyor: {' '.join(aur_pkgs)}")
                result = subprocess.run(cmd)
                if result.returncode != 0:
                    print("⚠️  AUR kurulumu başarısız (manuel kurulum gerekebilir)")
            else:
                print(f"⚠️  AUR helper bulunamadı. Manuel kurun: paru -S {' '.join(aur_pkgs)}")

        # Debtap database sync
        if "debtap" in [t for t, _ in all_missing]:
            debtap_db = Path("/var/cache/debtap/debian-main-packages-files")
            if shutil.which("debtap") and not debtap_db.exists():
                print("🔄 Debtap veritabanı senkronize ediliyor...")
                subprocess.run(["sudo", "debtap", "-u"])

        # Re-check
        print("\n🔍 Yeniden kontrol ediliyor...")
        still_missing = [t for t, p, r in SYSTEM_DEPS if r and not shutil.which(t)]
        if still_missing:
            print(f"❌ Hâlâ eksik: {', '.join(still_missing)}")
            return False

        print("✅ Bağımlılıklar kuruldu!\n")
        return True

    if missing_required:
        print(f"\n💡 Otomatik kurmak için: python main.py --install-deps")
        return False

    return True


# ── PyQt6 check ──────────────────────────────────────────────────

def _check_pyqt6() -> bool:
    """Check if PyQt6 is installed."""
    try:
        import PyQt6.QtWidgets  # noqa: F401
        return True
    except ImportError:
        print("❌ PyQt6 bulunamadı!")
        print("   Kurmak için: sudo pacman -S python-pyqt6 python-pyqt6-sip")
        print("   veya: pip install PyQt6")
        return False


# ── Main ─────────────────────────────────────────────────────────

def main() -> int:
    """Application main entry point."""
    # Early language detection from CLI flags or settings
    lang_override = None
    if "--lang" in sys.argv:
        idx = sys.argv.index("--lang")
        if idx + 1 < len(sys.argv):
            lang_override = sys.argv[idx + 1]
    elif "-l" in sys.argv:
        idx = sys.argv.index("-l")
        if idx + 1 < len(sys.argv):
            lang_override = sys.argv[idx + 1]

    from i18n import init_language, tr
    init_language(lang_override)

    parser = argparse.ArgumentParser(
        prog="pkgforge",
        description=tr("cli.help_desc"),
    )
    subparsers = parser.add_subparsers(dest="command", help=tr("cli.subcommands_help"))

    # convert subcommand
    convert_parser = subparsers.add_parser("convert", help=tr("cli.convert_help"))
    convert_parser.add_argument("target", help=tr("cli.arg_target"))
    convert_parser.add_argument("--install", "-i", action="store_true", help=tr("cli.arg_install"))
    convert_parser.add_argument("--yes", "-y", action="store_true", help=tr("cli.arg_yes"))
    convert_parser.add_argument("--dry-run", action="store_true", help=tr("cli.arg_dry_run"))
    convert_parser.add_argument("--output-dir", "-o", help=tr("cli.arg_output_dir"))
    convert_parser.add_argument("--to-oci", action="store_true", help=tr("cli.arg_to_oci"))
    convert_parser.add_argument("--oci-tag", help=tr("cli.arg_oci_tag"))
    convert_parser.add_argument("--delta", action="store_true", help=tr("cli.arg_delta"))
    convert_parser.add_argument("--verify-build", action="store_true", help=tr("cli.arg_verify_build"))

    # list subcommand
    subparsers.add_parser("list", help=tr("cli.list_help"))

    # remove subcommand
    remove_parser = subparsers.add_parser("remove", help=tr("cli.remove_help"))
    remove_parser.add_argument("package", help="Package name to remove")

    # rollback subcommand
    rollback_parser = subparsers.add_parser("rollback", help=tr("cli.rollback_help"))
    rollback_parser.add_argument("package", help="Package name to rollback")

    # check-updates subcommand
    subparsers.add_parser("check-updates", help=tr("cli.updates_help"))

    # flatpak-export subcommand
    flatpak_parser = subparsers.add_parser("flatpak-export", help=tr("cli.flatpak_export_help"))
    flatpak_parser.add_argument("app_id", nargs="?", help=tr("cli.arg_flatpak_app_id"))
    flatpak_parser.add_argument("--list", action="store_true", help=tr("cli.arg_flatpak_list"))
    flatpak_parser.add_argument("--branch", default="stable", help=tr("cli.arg_flatpak_branch"))
    flatpak_parser.add_argument("--output-dir", "-o", help=tr("cli.arg_output_dir"))

    # appimage-export subcommand
    appimage_parser = subparsers.add_parser("appimage-export", help=tr("cli.appimage_export_help"))
    appimage_parser.add_argument("appimage", help=tr("cli.arg_appimage_path"))
    appimage_parser.add_argument("--output-dir", "-o", help=tr("cli.arg_output_dir"))

    # provenance subcommand
    prov_parser = subparsers.add_parser("provenance", help=tr("cli.provenance_help"))
    prov_parser.add_argument("package", help=tr("cli.arg_provenance_pkg"))

    # gui subcommand
    subparsers.add_parser("gui", help=tr("cli.gui_help"))

    # Global flags
    parser.add_argument("--file", "-f", nargs="+", type=Path, help=tr("cli.arg_file"))
    parser.add_argument("--lang", "-l", choices=["tr", "en"], help=tr("cli.arg_lang"))
    parser.add_argument("--theme", "-t", choices=["dark", "light", "system"], help=tr("cli.arg_theme"))
    parser.add_argument("--version", "-v", action="store_true", help=tr("cli.arg_version"))
    parser.add_argument("--check-deps", action="store_true", help=tr("cli.arg_check_deps"))
    parser.add_argument("--install-deps", action="store_true", help=tr("cli.arg_install_deps"))

    args = parser.parse_args()

    if args.version:
        from config import APP_NAME, APP_VERSION
        print(f"{APP_NAME} v{APP_VERSION}")
        return 0

    if args.check_deps:
        ok = check_dependencies(install=False)
        return 0 if ok else 1

    if args.install_deps:
        ok = check_dependencies(install=True)
        return 0 if ok else 1

    # Cleanup orphaned temp directories
    from config import cleanup_orphaned_temp_dirs
    cleaned = cleanup_orphaned_temp_dirs()
    if cleaned > 0:
        log.info("Temizlenen eski geçici dizin sayısı: %d", cleaned)

    # Route CLI subcommands
    if args.command and args.command != "gui":
        from cli import run_cli
        return run_cli(args)

    # If no subcommand and no files passed, print CLI help unless launched via pkgforge-gui
    is_gui_binary = sys.argv[0].endswith("pkgforge-gui")
    if not args.command and not args.file and not is_gui_binary:
        parser.print_help()
        print(f"\n💡 {tr('cli.gui_tip')}")
        return 0
    if not _check_pyqt6():
        return 1

    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("PkgForge")
    app.setOrganizationName("PkgForge")
    app.setDesktopFileName("pkgforge")

    from ui.styles import build_stylesheet
    app.setStyleSheet(build_stylesheet(args.theme))

    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    if args.file:
        valid_files = [f for f in args.file if f.is_file()]
        if valid_files:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, lambda: window._on_files_dropped(valid_files))

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
