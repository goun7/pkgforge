"""PkgForge — Conversion pipeline orchestrator.

Coordinates all steps (security → analysis → conversion →
compatibility → install → verify → cleanup) in a background
QThread, emitting signals for UI progress updates.
"""

from __future__ import annotations

import logging
import shutil
from enum import IntEnum
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, pyqtSignal, QEventLoop, QTimer

from config import (
    MAX_PACKAGE_SIZE_MB,
    WARN_PACKAGE_SIZE_MB,
    ToolPaths,
    create_temp_dir,
    discover_tools,
)
from core.compatibility_checker import (
    CheckSeverity,
    CompatibilityReport,
    run_compatibility_checks,
)
from core.deb_converter import DebConverter
from core.installer import Installer
from core.package_analyzer import PackageMetadata, analyze_package
from core.rpm_converter import RpmConverter
from core.security import (
    SignatureResult,
    check_path_traversal,
    sha256_hash,
    validate_file_size,
    validate_mime_type,
    verify_deb_signature,
    verify_rpm_signature,
)

log = logging.getLogger(__name__)


class PipelineStep(IntEnum):
    SECURITY = 0
    MALWARE_SCAN = 1
    ANALYSIS = 2
    CONVERSION = 3
    COMPATIBILITY = 4
    INSTALL = 5


STEP_LABELS = {
    PipelineStep.SECURITY: "Güvenlik Kontrolü",
    PipelineStep.MALWARE_SCAN: "Malware Tarama",
    PipelineStep.ANALYSIS: "Paket Analizi",
    PipelineStep.CONVERSION: "Dönüşüm",
    PipelineStep.COMPATIBILITY: "Uyumluluk Testi",
    PipelineStep.INSTALL: "Kurulum",
}


class PipelineResult:
    """Final result of the conversion pipeline."""

    __slots__ = (
        "success", "message", "metadata", "converted_pkg",
        "compatibility", "signature", "sha256", "size_warning",
        "original_file",
    )

    def __init__(self) -> None:
        self.success: bool = False
        self.message: str = ""
        self.metadata: PackageMetadata | None = None
        self.converted_pkg: Path | None = None
        self.compatibility: CompatibilityReport | None = None
        self.signature: SignatureResult | None = None
        self.sha256: str = ""
        self.size_warning: str = ""
        self.original_file: Path | None = None


