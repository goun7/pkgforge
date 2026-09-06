"""PkgForge — Headless Command Line Interface (CLI).

Provides full headless operation without Qt GUI for package conversion, URL downloading,
lifecycle management (list, remove, rollback), update checks, and GUI invocation.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from config import discover_tools, extract_package_name
from core.downloader import download_package
from core.history_db import HistoryDB
from core.security import is_valid_package_name, safe_run
from core.upstream_tracker import check_all_installed_updates
from i18n import load_setting, tr

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
    elif command == "sbom":
        return _cmd_sbom(args)
    elif command == "attest":
        return _cmd_attest(args)
    elif command == "graph":
        return _cmd_graph(args)
    elif command == "audit":
        return _cmd_audit(args)
    elif command == "scan-image":
        return _cmd_scan_image(args)
    elif command == "from-source":
        return _cmd_from_source(args)
    elif command == "abi-check":
        return _cmd_abi_check(args)
    elif command == "health":
        return _cmd_health(args)
    elif command == "doctor":
        return _cmd_doctor(args)
    elif command == "signing-setup":
        return _cmd_signing_setup(args)
    elif command == "serve-api":
        return _cmd_serve_api(args)
    elif command == "wrapped":
        return _cmd_wrapped(args)
    elif command == "snapshot-cleanup":
        return _cmd_snapshot_cleanup(args)
    elif command == "quality":
        return _cmd_quality(args)
    elif command == "publish":
        return _cmd_publish(args)
    elif command == "verify-rollback":
        return _cmd_verify_rollback(args)
    elif command == "plugin":
        return _cmd_plugin(args)
    elif command == "delta":
        return _cmd_delta(args)
    elif command == "completion":
        return _cmd_completion(args)
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
    if target.startswith(("http://", "https://")):
        print(tr("cli.downloading_url").format(target=target))
        try:
            use_delta = getattr(args, "delta", False)
            if use_delta:
                from config import create_temp_dir
                from core.delta_updater import download_with_delta, find_local_previous
                # Try to find a previous local version for delta
                pkg_name_guess = extract_package_name(target)
                old_pkg = find_local_previous(pkg_name_guess)
                tmp = create_temp_dir()
                dest = tmp / Path(target).name
                file_path, used_delta = download_with_delta(
                    target, dest, old_pkg,
                    require_https=not load_setting("allow_insecure_http", False),
                    allow_private_hosts=bool(load_setting("allow_private_hosts", False)),
                )
                if used_delta:
                    print(tr("cli.download_complete").format(name=file_path.name) + " (delta)")
                else:
                    print(tr("cli.download_complete").format(name=file_path.name))
            else:
                file_path = download_package(
                    target, require_https=not load_setting("allow_insecure_http", False),
                    allow_private_hosts=bool(load_setting("allow_private_hosts", False)),
                    response_info=http_info,
                )
                print(tr("cli.download_complete").format(name=file_path.name))
        except Exception as exc:  # noqa: BLE001
            print(tr("cli.download_error").format(error=str(exc)))
            return 1
    else:
        from core.workspace import Workspace
        workspace = Workspace()
        file_path = workspace.resolve_path(target)
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
        print(tr("cli.auto_001"))
        ok, oci_msg, oci_path = build_oci_image(Path(pkg_path), tools, tag=oci_tag)
        if ok:
            print(f"✅ {oci_msg}")
            if oci_path:
                print(tr("cli.auto_002").format(oci_path))
        else:
            print(f"❌ {oci_msg}")
            return 1
        # Record and exit
        db = HistoryDB()
        db.add_record(
            package_name=extract_package_name(file_path.name),
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
        print(tr("cli.auto_003"))
        vr = verify_reproducible(Path(pkg_path), tools)
        print(f"  {vr.detail}")
        if vr.verified:
            print(tr("cli.auto_004"))
        else:
            print(tr("cli.auto_005"))
        # Continue to install even if verification fails (informational)

    # Compatibility grade + "what will change" preview (best-effort, never fatal)
    try:
        from core.compatibility_checker import run_compatibility_checks
        from core.package_analyzer import analyze_package

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
        print(tr("cli.auto_compat_preview_skipped").format(exc=exc), file=sys.stderr)
        log.warning("Uyumluluk önizleme hatası", exc_info=True)

    # Smart dependency resolution (--resolve-deps)
    if getattr(args, "resolve_deps", False):
        from core.dep_resolver import resolve_dependencies
        print(tr("cli.auto_006"))
        try:
            from core.package_analyzer import analyze_package as _ap
            _meta = _ap(file_path, tools)
            resolve_report = resolve_dependencies(_meta.depends)
            print(resolve_report.summary())
            if not resolve_report.all_resolved:
                aur_pkgs = [d.aur_package or d.name for d in resolve_report.deps if not d.resolved and d.source != "not_found"]
                if aur_pkgs:
                    print(tr("cli.auto_167").format(aur_pkgs=', '.join(aur_pkgs)))
        except Exception as exc:
            print(tr("cli.auto_dep_resolve_skipped").format(exc=exc), file=sys.stderr)
            log.warning("Bağımlılık çözümleme hatası", exc_info=True)

    # Generate SLSA provenance record
    from core.provenance import create_provenance, save_provenance
    from core.security import sha256_hash
    prov = create_provenance(
        source_file=file_path,
        source_url=target if target.startswith("http") else "",
        source_sha256=http_info.get("source_sha256", conv_result.message.split("SHA-256: ")[1][:16] if "SHA-256:" in conv_result.message else ""),
        output_file=Path(pkg_path),
        output_sha256=sha256_hash(Path(pkg_path)) if Path(pkg_path).exists() else "",
        package_name=extract_package_name(file_path.name),
        package_type="deb" if is_deb else "rpm",
    )
    prov_path = save_provenance(prov, Path(pkg_path).parent / f"{Path(pkg_path).name}.provenance.json")
    print(f"📋 Provenance: {prov_path.name}")

    # Auto-sign if requested
    if getattr(args, "sign", False):
        from core.package_signing import sign_package
        sign_key = Path(args.sign_key).resolve() if getattr(args, "sign_key", None) else None
        print(tr("cli.auto_007").format(Path(pkg_path).name))
        sign_ok, sign_msg = sign_package(Path(pkg_path), sign_key)
        if sign_ok:
            print(f"✅ {sign_msg}")
        else:
            print(tr("cli.auto_008").format(sign_msg))

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
            if sys.stdin.isatty():
                print(tr("cli.confirm_install").format(name=pkg_path.name))
                try:
                    answer = input("[y/N] ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    answer = ""
                confirmed = answer in ("y", "yes", "e", "evet")
            else:
                # Non-interactive mode: skip install without --yes
                print(tr("cli.dry_run_note"))
                confirmed = False

        if confirmed:
            print(tr("cli.installing_pkg").format(name=pkg_path.name))
            from core.privileged import (
                find_privileged_helper,
                privileged_install_pkg_argv,
                privileged_setup_hint,
            )
            hint = privileged_setup_hint()
            if hint:
                print(f"  💡 {hint}")
            # Snapshot + kurulum TEK pkexec diyalogunda (helper --snapshot).
            # Eski akis ham `pkexec pacman` cagiriyordu: policy eslesmez,
            # dogrulama katmani yoktu, snapshot hic alinmiyordu.
            # NOT: konsolide helper kullanilir (install_helper.sh degil);
            # boylece basiz (PyQt6'siz) CLI calisir.
            snap_args: list[str] = []
            try:
                from core.snapshot_manager import detect_backend, snapshot_name
                if load_setting("snapshot", True) and detect_backend() != "none":
                    snap_args = ["--snapshot", snapshot_name(extract_package_name(file_path.name))]
            except Exception:  # noqa: BLE001
                snap_args = []
            pkexec = tools.pkexec or "pkexec"

            helper = find_privileged_helper()
            if helper.is_file():
                argv = privileged_install_pkg_argv(pkexec, str(pkg_path),
                                                   snapshot=snap_args[1] if snap_args else "")
            else:
                pacman = tools.pacman or "pacman"
                argv = [pkexec, pacman, "-U", "--noconfirm", "--", str(pkg_path)]
            res = safe_run(argv, timeout=600)
            if res.returncode == 0:
                print(tr("cli.install_success").format(name=pkg_path.name))
                install_status = "installed"
                for _line in res.stdout.splitlines():
                    if _line.strip().startswith("snapshot-ok:"):
                        print(tr("cli.auto_009").format(_line.strip().split('snapshot-ok:', 1)[1].strip()))
                        break
            else:
                print(tr("cli.install_failed").format(error=res.stderr))
                install_status = "install_failed"
        else:
            print(tr("cli.install_cancelled"))

    db.add_record(
        package_name=extract_package_name(file_path.name),
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

    # Helper uzerinden kurulum: policy eslesmesi + arguman dogrulamasi.
    # Eski akis ham `pkexec pacman` idi (genel fallback = ayri parola).
    from core.privileged import find_privileged_helper, privileged_install_pkg_argv
    helper = find_privileged_helper()
    if helper.is_file():
        argv = privileged_install_pkg_argv(pkexec, str(target_backup))
    else:
        pacman = tools.pacman or "pacman"
        argv = [pkexec, pacman, "-U", "--noconfirm", "--", str(target_backup)]
    res = safe_run(argv, timeout=600)
    if res.returncode == 0:
        print(tr("cli.rollback_success").format(name=pkg_name))
        return 0
    else:
        print(tr("cli.rollback_failed").format(error=res.stderr))
        return 1


def _cmd_check_updates(args: argparse.Namespace) -> int:
    """Handle `pkgforge check-updates`."""
    import time as _time

    watch_mode = getattr(args, "watch", False)
    interval = getattr(args, "interval", 300)

    if watch_mode:
        print(tr("cli.auto_010").format(interval))
        print(tr("cli.auto_011"))

    while True:
        print(tr("cli.checking_updates") + "\n")
        results = check_all_installed_updates()

        if not results:
            print(tr("cli.no_url_pkgs"))
            if not watch_mode:
                return 0
        else:
            updates_found = [r for r in results if r.has_update]
            for r in results:
                status_icon = "🟢" if r.has_update else "⚪"
                print(f"  {status_icon} {r.package_name:<20} | {r.detail}")

            if updates_found:
                print(tr("cli.auto_012").format(len(updates_found)))
                for r in updates_found:
                    print(f"     → {r.package_name}: {r.detail}")

        if not watch_mode:
            return 0

        print(f"\n  ⏳ {interval}s sonra tekrar kontrol edilecek...")
        try:
            _time.sleep(interval)
        except KeyboardInterrupt:
            print(tr("cli.auto_013"))
            return 0


def _cmd_flatpak_export(args: argparse.Namespace) -> int:
    """Handle `pkgforge flatpak-export`."""
    from core.flatpak_converter import (
        flatpak_to_deb,
        is_flatpak_available,
        list_installed_apps,
    )

    if not is_flatpak_available():
        print(tr("cli.auto_014"))
        return 1

    # --list: show installed apps
    if getattr(args, "list", False):
        apps = list_installed_apps()
        if not apps:
            print(tr("cli.auto_015"))
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
        print(tr("cli.auto_016"))
        print(tr("cli.auto_017"))
        return 1

    branch = getattr(args, "branch", "stable")
    out_dir = Path(args.output_dir).resolve() if args.output_dir else Path.cwd()

    print(tr("cli.auto_018").format(app_id, branch))
    ok, msg, deb_path = flatpak_to_deb(app_id, out_dir, branch)

    if ok:
        print(f"✅ {msg}")
        print(tr("cli.auto_019").format(deb_path))
    else:
        print(f"❌ {msg}")
        return 1

    return 0


def _cmd_provenance(args: argparse.Namespace) -> int:
    """Handle `pkgforge provenance <package>`."""
    from core.provenance import find_provenance, load_provenance, verify_provenance

    pkg_path = Path(args.package).resolve()
    if not pkg_path.is_file():
        print(tr("cli.auto_020").format(pkg_path))
        return 1

    prov_path = find_provenance(pkg_path)
    if not prov_path:
        # Try looking for .provenance.json next to the package
        print(tr("cli.auto_021").format(pkg_path.name))
        print(tr("cli.auto_022"))
        return 1

    prov = load_provenance(prov_path)
    if not prov:
        print(tr("cli.auto_023").format(prov_path))
        return 1

    print(tr("cli.auto_024").format(pkg_path.name))
    print(tr("cli.auto_025").format(prov.tool_name, prov.tool_version))
    print(f"  Build ID:      {prov.build_id}")
    print(f"  Kaynak:        {prov.source_file}")
    if prov.source_url:
        print(f"  Kaynak URL:    {prov.source_url}")
    print(f"  Kaynak SHA-256:{prov.source_sha256[:32]}…" if prov.source_sha256 else "  Kaynak SHA-256: (yok)")
    print(tr("cli.auto_026").format(prov.output_file))
    print(f"  Çıktı SHA-256: {prov.output_sha256[:32]}…" if prov.output_sha256 else "  Çıktı SHA-256: (yok)")
    print(tr("cli.auto_027").format(prov.build_timestamp))
    print(f"  Build Host:    {prov.build_host}")
    print(f"  Build OS:      {prov.build_os}")
    print(f"  Paket:         {prov.package_name} {prov.package_version}")
    print(f"  Mimari:        {prov.package_arch}")
    print()
    print(f"  🔒 ClamAV:     {prov.clamav_result}")
    print(f"  💣 Bomb Check: {prov.decompression_bomb_result}")
    print(tr("cli.auto_028").format('Geçerli' if prov.signature_valid else 'Yok/Geçersiz'))
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
    from core.appimage_converter import appimage_to_deb, is_appimage_available

    if not is_appimage_available():
        print(tr("cli.auto_029"))
        return 1

    appimage_path = Path(args.appimage).resolve()
    if not appimage_path.is_file():
        print(tr("cli.auto_030").format(appimage_path))
        return 1

    out_dir = Path(args.output_dir).resolve() if args.output_dir else Path.cwd()

    print(tr("cli.auto_031").format(appimage_path.name))
    ok, msg, deb_path = appimage_to_deb(appimage_path, out_dir)

    if ok:
        print(f"✅ {msg}")
        print(tr("cli.auto_019").format(deb_path))
    else:
        print(f"❌ {msg}")
        return 1

    return 0


def _cmd_rpm_to_deb(args: argparse.Namespace) -> int:
    """Handle `pkgforge rpm-to-deb`."""
    from core.rpm_to_deb_converter import is_rpm_to_deb_available, rpm_to_deb

    if not is_rpm_to_deb_available():
        print(tr("cli.auto_032"))
        return 1

    rpm_path = Path(args.rpm).resolve()
    if not rpm_path.is_file():
        print(tr("cli.auto_030").format(rpm_path))
        return 1

    out_dir = Path(args.output_dir).resolve() if args.output_dir else Path.cwd()

    print(tr("cli.auto_033").format(rpm_path.name))
    ok, msg, deb_path = rpm_to_deb(rpm_path, out_dir)

    if ok:
        print(f"✅ {msg}")
        print(tr("cli.auto_019").format(deb_path))
    else:
        print(f"❌ {msg}")
        return 1

    return 0


def _cmd_benchmark(args: argparse.Namespace) -> int:
    """Handle `pkgforge benchmark`."""
    from core.benchmark import run_benchmarks

    test_file = Path(args.bench_file).resolve() if args.bench_file else None
    quick = getattr(args, "quick", False)

    print(tr("cli.auto_034"))
    report = run_benchmarks(test_file=test_file, quick=quick)
    print(report.summary())
    print()

    rc = 0
    if report.passed:
        print(tr("cli.auto_035"))
    else:
        print(tr("cli.auto_036"))
        rc = 1

    # F5.26: perf butcesi — baseline kaydet / karsilastir.
    save_path = getattr(args, "save_baseline", None)
    if save_path:
        from core.perf_budget import save_baseline

        out = save_baseline(report, save_path)
        print(f"💾 Baseline kaydedildi: {out}")
    baseline_path = getattr(args, "baseline", None)
    if baseline_path:
        from core.perf_budget import compare, load_baseline

        baseline = load_baseline(baseline_path)
        if not baseline:
            print(tr("cli.auto_037").format(baseline_path))
        else:
            res = compare(report, baseline)
            print(tr("cli.auto_038").format(res['compared'], int(res['threshold'] * 100)))
            for reg in res["regressions"]:
                print(f"  ❌ {reg['name']}: {reg['baseline_ms']}ms →"
                      f" {reg['current_ms']}ms (%{reg['delta_pct']:+.1f})")
            for imp in res["improvements"]:
                print(f"  🚀 {imp['name']}: {imp['baseline_ms']}ms →"
                      f" {imp['current_ms']}ms (%{imp['delta_pct']:+.1f})")
            if not res["ok"]:
                print(tr("cli.auto_039").format(len(res['regressions'])))
                rc = 1
            else:
                print(tr("cli.auto_040"))
    return rc


def _cmd_sign(args: argparse.Namespace) -> int:
    """Handle `pkgforge sign <package>`."""
    from core.package_signing import sign_package

    pkg_path = Path(args.package).resolve()
    if not pkg_path.is_file():
        print(tr("cli.auto_020").format(pkg_path))
        return 1

    key_path = Path(args.key).resolve() if args.key else None

    print(tr("cli.auto_041").format(pkg_path.name))
    ok, msg = sign_package(pkg_path, key_path)

    if ok:
        print(f"✅ {msg}")
    else:
        print(f"❌ {msg}")
        return 1

    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    """Handle `pkgforge verify <package>`."""
    pkg_path = Path(args.package).resolve()
    if not pkg_path.is_file():
        print(tr("cli.auto_020").format(pkg_path))
        return 1

    # Sigstore verification mode
    if getattr(args, "sigstore", False):
        from core.sigstore import verify_with_sigstore
        print(tr("cli.auto_042").format(pkg_path.name))
        result = verify_with_sigstore(pkg_path)
        print(result.summary())
        return 0 if result.success else 1

    # Default: GPG verification
    from core.package_signing import verify_signature
    print(tr("cli.auto_043").format(pkg_path.name))
    info = verify_signature(pkg_path)

    print(tr("cli.auto_044").format('✅ Geçerli' if info.valid else '❌ Geçersiz/Yok'))
    if info.signer:
        print(tr("cli.auto_045").format(info.signer))
    if info.key_id:
        print(f"  Key ID:       {info.key_id}")
    if info.key_fingerprint:
        print(f"  Fingerprint:  {info.key_fingerprint}")
    print(f"  Detay:        {info.detail}")

    return 0 if info.valid else 1


def _cmd_sbom(args: argparse.Namespace) -> int:
    """Handle `pkgforge sbom`."""
    from core.sbom import diff_sboms, generate_sbom, save_sbom, save_sbom_diff

    # SBOM diff mode
    diff_pair = getattr(args, "diff", None)
    if diff_pair:
        old_path = Path(diff_pair[0]).resolve()
        new_path = Path(diff_pair[1]).resolve()
        for p in (old_path, new_path):
            if not p.is_file():
                print(tr("cli.auto_020").format(p))
                return 1

        tools = discover_tools()
        no_hashes = getattr(args, "no_hashes", False)

        print(tr("cli.auto_046").format(old_path.name))
        old_sbom = generate_sbom(old_path, tools, include_hashes=not no_hashes)
        print(tr("cli.auto_047").format(new_path.name))
        new_sbom = generate_sbom(new_path, tools, include_hashes=not no_hashes)

        diff = diff_sboms(old_sbom, new_sbom)

        out_dir = Path(args.output_dir).resolve() if args.output_dir else Path.cwd()
        diff_path = out_dir / f"{old_path.stem}-diff-{new_path.stem}.json"
        save_sbom_diff(diff, diff_path)

        print("\n📊 SBOM Diff:\n")
        print(diff.summary())
        print(tr("cli.auto_048").format(diff_path))
        return 0

    # Single SBOM generation
    if not args.package:
        print(tr("cli.auto_049"))
        return 1

    pkg_path = Path(args.package).resolve()
    if not pkg_path.is_file():
        print(tr("cli.auto_020").format(pkg_path))
        return 1

    tools = discover_tools()
    no_hashes = getattr(args, "no_hashes", False)
    out_dir = Path(args.output_dir).resolve() if args.output_dir else pkg_path.parent

    print(tr("cli.auto_050").format(pkg_path.name))
    sbom = generate_sbom(pkg_path, tools, include_hashes=not no_hashes)

    # Save to file
    sbom_path = out_dir / f"{pkg_path.name}.spdx.json"
    save_sbom(sbom, sbom_path)

    # Print summary
    print(sbom.summary())
    print(tr("cli.auto_051").format(sbom_path))

    return 0


def _cmd_attest(args: argparse.Namespace) -> int:
    """Handle `pkgforge attest`."""
    from core.provenance import (
        create_attestation,
        find_provenance,
        load_provenance,
        save_attestation,
    )

    pkg_path = Path(args.package).resolve()
    if not pkg_path.is_file():
        print(tr("cli.auto_020").format(pkg_path))
        return 1

    # Find existing provenance record
    prov_path = find_provenance(pkg_path)
    if not prov_path:
        print(tr("cli.auto_052").format(pkg_path.name))
        print(tr("cli.auto_053"))
        return 1

    prov = load_provenance(prov_path)
    if not prov:
        print(tr("cli.auto_054").format(prov_path))
        return 1

    # Create in-toto attestation
    signer_key = getattr(args, "key", "") or ""
    attestation = create_attestation(prov, signer_key=signer_key)

    # Save attestation
    att_path = save_attestation(attestation, pkg_path.parent / f"{pkg_path.name}.attestation.json")

    # Summary
    print(tr("cli.auto_055"))
    print(f"  Statement:  {attestation._type}")
    print(f"  Predicate:  {attestation.predicate_type}")
    print(f"  Subject:    {attestation.subject[0]['name'] if attestation.subject else '(yok)'}")
    print(f"  Builder:    {attestation.predicate.get('builder', {}).get('id', '?')}")
    print(f"  Build ID:   {attestation.predicate.get('metadata', {}).get('buildInvocationId', '?')}")
    print(f"  Security:   ClamAV={attestation.predicate.get('security', {}).get('clamav', '?')}")
    print(f"  Dosya:      {att_path}")

    return 0


def _cmd_graph(args: argparse.Namespace) -> int:
    """Handle `pkgforge graph`."""
    from core.dep_graph import build_dep_graph, build_file_dep_graph

    pkg_name = args.package
    show_files = getattr(args, "files", False)
    fmt = getattr(args, "format", "ascii")

    def _resolve_pkg_file(name: str) -> Path | None:
        """Accept a direct file path, or search the pacman package cache."""
        direct = Path(name).expanduser()
        if direct.is_file():
            return direct
        import glob as globmod
        for pattern in [f"/var/cache/pacman/pkg/{name}*.pkg.tar.zst",
                        f"/var/cache/pacman/pkg/{name}*.pkg.tar.xz"]:
            matches = globmod.glob(pattern)
            if matches:
                return Path(matches[0])
        return None

    pkg_file = _resolve_pkg_file(pkg_name)
    if not pkg_file:
        print(tr("cli.auto_056").format(pkg_name))
        print(tr("cli.auto_057"))
        return 1

    if show_files:
        graph = build_file_dep_graph(pkg_file)
    else:
        graph = build_dep_graph(pkg_file)
        if not graph.nodes:
            print(tr("cli.auto_058").format(pkg_name))
            return 1

    stats = graph.stats()
    print(tr("cli.auto_059").format(graph.root))
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

    print("\n🔍 PkgForge Audit Trail\n")
    print(tr("cli.auto_060").format(len(records)))

    if not records:
        print(tr("cli.auto_061"))
        return 0

    # Summary
    status_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    for r in records:
        status_counts[r.status] = status_counts.get(r.status, 0) + 1
        type_counts[r.package_type] = type_counts.get(r.package_type, 0) + 1

    print(tr("cli.auto_062"))
    for status, count in sorted(status_counts.items()):
        icon = {"installed": "✅", "converted": "📦", "install_failed": "❌", "oci_built": "🐳"}.get(status, "•")
        print(f"   {icon} {status}: {count}")
    print()

    print(tr("cli.auto_063"))
    for ptype, count in sorted(type_counts.items()):
        print(f"   • {ptype}: {count}")
    print()

    # Integrity check
    print(tr("cli.auto_064"))
    integrity_issues = 0
    for r in records:
        # Check if output package still exists
        if r.output_pkg and not Path(r.output_pkg).exists():
            print(tr("cli.auto_065").format(r.package_name, r.output_pkg))
            integrity_issues += 1
        # Check if backup still exists
        if r.backup_pkg and not Path(r.backup_pkg).exists():
            print(tr("cli.auto_066").format(r.package_name, r.backup_pkg))
            integrity_issues += 1
        # Check if source URL is recorded but no http headers
        if r.source_url and not r.http_etag and not r.http_last_modified:
            pass  # Not necessarily an issue, just informational
    if integrity_issues == 0:
        print(tr("cli.auto_067"))
    else:
        print(tr("cli.auto_068").format(integrity_issues))
    print()

    # Anomaly detection
    print("🔎 Anomali Tespiti:")
    anomalies = 0
    # Check for duplicate packages
    name_counts: dict[str, int] = {}
    for r in records:
        name_counts[r.package_name] = name_counts.get(r.package_name, 0) + 1
    for name, count in name_counts.items():
        if count > 3:
            print(tr("cli.auto_069").format(name, count))
            anomalies += 1
    # Check for rapid-fire installs (potential abuse)
    recent_installed = [r for r in records if r.status == "installed"][:5]
    if len(recent_installed) >= 5:
        print(tr("cli.auto_070"))
        anomalies += 1
    # Check for failed packages without retry
    failed_names = set()
    for r in records:
        if r.status == "install_failed":
            failed_names.add(r.package_name)
    for name in failed_names:
        installed_count = sum(1 for r in records if r.package_name == name and r.status == "installed")
        if installed_count == 0:
            print(tr("cli.auto_071").format(name))
            anomalies += 1
    if anomalies == 0:
        print("   ✅ Anomali tespit edilmedi")
    print()

    # Provenance verification
    print(tr("cli.auto_072"))
    provenance_count = 0
    for r in records:
        if r.output_pkg:
            prov_file = Path(r.output_pkg).parent / f"{Path(r.output_pkg).name}.provenance.json"
            if prov_file.exists():
                provenance_count += 1
    if provenance_count > 0:
        print(tr("cli.auto_073").format(provenance_count, len(records)))
    else:
        print(tr("cli.auto_074"))
    print()

    # Detailed trail
    print(tr("cli.auto_075"))
    print(f"{'ID':<4} {'Tarih':<20} {'Paket':<20} {'Tür':<6} {'Durum':<12} {'Orijinal Dosya'}")
    print("-" * 90)
    for r in records:
        print(f"{r.id:<4} {r.timestamp:<20} {r.package_name:<20} {r.package_type:<6} {r.status:<12} {r.original_file}")

    return 0


def _cmd_scan_image(args: argparse.Namespace) -> int:
    """Handle `pkgforge scan-image` (core.scan_oci_image tek kaynaktan)."""
    from core.malware_scanner import scan_oci_image

    image_path = Path(args.image).resolve()
    if not image_path.is_file():
        print(tr("cli.auto_076").format(image_path))
        return 1

    print(tr("cli.auto_077").format(image_path.name))
    result = scan_oci_image(image_path)
    tools_avail = result["tools"]

    if not any(tools_avail.values()):
        print(tr("cli.auto_078"))
        print("   Kurulum: sudo pacman -S trivy")
        print("   veya: sudo pacman -S grype")
        print("   veya: sudo pacman -S clamav")
        return 1

    status = result["status"]
    findings = result["findings"]
    errors = result["errors"]

    def _print_tool(tool: str, label: str, clean_msg: str, unit: str) -> None:
        st = status.get(tool)
        if st == "clean":
            print(f"  ✅ {clean_msg}")
        elif st == "findings":
            tf = [f for f in findings if f["tool"] == tool]
            print(tr("cli.auto_079").format(label, len(tf), unit))
            for f in tf[:10]:
                print(f"      {f['line']}")
        elif st == "error":
            print(tr("cli.auto_080").format(label, errors.get(tool, '')))

    if tools_avail["trivy"]:
        print(tr("cli.auto_081"))
        _print_tool("trivy", "Trivy", "Trivy: Kritik CVE bulunamadı", "satır")
    if tools_avail["grype"]:
        print(tr("cli.auto_082"))
        _print_tool("grype", "Grype", "Grype: Yüksek-seviye açık bulunamadı", "adet")
    if tools_avail["clamscan"]:
        print(tr("cli.auto_083"))
        st = status.get("clamscan")
        if st == "clean":
            print("  ✅ ClamAV: Temiz")
        elif st == "findings":
            cf = [f for f in findings if f["tool"] == "clamscan"]
            body = "\n".join(f["line"] for f in cf)
            print(tr("cli.auto_168").format(body=body))
        elif st == "error":
            print(tr("cli.auto_084").format(errors.get('clamscan', '')))

    print()
    if result["clean"]:
        print(tr("cli.auto_085"))
        return 0
    print(tr("cli.auto_086"))
    return 1


def _cmd_from_source(args: argparse.Namespace) -> int:
    """Handle `pkgforge from-source`."""
    from core.from_source import generate_pkgbuild_from_source

    repo_url = args.repo_url
    out_dir = Path(args.output_dir).resolve() if args.output_dir else Path.cwd()

    print(tr("cli.auto_087").format(repo_url))

    import tempfile
    with tempfile.TemporaryDirectory(prefix="pkgforge_src_") as tmpdir:
        tmp = Path(tmpdir)

        # 1. Clone repo
        print(tr("cli.auto_088"))
        res = safe_run(["git", "clone", "--depth=1", repo_url, str(tmp / "repo")], timeout=120)
        if res.returncode != 0:
            print(tr("cli.auto_089").format(res.stderr[:200]))
            return 1

        repo_dir = tmp / "repo"

        # 2. Detect project type
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
        pkgbuild_content = generate_pkgbuild_from_source(
            proj_name, repo_url, build_system, repo_dir
        )

        # 4. Write PKGBUILD
        output_pkgbuild = out_dir / f"PKGBUILD-{proj_name}"
        output_pkgbuild.write_text(pkgbuild_content, encoding="utf-8")
        print(tr("cli.auto_090").format(output_pkgbuild))

        # Show preview
        print(tr("cli.auto_091"))
        print("-" * 60)
        for i, line in enumerate(pkgbuild_content.splitlines()[:30]):
            print(f"  {line}")
        if len(pkgbuild_content.splitlines()) > 30:
            print(tr("cli.auto_092").format(len(pkgbuild_content.splitlines()) - 30))
        print("-" * 60)

        print(tr("cli.auto_093").format(out_dir))

    return 0




def _cmd_abi_check(args: argparse.Namespace) -> int:
    """Handle `pkgforge abi-check`."""
    from core.abi_scanner import check_abi_compatibility

    pkg_path = Path(args.package).resolve()
    if not pkg_path.is_file():
        print(tr("cli.auto_020").format(pkg_path))
        return 1

    print(tr("cli.auto_094").format(pkg_path.name))
    report = check_abi_compatibility(pkg_path)
    print(report.summary())

    if report.passed:
        print(tr("cli.auto_095"))
    else:
        print(f"\n⚠️  {report.error_count} uyumsuzluk tespit edildi.")
        print(tr("cli.auto_096"))
        return 1

    return 0


def _cmd_health(args: argparse.Namespace) -> int:
    """Handle `pkgforge health`."""
    db = HistoryDB()
    records = db.get_history(limit=1000)
    stats = db.get_usage_stats()

    print(tr("cli.auto_097"))

    if not records:
        print(tr("cli.auto_098"))
        print(tr("cli.auto_099"))
        return 0

    # Status distribution
    status_counts = stats["by_status"]
    type_counts = stats["by_type"]
    url_count = stats["url_count"]

    total = stats["total"]
    installed = status_counts.get("installed", 0)
    converted = status_counts.get("converted", 0)
    failed = status_counts.get("install_failed", 0)
    success_rate = ((installed + converted) / total * 100) if total > 0 else 0

    print(tr("cli.auto_100"))
    print(tr("cli.auto_101").format(total))
    print(tr("cli.auto_182").format(installed=installed, pct=installed/total*100) if total else "")
    print(tr("cli.auto_183").format(converted=converted, pct=converted/total*100) if total else "")
    print(tr("cli.auto_184").format(failed=failed, pct=failed/total*100) if total else "")
    print(tr("cli.auto_102").format(success_rate))
    print(tr("cli.auto_169").format(url_count=url_count))
    print()

    # Type breakdown
    print(tr("cli.auto_103"))
    for ptype, count in sorted(type_counts.items()):
        pct = count / total * 100 if total else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"   {ptype:<8} {bar} {count} ({pct:.0f}%)")
    print()

    # Architecture breakdown
    arch_counts = stats.get("by_arch", {})
    if arch_counts:
        print(tr("cli.auto_104"))
        for arch, count in sorted(arch_counts.items(), key=lambda x: -x[1]):
            pct = count / total * 100 if total else 0
            print(f"   {arch:<12} {count} ({pct:.0f}%)")
        print()

    # Output size
    avg_size = stats.get("avg_output_size_mb", 0.0)
    if avg_size > 0:
        print(tr("cli.auto_105").format(avg_size))
        print()

    # Recent activity
    if records:
        print(tr("cli.auto_170"))
        print(tr("cli.auto_106").format(records[-1].timestamp))
        print(tr("cli.auto_107").format(records[0].timestamp))
        print()

    # Failed packages (error patterns)
    if failed > 0:
        print(tr("cli.auto_108"))
        for r in records:
            if r.status == "install_failed":
                print(f"   ❌ {r.package_name} ({r.package_type}) — {r.original_file}")
        print()

    # Most-converted packages
    name_counts: dict[str, int] = {}
    for r in records:
        name_counts[r.package_name] = name_counts.get(r.package_name, 0) + 1
    top_packages = sorted(name_counts.items(), key=lambda x: -x[1])[:5]
    if top_packages and top_packages[0][1] > 1:
        print(tr("cli.auto_109"))
        for name, count in top_packages:
            if count > 1:
                print(tr("cli.auto_171").format(name=name, count=count))
        print()

    # Health score
    if success_rate >= 90:
        health = tr("cli.health_excellent")
    elif success_rate >= 70:
        health = tr("cli.health_good")
    else:
        health = tr("cli.health_poor")

    print(tr("cli.auto_110").format(health, success_rate))

    return 0


def _cmd_serve_api(args: argparse.Namespace) -> int:
    """Handle `pkgforge serve-api` (Tur-55 C10)."""
    try:
        from core.api_v2 import export_openapi
        from core.api_v2 import run as _run_api
    except ImportError as exc:
        print(f"❌ REST API bagimlilklari kurulu degil: {exc}", file=sys.stderr)
        print("   Kurulum: pip install 'pkgforge[api]'", file=sys.stderr)
        return 2

    export_target = getattr(args, "export_openapi", None)
    if export_target:
        out = export_openapi(export_target)
        print(f"📦 OpenAPI → {out}")
        return 0

    host = getattr(args, "host", "127.0.0.1") or "127.0.0.1"
    port = int(getattr(args, "port", 8899) or 8899)
    print(f"🚀 PkgForge API v2: http://{host}:{port}")
    print(f"   • Docs:   http://{host}:{port}/docs")
    print(f"   • Schema: http://{host}:{port}/api/v2/openapi.json")
    _run_api(host=host, port=port)
    return 0


def _cmd_signing_setup(args: argparse.Namespace) -> int:
    """Handle `pkgforge signing-setup` (Tur-55 B7)."""
    import json as _json
    from pathlib import Path

    from core.signing_wizard import render_text, run_wizard

    method = getattr(args, "method", "auto") or "auto"
    save_path = getattr(args, "save_config", None)
    save_to = Path(save_path) if save_path else None

    result = run_wizard(method=method, persist_to=save_to)
    print(render_text(result))
    if save_to is not None:
        print()
        print("📦 JSON config:")
        print(_json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    """Handle `pkgforge doctor` (F5.22) — Tur-55 A2: --tools/--json."""
    import json as _json

    from core.doctor import run_doctor

    if getattr(args, "json", False):
        # Salt JSON çıktı: scriptler / dashboard entegrasyonu için.
        print(_json.dumps(run_doctor(), ensure_ascii=False, indent=2,
                          default=str))
        return 0

    if getattr(args, "tools", False):
        # Salt araç denetimi: kurulum betiği öncesi kuru kontrol.
        r = run_doctor()
        t = r["tools"]
        print(_json.dumps(t, ensure_ascii=False, indent=2))
        if t["missing_required"]:
            print(f"\n❌ Eksik zorunlu: {', '.join(t['missing_required'])}",
                  file=sys.stderr)
            return 2
        print(tr("cli.auto_111"))
        return 0

    def mark(ok: bool) -> str:
        return "✅" if ok else "❌"

    r = run_doctor()
    print(f"🩺 PkgForge Doctor — v{r['version']}")
    print()

    t = r["tools"]
    print(tr("cli.auto_112").format(mark(t['ok'])))
    if t["missing_required"]:
        print(f"   Eksik zorunlu: {', '.join(t['missing_required'])}")
    if t["missing_optional"]:
        print(f"   Eksik opsiyonel: {', '.join(t['missing_optional'])}")
    print(f"   debtap: {mark(t['debtap'])}  pkexec: {mark(t['pkexec'])}"
          f"  distrobox: {mark(t['distrobox'])}")

    k = r["keyring"]
    print(tr("cli.auto_113").format(mark(k['ok']), k.get('detail', '')))

    s = r["storage"]
    print(f"{mark(s['ok'])} Depolama — profil: {s['profile']},"
          f" config: {s['config_dir']}")
    print(f"   history.db: {mark(s['history_db_exists'])}"
          f"  queue.db: {mark(s['queue_db_exists'])}")

    d = r["dbus"]
    print(f"{mark(d['ok'])} D-Bus")

    sc = r["scheduler"]
    print(tr("cli.auto_114").format(mark(sc['ok']), sc.get('tasks', 0)))

    print()
    if r["ok"]:
        print(tr("cli.auto_115"))
        return 0
    print(tr("cli.auto_116"))
    return 1


def _cmd_wrapped(args: argparse.Namespace) -> int:
    """Handle `pkgforge wrapped` (F5.24)."""
    from core.stats_wrapped import build_wrapped

    r = build_wrapped(year=getattr(args, "year", None))
    year = r["year"]
    print(f"🎁 PkgForge {year} Wrapped")
    print()
    if r["total"] == 0:
        print(tr("cli.auto_117").format(year))
        return 0
    print(tr("cli.auto_118").format(r['total']))
    print(tr("cli.auto_119").format(r['success'], r['failed'], r['success_rate']))
    print(tr("cli.auto_120").format(r['distinct_packages']))
    if r["busiest_month"]:
        print(tr("cli.auto_121").format(r['busiest_month']))
    if r["by_type"]:
        types = ", ".join(f"{k}: {v}"
                          for k, v in sorted(r["by_type"].items()))
        print(tr("cli.auto_122").format(types))
    if r["top_packages"]:
        print(tr("cli.auto_123"))
        for i, p in enumerate(r["top_packages"], 1):
            print(f"     {i}. {p['name']} ({p['count']})")
    return 0


def _cmd_snapshot_cleanup(args: argparse.Namespace) -> int:
    """Handle `pkgforge snapshot-cleanup`."""
    from core.privileged import privileged_setup_hint
    from core.snapshot_cleanup import (
        get_cleanup_status,
        install_cleanup_service,
        remove_cleanup_service,
    )

    hint = privileged_setup_hint()
    if hint and (getattr(args, "install", False) or getattr(args, "remove", False)):
        print(f"  💡 {hint}\n")

    if getattr(args, "install", False):
        max_age = getattr(args, "max_age", 7)
        print(tr("cli.auto_124").format(max_age))
        ok, msg = install_cleanup_service(max_age_days=max_age)
        if ok:
            print(msg)
        else:
            print(f"❌ {msg}")
            return 1
        return 0

    elif getattr(args, "remove", False):
        print(tr("cli.auto_125"))
        ok, msg = remove_cleanup_service()
        if ok:
            print(msg)
        else:
            print(f"❌ {msg}")
            return 1
        return 0

    else:
        # Default: show status
        status = get_cleanup_status()
        print("\n🔍 PkgForge Snapshot Cleanup Durumu\n")
        if status["installed"]:
            print(tr("cli.auto_172"))
            print(tr("cli.auto_173_aktif") if status['active'] else tr("cli.auto_173_pasif"))
            if status["next_run"]:
                print(tr("cli.auto_126").format(status['next_run']))
        else:
            print(tr("cli.auto_127"))
            print(tr("cli.auto_128"))

        print("\n  📋 Mevcut snapshot'lar:")
        from core.snapshot_manager import detect_backend, list_snapshots
        backend = detect_backend()
        print(tr("cli.auto_129").format(backend))
        snaps = list_snapshots()
        if snaps:
            for s in snaps:
                print(f"    • {s['name']} ({s.get('date', '?')})")
        else:
            print(tr("cli.auto_130"))
        return 0


def _cmd_quality(args: argparse.Namespace) -> int:
    """Handle `pkgforge quality`."""
    from core.quality_score import score_package

    pkg_path = Path(args.package).resolve()
    if not pkg_path.is_file():
        print(tr("cli.auto_020").format(pkg_path))
        return 1

    tools = discover_tools()
    print(tr("cli.auto_131").format(pkg_path.name))
    report = score_package(pkg_path, tools)
    print(report.summary())
    return 0 if report.passed else 1


def _cmd_publish(args: argparse.Namespace) -> int:
    """Handle `pkgforge publish`."""
    from core.aur_publish import prepare_aur_package, push_to_aur

    pkg_path = Path(args.package).resolve()
    if not pkg_path.is_file():
        print(tr("cli.auto_020").format(pkg_path))
        return 1

    out_dir = Path(args.output_dir).resolve() if args.output_dir else Path.cwd()
    aur_url = getattr(args, "aur_url", None)

    print(tr("cli.auto_132").format(pkg_path.name))
    ok, msg, aur_pkg = prepare_aur_package(pkg_path, out_dir)

    if not ok or not aur_pkg:
        print(f"❌ {msg}")
        return 1

    print(f"✅ {msg}")
    print(f"   PKGBUILD: {aur_pkg.pkgbuild}")
    if aur_pkg.srcinfo.exists():
        print(f"   .SRCINFO: {aur_pkg.srcinfo}")

    if aur_url:
        print(tr("cli.auto_133"))
        ok2, msg2 = push_to_aur(aur_pkg.pkgbuild.parent, aur_url)
        if ok2:
            print(f"✅ {msg2}")
        else:
            print(f"❌ {msg2}")
            return 1
    else:
        print(tr("cli.auto_134"))
        print(f"   pkgforge publish {pkg_path} --aur-url ssh://aur@aur.archlinux.org/{aur_pkg.name}.git")

    return 0


def _cmd_verify_rollback(args: argparse.Namespace) -> int:
    """Handle `pkgforge verify-rollback`."""
    from core.rollback_verify import verify_rollback

    print(tr("cli.auto_135"))
    result = verify_rollback()
    print(result.detail)

    if result.verified:
        print(tr("cli.auto_136"))
    else:
        print(tr("cli.auto_137"))
        return 1

    return 0


def _cmd_plugin(args: argparse.Namespace) -> int:
    """Handle `pkgforge plugin`."""
    from core.plugins import reload_plugins
    from core.plugins.marketplace import (
        fetch_available_plugins,
        install_plugin,
        list_installed_plugins,
        uninstall_plugin,
    )

    action = getattr(args, "plugin_action", None)

    if action == "install":
        name = args.name
        force = getattr(args, "force", False)
        version = getattr(args, "version", "latest")
        # Support name==version syntax
        if "==" in name:
            name, version = name.split("==", 1)
        # F2.3: uzak kod onayi — marketplace kodu yuklenir yuklenmez
        # calistigi icin sessiz kurulum yok; --yes veya acik evet gerekli.
        confirmed = getattr(args, "yes", False)
        if not confirmed:
            if sys.stdin.isatty():
                print(tr("cli.plugin_confirm_remote").format(
                    name=name, url="https://github.com/goun7/pkgforge-plugins"))
                try:
                    answer = input("[y/N] ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    answer = ""
                confirmed = answer in ("y", "yes", "e", "evet")
            else:
                confirmed = False
        if not confirmed:
            print(tr("cli.plugin_need_confirm"))
            return 1
        print(f"📦 Plugin indiriliyor: {name} v{version}")
        try:
            path = install_plugin(name, version=version, force=force)
            print(f"✅ Plugin kuruldu: {path}")
            # Reload plugins to pick up the new one
            reloaded = reload_plugins()
            print(f"🔄 {len(reloaded)} plugin aktif")
        except FileNotFoundError as exc:
            print(f"❌ {exc}")
            return 1
        except (RuntimeError, ValueError) as exc:
            print(tr("cli.auto_138").format(exc))
            return 1

    elif action == "remove":
        name = args.name
        try:
            removed = uninstall_plugin(name)
        except ValueError as exc:
            print(f"❌ {exc}")
            return 1
        if removed:
            print(tr("cli.auto_139").format(name))
            reload_plugins()
        else:
            print(tr("cli.auto_140").format(name))
            return 1

    elif action == "list":
        installed = list_installed_plugins()
        if not installed:
            print(tr("cli.auto_141"))
        else:
            print(tr("cli.auto_174").format(count=len(installed)))
            for p in installed:
                print(f"  • {p['name']} ({p['size']} bytes)")

    elif action == "available":
        print(tr("cli.auto_142"))
        available = fetch_available_plugins()
        if not available:
            print(tr("cli.auto_143"))
        else:
            print(tr("cli.auto_144").format(len(available)))
            for p in available:
                print(f"  • {p['name']} v{p['version']} — {p['description']}")

    elif action == "update":
        from core.plugins.marketplace import update_plugin as _update_plugin
        name = args.name
        print(tr("cli.auto_145").format(name))
        ok, msg, _path = _update_plugin(name)
        if ok:
            print(f"✅ {msg}")
            reload_plugins()
        else:
            print(f"❌ {msg}")
            return 1

    elif action == "audit":
        from core.plugins.marketplace import audit_plugins as _audit_plugins
        print(tr("cli.auto_146"))
        results = _audit_plugins()
        if not results:
            print(tr("cli.auto_175"))
        else:
            for r in results:
                icon = {"ok": "✅", "changed": "⚠️", "unknown": "❓", "error": "❌"}.get(r["status"], "?")
                print(f"  {icon} {r['name']}: {r['message']}")

    else:
        print(tr("cli.auto_147"))
        return 1

    return 0


def _cmd_delta(args: argparse.Namespace) -> int:
    """Handle `pkgforge delta`."""
    from core.delta_updater import (
        disable_auto_update,
        enable_auto_update,
        get_auto_update_status,
    )
    from core.privileged import privileged_setup_hint

    action = getattr(args, "delta_action", None)

    if action == "status":
        status = get_auto_update_status()
        print("\n📊 Delta Auto-Update Durumu:\n")
        print(f"  systemctl:     {'✅' if status.get('systemctl_available') else '❌'}")
        print(f"  Timer kurulu:  {'✅' if status.get('installed') else '❌'}")
        print(f"  Timer aktif:   {'✅' if status.get('active') else '❌'}")
        if status.get("next_run"):
            print(tr("cli.auto_148").format(status['next_run']))

    elif action == "enable":
        hint = privileged_setup_hint()
        if hint:
            print(f"  💡 {hint}")
        ok, msg = enable_auto_update()
        print(f"{'✅' if ok else '❌'} {msg}")
        return 0 if ok else 1

    elif action == "disable":
        ok, msg = disable_auto_update()
        print(f"{'✅' if ok else '❌'} {msg}")
        return 0 if ok else 1

    else:
        print(tr("cli.auto_149"))
        return 1

    return 0


def _cmd_completion(args: argparse.Namespace) -> int:
    """Handle `pkgforge completion`."""
    from core.completion import generate_completion

    shell = args.shell
    try:
        script = generate_completion(shell)
        print(script)
        return 0
    except ValueError as exc:
        print(f"❌ {exc}")
        return 1
