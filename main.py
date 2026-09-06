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
            result = subprocess.run(cmd, check=False)
            if result.returncode != 0:
                print("❌ Pacman kurulumu başarısız!")
                return False

        if aur_pkgs:
            aur_helper = shutil.which("paru") or shutil.which("yay")
            if aur_helper:
                cmd = [aur_helper, "-S", "--needed", "--noconfirm"] + aur_pkgs
                print(f"📦 AUR ile kuruluyor: {' '.join(aur_pkgs)}")
                result = subprocess.run(cmd, check=False)
                if result.returncode != 0:
                    print("⚠️  AUR kurulumu başarısız (manuel kurulum gerekebilir)")
            else:
                print(f"⚠️  AUR helper bulunamadı. Manuel kurun: paru -S {' '.join(aur_pkgs)}")

        # Debtap database sync
        if "debtap" in [t for t, _ in all_missing]:
            debtap_db = Path("/var/cache/debtap/debian-main-packages-files")
            if shutil.which("debtap") and not debtap_db.exists():
                print("🔄 Debtap veritabanı senkronize ediliyor...")
                subprocess.run(["sudo", "debtap", "-u"], check=False)

        # Re-check
        print("\n🔍 Yeniden kontrol ediliyor...")
        still_missing = [t for t, p, r in SYSTEM_DEPS if r and not shutil.which(t)]
        if still_missing:
            print(f"❌ Hâlâ eksik: {', '.join(still_missing)}")
            return False

        print("✅ Bağımlılıklar kuruldu!\n")
        return True

    if missing_required:
        print("\n💡 Otomatik kurmak için: python main.py --install-deps")
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
    convert_parser.add_argument("--sign", action="store_true", help=tr("cli.arg_sign_auto"))
    convert_parser.add_argument("--sign-key", help=tr("cli.arg_sign_key_auto"))
    convert_parser.add_argument("--resolve-deps", action="store_true", help=tr("cli.arg_resolve_deps"))

    # list subcommand
    subparsers.add_parser("list", help=tr("cli.list_help"))

    # remove subcommand
    remove_parser = subparsers.add_parser("remove", help=tr("cli.remove_help"))
    remove_parser.add_argument("package", help="Package name to remove")

    # rollback subcommand
    rollback_parser = subparsers.add_parser("rollback", help=tr("cli.rollback_help"))
    rollback_parser.add_argument("package", help="Package name to rollback")

    # check-updates subcommand
    updates_parser = subparsers.add_parser("check-updates", help=tr("cli.updates_help"))
    updates_parser.add_argument("--watch", action="store_true", help=tr("cli.arg_watch"))
    updates_parser.add_argument("--interval", type=int, default=300, help=tr("cli.arg_watch_interval"))

    # delta subcommand
    delta_parser = subparsers.add_parser("delta", help=tr("cli.delta_help"))
    delta_sub = delta_parser.add_subparsers(dest="delta_action")
    delta_sub.add_parser("status", help=tr("cli.delta_status_help"))
    delta_sub.add_parser("enable", help=tr("cli.delta_enable_help"))
    delta_sub.add_parser("disable", help=tr("cli.delta_disable_help"))

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

    # graph subcommand
    graph_parser = subparsers.add_parser("graph", help=tr("cli.graph_help"))
    graph_parser.add_argument("package", help=tr("cli.arg_graph_pkg"))
    graph_parser.add_argument("--files", action="store_true", help=tr("cli.arg_graph_files"))
    graph_parser.add_argument("--format", choices=["ascii", "mermaid"], default="ascii", help=tr("cli.arg_graph_format"))

    # audit subcommand
    audit_parser = subparsers.add_parser("audit", help=tr("cli.audit_help"))
    audit_parser.add_argument("--from", dest="date_from", help=tr("cli.arg_audit_from"))
    audit_parser.add_argument("--to", dest="date_to", help=tr("cli.arg_audit_to"))

    # scan-image subcommand
    scan_parser = subparsers.add_parser("scan-image", help=tr("cli.scan_image_help"))
    scan_parser.add_argument("image", help=tr("cli.arg_scan_image_path"))

    # abi-check subcommand
    abi_parser = subparsers.add_parser("abi-check", help=tr("cli.abi_check_help"))
    abi_parser.add_argument("package", help=tr("cli.arg_abi_check_pkg"))

    # health subcommand
    subparsers.add_parser("health", help=tr("cli.health_help"))

    # doctor subcommand (F5.22) — Tur-55 A2: --tools / --json alt seçenekleri
    doctor_parser = subparsers.add_parser("doctor", help=tr("cli.doctor_help"))
    doctor_parser.add_argument("--tools", action="store_true",
                               help=tr("cli.doctor_tools_help"))
    doctor_parser.add_argument("--json", action="store_true",
                               help=tr("cli.doctor_json_help"))

    # wrapped subcommand (F5.24)
    wrapped_parser = subparsers.add_parser("wrapped", help=tr("cli.wrapped_help"))
    wrapped_parser.add_argument("--year", type=int, default=None,
                            help=tr("cli.arg_wrapped_year"))

    # snapshot-cleanup subcommand
    snap_clean_parser = subparsers.add_parser("snapshot-cleanup", help=tr("cli.snapshot_cleanup_help"))
    snap_clean_parser.add_argument("--install", action="store_true", help=tr("cli.arg_cleanup_install"))
    snap_clean_parser.add_argument("--remove", action="store_true", help=tr("cli.arg_cleanup_remove"))
    snap_clean_parser.add_argument("--status", action="store_true", help=tr("cli.arg_cleanup_status"))
    snap_clean_parser.add_argument("--max-age", type=int, default=7, help=tr("cli.arg_cleanup_max_age"))

    # quality subcommand
    quality_parser = subparsers.add_parser("quality", help=tr("cli.quality_help"))
    quality_parser.add_argument("package", help=tr("cli.arg_quality_pkg"))

    # signing-setup subcommand (Tur-55 B7)
    signing_setup = subparsers.add_parser("signing-setup",
                                           help=tr("cli.signing_setup_help"))
    signing_setup.add_argument("--method",
                               choices=["pgp", "sigstore", "skip", "auto"],
                               default="auto",
                               help=tr("cli.signing_setup_help"))
    signing_setup.add_argument("--save-config", metavar="PATH",
                               help=tr("cli.signing_setup_save_help"))

    # serve-api subcommand (Tur-55 C10)
    serve_api = subparsers.add_parser("serve-api",
                                      help=tr("cli.serve_api_help"))
    serve_api.add_argument("--host", default="127.0.0.1",
                           help=tr("cli.serve_api_host_help"))
    serve_api.add_argument("--port", type=int, default=8899,
                           help=tr("cli.serve_api_port_help"))
    serve_api.add_argument("--export-openapi", metavar="PATH",
                           help=tr("cli.serve_api_export_help"))

    # publish subcommand
    publish_parser = subparsers.add_parser("publish", help=tr("cli.publish_help"))
    publish_parser.add_argument("package", help=tr("cli.arg_publish_pkg"))
    publish_parser.add_argument("--aur-url", help=tr("cli.arg_publish_aur_url"))
    publish_parser.add_argument("--output-dir", "-o", help=tr("cli.arg_output_dir"))

    # verify-rollback subcommand
    subparsers.add_parser("verify-rollback", help=tr("cli.verify_rollback_help"))

    # from-source subcommand
    source_parser = subparsers.add_parser("from-source", help=tr("cli.from_source_help"))
    source_parser.add_argument("repo_url", help=tr("cli.arg_source_repo_url"))
    source_parser.add_argument("--output-dir", "-o", help=tr("cli.arg_output_dir"))

    # rpm-to-deb subcommand
    rpm2deb_parser = subparsers.add_parser("rpm-to-deb", help=tr("cli.rpm_to_deb_help"))
    rpm2deb_parser.add_argument("rpm", help=tr("cli.arg_rpm_to_deb_path"))
    rpm2deb_parser.add_argument("--output-dir", "-o", help=tr("cli.arg_output_dir"))

    # provenance subcommand
    prov_parser = subparsers.add_parser("provenance", help=tr("cli.provenance_help"))
    prov_parser.add_argument("package", help=tr("cli.arg_provenance_pkg"))

    # benchmark subcommand
    bench_parser = subparsers.add_parser("benchmark", help=tr("cli.benchmark_help"))
    bench_parser.add_argument("--bench-file", help=tr("cli.arg_bench_file"))
    bench_parser.add_argument("--quick", action="store_true", help=tr("cli.arg_bench_quick"))
    bench_parser.add_argument("--baseline", help=tr("cli.arg_bench_baseline"))
    bench_parser.add_argument("--save-baseline", help=tr("cli.arg_bench_save_baseline"))

    # sign subcommand
    sign_parser = subparsers.add_parser("sign", help=tr("cli.sign_help"))
    sign_parser.add_argument("package", help=tr("cli.arg_sign_pkg"))
    sign_parser.add_argument("--key", help=tr("cli.arg_sign_key"))

    # verify subcommand
    verify_parser = subparsers.add_parser("verify", help=tr("cli.verify_help"))
    verify_parser.add_argument("package", help=tr("cli.arg_verify_pkg"))
    verify_parser.add_argument("--sigstore", action="store_true", help=tr("cli.arg_verify_sigstore"))

    # sbom subcommand
    sbom_parser = subparsers.add_parser("sbom", help=tr("cli.sbom_help"))
    sbom_parser.add_argument("package", nargs="?", help=tr("cli.arg_sbom_pkg"))
    sbom_parser.add_argument("--output-dir", "-o", help=tr("cli.arg_output_dir"))
    sbom_parser.add_argument("--no-hashes", action="store_true", help=tr("cli.arg_sbom_no_hashes"))
    sbom_parser.add_argument("--diff", nargs=2, metavar=("OLD", "NEW"), help=tr("cli.arg_sbom_diff"))

    # attest subcommand
    attest_parser = subparsers.add_parser("attest", help=tr("cli.attest_help"))
    attest_parser.add_argument("package", help=tr("cli.arg_attest_pkg"))
    attest_parser.add_argument("--key", help=tr("cli.arg_attest_key"))

    # plugin subcommand
    plugin_parser = subparsers.add_parser("plugin", help=tr("cli.plugin_help"))
    plugin_sub = plugin_parser.add_subparsers(dest="plugin_action")
    plugin_install = plugin_sub.add_parser("install", help=tr("cli.plugin_install_help"))
    plugin_install.add_argument("name", help=tr("cli.plugin_install_name"))
    plugin_install.add_argument("--version", "-V", default="latest", help=tr("cli.plugin_version"))
    plugin_install.add_argument("--force", action="store_true", help=tr("cli.plugin_force"))
    plugin_install.add_argument("--yes", "-y", action="store_true", help=tr("cli.plugin_yes"))
    plugin_sub.add_parser("list", help=tr("cli.plugin_list_help"))
    plugin_sub.add_parser("available", help=tr("cli.plugin_available_help"))
    plugin_remove = plugin_sub.add_parser("remove", help=tr("cli.plugin_remove_help"))
    plugin_remove.add_argument("name", help=tr("cli.plugin_remove_name"))
    plugin_update = plugin_sub.add_parser("update", help=tr("cli.plugin_update_help"))
    plugin_update.add_argument("name", help=tr("cli.plugin_update_name"))
    plugin_sub.add_parser("audit", help=tr("cli.plugin_audit_help"))

    # gui subcommand
    subparsers.add_parser("gui", help=tr("cli.gui_help"))

    # serve subcommand (JSON-RPC sidecar for the desktop UI)
    serve_parser = subparsers.add_parser("serve", help=tr("cli.serve_help"))
    serve_parser.add_argument("--http", action="store_true",
                              help="Serve JSON-RPC over HTTP (LAN remote management)")
    serve_parser.add_argument("--port", type=int, default=8765,
                              help="HTTP port (with --http, default 8765)")
    serve_parser.add_argument("--token", default="",
                              help="Bearer token required for HTTP requests")
    serve_parser.add_argument("--host", default="127.0.0.1",
                              help="HTTP bind address (with --http)")
    serve_parser.add_argument("--read-token", default="",
                              help="Additional read-only token (with --http)")
    serve_parser.add_argument("--dbus", action="store_true",
                              help="Also expose the JSON-RPC registry on the D-Bus session bus")
    serve_parser.add_argument("--token-file", default="",
                              help="Token'ı dosyadan oku (--token yerine; ps'te görünmez)")
    serve_parser.add_argument("--insecure-http-lan", action="store_true",
                              help="TLS olmadan LAN HTTP'ye izin ver (risk bilincli onay; F5.2b)")
    serve_parser.add_argument("--trusted-proxy", action="store_true",
                              help="X-Forwarded-For basligina guven (onde TLS proxy varsa; F5.2b)")

    # schedule subcommands (F4.6: headless systemd-friendly entry points)
    sched_run = subparsers.add_parser(
        "schedule-run", help="Zamanlanmis gorevi simdi calistir")
    sched_run.add_argument("--force", action="store_true",
                           help="Zaman bakilmaksizin calistir")
    sched_install = subparsers.add_parser(
        "schedule-install",
        help="systemd user timer birimlerini kur/onizle")
    sched_install.add_argument("--interval-hours", type=float, default=None,
                               help="Aralik (saat); varsayilan ayarlardan")
    sched_install.add_argument("--dry-run", action="store_true",
                               help="Dosyalari yazma, icerigi goster")

    # completion subcommand
    completion_parser = subparsers.add_parser("completion", help=tr("cli.completion_help"))
    completion_parser.add_argument("shell", choices=["bash", "zsh", "fish"], help=tr("cli.completion_shell"))

    # Global flags
    parser.add_argument("--file", "-f", nargs="+", type=Path, help=tr("cli.arg_file"))
    parser.add_argument("--lang", "-l", choices=["tr", "en"], help=tr("cli.arg_lang"))
    parser.add_argument("--theme", "-t", choices=["dark", "light", "system"], help=tr("cli.arg_theme"))
    parser.add_argument("--version", "-v", action="store_true", help=tr("cli.arg_version"))
    parser.add_argument("--check-deps", action="store_true", help=tr("cli.arg_check_deps"))
    parser.add_argument("--install-deps", action="store_true", help=tr("cli.arg_install_deps"))
    parser.add_argument("--offline", action="store_true", help=tr("cli.arg_offline"))
    parser.add_argument("--clear-cache", action="store_true", help=tr("cli.arg_clear_cache"))
    parser.add_argument("--verbose", action="store_true", help=tr("cli.arg_verbose"))

    args = parser.parse_args()

    # Activate verbose mode if requested
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("pkgforge").setLevel(logging.DEBUG)
        log.debug("Verbose logging aktif")

    # Activate offline mode if requested
    if args.offline:
        import config
        config.OFFLINE_MODE = True
        log.info("Çevrimdışı mod aktif")

    if args.clear_cache:
        from core.offline_cache import get_cache
        cache = get_cache()
        count = cache.clear_all()
        print(f"🗑️  {count} önbellek kaydı temizlendi.")
        return 0

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
    # Handle --file batch mode
    file_list = getattr(args, "file", None)
    if file_list and len(file_list) > 1 and hasattr(args, "install"):
        from cli import run_cli
        print(f"📦 Toplu dönüştürme: {len(file_list)} dosya")
        failures = 0
        for fp in file_list:
            args.target = str(fp)
            result = run_cli(args)
            if result != 0:
                failures += 1
        if failures:
            print(f"\n⚠️  {failures}/{len(file_list)} dosya başarısız")
            return 1
        print(f"\n✅ {len(file_list)} dosya başarıyla dönüştürüldü")
        return 0
    if args.command == "serve":
        if getattr(args, "http", False):
            import os as _os
            from pathlib import Path as _P

            from core.api_server import serve_http

            token = args.token
            # F5.2a: keep the secret out of the process list.
            tf = getattr(args, "token_file", "")
            if not token and isinstance(tf, str) and tf:
                try:
                    token = _P(tf).read_text(encoding="utf-8").strip()
                except OSError as exc:
                    print(f"hata: token dosyası okunamadı: {exc}")
                    return 2
            if not token:
                token = _os.environ.get("PKGFORGE_TOKEN", "")
            serve_http(port=args.port, token=token, host=args.host,
                       read_token=getattr(args, "read_token", ""),
                       insecure_http_lan=getattr(args, "insecure_http_lan", False),
                       trusted_proxy=getattr(args, "trusted_proxy", False))
        else:
            if getattr(args, "dbus", False):
                import threading as _threading

                def _start_dbus():
                    from core.dbus_service import start_default

                    try:
                        start_default()
                        print("D-Bus servisi yayında:", "org.pkgforge.App")
                    except Exception as exc:  # noqa: BLE001
                        logging.getLogger(__name__).error(
                            "D-Bus servisi başlatılamadı: %s", exc)

                _threading.Thread(target=_start_dbus, daemon=True).start()
            from core.api_server import serve

            serve()
        return 0
    if args.command == "schedule-run":
        from core.scheduler import run_due

        out = run_due(force=bool(getattr(args, "force", False)))
        print("calisti:" , out.get("ran"), "| gorev:", out.get("task", "-"),
              "| sonuc:", out.get("ok", "-"), "|", out.get("detail", out.get("reason", "")))
        return 0 if out.get("ok", True) else 1
    if args.command == "schedule-install":
        from core.scheduler import install_timer

        try:
            res = install_timer(interval_hours=args.interval_hours,
                                dry_run=bool(args.dry_run))
        except ValueError as exc:
            print("hata:", exc)
            return 2
        for path, text in res["units"].items():
            print("--- " + path + " ---")
            print(text)
        if res["installed"]:
            print("kurulum tamam. etkinlestirme:", res["enable"])
        else:
            print("(dry-run: hicbir dosya yazilmadi)")
        return 0
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