class ConversionPipeline(QObject):
    """Orchestrates the full package conversion pipeline.

    Run this on a QThread to avoid blocking the UI.

    Signals:
        step_changed(int, str)      – step index, status string
        progress(int)               – 0-100 overall progress
        log_message(str, str)       – message, level (info/warning/error/success)
        compatibility_ready(object) – CompatibilityReport, emitted when user approval is needed
        finished(object)            – PipelineResult
    """

    step_changed = pyqtSignal(int, str)
    progress = pyqtSignal(int)
    log_message = pyqtSignal(str, str)
    compatibility_ready = pyqtSignal(object)
    finished = pyqtSignal(object)
    # Internal: emitted from the UI thread to wake the worker thread that is
    # blocked in _wait_for_decision() once the user approves/dismisses install.
    _decision_signal = pyqtSignal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._tools: ToolPaths = discover_tools()
        self._cancelled = False
        self._temp_dir: Path | None = None
        self._user_approved = False
        self._result = PipelineResult()

        # Decision gate for the compatibility-warning pause: the worker thread
        # blocks in _wait_for_decision() until the UI thread records a choice,
        # so cleanup cannot delete the converted package mid-review.
        self._decision_made = False
        self._decision_approved = False
        self._decision_message: str | None = None

        # Converters and installer (will be created during pipeline)
        self._deb_converter: DebConverter | None = None
        self._rpm_converter: RpmConverter | None = None
        self._installer: Installer | None = None

        # For waiting on async operations
        self._waiting = False
        self._async_success = False
        self._async_message = ""
        self._async_pkg_path: Path | None = None

    def cancel(self) -> None:
        """Cancel the pipeline at the earliest opportunity."""
        self._cancelled = True
        # Wake the worker if it is blocked in _wait_for_decision().
        self._decision_signal.emit()
        if self._deb_converter:
            self._deb_converter.cancel()
        if self._rpm_converter:
            self._rpm_converter.cancel()
        if self._installer:
            self._installer.cancel()

    def approve_install(self) -> None:
        """User approved the installation after reviewing compatibility.

        Thread-safe: may be called from the UI thread while the worker thread
        is blocked in _wait_for_decision(); the queued _decision_signal wakes
        the worker's nested event loop.
        """
        self._decision_approved = True
        self._decision_made = True
        self._decision_signal.emit()

    def dismiss_install(self, message: str | None = None) -> None:
        """User declined installation (closed the report / chose fallback).

        Thread-safe counterpart of approve_install(): releases the worker
        thread so the pipeline can finish and clean up. An optional *message*
        overrides the default result text (e.g. when the user chose the
        distrobox fallback instead of a plain decline).
        """
        self._decision_approved = False
        self._decision_made = True
        if message:
            self._decision_message = message
        self._decision_signal.emit()

    def _wait_for_decision(self) -> bool:
        """Block the worker thread until the UI records an install decision.

        The converted package lives inside the temp dir, so the pipeline must
        not return (and trigger cleanup) while the user is still reviewing the
        compatibility report. A nested QEventLoop keeps processing events on
        the worker thread — including the queued _decision_signal that wakes
        it — until approve_install()/dismiss_install() runs. A fresh loop is
        used per iteration because a QEventLoop that was quit() cannot be
        reliably re-exec()ed.

        The decision flags are deliberately NOT reset here: each pipeline
        instance processes exactly one file, and not resetting closes the race
        where the UI records a decision before the worker reaches this method
        (the flags are already authoritative; a pre-connection signal emit is
        simply dropped).
        """
        while not self._decision_made and not self._cancelled:
            loop = QEventLoop()
            self._decision_signal.connect(loop.quit)
            try:
                loop.exec()
            finally:
                try:
                    self._decision_signal.disconnect(loop.quit)
                except TypeError:
                    pass

        return self._decision_approved and not self._cancelled

    def run(self, file_path: Path) -> None:
        """Execute the full pipeline synchronously (call from QThread)."""
        self._log("info", f"Pipeline başlatıldı: {file_path.name}")
        self._result = PipelineResult()
        self._result.original_file = file_path

        try:
            self._run_pipeline(file_path)
        except Exception as exc:
            self._result.success = False
            self._result.message = f"Beklenmeyen hata: {exc}"
            self._log("error", str(exc))
        finally:
            self._record_history(file_path)
            self._cleanup()
            self.finished.emit(self._result)

    def _record_history(self, file_path: Path) -> None:
        """Persist result in SQLite history database."""
        try:
            from core.history_db import HistoryDB
            HistoryDB().add_record(
                package_name=self._result.metadata.name if self._result.metadata else file_path.name,
                original_file=file_path.name,
                package_type=self._result.metadata.package_type if self._result.metadata else ("deb" if file_path.suffix.lower() == ".deb" else "rpm"),
                sha256=self._result.sha256,
                status="success" if self._result.success else "failed",
                output_pkg=str(self._result.converted_pkg) if self._result.converted_pkg else "",
                details=self._result.message,
            )
        except Exception as exc:
            log.warning("Geçmiş kaydı tutulamadı: %s", exc)


    def _run_pipeline(self, file_path: Path) -> None:
        """Internal pipeline execution."""
        # Check required tools
        missing = self._tools.missing_required
        if missing:
            self._result.message = f"Gerekli araçlar bulunamadı: {', '.join(missing)}"
            self._log("error", self._result.message)
            return

        optional_missing = self._tools.missing_optional
        if optional_missing:
            self._log("warning", f"İsteğe bağlı araçlar eksik: {', '.join(optional_missing)}")

        # Create temp directory
        self._temp_dir = create_temp_dir()
        self._log("info", f"Geçici dizin: {self._temp_dir}")

        # ── Step 1: Security checks ──────────────────────────────
        if self._cancelled:
            return
        self._set_step(PipelineStep.SECURITY, "running")
        self.progress.emit(5)

        # MIME type
        try:
            mime = validate_mime_type(file_path, self._tools)
            self._log("info", f"MIME doğrulandı: {mime}")
        except (ValueError, FileNotFoundError) as exc:
            self._set_step(PipelineStep.SECURITY, "error")
            self._result.message = str(exc)
            self._log("error", str(exc))
            return

        # File size
        size_warn = validate_file_size(file_path, MAX_PACKAGE_SIZE_MB, WARN_PACKAGE_SIZE_MB)
        if size_warn:
            self._result.size_warning = size_warn
            self._log("warning", size_warn)
        self.progress.emit(10)

        # SHA-256
        self._result.sha256 = sha256_hash(file_path)
        self._log("info", f"SHA-256: {self._result.sha256[:16]}...")
        self.progress.emit(15)

        # GPG signature
        is_deb = file_path.suffix.lower() == ".deb"
        if is_deb:
            self._result.signature = verify_deb_signature(file_path, self._tools)
        else:
            self._result.signature = verify_rpm_signature(file_path, self._tools)
        self._log(
            "warning" if not self._result.signature.has_signature else "info",
            self._result.signature.detail,
        )
        self.progress.emit(20)

        self._set_step(PipelineStep.SECURITY, "done")

        # ── Step 1.5: Malware scan (optional, non-fatal) ────────
        if self._cancelled:
            return
        from i18n import load_setting
        if load_setting("clamav_scan", True):
            self._set_step(PipelineStep.MALWARE_SCAN, "running")
            self.progress.emit(22)
            try:
                from core.malware_scanner import scan_file, is_clamav_available
                if is_clamav_available():
                    scan_result = scan_file(file_path, self._tools)
                    if scan_result.engine_version:
                        self._log("info", f"ClamAV motoru: {scan_result.engine_version}")
                    if scan_result.infected:
                        self._set_step(PipelineStep.MALWARE_SCAN, "error")
                        self._result.message = (
                            f"⚠️ Malware tespit edildi: {scan_result.detail}. "
                            f"Enfekte dosyalar: {scan_result.infected_files[:5]}"
                        )
                        self._log("error", self._result.message)
                        return
                    self._log("info", scan_result.detail)
                else:
                    self._log("warning", "clamscan bulunamadı — malware taraması atlandı")
                self._set_step(PipelineStep.MALWARE_SCAN, "done")
            except Exception as exc:
                self._log("warning", f"Malware taraması başarısız: {exc}")
                self._set_step(PipelineStep.MALWARE_SCAN, "done")
            self.progress.emit(25)

        # ── Step 2: Package analysis ─────────────────────────────
        if self._cancelled:
            return
        self._set_step(PipelineStep.ANALYSIS, "running")
        self.progress.emit(30)

        try:
            meta = analyze_package(file_path, self._tools)
            self._result.metadata = meta
        except Exception as exc:
            self._set_step(PipelineStep.ANALYSIS, "error")
            self._result.message = f"Paket analizi başarısız: {exc}"
            self._log("error", str(exc))
            return

        self._log("info", f"Paket: {meta.name} {meta.version} ({meta.arch_mapped})")

        if not meta.arch_compatible:
            self._set_step(PipelineStep.ANALYSIS, "error")
            self._result.message = (
                f"Uyumsuz mimari: {meta.arch} → {meta.arch_mapped}. "
                f"Bu sistem yalnızca x86_64 ve any destekler."
            )
            self._log("error", self._result.message)
            return

        if meta.already_installed:
            self._log("info", f"Zaten kurulu: {meta.name} {meta.installed_version}")

        # Path traversal check
        if meta.file_list:
            traversal = check_path_traversal(meta.file_list)
            if traversal:
                self._set_step(PipelineStep.ANALYSIS, "error")
                self._result.message = f"Path traversal saldırısı tespit edildi: {traversal[:3]}"
                self._log("error", self._result.message)
                return

        self.progress.emit(35)

        # AUR Check (purely informational — must never abort the conversion)
        from i18n import load_setting
        if load_setting("aur_check", True):
            self._log("info", f"AUR'da kontrol ediliyor: {meta.name}")
            try:
                from core.aur_checker import check_aur
                aur_res = check_aur(meta.name, meta.version)
                if aur_res.status == "found_newer":
                    self._log("warning", f"AUR'da daha yeni versiyon mevcut: {aur_res.aur_version} (paket: {meta.version})")
                elif aur_res.status == "out_of_date":
                    self._log("info", f"AUR paketi eskimiş (OutOfDate): {aur_res.aur_version}, yerel dönüşüm önerilir")
                elif aur_res.status == "found_older":
                    self._log("info", f"Yerel paket AUR'dakinden daha yeni: {meta.version} > {aur_res.aur_version}")
                elif aur_res.status == "not_found":
                    self._log("info", "Paket AUR'da bulunamadı, özel dönüşüm yapılıyor")
            except Exception as exc:
                log.warning("AUR kontrolü atlandı: %s", exc)
                self._log("warning", f"AUR kontrolü yapılamadı: {exc}")

        self._set_step(PipelineStep.ANALYSIS, "done")

        # ── Step 3: Conversion ───────────────────────────────────
        if self._cancelled:
            return
        self._set_step(PipelineStep.CONVERSION, "running")
        self.progress.emit(40)

        convert_dir = self._temp_dir / "convert"
        convert_dir.mkdir(exist_ok=True)

        if is_deb:
            self._convert_deb(file_path, convert_dir)
        else:
            self._convert_rpm(file_path, convert_dir, meta)

        if not self._async_success:
            self._set_step(PipelineStep.CONVERSION, "error")
            self._result.message = self._async_message or "Dönüşüm başarısız"
            return

        converted_pkg = self._async_pkg_path
        if converted_pkg is None:
            self._set_step(PipelineStep.CONVERSION, "error")
            self._result.message = "Dönüştürülmüş paket bulunamadı"
            return

        self._result.converted_pkg = converted_pkg
        self.progress.emit(65)
        self._set_step(PipelineStep.CONVERSION, "done")

        # ── Step 4: Compatibility checks ─────────────────────────
        if self._cancelled:
            return
        self._set_step(PipelineStep.COMPATIBILITY, "running")
        self.progress.emit(70)

        report = run_compatibility_checks(
            converted_pkg,
            meta.file_list,
            meta.depends,
            self._tools,
        )
        self._result.compatibility = report

        for check in report.checks:
            level = {
                CheckSeverity.PASS: "success",
                CheckSeverity.WARNING: "warning",
                CheckSeverity.ERROR: "error",
            }[check.severity]
            self._log(level, f"[{check.name}] {check.message}")
            for detail in check.details[:5]:
                self._log(level, f"  {detail}")

        self.progress.emit(80)

        if report.overall == CheckSeverity.ERROR:
            self._set_step(PipelineStep.COMPATIBILITY, "error")
            self._result.message = "Uyumluluk testleri başarısız — kurulum önerilmez"
            self._result.success = False
            self.compatibility_ready.emit(report)
            return
        elif report.overall == CheckSeverity.WARNING:
            self._set_step(PipelineStep.COMPATIBILITY, "warning")
            self._log("warning", "Uyarılar var — kullanıcı onayı bekleniyor")
            self.compatibility_ready.emit(report)
            # Block until the UI records a decision (approve_install /
            # dismiss_install). The temp dir — and therefore the converted
            # package — stays alive while the user reviews the report.
            if not self._wait_for_decision():
                self._set_step(PipelineStep.INSTALL, "error")
                self._result.success = False
                self._result.message = (
                    "İptal edildi" if self._cancelled
                    else self._decision_message
                    or "Uyumluluk uyarıları mevcut — kurulum onaylanmadı"
                )
                return
            self._user_approved = True
            self._set_step(PipelineStep.COMPATIBILITY, "done")
        else:
            self._set_step(PipelineStep.COMPATIBILITY, "done")
            # Auto-approve if all checks passed
            self._user_approved = True

        self.progress.emit(85)

        # ── Step 5: Install ──────────────────────────────────────
        if not self._user_approved or self._cancelled:
            return

        self._do_install(converted_pkg, meta.name)

    def do_install_after_approval(self) -> None:
        """Called by the UI after user approves installation despite warnings.

        Kept for API compatibility; the install itself now runs on the worker
        thread that is blocked in _wait_for_decision(), so this only records
        the decision and wakes that thread.
        """
        self.approve_install()

    def _do_install(self, pkg_path: Path, pkg_name: str) -> None:
        """Execute the installation step."""
        # Dry-run: convert + analyze only, never touch the real system.
        from i18n import load_setting
        if load_setting("dry_run", False):
            self._set_step(PipelineStep.INSTALL, "done")
            self.progress.emit(100)
            self._result.success = True
            self._result.message = f"{pkg_name} dönüştürüldü (dry-run: kurulmadı)"
            self._log("info", self._result.message)
            return

        self._set_step(PipelineStep.INSTALL, "running")
        self.progress.emit(90)

        self._installer = Installer(self._tools, self)
        self._installer.output_line.connect(lambda msg: self._log("info", msg))

        self._async_success = False
        self._async_message = ""

        loop = QEventLoop()

        def on_install_done(success: bool, msg: str) -> None:
            self._async_success = success
            self._async_message = msg
            loop.quit()

        self._installer.finished.connect(on_install_done)
        self._installer.install(pkg_path, pkg_name)
        loop.exec()

        if self._async_success:
            self._set_step(PipelineStep.INSTALL, "done")
            self.progress.emit(100)
            self._result.success = True
            self._result.message = f"{pkg_name} başarıyla kuruldu"
        else:
            self._set_step(PipelineStep.INSTALL, "error")
            self._result.success = False
            self._result.message = self._async_message or "Kurulum başarısız"

    def _convert_deb(self, deb_path: Path, output_dir: Path) -> None:
        """Run DEB conversion using NativeDebConverter (with debtap fallback)."""
        from core.native_deb_converter import NativeDebConverter

        self._deb_converter = NativeDebConverter(self._tools, self)
        self._deb_converter.output_line.connect(lambda msg: self._log("info", msg))

        self._async_success = False
        self._async_message = ""
        self._async_pkg_path = None

        loop = QEventLoop()

        def on_done(success: bool, msg: str, pkg: object) -> None:
            self._async_success = success
            self._async_message = msg
            self._async_pkg_path = pkg  # type: ignore
            loop.quit()

        self._deb_converter.finished.connect(on_done)
        self._deb_converter.convert(deb_path, output_dir)
        loop.exec()

        # Disconnect native converter signals before attempting fallback
        # to prevent stale callbacks from corrupting shared state.
        try:
            self._deb_converter.finished.disconnect(on_done)
        except TypeError:
            pass

        # Fallback to debtap if native converter fails and debtap exists
        if not self._async_success and self._tools.debtap:
            self._log("warning", "Native DEB dönüştürücü başarısız oldu, debtap deneniyor...")
            from core.deb_converter import DebConverter
            fallback_converter = DebConverter(self._tools, self)
            fallback_converter.output_line.connect(lambda msg: self._log("info", msg))

            loop_fb = QEventLoop()

            def on_fb_done(success: bool, msg: str, pkg: object) -> None:
                self._async_success = success
                self._async_message = msg
                self._async_pkg_path = pkg  # type: ignore
                loop_fb.quit()

            fallback_converter.finished.connect(on_fb_done)
            fallback_converter.convert(deb_path, output_dir)
            loop_fb.exec()


    def _convert_rpm(self, rpm_path: Path, work_dir: Path, meta: PackageMetadata) -> None:
        """Run RPM conversion."""
        self._rpm_converter = RpmConverter(self._tools, self)
        self._rpm_converter.output_line.connect(lambda msg: self._log("info", msg))

        self._async_success = False
        self._async_message = ""
        self._async_pkg_path = None

        loop = QEventLoop()

        def on_done(success: bool, msg: str, pkg: object) -> None:
            self._async_success = success
            self._async_message = msg
            self._async_pkg_path = pkg  # type: ignore
            loop.quit()

        self._rpm_converter.finished.connect(on_done)
        self._rpm_converter.convert(rpm_path, work_dir, meta)
        loop.exec()

    def _cleanup(self) -> None:
        """Remove temporary directory."""
        if self._temp_dir and self._temp_dir.exists():
            try:
                shutil.rmtree(self._temp_dir)
                self._log("info", "Geçici dosyalar temizlendi")
            except OSError as exc:
                self._log("warning", f"Temizlik hatası: {exc}")


    def _set_step(self, step: PipelineStep, status: str) -> None:
        label = STEP_LABELS[step]
        self.step_changed.emit(int(step), status)
        if status == "running":
            self._log("info", f"━━ {label} ━━")
        elif status == "done":
            self._log("success", f"✓ {label} tamamlandı")
        elif status == "error":
            self._log("error", f"✗ {label} başarısız")
        elif status == "warning":
            self._log("warning", f"⚠ {label} — uyarılar mevcut")

    def _log(self, level: str, message: str) -> None:
        self.log_message.emit(message, level)
        getattr(log, level if level != "success" else "info", log.info)(message)
