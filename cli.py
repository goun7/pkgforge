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
    elif command == "flatpak-export":
        return _cmd_flatpak_export(args)
    elif command == "appimage-export":
        return _cmd_appimage_export(args)
    elif command == "rpm-to-deb":
        return _cmd_rpm_to_deb(args)
    elif command == "provenance":
        return _cmd_provenance(args)
    elif command == "benchmark":
        return _cmd_benchmark(args)
    elif command == "sign":
        return _cmd_sign(args)
    elif command == "verify":
        return _cmd_verify(args)
    elif command == "graph":
        return _cmd_graph(args)
    elif command == "audit":
        return _cmd_audit(args)
    elif command == "scan-image":
        return _cmd_scan_image(args)
    elif command == "from-source":
        return _cmd_from_source(args)
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
    http_info: dict[str, str] = {}
    if target.startswith("http://") or target.startswith("https://"):
        print(tr("cli.downloading_url").format(target=target))
        try:
            use_delta = getattr(args, "delta", False)
            if use_delta:
                from core.delta_updater import download_with_delta, find_local_previous
                from config import create_temp_dir
                # Try to find a previous local version for delta
                pkg_name_guess = Path(target).stem.split("_")[0].split("-")[0]
                old_pkg = find_local_previous(pkg_name_guess)
                tmp = create_temp_dir()
                dest = tmp / Path(target).name
                file_path, used_delta = download_with_delta(
                    target, dest, old_pkg,
                    require_https=not load_setting("allow_insecure_http", False),
                )
                if used_delta:
                    print(tr("cli.download_complete").format(name=file_path.name) + " (delta)")
                else:
                    print(tr("cli.download_complete").format(name=file_path.name))
            else:
                file_path = download_package(
                    target, require_https=not load_setting("allow_insecure_http", False),
                    response_info=http_info,
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

    # Run conversion via cli_bridge (no direct PyQt6 event loop needed)
    out_dir = Path(args.output_dir).resolve() if args.output_dir else file_path.parent
    is_deb = file_path.suffix.lower() == ".deb"

    print(tr("cli.starting_conversion").format(name=file_path.name))

    from core.cli_bridge import convert_deb_sync, convert_rpm_sync

    def _print_line(line: str):
        print(f"  {line}")

    if is_deb:
        conv_result = convert_deb_sync(file_path, out_dir, tools, progress_callback=_print_line)
    else:
        conv_result = convert_rpm_sync(file_path, out_dir, tools=tools, progress_callback=_print_line)

    success = conv_result.success
    msg = conv_result.message
    pkg_path = conv_result.output_pkg

    if not success or not pkg_path:
        print(tr("cli.conversion_failed").format(msg=msg))
        return 1

    print(tr("cli.conversion_success").format(pkg=pkg_path))

    # --to-oci: convert to OCI container image instead of installing
    if getattr(args, "to_oci", False):
        from core.oci_builder import build_oci_image
        oci_tag = getattr(args, "oci_tag", None)
        print(f"🐳 OCI konteyner görüntüsü oluşturuluyor...")
        ok, oci_msg, oci_path = build_oci_image(Path(pkg_path), tools, tag=oci_tag)
        if ok:
            print(f"✅ {oci_msg}")
            if oci_path:
                print(f"   Yüklemek için: podman load -i {oci_path}")
        else:
            print(f"❌ {oci_msg}")
            return 1
        # Record and exit
        db = HistoryDB()
        db.add_record(
            package_name=file_path.stem.split("_")[0].split("-")[0],
            original_file=file_path.name,
            package_type="deb" if is_deb else "rpm",
            sha256="", status="oci_built",
            output_pkg=str(oci_path) if oci_path else "",
            source_url=target if target.startswith("http") else "",
            details=oci_msg,
            http_etag=http_info.get("etag", ""),
            http_last_modified=http_info.get("last_modified", ""),
        )
        return 0

    # --verify-build: reproducible build verification
    if getattr(args, "verify_build", False):
        from core.reproducible_build import verify_reproducible
        print(f"🔍 Reproducible build doğrulanıyor...")
        vr = verify_reproducible(Path(pkg_path), tools)
        print(f"  {vr.detail}")
        if vr.verified:
            print(f"  ✅ Doğrulama başarılı — paket reproducible")
        else:
            print(f"  ⚠️  Paket farklı — supply chain riski olabilir")
        # Continue to install even if verification fails (informational)

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

    # Generate SLSA provenance record
    from core.provenance import create_provenance, save_provenance
    from core.security import sha256_hash
    prov = create_provenance(
        source_file=file_path,
        source_url=target if target.startswith("http") else "",
        source_sha256=http_info.get("source_sha256", conv_result.message.split("SHA-256: ")[1][:16] if "SHA-256:" in conv_result.message else ""),
        output_file=Path(pkg_path),
        output_sha256=sha256_hash(Path(pkg_path)) if Path(pkg_path).exists() else "",
        package_name=file_path.stem.split("_")[0].split("-")[0],
        package_type="deb" if is_deb else "rpm",
    )
    prov_path = save_provenance(prov, Path(pkg_path).parent / f"{Path(pkg_path).name}.provenance.json")
    print(f"📋 Provenance: {prov_path.name}")

    # Auto-sign if requested
    if getattr(args, "sign", False):
        from core.package_signing import sign_package
        sign_key = Path(args.sign_key).resolve() if getattr(args, "sign_key", None) else None
        print(f"✍️  Otomatik imzalanıyor: {Path(pkg_path).name}...")
        sign_ok, sign_msg = sign_package(Path(pkg_path), sign_key)
        if sign_ok:
            print(f"✅ {sign_msg}")
        else:
            print(f"⚠️  İmza başarısız: {sign_msg}")

    # Backup converted package in HistoryDB
    db = HistoryDB()
    backup_path = db.backup_package(Path(pkg_path))

    # Auto-install if requested (dry-run disables installation entirely)
    install_status = "converted"
    dry_run = getattr(args, "dry_run", False) or load_setting("dry_run", False)
    if args.install and dry_run:
        print(tr("cli.dry_run_note"))
    elif args.install:
        # Onay iste (eğer --yes verilmemişse)
        confirmed = getattr(args, "yes", False)
        if not confirmed:
            print(tr("cli.confirm_install").format(name=pkg_path.name))
            try:
                answer = input("[y/N] ").strip().lower()
            except EOFError:
                answer = ""
            confirmed = answer in ("y", "yes", "e", "evet")

        if confirmed:
            print(tr("cli.installing_pkg").format(name=pkg_path.name))
            pkexec = tools.pkexec or "pkexec"
            pacman = tools.pacman or "pacman"

            res = safe_run([pkexec, pacman, "-U", "--noconfirm", "--", str(pkg_path)], timeout=120)
            if res.returncode == 0:
                print(tr("cli.install_success").format(name=pkg_path.name))
                install_status = "installed"
            else:
                print(tr("cli.install_failed").format(error=res.stderr))
                install_status = "install_failed"
        else:
            print(tr("cli.install_cancelled"))

    db.add_record(
        package_name=file_path.stem.split("_")[0].split("-")[0],
        original_file=file_path.name,
        package_type="deb" if is_deb else "rpm",
        sha256="",
        status=install_status,
        output_pkg=str(pkg_path),
        source_url=target if target.startswith("http") else "",
        backup_pkg=str(backup_path) if backup_path else "",
        details=msg,
        http_etag=http_info.get("etag", ""),
        http_last_modified=http_info.get("last_modified", ""),
    )

    return 0 if install_status != "install_failed" else 1


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


def _cmd_flatpak_export(args: argparse.Namespace) -> int:
    """Handle `pkgforge flatpak-export`."""
    from core.flatpak_converter import (
        is_flatpak_available, list_installed_apps, flatpak_to_deb,
    )

    if not is_flatpak_available():
        print("❌ flatpak bulunamadı — kurulum: sudo pacman -S flatpak")
        return 1

    # --list: show installed apps
    if getattr(args, "list", False):
        apps = list_installed_apps()
        if not apps:
            print("  Yüklü Flatpak uygulaması bulunamadı.")
            return 0
        print(f"{'App ID':<40} {'Name':<25} {'Version':<15} {'Branch'}")
        print("-" * 95)
        for app in apps:
            print(f"{app.app_id:<40} {app.name:<25} {app.version:<15} {app.branch}")
        return 0

    # Export a specific app
    app_id = getattr(args, "app_id", None)
    if not app_id:
        print("❌ Flatpak uygulama ID'si gerekli.")
        print("   Örnek: pkgforge flatpak-export org.mozilla.firefox")
        print("   Listelemek için: pkgforge flatpak-export --list")
        return 1

    branch = getattr(args, "branch", "stable")
    out_dir = Path(args.output_dir).resolve() if args.output_dir else Path.cwd()

    print(f"🐳 Flatpak → DEB dönüştürülüyor: {app_id}//{branch}...")
    ok, msg, deb_path = flatpak_to_deb(app_id, out_dir, branch)

    if ok:
        print(f"✅ {msg}")
        print(f"   Kurmak için: sudo dpkg -i {deb_path}")
    else:
        print(f"❌ {msg}")
        return 1

    return 0


def _cmd_provenance(args: argparse.Namespace) -> int:
    """Handle `pkgforge provenance <package>`."""
    from core.provenance import load_provenance, verify_provenance, find_provenance

    pkg_path = Path(args.package).resolve()
    if not pkg_path.is_file():
        print(f"❌ Paket bulunamadı: {pkg_path}")
        return 1

    prov_path = find_provenance(pkg_path)
    if not prov_path:
        # Try looking for .provenance.json next to the package
        print(f"❌ Provenance dosyası bulunamadı: {pkg_path.name}.provenance.json")
        print(f"   Not: Provenance sadece pkgforge convert ile oluşturulan paketler için mevcut.")
        return 1

    prov = load_provenance(prov_path)
    if not prov:
        print(f"❌ Provenance dosyası okunamadı: {prov_path}")
        return 1

    print(f"📋 Provenance Doğrulama: {pkg_path.name}\n")
    print(f"  Araç:          {prov.tool_name} v{prov.tool_version}")
    print(f"  Build ID:      {prov.build_id}")
    print(f"  Kaynak:        {prov.source_file}")
    if prov.source_url:
        print(f"  Kaynak URL:    {prov.source_url}")
    print(f"  Kaynak SHA-256:{prov.source_sha256[:32]}…" if prov.source_sha256 else "  Kaynak SHA-256: (yok)")
    print(f"  Çıktı:         {prov.output_file}")
    print(f"  Çıktı SHA-256: {prov.output_sha256[:32]}…" if prov.output_sha256 else "  Çıktı SHA-256: (yok)")
    print(f"  Build Zamanı:  {prov.build_timestamp}")
    print(f"  Build Host:    {prov.build_host}")
    print(f"  Build OS:      {prov.build_os}")
    print(f"  Paket:         {prov.package_name} {prov.package_version}")
    print(f"  Mimari:        {prov.package_arch}")
    print()
    print(f"  🔒 ClamAV:     {prov.clamav_result}")
    print(f"  💣 Bomb Check: {prov.decompression_bomb_result}")
    print(f"  ✍️  İmza:       {'Geçerli' if prov.signature_valid else 'Yok/Geçersiz'}")
    print()

    valid, msg = verify_provenance(prov)
    if valid:
        print(f"  ✅ {msg}")
    else:
        print(f"  ❌ {msg}")
        return 1

    return 0


def _cmd_appimage_export(args: argparse.Namespace) -> int:
    """Handle `pkgforge appimage-export`."""
    from core.appimage_converter import is_appimage_available, appimage_to_deb

    if not is_appimage_available():
        print("❌ unsquashfs bulunamadı — kurulum: sudo pacman -S squashfs-tools")
        return 1

    appimage_path = Path(args.appimage).resolve()
    if not appimage_path.is_file():
        print(f"❌ Dosya bulunamadı: {appimage_path}")
        return 1

    out_dir = Path(args.output_dir).resolve() if args.output_dir else Path.cwd()

    print(f"📦 AppImage → DEB dönüştürülüyor: {appimage_path.name}...")
    ok, msg, deb_path = appimage_to_deb(appimage_path, out_dir)

    if ok:
        print(f"✅ {msg}")
        print(f"   Kurmak için: sudo dpkg -i {deb_path}")
    else:
        print(f"❌ {msg}")
        return 1

    return 0


def _cmd_rpm_to_deb(args: argparse.Namespace) -> int:
    """Handle `pkgforge rpm-to-deb`."""
    from core.rpm_to_deb_converter import is_rpm_to_deb_available, rpm_to_deb

    if not is_rpm_to_deb_available():
        print("❌ rpm2cpio veya dpkg-deb bulunamadı — kurulum: sudo pacman -S rpmextract dpkg")
        return 1

    rpm_path = Path(args.rpm).resolve()
    if not rpm_path.is_file():
        print(f"❌ Dosya bulunamadı: {rpm_path}")
        return 1

    out_dir = Path(args.output_dir).resolve() if args.output_dir else Path.cwd()

    print(f"📦 RPM → DEB dönüştürülüyor: {rpm_path.name}...")
    ok, msg, deb_path = rpm_to_deb(rpm_path, out_dir)

    if ok:
        print(f"✅ {msg}")
        print(f"   Kurmak için: sudo dpkg -i {deb_path}")
    else:
        print(f"❌ {msg}")
        return 1

    return 0


def _cmd_benchmark(args: argparse.Namespace) -> int:
    """Handle `pkgforge benchmark`."""
    from core.benchmark import run_benchmarks

    test_file = Path(args.bench_file).resolve() if args.bench_file else None
    quick = getattr(args, "quick", False)

    print("⚡ PkgForge Performans Ölçümü\n")
    report = run_benchmarks(test_file=test_file, quick=quick)
    print(report.summary())
    print()

    if report.passed:
        print("✅ Tüm testler başarılı")
    else:
        print("❌ Bazı testler başarısız")
        return 1

    return 0


def _cmd_sign(args: argparse.Namespace) -> int:
    """Handle `pkgforge sign <package>`."""
    from core.package_signing import sign_package

    pkg_path = Path(args.package).resolve()
    if not pkg_path.is_file():
        print(f"❌ Paket bulunamadı: {pkg_path}")
        return 1

    key_path = Path(args.key).resolve() if args.key else None

    print(f"✍️  Paket imzalanıyor: {pkg_path.name}...")
    ok, msg = sign_package(pkg_path, key_path)

    if ok:
        print(f"✅ {msg}")
    else:
        print(f"❌ {msg}")
        return 1

    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    """Handle `pkgforge verify <package>`."""
    from core.package_signing import verify_signature

    pkg_path = Path(args.package).resolve()
    if not pkg_path.is_file():
        print(f"❌ Paket bulunamadı: {pkg_path}")
        return 1

    print(f"🔍 İmza doğrulanıyor: {pkg_path.name}...")
    info = verify_signature(pkg_path)

    print(f"\n  İmza Durumu:  {'✅ Geçerli' if info.valid else '❌ Geçersiz/Yok'}")
    if info.signer:
        print(f"  İmzalayan:    {info.signer}")
    if info.key_id:
        print(f"  Key ID:       {info.key_id}")
    if info.key_fingerprint:
        print(f"  Fingerprint:  {info.key_fingerprint}")
    print(f"  Detay:        {info.detail}")

    return 0 if info.valid else 1


def _cmd_graph(args: argparse.Namespace) -> int:
    """Handle `pkgforge graph`."""
    from core.dep_graph import build_dep_graph, build_file_dep_graph

    pkg_name = args.package
    show_files = getattr(args, "files", False)
    fmt = getattr(args, "format", "ascii")

    if show_files:
        # Find the package file
        import glob as globmod
        for pattern in [f"/var/cache/pacman/pkg/{pkg_name}*.pkg.tar.zst",
                        f"/var/cache/pacman/pkg/{pkg_name}*.pkg.tar.xz"]:
            matches = globmod.glob(pattern)
            if matches:
                graph = build_file_dep_graph(Path(matches[0]))
                break
        else:
            print(f"❌ Paket dosyası bulunamadı: {pkg_name}")
            return 1
    else:
        graph = build_dep_graph(Path(f"/var/cache/pacman/pkg/{pkg_name}*.pkg.tar.zst"))
        if not graph.nodes:
            print(f"❌ Grafik oluşturulamadı: {pkg_name}")
            print("   Paket kurulu olmalı veya .pkg.tar.zst dosyası mevcut olmalı.")
            return 1

    stats = graph.stats()
    print(f"\n📊 Bağımlılık Grafiği: {graph.root}\n")
    print(f"   Toplam: {stats['total']}, Kurulu: {stats['installed']}, Eksik: {stats['missing']}")
    print(f"   Maks Derinlik: {stats['max_depth']}")
    print()

    if fmt == "mermaid":
        print(graph.to_mermaid())
    else:
        print(graph.to_ascii())

    return 0


def _cmd_audit(args: argparse.Namespace) -> int:
    """Handle `pkgforge audit`."""
    db = HistoryDB()
    records = db.get_history(limit=100)

    date_from = getattr(args, "date_from", None)
    date_to = getattr(args, "date_to", None)

    # Filter by date range if specified
    if date_from or date_to:
        filtered = []
        for r in records:
            if date_from and r.timestamp < date_from:
                continue
            if date_to and r.timestamp > date_to:
                continue
            filtered.append(r)
        records = filtered

    print(f"\n🔍 PkgForge Audit Trail\n")
    print(f"   Toplam kayıt: {len(records)}\n")

    if not records:
        print("  Kayıt bulunamadı.")
        return 0

    # Summary
    status_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    for r in records:
        status_counts[r.status] = status_counts.get(r.status, 0) + 1
        type_counts[r.package_type] = type_counts.get(r.package_type, 0) + 1

    print("📊 Özet:")
    for status, count in sorted(status_counts.items()):
        icon = {"installed": "✅", "converted": "📦", "install_failed": "❌", "oci_built": "🐳"}.get(status, "•")
        print(f"   {icon} {status}: {count}")
    print()

    print("📦 Paket Türleri:")
    for ptype, count in sorted(type_counts.items()):
        print(f"   • {ptype}: {count}")
    print()

    # Detailed trail
    print("📋 Detaylı Kayıtlar:")
    print(f"{'ID':<4} {'Tarih':<20} {'Paket':<20} {'Tür':<6} {'Durum':<12} {'Orijinal Dosya'}")
    print("-" * 90)
    for r in records:
        print(f"{r.id:<4} {r.timestamp:<20} {r.package_name:<20} {r.package_type:<6} {r.status:<12} {r.original_file}")

    return 0


def _cmd_scan_image(args: argparse.Namespace) -> int:
    """Handle `pkgforge scan-image`."""
    image_path = Path(args.image).resolve()
    if not image_path.is_file():
        print(f"❌ Görüntü dosyası bulunamadı: {image_path}")
        return 1

    # Check for trivy or grype
    trivy = shutil.which("trivy")
    grype = shutil.which("grype")
    clamscan = shutil.which("clamscan")

    if not trivy and not grype and not clamscan:
        print("❌ Tarama aracı bulunamadı.")
        print("   Kurulum: sudo pacman -S trivy")
        print("   veya: sudo pacman -S grype")
        print("   veya: sudo pacman -S clamav")
        return 1

    print(f"🔍 OCI Görüntü Taraması: {image_path.name}\n")
    all_clean = True

    # Trivy scan
    if trivy:
        print("  🔬 Trivy CVE taraması...")
        res = safe_run([trivy, "fs", "--severity", "HIGH,CRITICAL", str(image_path)], timeout=300)
        if res.returncode == 0:
            print("  ✅ Trivy: Kritik CVE bulunamadı")
        else:
            all_clean = False
            print(f"  ⚠️  Trivy sonuçları:\n{res.stdout[:500]}")

    # Grype scan
    if grype:
        print("  🔬 Grype bağımlılık taraması...")
        res = safe_run([grype, "dir:" + str(image_path.parent), "--fail-on", "high"], timeout=300)
        if res.returncode == 0:
            print("  ✅ Grype: Yüksek-seviye açık bulunamadı")
        else:
            all_clean = False
            print(f"  ⚠️  Grype sonuçları:\n{res.stdout[:500]}")

    # ClamAV scan
    if clamscan:
        print("  🔬 ClamAV malware taraması...")
        res = safe_run([clamscan, "--infected", "--no-summary", str(image_path)], timeout=120)
        if res.returncode == 1:
            print("  ✅ ClamAV: Temiz")
        elif res.returncode == 0:
            print(f"  ❌ ClamAV enfekte dosya tespit etti:\n{res.stdout[:500]}")
            all_clean = False
        else:
            print(f"  ⚠️  ClamAV çalışamadı: {res.stderr[:200]}")

    print()
    if all_clean:
        print("✅ Tüm taramalar temiz — görüntü güvenli.")
    else:
        print("⚠️  Bazı taramalar uyarı verdi — sonuçları inceleyin.")
        return 1

    return 0


def _cmd_from_source(args: argparse.Namespace) -> int:
    """Handle `pkgforge from-source`."""
    repo_url = args.repo_url
    out_dir = Path(args.output_dir).resolve() if args.output_dir else Path.cwd()

    print(f"📥 Kaynaktan PKGBUILD oluşturuluyor: {repo_url}\n")

    import tempfile
    with tempfile.TemporaryDirectory(prefix="pkgforge_src_") as tmpdir:
        tmp = Path(tmpdir)

        # 1. Clone repo
        print("  📥 Depo klonlanıyor...")
        res = safe_run(["git", "clone", "--depth=1", repo_url, str(tmp / "repo")], timeout=120)
        if res.returncode != 0:
            print(f"❌ Git clone başarısız: {res.stderr[:200]}")
            return 1

        repo_dir = tmp / "repo"

        # 2. Detect project type
        pkgbuild = None
        has_cmake = (repo_dir / "CMakeLists.txt").exists()
        has_makefile = (repo_dir / "Makefile").exists() or (repo_dir / "makefile").exists()
        has_meson = (repo_dir / "meson.build").exists()
        has_configure = (repo_dir / "configure").exists()
        has_setup_py = (repo_dir / "setup.py").exists()
        has_cargo = (repo_dir / "Cargo.toml").exists()

        # Determine project name from URL
        proj_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")

        print(f"  📁 Proje tespit edildi: {proj_name}")
        if has_cmake:
            build_system = "cmake"
        elif has_meson:
            build_system = "meson"
        elif has_cargo:
            build_system = "cargo"
        elif has_configure:
            build_system = "autotools"
        elif has_makefile:
            build_system = "make"
        elif has_setup_py:
            build_system = "python"
        else:
            build_system = "unknown"
        print(f"  🔧 Build sistemi: {build_system}\n")

        # 3. Generate PKGBUILD
        pkgbuild_content = _generate_pkgbuild_from_source(
            proj_name, repo_url, build_system, repo_dir
        )

        # 4. Write PKGBUILD
        output_pkgbuild = out_dir / f"PKGBUILD-{proj_name}"
        output_pkgbuild.write_text(pkgbuild_content, encoding="utf-8")
        print(f"✅ PKGBUILD oluşturuldu: {output_pkgbuild}\n")

        # Show preview
        print("📋 PKGBUILD Önizleme:")
        print("-" * 60)
        for i, line in enumerate(pkgbuild_content.splitlines()[:30]):
            print(f"  {line}")
        if len(pkgbuild_content.splitlines()) > 30:
            print(f"  ... ({len(pkgbuild_content.splitlines()) - 30} satır daha)")
        print("-" * 60)

        print(f"\n💡 Derlemek için: cd {out_dir} && makepkg -si")

    return 0


def _generate_pkgbuild_from_source(
    name: str,
    repo_url: str,
    build_system: str,
    repo_dir: Path,
) -> str:
    """Generate a PKGBUILD template from source repo info."""
    # Try to extract version from common files
    version = "1.0.0"
    for vf in [repo_dir / "VERSION", repo_dir / "version.txt", repo_dir / "VERSION.txt"]:
        if vf.exists():
            version = vf.read_text().strip().splitlines()[0]
            break

    # Try to extract description from README
    description = f"{name} — kaynaktan derlenen paket"
    for readme in [repo_dir / "README.md", repo_dir / "README", repo_dir / "README.rst"]:
        if readme.exists():
            for line in readme.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and len(line) > 10:
                    description = line[:100]
                    break
            break

    # Escape for PKGBUILD
    description = description.replace("'", "''")

    # Build commands based on build system
    if build_system == "cmake":
        build_cmds = """    cmake -B build -DCMAKE_INSTALL_PREFIX=/usr
    cmake --build build"""
        install_cmds = """    DESTDIR=\"$pkgdir" cmake --install build"""
    elif build_system == "meson":
        build_cmds = """    meson setup build
    meson compile -C build"""
        install_cmds = """    DESTDIR=\"$pkgdir" meson install -C build"""
    elif build_system == "cargo":
        build_cmds = """    cargo build --release --locked"""
        install_cmds = """    install -Dm755 target/release/\"$pkgname\" \"$pkgdir/usr/bin/$pkgname\""""
    elif build_system == "autotools":
        build_cmds = """    ./configure --prefix=/usr
    make"""
        install_cmds = """    make DESTDIR=\"$pkgdir\" install"""
    elif build_system == "python":
        build_cmds = """    python -m build"""
        install_cmds = """    python -m installer --destdir=\"$pkgdir\" dist/*.whl"""
    else:
        build_cmds = """    make"""
        install_cmds = """    make DESTDIR=\"$pkgdir\" install"""

    pkgbuild = f"""# Maintainer: PkgForge <noreply@pkgforge.app>

pkgname={name}
pkgver={version}
pkgrel=1
pkgdesc='{description}'
arch=('x86_64')
url='{repo_url}'
license=('GPL-3.0-or-later')
depends=()
makedepends=('git' '{'cmake' if build_system == 'cmake' else ''}' '{'meson' if build_system == 'meson' else ''}' '{'rust' if build_system == 'cargo' else ''}')

source=($url/archive/v$pkgver.tar.gz)
sha256sums=('SKIP')

prepare() {{
    cd \"$pkgname-$pkgver\" || cd \"$srcdir/$pkgname-$pkgver\"

    # Prepare step
}}

build() {{
    cd \"$pkgname-$pkgver\" || cd \"$srcdir/$pkgname-$pkgver\"

{build_cmds}
}}

package() {{
    cd \"$pkgname-$pkgver\" || cd \"$srcdir/$pkgname-$pkgver\"

{install_cmds}
}}
"""

    return pkgbuild
