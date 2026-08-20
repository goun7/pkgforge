"""PkgForge — Main application window.

Assembles all UI components: header bar, drop zone, step progress,
log panel, queue sidebar, and coordinates with the conversion pipeline.
Supports multi-package queue, language switching, and theme changes.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, QSize, pyqtSlot
from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QStatusBar,
    QFrame,
    QScrollArea,
)

from config import APP_NAME, APP_VERSION, discover_tools
from core.compatibility_checker import CompatibilityReport, CheckSeverity
from core.pipeline import ConversionPipeline, PipelineResult
from core.queue_manager import QueueManager, QueueItemStatus
from i18n import tr, set_language, get_language, load_setting, init_language
from ui.drop_zone import DropZone
from ui.log_panel import LogPanel
from ui.loading_indicator import LoadingIndicator
from ui.about_dialog import AboutDialog
from ui.confirm_dialog import confirm_action
from ui.result_dialog import ResultDialog
from ui.settings_dialog import SettingsDialog
from ui.step_progress import StepProgress
from ui.styles import build_stylesheet, get_colors
from ui.resources.icons import (
    HEADER_URL, HEADER_HISTORY, HEADER_UPDATES, HEADER_SETTINGS, HEADER_ABOUT,
)

log = logging.getLogger(__name__)


def _render_svg_icon(svg_data: str, size: int = 20) -> QIcon:
    """Render an inline SVG string into a QIcon at *size* px."""
    renderer = QSvgRenderer(svg_data.encode("utf-8"))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def _load_app_icon() -> QIcon:
    """Load app icon from data/pkgforge.svg or fallback to inline."""
    svg_path = Path(__file__).parent.parent / "data" / "pkgforge.svg"
    if svg_path.is_file():
        svg_data = svg_path.read_text(encoding="utf-8")
    else:
        from ui.resources.icons import APP_ICON
        svg_data = APP_ICON

    renderer = QSvgRenderer(svg_data.encode("utf-8"))
    pixmap = QPixmap(128, 128)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self._pipeline: ConversionPipeline | None = None
        self._pipeline_thread: QThread | None = None
        self._tools = discover_tools()
        self._queue = QueueManager(self)
        self._queue.item_started.connect(self._on_queue_item_started)
        self._queue.all_finished.connect(self._on_queue_all_finished)
        self._queue.queue_changed.connect(self._on_queue_changed)
        self._setup_window()
        self._setup_ui()
        self._check_tools()

    def _setup_window(self) -> None:
        self.setWindowTitle(tr("app.window_title"))
        self.setMinimumSize(600, 450)
        self.resize(800, 600)
        self.setWindowIcon(_load_app_icon())

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Main content area ────────────────────────────────────
        main_col = QWidget()
        main_layout = QVBoxLayout(main_col)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Header Bar ───────────────────────────────────────────
        header = QWidget()
        header.setObjectName("headerBar")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 8, 20, 8)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)

        self._title_label = QLabel(APP_NAME)
        self._title_label.setObjectName("headerTitle")
        title_col.addWidget(self._title_label)

        self._subtitle_label = QLabel(f"v{APP_VERSION} — {tr('app.subtitle')}")
        self._subtitle_label.setObjectName("headerSubtitle")
        title_col.addWidget(self._subtitle_label)

        header_layout.addLayout(title_col)
        header_layout.addStretch()

        # ── Header action buttons (SVG icons + accessible names) ──
        accent = get_colors().TEAL
        icon_size = QSize(20, 20)

        def _make_header_btn(svg: str, tooltip: str, handler) -> QPushButton:
            btn = QPushButton()
            btn.setObjectName("headerBtn")
            btn.setFixedSize(44, 44)
            btn.setIcon(_render_svg_icon(svg.format(color=accent)))
            btn.setIconSize(icon_size)
            btn.setToolTip(tooltip)
            btn.setAccessibleName(tooltip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(handler)
            header_layout.addWidget(btn)
            return btn

        self._url_btn = _make_header_btn(HEADER_URL, tr("url.title"), self._show_url_dialog)
        self._history_btn = _make_header_btn(HEADER_HISTORY, tr("history.title"), self._show_history)
        self._updates_btn = _make_header_btn(HEADER_UPDATES, tr("updates.title"), self._check_upstream_updates)
        self._settings_btn = _make_header_btn(HEADER_SETTINGS, tr("settings.title"), self._show_settings)
        self._about_btn = _make_header_btn(HEADER_ABOUT, tr("about.title"), self._show_about)

        main_layout.addWidget(header)

        # ── Content Area ─────────────────────────────────────────
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 12)
        content_layout.setSpacing(16)

        self._step_progress = StepProgress()
        self._step_progress.setVisible(False)
        content_layout.addWidget(self._step_progress)

        self._drop_zone = DropZone()
        self._drop_zone.files_dropped.connect(self._on_files_dropped)
        content_layout.addWidget(self._drop_zone, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._cancel_btn = QPushButton(tr("btn.cancel"))
        self._cancel_btn.setObjectName("dangerBtn")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.setVisible(False)
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._cancel_btn)

        self._new_btn = QPushButton(tr("btn.new"))
        self._new_btn.setObjectName("primaryBtn")
        self._new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_btn.setVisible(False)
        self._new_btn.clicked.connect(self._reset_ui)
        btn_row.addWidget(self._new_btn)

        content_layout.addLayout(btn_row)

        self._log_panel = LogPanel()
        content_layout.addWidget(self._log_panel)

        main_layout.addWidget(content, stretch=1)
        root_layout.addWidget(main_col, stretch=3)

        # ── Queue Sidebar ────────────────────────────────────────
        self._queue_sidebar = QWidget()
        self._queue_sidebar.setObjectName("queueSidebar")
        self._queue_sidebar.setFixedWidth(220)
        self._queue_sidebar.setVisible(False)

        queue_layout = QVBoxLayout(self._queue_sidebar)
        queue_layout.setContentsMargins(8, 12, 8, 12)
        queue_layout.setSpacing(8)

        queue_title = QLabel(tr("queue.title"))
        queue_title.setStyleSheet("font-weight: 700; font-size: 13px;")
        queue_layout.addWidget(queue_title)

        queue_scroll = QScrollArea()
        queue_scroll.setWidgetResizable(True)
        queue_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._queue_list_widget = QWidget()
        self._queue_list_layout = QVBoxLayout(self._queue_list_widget)
        self._queue_list_layout.setSpacing(4)
        self._queue_list_layout.setContentsMargins(0, 0, 0, 0)
        self._queue_list_layout.addStretch()

        queue_scroll.setWidget(self._queue_list_widget)
        queue_layout.addWidget(queue_scroll, stretch=1)

        root_layout.addWidget(self._queue_sidebar)

        # ── Status Bar ───────────────────────────────────────────
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage(tr("status.ready"))

    def _check_tools(self) -> None:
        missing = self._tools.missing_required
        if missing:
            self._log_panel.append_log(
                tr("tools.critical_missing", tools=", ".join(missing)), "error"
            )
            self._status_bar.showMessage(f"⚠ {', '.join(missing)}")

        optional_missing = self._tools.missing_optional
        if optional_missing:
            self._log_panel.append_log(
                tr("tools.optional_missing", tools=", ".join(optional_missing)), "warning"
            )

        if self._tools.debtap:
            debtap_db = Path("/var/cache/debtap/debian-main-packages-files")
            if not debtap_db.exists():
                self._log_panel.append_log(tr("tools.debtap_db"), "warning")

    # ── Queue management ─────────────────────────────────────────

    @pyqtSlot(list)
    def _on_files_dropped(self, file_paths: list[Path]) -> None:
        self._queue.add_files(file_paths)
        count = self._queue.total

        if count > 1:
            self._queue_sidebar.setVisible(True)
            self._drop_zone.set_queue_info(count)
        elif count == 1:
            item = self._queue.items[0]
            self._drop_zone.set_file_info(item.name, item.pkg_type)

        self._start_next_in_queue()

    def _start_next_in_queue(self) -> None:
        """Start processing the next pending item in the queue."""
        next_item = self._queue.get_next()
        if next_item is None:
            return

        idx, item = next_item
        self._queue.mark_started(idx)

        self._log_panel.clear()
        self._step_progress.reset()
        self._step_progress.setVisible(True)
        self._cancel_btn.setVisible(True)
        self._new_btn.setVisible(False)
        self._drop_zone.set_processing(True)

        if self._queue.total > 1:
            self._status_bar.showMessage(
                tr("status.queue", current=idx + 1, total=self._queue.total)
            )
        else:
            self._status_bar.showMessage(tr("status.processing", name=item.name))

        self._pipeline = ConversionPipeline()
        self._pipeline.step_changed.connect(self._on_step_changed)
        self._pipeline.progress.connect(self._on_progress)
        self._pipeline.log_message.connect(self._on_log)
        self._pipeline.compatibility_ready.connect(self._on_compatibility_ready)
        self._pipeline.finished.connect(
            lambda result, i=idx: self._on_pipeline_finished(result, i)
        )

        self._pipeline_thread = QThread()
        self._pipeline.moveToThread(self._pipeline_thread)
        self._pipeline_thread.started.connect(lambda: self._pipeline.run(item.file_path))
        self._pipeline_thread.start()

    @pyqtSlot(list)
    def _on_queue_changed(self, items: list) -> None:
        """Rebuild queue sidebar list."""
        # Clear existing items
        while self._queue_list_layout.count() > 1:
            child = self._queue_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        status_icons = {
            QueueItemStatus.PENDING: "⏳",
            QueueItemStatus.PROCESSING: "🔄",
            QueueItemStatus.DONE: "✅",
            QueueItemStatus.ERROR: "❌",
            QueueItemStatus.CANCELLED: "⊘",
        }

        for i, item in enumerate(items):
            item_widget = QFrame()
            item_widget.setObjectName(
                "queueItemActive" if item.status == QueueItemStatus.PROCESSING else "queueItem"
            )
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(6, 4, 6, 4)

            icon = QLabel(status_icons.get(item.status, "?"))
            item_layout.addWidget(icon)

            name_label = QLabel(item.name)
            name_label.setStyleSheet("font-size: 11px;")
            name_label.setToolTip(str(item.file_path))
            item_layout.addWidget(name_label, stretch=1)

            # Finished items with a report can be reopened (clickable history)
            if item.status in (QueueItemStatus.DONE, QueueItemStatus.ERROR) and getattr(
                item.result, "compatibility", None
            ):
                view_btn = QPushButton(tr("queue.view_result"))
                view_btn.setObjectName("logToggle")
                view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                view_btn.clicked.connect(lambda _=False, idx=i: self._show_queue_result(idx))
                item_layout.addWidget(view_btn)

            self._queue_list_layout.insertWidget(i, item_widget)

    def _show_queue_result(self, index: int) -> None:
        """Reopen the compatibility report for a finished queue item."""
        items = self._queue.items
        if not (0 <= index < len(items)):
            return
        result = items[index].result
        if not result or not getattr(result, "compatibility", None):
            return
        dialog = ResultDialog(
            report=result.compatibility,
            metadata=result.metadata,
            signature=result.signature,
            sha256=result.sha256,
            show_distrobox=False,
            parent=self,
        )
        dialog.exec()

    @pyqtSlot(int)
    def _on_queue_item_started(self, index: int) -> None:
        pass  # Queue UI already updated via queue_changed

    @pyqtSlot()
    def _on_queue_all_finished(self) -> None:
        summary = self._queue.get_summary()
        done = summary.get("done", 0)
        errors = summary.get("error", 0)
        total = done + errors
        self._status_bar.showMessage(tr("queue.completed", done=done, total=total))
        self._new_btn.setVisible(True)

    # ── Pipeline control ─────────────────────────────────────────

    @pyqtSlot()
    def _on_cancel(self) -> None:
        if self._pipeline:
            self._pipeline.cancel()
        self._status_bar.showMessage(tr("status.cancelling"))

    @pyqtSlot(int, str)
    def _on_step_changed(self, step: int, status: str) -> None:
        self._step_progress.set_step_status(step, status)

    @pyqtSlot(int)
    def _on_progress(self, value: int) -> None:
        self._step_progress.set_progress(value)

    @pyqtSlot(str, str)
    def _on_log(self, message: str, level: str) -> None:
        self._log_panel.append_log(message, level)

    @pyqtSlot(object)
    def _on_compatibility_ready(self, report: CompatibilityReport) -> None:
        result = self._pipeline._result if self._pipeline else None

        show_distrobox = (
            self._tools.has_distrobox
            and load_setting("distrobox_fallback", False)
            and report.overall == CheckSeverity.ERROR
        )

        dialog = ResultDialog(
            report=report,
            metadata=result.metadata if result else None,
            signature=result.signature if result else None,
            sha256=result.sha256 if result else "",
            show_distrobox=show_distrobox,
            parent=self,
        )

        def on_approved() -> None:
            # Wakes the worker thread blocked in _wait_for_decision(); the
            # install itself runs on that thread, never on the UI thread.
            if self._pipeline:
                self._pipeline.approve_install()

        def on_distrobox() -> None:
            # The container fallback handles installation; release the worker
            # without approving a host install.
            if self._pipeline:
                self._pipeline.dismiss_install(
                    "Kurulum distrobox konteynerine yönlendirildi"
                )
            if result and result.metadata:
                self._run_distrobox_fallback(result)

        dialog.install_approved.connect(on_approved)
        dialog.distrobox_requested.connect(on_distrobox)
        dialog.exec()

        if dialog.result() == 0:
            # User closed the report without approving: release the blocked
            # worker so the pipeline can finish and clean up.
            if self._pipeline:
                self._pipeline.dismiss_install()
            self._finish_with_message(tr("pipe.cancelled"), success=False)

    def _run_distrobox_fallback(self, result: PipelineResult) -> None:
        """Run distrobox container installation."""
        from core.distrobox_fallback import DistroboxFallback

        meta = result.metadata
        original = result.original_file
        if not meta or not original or not original.is_file():
            return

        pkg_type = "deb" if original.suffix.lower() == ".deb" else "rpm"
        fb = DistroboxFallback(self._tools, self)
        fb.output_line.connect(lambda msg: self._log_panel.append_log(msg, "info"))

        def on_done(success: bool, msg: str) -> None:
            level = "success" if success else "error"
            self._log_panel.append_log(msg, level)
            self._status_bar.showMessage(msg)

        fb.finished.connect(on_done)
        fb.install_in_container(original, meta.name, pkg_type)

    def _on_pipeline_finished(self, result: PipelineResult, queue_index: int = -1) -> None:
        if self._pipeline_thread:
            self._pipeline_thread.quit()
            self._pipeline_thread.wait()

        self._cancel_btn.setVisible(False)
        self._drop_zone.set_processing(False)

        # Update queue
        if queue_index >= 0:
            self._queue.mark_finished(queue_index, result.success, result.message, result)

        if result.success:
            self._step_progress.set_progress(100)
            self._status_bar.showMessage(f"✓ {result.message}")
            self._log_panel.append_log(result.message, "success")
        else:
            msg = result.message or tr("pipe.failed_generic")
            self._status_bar.showMessage(f"✗ {msg}")
            self._log_panel.append_log(msg, "error" if not result.compatibility else "warning")

        # Process next in queue
        if self._queue.pending_count > 0:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1000, self._start_next_in_queue)
        else:
            self._new_btn.setVisible(True)

    def _finish_with_message(self, message: str, success: bool) -> None:
        self._cancel_btn.setVisible(False)
        self._new_btn.setVisible(True)
        self._drop_zone.set_processing(False)
        level = "success" if success else "warning"
        self._log_panel.append_log(message, level)
        self._status_bar.showMessage(message)

    def _reset_ui(self) -> None:
        self._step_progress.reset()
        self._step_progress.setVisible(False)
        self._log_panel.clear()
        self._drop_zone.set_processing(False)
        self._cancel_btn.setVisible(False)
        self._new_btn.setVisible(False)
        self._queue_sidebar.setVisible(False)
        self._queue.clear()
        self._status_bar.showMessage(tr("status.ready"))

    def _show_url_dialog(self) -> None:
        """Open paste & download URL dialog."""
        try:
            from ui.url_dialog import UrlDialog
            dialog = UrlDialog(self)
            dialog.file_downloaded.connect(lambda pkg_path: self._on_files_dropped([pkg_path]))
            dialog.exec()
        except Exception as exc:
            log.exception("Error opening UrlDialog: %s", exc)
            QMessageBox.critical(self, tr("url.title"), str(exc))

    def _show_history(self) -> None:
        """Open history & package manager dialog."""
        try:
            from ui.history_dialog import HistoryDialog
            dialog = HistoryDialog(self)
            dialog.exec()
        except Exception as exc:
            log.exception("Error opening HistoryDialog: %s", exc)
            QMessageBox.critical(self, tr("history.title"), str(exc))

    def _check_upstream_updates(self) -> None:
        """Check all saved URLs for upstream updates."""
        try:
            from core.upstream_tracker import check_all_installed_updates
            results = check_all_installed_updates()
            if not results:
                QMessageBox.information(self, tr("updates.title"), tr("updates.no_pkgs"))
                return

            updates = [r for r in results if r.has_update]
            if updates:
                lines = "\n".join([f"• {r.package_name}: {r.detail}" for r in updates])
                msg = tr("updates.found").format(count=len(updates), details=lines)
                QMessageBox.information(self, tr("updates.title"), msg)
            else:
                QMessageBox.information(self, tr("updates.title"), tr("updates.up_to_date"))
        except Exception as exc:
            log.exception("Error checking updates: %s", exc)
            QMessageBox.critical(self, tr("updates.title"), str(exc))

    # ── Settings ─────────────────────────────────────────────────

    def _show_settings(self) -> None:
        dialog = SettingsDialog(self)
        dialog.settings_changed.connect(self._apply_settings)
        dialog.exec()

    @pyqtSlot(dict)
    def _apply_settings(self, settings: dict) -> None:
        # Language change
        new_lang = settings.get("language", get_language())
        if new_lang != get_language():
            set_language(new_lang)
            self._retranslate_ui()

        # Theme change
        new_theme = settings.get("theme", "dark")
        app = QApplication.instance()
        if app:
            app.setStyleSheet(build_stylesheet(new_theme))

    def _retranslate_ui(self) -> None:
        """Update all UI strings after language change."""
        self.setWindowTitle(tr("app.window_title"))
        self._subtitle_label.setText(f"v{APP_VERSION} — {tr('app.subtitle')}")
        self._cancel_btn.setText(tr("btn.cancel"))
        self._new_btn.setText(tr("btn.new"))
        self._status_bar.showMessage(tr("status.ready"))

        if hasattr(self, "_url_btn"):
            self._url_btn.setToolTip(tr("url.title"))
            self._history_btn.setToolTip(tr("history.title"))
            self._updates_btn.setToolTip(tr("updates.title"))
            self._settings_btn.setToolTip(tr("settings.title"))
            self._about_btn.setToolTip(tr("about.title"))

        self._drop_zone.retranslate()
        self._step_progress.retranslate()
        self._log_panel.retranslate()

    # ── About dialog ─────────────────────────────────────────────

    def _show_about(self) -> None:
        from ui.about_dialog import AboutDialog
        dialog = AboutDialog(self)
        dialog.exec()

    # ── Close event ──────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        if self._pipeline_thread and self._pipeline_thread.isRunning():
            reply = QMessageBox.question(
                self,
                tr("exit.title"),
                tr("exit.message"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            if self._pipeline:
                self._pipeline.cancel()
            if self._pipeline_thread:
                self._pipeline_thread.quit()
                self._pipeline_thread.wait(3000)

        event.accept()
