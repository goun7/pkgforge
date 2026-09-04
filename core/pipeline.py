"""PkgForge — Conversion pipeline orchestrator.

Coordinates all steps (security → analysis → conversion →
compatibility → install → verify → cleanup) in a background
QThread, emitting signals for UI progress updates.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import threading
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

# ── PyQt6 availability gate ──────────────────────────────────────
# Runtime: import real Qt classes when available, otherwise stubs.
# Type-checking: always see the real signatures via TYPE_CHECKING.
if TYPE_CHECKING:  # pragma: no cover
    from PyQt6.QtCore import QEventLoop, QObject, QThread, QTimer, pyqtSignal, pyqtSlot
else:
    try:
        from PyQt6.QtCore import (
            QEventLoop,
            QObject,
            QThread,
            QTimer,
            pyqtSignal,
            pyqtSlot,
        )
        _HAS_PYQT6 = True
    except ImportError:  # pragma: no cover — PyQt6 kurulu ortamda ulaşılmaz
        _HAS_PYQT6 = False
        # Minimal stubs — only used at runtime when PyQt6 is missing.
        class QObject:  # type: ignore[no-redef]
            pass
        class QThread(QObject):  # type: ignore[no-redef]
            pass
        def pyqtSignal(*args: Any, **kwargs: Any) -> Any:  # type: ignore[misc]
            return None
        def pyqtSlot(*args: Any, **kwargs: Any) -> Any:  # type: ignore[misc]
            def deco(fn: Any) -> Any:
                return fn
            return deco
        class QEventLoop:  # type: ignore[no-redef]
            def exec(self) -> None: pass
            def quit(self) -> None: pass
        class QTimer:  # type: ignore[no-redef]
            @staticmethod
            def singleShot(ms: int, fn: Any) -> None: fn()

from config import (
    MAX_PACKAGE_SIZE_MB,
    WARN_PACKAGE_SIZE_MB,
    ToolPaths,
    create_temp_dir,
    discover_tools,
)
from core import intake
from core.compatibility_checker import (
    CheckSeverity,
    CompatibilityReport,
    run_compatibility_checks,
)
from core.package_analyzer import PackageMetadata, analyze_package
from core.security import (
    SignatureResult,
    check_path_traversal,
    sha256_hash,
    validate_file_size,
    validate_mime_type,
    verify_deb_signature,
    verify_rpm_signature,
)
from i18n import tr

# Conditional import: PyQt6 for GUI, subprocess for CLI
if TYPE_CHECKING:  # pragma: no cover
    from core.deb_converter import DebConverter
    from core.installer import Installer
    from core.native_deb_converter import NativeDebConverter
    from core.rpm_converter import RpmConverter
    _HAS_PYQT6 = True
else:
    try:
        # Importing rpm_converter pulls in PyQt6; if it is missing the
        # ImportError below switches to the subprocess backend.
        from core.rpm_converter import RpmConverter  # type: ignore[no-redef]
        _HAS_PYQT6 = True
    except ImportError:  # pragma: no cover — PyQt6 kurulu ortamda ulaşılmaz
        from core.subprocess_converters import (
            RpmConverterSubprocess as RpmConverter,  # type: ignore[no-redef]
        )
        _HAS_PYQT6 = False

log = logging.getLogger(__name__)

__all__ = [
    "ConversionPipeline", "PipelineResult",
]


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
        "compatibility",
        "converted_pkg",
        "message",
        "metadata",
        "original_file",
        "sha256",
        "signature",
        "size_warning",
        "success",
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


def _sha256_of(path: Path) -> str:
    """Tarball'in sha256 ozetini hesaplar; yoksa SKIP dondurur."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, ValueError):
        return "SKIP"


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
        # F4.3 batch mode: when set, a dismissed decision gate means the
        # conversion SUCCEEDED and installation was skipped (not an error).
        self._skip_install_message: str = ""

        # Converters and installer (will be created during pipeline).
        # _deb_converter may hold either the native converter or the debtap
        # fallback; both expose cancel()/convert()/output_line/finished.
        self._deb_converter: DebConverter | NativeDebConverter | None = None
        self._rpm_converter: RpmConverter | None = None
        self._installer: Installer | None = None

        # For waiting on async operations (thread-safe)
        self._waiting = False
        self._async_lock = threading.Lock()
        self._async_success = False
        self._async_message = ""
        self._async_pkg_path: Path | None = None

        # Path staged for run_staged(); set before the worker thread starts so
        # the no-arg slot (connected to QThread.started) can pick it up.
        self._staged_path: Path | None = None
        # Optional intake override: when the UI resolves an ambiguous input
        # (e.g. a .tar.gz the user marked as source or binary) it stages the
        # chosen FileType value here so classify is bypassed.
        self._forced_type: str | None = None

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

    def stage(self, file_path: Path, forced_type: str | None = None) -> None:
        """Stage *file_path* for run_staged(); call BEFORE starting the thread.

        *forced_type* optionally overrides universal-intake classification
        (one of ``core.intake.FileType`` values, e.g. ``"source_tarball"``);
        used when the user resolves an ambiguous file in the UI.
        """
        self._staged_path = file_path
        self._forced_type = forced_type

    @pyqtSlot()
    def run_staged(self) -> None:
        """No-arg entry point for QThread.started connections.

        Connecting ``started`` to a bare lambda queues the call onto the
        *main* thread (lambdas have no thread affinity), which ran the whole
        pipeline on the UI thread and created QProcess children across a
        thread-affinity boundary ("Cannot create children for a parent that
        is in a different thread"). Connecting to this slot of the pipeline
        object -- which has already been moveToThread()ed -- executes it on
        the worker thread instead.
        """
        if self._staged_path is None:
            self._result.success = False
            self._result.message = "Pipeline başlatılamadı: dosya yolu verilmedi"
            self.finished.emit(self._result)
            return
        self.run(self._staged_path, self._forced_type)

    def run(self, file_path: Path, forced_type: str | None = None) -> None:
        """Execute the full pipeline synchronously (call from QThread)."""
        if forced_type is not None:
            self._forced_type = forced_type
        self._log("info", tr("log.pipeline.started", name=file_path.name))
        self._result = PipelineResult()
        self._result.original_file = file_path

        try:
            self._run_pipeline(file_path)
        except Exception as exc:  # noqa: BLE001
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
        except Exception as exc:  # noqa: BLE001
            log.warning(tr("pipeline.gecmis_kaydi_tutulamadi_s"), exc)


    def _stage_security(self, file_path: Path, is_deb: bool) -> None:
        """Adım 1: güvenlik denetimleri (MIME, boyut, SHA-256, imza, bomba).

        Hata durumunda adımı 'error' yapıp mesajı yazar; akış kesilir.
        """
        if self._cancelled:
            return
        self._set_step(PipelineStep.SECURITY, "running")
        self.progress.emit(5)

        # MIME type
        try:
            mime = validate_mime_type(file_path, self._tools)
            self._log("info", tr("pipeline.mime_dogrulandi_mime", mime=mime))
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
        if is_deb:
            self._result.signature = verify_deb_signature(file_path, self._tools)
        else:
            self._result.signature = verify_rpm_signature(file_path, self._tools)
        self._log(
            "warning" if not self._result.signature.has_signature else "info",
            self._result.signature.detail,
        )
        self.progress.emit(18)

        # Decompression bomb check
        from core.security import check_compression_bomb
        bomb_warn = check_compression_bomb(file_path, self._tools)
        if bomb_warn:
            self._log("warning", bomb_warn)
        self.progress.emit(20)

        self._set_step(PipelineStep.SECURITY, "done")

    def _stage_malware(self, file_path: Path) -> None:
        """Adım 1.5: ClamAV taraması (isteğe bağlı, ölümcül değil)."""
        if self._cancelled:
            return
        from i18n import load_setting
        if load_setting("clamav_scan", True):
            self._set_step(PipelineStep.MALWARE_SCAN, "running")
            self.progress.emit(22)
            try:
                # Database freshness check (informational)
                from core.malware_scanner import check_database_freshness
                db_warn = check_database_freshness()
                if db_warn:
                    self._log("warning", db_warn)

                from core.malware_scanner import is_clamav_available, scan_file
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
                    if not scan_result.clean:
                        # SEC: motor hatasi fail-closed — donusumu durdur.
                        self._set_step(PipelineStep.MALWARE_SCAN, "error")
                        self._result.message = (
                            f"⛔ Malware tarayıcısı hata verdi (fail-closed): "
                            f"{scan_result.detail}"
                        )
                        self._log("error", self._result.message)
                        return
                    self._log("info", scan_result.detail)
                    self._set_step(PipelineStep.MALWARE_SCAN, "done")
                else:
                    self._log("warning", "clamscan bulunamadı — malware taraması atlandı")
                    self._set_step(PipelineStep.MALWARE_SCAN, "skipped")
            except Exception as exc:  # noqa: BLE001
                self._log("warning", tr("pipeline.malware_taramasi_basarisiz_exc", exc=exc))
                self._set_step(PipelineStep.MALWARE_SCAN, "warning")
            self.progress.emit(25)
        else:
            # Tarama ayarlardan kapaliysa adimi "pending" birakma, atlandigini goster
            self._set_step(PipelineStep.MALWARE_SCAN, "skipped")
            self._log("info", "Malware taraması ayarlardan kapalı — atlandı")

    def _stage_analysis(self, file_path: Path) -> PackageMetadata | None:
        """Adım 2: paket analizi + mimari/traversal kontrolleri.

        Hata durumunda None döner; akış kesilir.
        """
        if self._cancelled:
            return None
        self._set_step(PipelineStep.ANALYSIS, "running")
        self.progress.emit(30)

        try:
            meta = analyze_package(file_path, self._tools)
            self._result.metadata = meta
        except Exception as exc:  # noqa: BLE001
            self._set_step(PipelineStep.ANALYSIS, "error")
            self._result.message = tr("pipeline.paket_analizi_basarisiz_exc", exc=exc)
            self._log("error", str(exc))
            return None

        self._log("info", f"Paket: {meta.name} {meta.version} ({meta.arch_mapped})")

        if not meta.arch_compatible:
            self._set_step(PipelineStep.ANALYSIS, "error")
            self._result.message = (
                tr("pipeline.uyumsuz_mimari_meta_arch", meta_arch=meta.arch, meta_arch_mapped=meta.arch_mapped)
            )
            self._log("error", self._result.message)
            return None

        if meta.already_installed:
            self._log("info", f"Zaten kurulu: {meta.name} {meta.installed_version}")

        # Path traversal check
        if meta.file_list:
            traversal = check_path_traversal(meta.file_list)
            if traversal:
                self._set_step(PipelineStep.ANALYSIS, "error")
                self._result.message = tr("pipeline.path_traversal_saldirisi_tespit", traversal=traversal[:3])
                self._log("error", self._result.message)
                return None

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
                    self._log("info", tr("pipeline.aur_paketi_eskimis_outofdate", aur_res_aur_version=aur_res.aur_version))
                elif aur_res.status == "found_older":
                    self._log("info", f"Yerel paket AUR'dakinden daha yeni: {meta.version} > {aur_res.aur_version}")
                elif aur_res.status == "not_found":
                    self._log("info", "Paket AUR'da bulunamadı, özel dönüşüm yapılıyor")
            except Exception as exc:  # noqa: BLE001
                log.warning(tr("pipeline.aur_kontrolu_atlandi_s"), exc)
                self._log("warning", tr("pipeline.aur_kontrolu_yapilamadi_exc", exc=exc))

        self._set_step(PipelineStep.ANALYSIS, "done")
        return meta

    def _stage_conversion(
        self, file_path: Path, is_deb: bool, meta: PackageMetadata,
    ) -> Path | None:
        """Adım 3: paketi dönüştür; başarısızlıkta None döner."""
        if self._cancelled:
            return None
        if self._temp_dir is None:
            self._result.message = "Dönüşüm dizini hazırlanamadı"
            self._log("error", self._result.message)
            self._set_step(PipelineStep.CONVERSION, "error")
            return None
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
            return None

        converted_pkg = self._async_pkg_path
        if converted_pkg is None:
            self._set_step(PipelineStep.CONVERSION, "error")
            self._result.message = "Dönüştürülmüş paket bulunamadı"
            return None

        self._result.converted_pkg = converted_pkg
        self.progress.emit(65)
        self._set_step(PipelineStep.CONVERSION, "done")
        return converted_pkg

    def _run_pipeline(self, file_path: Path) -> None:
        """Internal pipeline execution."""
        # Check required tools
        missing = self._tools.missing_required
        if missing:
            self._result.message = tr("pipeline.gerekli_araclar_bulunamadi_var0", var0=', '.join(missing))
            self._log("error", self._result.message)
            return

        optional_missing = self._tools.missing_optional
        if optional_missing:
            self._log("warning", tr("pipeline.stege_bagli_araclar_eksik", var0=', '.join(optional_missing)))

        # ── Universal intake: classify the input and route by type ──
        ir = self._classify_input(file_path)
        if ir.file_type not in (intake.FileType.DEB, intake.FileType.RPM):
            self._temp_dir = create_temp_dir()
            self._log("info", tr("pipeline.gecici_dizin_self_temp_2", self__temp_dir=self._temp_dir))
            self._run_intake_route(file_path, ir)
            return
        is_deb = ir.file_type == intake.FileType.DEB

        # Create temp directory
        self._temp_dir = create_temp_dir()
        self._log("info", tr("pipeline.gecici_dizin_self_temp", self__temp_dir=self._temp_dir))

        self._stage_security(file_path, is_deb)
        if self._result.message or self._cancelled:
            return

        self._stage_malware(file_path)
        if self._result.message or self._cancelled:
            return

        meta = self._stage_analysis(file_path)
        if meta is None:
            return

        converted_pkg = self._stage_conversion(file_path, is_deb, meta)
        if converted_pkg is None:
            return

        self._finalize_pkg(converted_pkg, meta)

    def _finalize_pkg(self, converted_pkg: Path, meta: PackageMetadata) -> None:
        """Shared tail: compatibility checks, install-approval gate, install."""
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
            self._log("error", "Uyumluluk testleri başarısız — kullanıcı kararı bekleniyor")
            self.compatibility_ready.emit(report)
            # Block until the UI records a decision (Install Anyway / Close),
            # exactly like the WARNING branch. Previously this returned
            # immediately, so the worker finished and cleaned up the temp
            # dir (deleting the converted package) before the user could
            # choose to proceed — leaving Install Anyway with no listener.
            if not self._wait_for_decision():
                if not self._cancelled and self._skip_install_message:
                    # F4.3 batch mode: conversion succeeded, install opted out.
                    msg = self._skip_install_message
                    self._set_step(PipelineStep.INSTALL, "done")
                    self.progress.emit(100)
                    self._result.success = True
                    self._result.message = msg
                    self._log("info", msg)
                    return
                self._set_step(PipelineStep.INSTALL, "error")
                self._result.success = False
                self._result.message = (
                    "İptal edildi" if self._cancelled
                    else self._decision_message
                    or "Uyumluluk testleri başarısız — kurulum onaylanmadı"
                )
                return
            self._user_approved = True
            self._set_step(PipelineStep.COMPATIBILITY, "done")
        elif report.overall == CheckSeverity.WARNING:
            self._set_step(PipelineStep.COMPATIBILITY, "warning")
            self._log("warning", "Uyarılar var — kullanıcı onayı bekleniyor")
            self.compatibility_ready.emit(report)
            # Block until the UI records a decision (approve_install /
            # dismiss_install). The temp dir — and therefore the converted
            # package — stays alive while the user reviews the report.
            if not self._wait_for_decision():
                if not self._cancelled and self._skip_install_message:
                    msg = self._skip_install_message
                    self._set_step(PipelineStep.INSTALL, "done")
                    self.progress.emit(100)
                    self._result.success = True
                    self._result.message = msg
                    self._log("info", msg)
                    return
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

    # ── Universal intake route (non deb/rpm) ────────────────────
    def _classify_input(self, file_path: Path) -> intake.IntakeResult:
        """Universal intake ile siniflandir; forced_type varsa onu kullan."""
        if self._forced_type:
            try:
                ft = intake.FileType(self._forced_type)
            except ValueError:
                ft = intake.FileType.UNKNOWN
            return intake.IntakeResult(ft, file_path, 1.0, "kullanici secimi")
        return intake.classify(file_path)

    def _run_intake_route(self, file_path: Path, ir: intake.IntakeResult) -> None:
        """deb/rpm disi turler icin rota: Arch paketi uret ve kur."""
        self._log("info", "Algilanan tur: " + ir.file_type.value + " (" + ir.reason + ")")

        # Adim 1: genel guvenlik (boyut + sha256)
        if self._cancelled:
            return
        self._set_step(PipelineStep.SECURITY, "running")
        self.progress.emit(5)
        size_warn = validate_file_size(file_path, MAX_PACKAGE_SIZE_MB, WARN_PACKAGE_SIZE_MB)
        if size_warn:
            self._result.size_warning = size_warn
            self._log("warning", size_warn)
        self._result.sha256 = sha256_hash(file_path)
        self._log("info", "SHA-256: " + self._result.sha256[:16] + "...")
        self._set_step(PipelineStep.SECURITY, "done")
        self.progress.emit(15)

        # Ilerlenemez turler
        if ir.file_type == intake.FileType.UNKNOWN:
            self._set_step(PipelineStep.ANALYSIS, "error")
            if ir.ambiguous:
                self._result.message = (
                    "Dosya turu belirsiz (kaynak mi, hazir binary mi?). "
                    "Arayuzden acikca secin."
                )
            else:
                self._result.message = "Taninamayan dosya turu: " + file_path.name
            self._log("error", self._result.message)
            return
        if ir.file_type == intake.FileType.FLATPAKREF:
            self._set_step(PipelineStep.ANALYSIS, "error")
            self._result.message = (
                "Flatpak referanslari GUIde henuz desteklenmiyor. "
                "CLI kullanin: pkgforge flatpak-export"
            )
            self._log("error", self._result.message)
            return

        # Adim 2: analiz (hafif metadata)
        if self._cancelled:
            return
        self._set_step(PipelineStep.ANALYSIS, "running")
        self.progress.emit(25)
        meta = self._intake_metadata(file_path, ir)
        self._result.metadata = meta
        self._log("info", "Paket: " + meta.name + " " + meta.version)
        self._set_step(PipelineStep.ANALYSIS, "done")
        self.progress.emit(35)

        # Adim 3: donusum -> Arch paketi uret
        if self._cancelled:
            return
        self._set_step(PipelineStep.CONVERSION, "running")
        self.progress.emit(40)
        try:
            converted_pkg = self._intake_convert(file_path, ir, meta)
        except Exception as exc:  # noqa: BLE001
            self._set_step(PipelineStep.CONVERSION, "error")
            self._result.message = "Donusum basarisiz: " + str(exc)
            self._log("error", str(exc))
            return
        if self._cancelled:
            return
        self._result.converted_pkg = converted_pkg
        self.progress.emit(65)
        self._set_step(PipelineStep.CONVERSION, "done")

        # Adim 4+5: uyumluluk + kurulum (ortak kuyruk)
        self._finalize_pkg(converted_pkg, meta)

    def _intake_metadata(self, file_path: Path, ir: intake.IntakeResult) -> PackageMetadata:
        """Intake rotalari icin hafif PackageMetadata uretir."""
        stem = file_path.name
        tails = (".pkg.tar.zst", ".pkg.tar.xz", ".pkg.tar.gz", ".tar.gz", ".tar.xz",
                 ".tar.bz2", ".tar.zst", ".tgz", ".txz", ".tar", ".zip",
                 ".appimage", ".flatpakref")
        low = stem.lower()
        for tail in tails:
            if low.endswith(tail):
                stem = stem[: -len(tail)]
                break
        name, version = intake.derive_name_version(stem)
        meta = PackageMetadata()
        meta.file_path = file_path
        meta.package_type = "deb"
        meta.name = name
        meta.version = version
        meta.arch = "any"
        meta.arch_mapped = "x86_64"
        meta.description = ir.reason
        meta.depends = []
        meta.file_list = []
        return meta

    def _intake_convert(self, file_path: Path, ir: intake.IntakeResult,
                        meta: PackageMetadata) -> Path:
        """Ture gore Arch paketi uretir; basarisizlikta RuntimeError firlatir."""
        assert self._temp_dir is not None
        ft = ir.file_type
        if ft == intake.FileType.ARCH_PKG:
            dest = self._temp_dir / file_path.name
            shutil.copy2(file_path, dest)
            self._log("info", "Zaten Arch paketi — dogrudan kuruluma hazirlaniyor")
            return dest
        if ft == intake.FileType.SOURCE_DIR:
            return self._build_from_source_dir(file_path, ir, meta)
        if ft == intake.FileType.SOURCE_TARBALL:
            return self._build_from_source_tarball(file_path, ir, meta)
        if ft in (intake.FileType.BINARY_TARBALL, intake.FileType.APPIMAGE):
            return self._wrap_binary(file_path, ir, meta)
        raise RuntimeError("Desteklenmeyen tur: " + ft.value)

    def _run_makepkg(self, build_dir: Path) -> Path:
        """build_dir icinde makepkg calistirir, uretilen paketi dondurur."""
        if not self._tools.makepkg:
            raise RuntimeError("makepkg bulunamadi (paketleme icin gerekli)")
        from core.security import safe_run
        self._log("info", "makepkg calistiriliyor: " + build_dir.name)
        r = safe_run([self._tools.makepkg, "-f", "--noconfirm"],
                     cwd=build_dir, timeout=3600, text=True)
        for line in (r.stdout or "").splitlines()[-15:]:
            self._log("info", line)
        if r.returncode != 0:
            tail = (r.stderr or r.stdout or "").strip()[-300:]
            raise RuntimeError("makepkg basarisiz: " + tail)
        built = sorted(build_dir.glob("*.pkg.tar.zst"))
        if not built:
            raise RuntimeError("makepkg tamamlandi ama paket dosyasi bulunamadi")
        return built[-1]

    def _extract_tarball(self, file_path: Path, dest: Path) -> None:
        """Tarballi guvenlice acar (data filtresi path traversal onler)."""
        import tarfile as _tarfile
        with _tarfile.open(file_path, "r:*") as tf:
            tf.extractall(dest, filter="data")

    def _build_from_source_tarball(self, file_path: Path, ir: intake.IntakeResult,
                                   meta: PackageMetadata) -> Path:
        """Kaynak tarballini derleyip Arch paketi uretir."""
        assert self._temp_dir is not None
        from core.from_source import (
            _detect_binary_name,
            _detect_license,
            _extract_version_from_cargo,
            _extract_version_from_cmake,
            _extract_version_from_file,
            _extract_version_from_meson,
            _extract_version_from_pyproject,
        )
        extract_dir = self._temp_dir / "src_extract"
        extract_dir.mkdir(exist_ok=True)
        self._extract_tarball(file_path, extract_dir)
        names = intake._list_archive(file_path) or []
        top = intake.find_top_level_dir(names)
        repo_dir = extract_dir / top if top else extract_dir
        system = ir.build_system or intake.detect_build_system(names) or "make"
        # Onceden derlenmis binary tarball'larda (orn. foo-linux-x64.tar.gz)
        # gercek bir build agaci yoktur; 'make' varsayip Makefile olmadan
        # derlemeye calismak makepkg'yi "make dosyasi yok" hatasiyla dusurur.
        # Bu durumda binary sarmalama yoluna geri don.
        if system == "make" and not any(
                (repo_dir / mk).is_file()
                for mk in ("Makefile", "makefile", "GNUmakefile")):
            self._log("info", "Makefile bulunamadi — binary tarball olarak sariliyor")
            return self._wrap_binary(file_path, ir, meta)
        version = (
            _extract_version_from_cargo(repo_dir)
            or _extract_version_from_cmake(repo_dir)
            or _extract_version_from_meson(repo_dir)
            or _extract_version_from_pyproject(repo_dir)
            or _extract_version_from_file(repo_dir)
            or meta.version
        )
        license_id = _detect_license(repo_dir)
        binary_name = (_detect_binary_name(repo_dir, meta.name)
                       if system in ("cargo", "go") else None)
        build_dir = self._temp_dir / "build_src"
        build_dir.mkdir(exist_ok=True)
        shutil.copy2(file_path, build_dir / file_path.name)
        content = intake.generate_source_tarball_pkgbuild(
            meta.name, version, file_path.name, top, system,
            license_id=license_id, binary_name=binary_name,
            url=getattr(meta, "url", ""),
            sha256=_sha256_of(build_dir / file_path.name))
        (build_dir / "PKGBUILD").write_text(content, encoding="utf-8")
        self._log("info", "Kaynak PKGBUILD uretildi (" + system + ")")
        return self._run_makepkg(build_dir)

    def _build_from_source_dir(self, file_path: Path, ir: intake.IntakeResult,
                               meta: PackageMetadata) -> Path:
        """Kaynak klasorunu tarball yapip kaynak rotasina verir."""
        assert self._temp_dir is not None
        import tarfile as _tarfile
        tarball = self._temp_dir / (meta.name + ".tar.gz")
        with _tarfile.open(tarball, "w:gz") as tf:
            tf.add(file_path, arcname=meta.name)
        sub_ir = intake.classify(tarball)
        if not sub_ir.build_system and ir.build_system:
            sub_ir.build_system = ir.build_system
        return self._build_from_source_tarball(tarball, sub_ir, meta)

    def _extract_appimage(self, file_path: Path) -> Path:
        """AppImageyi --appimage-extract ile acip tarball olarak dondurur."""
        assert self._temp_dir is not None
        import tarfile as _tarfile

        from core.security import safe_run
        extract_dir = self._temp_dir / "appimage_extract"
        extract_dir.mkdir(exist_ok=True)
        appimg = self._temp_dir / file_path.name
        shutil.copy2(file_path, appimg)
        appimg.chmod(0o755)
        r = safe_run([str(appimg), "--appimage-extract"],
                     cwd=extract_dir, timeout=300, text=True)
        if r.returncode != 0:
            raise RuntimeError("AppImage acilamadi (--appimage-extract basarisiz)")
        root = extract_dir / "squashfs-root"
        if not root.exists():
            raise RuntimeError("AppImage acildi ama squashfs-root bulunamadi")
        tarball = extract_dir / (file_path.stem + ".tar.gz")
        with _tarfile.open(tarball, "w:gz") as tf:
            tf.add(root, arcname=".")
        return tarball

    def _wrap_binary(self, file_path: Path, ir: intake.IntakeResult,
                     meta: PackageMetadata) -> Path:
        """Hazir binary icerigi (tarball/AppImage) Arch paketine sarar.

        Tarball/icerik PKGBUILD'in source listesine konur; package()
        adiminda tar -xf ile dogrudan pkgdir/opt/<name> altina acilir.
        Boylece tarball dosyasi pakete kopyalanmaz (dangling-symlink
        ve elffile-in-questionable-dirs namcap hatalari onlenir) ve
        /usr/bin baglantisinin hedefi paket icindeki ger dosyayi
        isaret eder. AppImage rotasinda oncelikle --appimage-extract
        ile acilir, sonra ayni sekilde tarball olarak paketlenir.
        """
        assert self._temp_dir is not None
        if ir.file_type == intake.FileType.APPIMAGE:
            src = self._extract_appimage(file_path)
        else:
            src = file_path
        names = intake._list_archive(src) or []
        entry = intake.find_binary_entrypoint(names)
        if entry is not None:
            # /usr/bin symlink hedefi paket icindeki dosyaya gitmeli;
            # tarball listesinde bulunamayan bir yol dangling olmasin.
            entry = entry.lstrip("/")
        build_dir = self._temp_dir / "build_bin"
        build_dir.mkdir(exist_ok=True)
        shutil.copy2(src, build_dir / src.name)
        content = intake.generate_binary_pkgbuild(
            meta.name, meta.version, src.name, exec_relpath=entry,
            extract=True, url=getattr(meta, "url", ""))
        (build_dir / "PKGBUILD").write_text(content, encoding="utf-8")
        self._log("info", "Binary PKGBUILD uretildi")
        return self._run_makepkg(build_dir)

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
            self._result.message = tr("pipeline.pkg_name_donusturuldu_dry", pkg_name=pkg_name)
            self._log("info", self._result.message)
            return

        self._set_step(PipelineStep.INSTALL, "running")
        self.progress.emit(90)

        # Local import: core.installer pulls in PyQt6, so importing it at module
        # level would break the PyQt6-free CLI path.
        from core.installer import Installer
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
            self._result.message = tr("pipeline.pkg_name_basariyla_kuruldu", pkg_name=pkg_name)
        else:
            self._set_step(PipelineStep.INSTALL, "error")
            self._result.success = False
            self._result.message = self._async_message or "Kurulum başarısız"

    def _convert_deb(self, deb_path: Path, output_dir: Path) -> None:
        """Run DEB conversion using NativeDebConverter (with debtap fallback)."""
        self._async_success = False
        self._async_message = ""
        self._async_pkg_path = None

        if _HAS_PYQT6:
            # Qt mode: use QEventLoop
            from core.native_deb_converter import NativeDebConverter
            converter_qt = NativeDebConverter(self._tools, self)
            self._deb_converter = converter_qt
            converter_qt.output_line.connect(lambda msg: self._log("info", msg))

            loop = QEventLoop()

            def on_done(success: bool, msg: str, pkg: Path | None) -> None:
                self._async_success = success
                self._async_message = msg
                self._async_pkg_path = pkg
                loop.quit()

            converter_qt.finished.connect(on_done)
            converter_qt.convert(deb_path, output_dir)
            loop.exec()
            try:
                converter_qt.finished.disconnect(on_done)
            except TypeError:
                pass
        else:
            # Subprocess mode: use threading.Event
            from core.subprocess_converters import NativeDebConverterSubprocess
            converter = NativeDebConverterSubprocess(self._tools)
            converter.output_line.connect(lambda msg: self._log("info", msg))

            done_event = threading.Event()

            def on_done(success: bool, msg: str, pkg: Path | None) -> None:
                with self._async_lock:
                    self._async_success = success
                    self._async_message = msg
                    self._async_pkg_path = pkg
                done_event.set()

            converter.finished.connect(on_done)
            converter.convert(deb_path, output_dir)
            done_event.wait()

        # Fallback to debtap if native converter fails and debtap exists
        if not self._async_success and self._tools.debtap:
            self._log("warning", "Native DEB dönüştürücü başarısız oldu, debtap deneniyor...")
            from core.deb_converter import DebConverter
            fallback_converter = DebConverter(self._tools, self)
            fallback_converter.output_line.connect(lambda msg: self._log("info", msg))

            if _HAS_PYQT6:
                loop_fb = QEventLoop()
                def on_fb_done(success: bool, msg: str, pkg: Path | None) -> None:
                    self._async_success = success
                    self._async_message = msg
                    self._async_pkg_path = pkg
                    loop_fb.quit()
                fallback_converter.finished.connect(on_fb_done)
                fallback_converter.convert(deb_path, output_dir)
                loop_fb.exec()
            else:
                done_event2 = threading.Event()
                def on_fb_done2(success: bool, msg: str, pkg: Path | None) -> None:
                    with self._async_lock:
                        self._async_success = success
                        self._async_message = msg
                        self._async_pkg_path = pkg
                    done_event2.set()
                fallback_converter.finished.connect(on_fb_done2)
                fallback_converter.convert(deb_path, output_dir)
                done_event2.wait()


    def _convert_rpm(self, rpm_path: Path, work_dir: Path, meta: PackageMetadata) -> None:
        """Run RPM conversion."""
        self._async_success = False
        self._async_message = ""
        self._async_pkg_path = None

        if _HAS_PYQT6:
            self._rpm_converter = RpmConverter(self._tools, self)
            self._rpm_converter.output_line.connect(lambda msg: self._log("info", msg))
            loop = QEventLoop()
            def on_done(success: bool, msg: str, pkg: Path | None) -> None:
                with self._async_lock:
                    self._async_success = success
                    self._async_message = msg
                    self._async_pkg_path = pkg
                loop.quit()
            self._rpm_converter.finished.connect(on_done)
            self._rpm_converter.convert(rpm_path, work_dir, meta)
            loop.exec()
        else:
            from core.subprocess_converters import RpmConverterSubprocess
            converter = RpmConverterSubprocess(self._tools)
            converter.output_line.connect(lambda msg: self._log("info", msg))
            done_event = threading.Event()
            def on_done_sub(success: bool, msg: str, pkg: Path | None) -> None:
                with self._async_lock:
                    self._async_success = success
                    self._async_message = msg
                    self._async_pkg_path = pkg
                done_event.set()
            converter.finished.connect(on_done_sub)
            converter.convert(rpm_path, work_dir, meta)
            done_event.wait()

    @staticmethod
    def _on_rm_error(func, path, exc_info):
        """makepkg salt-okunur/root sahipli dosya birakabilir; yolun kendisine ve
        ebeveynine yazma izni verip silmeyi yeniden dene (EACCES temizligi)."""
        try:
            try:
                os.chmod(os.path.dirname(path), 0o700)
            except OSError:
                pass
            os.chmod(path, 0o700)
            func(path)
        except OSError:
            pass

    def _cleanup(self) -> None:
        """Remove temporary directory."""
        if self._temp_dir and self._temp_dir.exists():
            try:
                shutil.rmtree(self._temp_dir, onerror=self._on_rm_error)
                self._log("info", "Geçici dosyalar temizlendi")
            except OSError as exc:
                self._log("warning", tr("pipeline.temizlik_hatasi_exc", exc=exc))


    def _set_step(self, step: PipelineStep, status: str) -> None:
        label = STEP_LABELS[step]
        self.step_changed.emit(int(step), status)
        if status == "running":
            self._log("info", f"━━ {label} ━━")
        elif status == "done":
            self._log("success", tr("pipeline.label_tamamlandi", label=label))
        elif status == "error":
            self._log("error", tr("pipeline.label_basarisiz", label=label))
        elif status == "warning":
            self._log("warning", tr("pipeline.label_uyarilar_mevcut", label=label))

    def _log(self, level: str, message: str) -> None:
        self.log_message.emit(message, level)
        getattr(log, level if level != "success" else "info", log.info)(message)