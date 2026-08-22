"""PkgForge — Result and compatibility report dialog.

Shows check results with expandable details, distrobox fallback
option, and Approve/Cancel actions.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.compatibility_checker import CheckResult, CheckSeverity, CompatibilityReport
from core.package_analyzer import PackageMetadata
from core.security import SignatureResult
from i18n import tr
from ui.styles import Colors


class ResultDialog(QDialog):
    """Dialog showing compatibility report and install decision.

    Signals:
        install_approved()       – user chose to install.
        distrobox_requested()    – user chose distrobox fallback.
    """

    install_approved = pyqtSignal()
    distrobox_requested = pyqtSignal()

    def __init__(
        self,
        report: CompatibilityReport,
        metadata: PackageMetadata | None = None,
        signature: SignatureResult | None = None,
        sha256: str = "",
        show_distrobox: bool = False,
        read_only: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._report = report
        self._metadata = metadata
        self._signature = signature
        self._sha256 = sha256
        self._show_distrobox = show_distrobox
        # read_only: the report is being reopened after the pipeline has
        # already finished and cleaned up the converted package, so there
        # is nothing left to install — hide the install actions to avoid
        # a dead button.
        self._read_only = read_only
        self.setWindowTitle(tr("result.window_title"))
        self.setMinimumSize(560, 480)
        self.setMaximumSize(800, 700)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # ── Title ────────────────────────────────────────────────
        overall = self._report.overall
        icon_map = {
            CheckSeverity.PASS: ("✅", tr("result.title_pass"), Colors.TEAL),
            CheckSeverity.WARNING: ("⚠️", tr("result.title_warning"), Colors.ORANGE),
            CheckSeverity.ERROR: ("❌", tr("result.title_error"), Colors.RED),
        }
        icon, title_text, color = icon_map[overall]

        title_row = QHBoxLayout()
        icon_label = QLabel(icon)
        icon_label.setFont(QFont("", 28))
        title_row.addWidget(icon_label)

        title = QLabel(title_text)
        title.setObjectName("resultTitle")
        title.setStyleSheet(f"color: {color};")
        title_row.addWidget(title)
        title_row.addStretch()

        # ── Compatibility grade badge (A–F) ──────────────────────
        grade = self._report.grade
        grade_color = {
            "A": Colors.TEAL, "B": Colors.TEAL,
            "C": Colors.ORANGE,
            "D": Colors.RED, "F": Colors.RED,
        }.get(grade, Colors.ORANGE)
        grade_badge = QLabel(grade)
        grade_badge.setFixedSize(40, 40)
        grade_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grade_badge.setToolTip(tr("result.grade_tip"))
        grade_badge.setAccessibleName(tr("result.grade_tip"))
        grade_badge.setStyleSheet(
            f"background: {grade_color}; color: #0a0e1a; border-radius: 20px; "
            f"font-size: 20px; font-weight: 800;"
        )
        title_row.addWidget(grade_badge)
        layout.addLayout(title_row)

        # ── Package info ─────────────────────────────────────────
        if self._metadata:
            info_card = self._build_info_card()
            layout.addWidget(info_card)

        # ── Security info ────────────────────────────────────────
        if self._signature or self._sha256:
            security_card = self._build_security_card()
            layout.addWidget(security_card)

        # ── Files to be installed (what will change) ─────────────
        if self._metadata and self._metadata.file_list:
            layout.addWidget(self._build_files_card())

        # ── Check results (scrollable) ───────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(8)

        for check in self._report.checks:
            card = self._build_check_card(check)
            scroll_layout.addWidget(card)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)

        # ── Distrobox fallback ───────────────────────────────────
        if self._show_distrobox and overall == CheckSeverity.ERROR:
            distrobox_card = QFrame()
            distrobox_card.setObjectName("infoCard")
            distrobox_card.setStyleSheet("border-color: #3742fa;")
            db_layout = QVBoxLayout(distrobox_card)

            db_title = QLabel(tr("result.distrobox_offer"))
            db_title.setStyleSheet("font-weight: bold; font-size: 14px;")
            db_layout.addWidget(db_title)

            db_desc = QLabel(tr("result.distrobox_desc"))
            db_desc.setWordWrap(True)
            db_layout.addWidget(db_desc)

            db_btn = QPushButton(tr("result.distrobox_btn"))
            db_btn.setObjectName("primaryBtn")
            db_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            db_btn.clicked.connect(self._on_distrobox)
            db_layout.addWidget(db_btn)

            layout.addWidget(distrobox_card)

        # ── Action buttons ───────────────────────────────────────
        btn_layout = QHBoxLayout()

        export_btn = QPushButton(tr("result.export_report"))
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.clicked.connect(self._on_export_report)
        btn_layout.addWidget(export_btn)
        btn_layout.addStretch()

        if self._read_only:
            # Reopened after the pipeline finished: the converted package was
            # already cleaned up, so there is nothing to install. Show only
            # Close to avoid a dead Install button.
            close_btn = QPushButton(tr("btn.close"))
            close_btn.clicked.connect(self.reject)
            btn_layout.addWidget(close_btn)
        elif overall == CheckSeverity.PASS:
            install_btn = QPushButton(tr("btn.install"))
            install_btn.setObjectName("primaryBtn")
            install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            install_btn.clicked.connect(self._on_approve)
            btn_layout.addWidget(install_btn)
        else:
            # WARNING and ERROR both offer Close + Install Anyway. The user
            # keeps the final say even when installation is not
            # recommended (ERROR); previously ERROR showed only Close,
            # which left no way to proceed with a not-recommended package.
            close_btn = QPushButton(tr("btn.close"))
            close_btn.clicked.connect(self.reject)
            btn_layout.addWidget(close_btn)

            install_btn = QPushButton(tr("btn.install_anyway"))
            install_btn.setObjectName("dangerBtn")
            install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            install_btn.clicked.connect(self._on_approve)
            btn_layout.addWidget(install_btn)

        layout.addLayout(btn_layout)

    def _on_approve(self) -> None:
        self.install_approved.emit()
        self.accept()

    def _on_distrobox(self) -> None:
        self.distrobox_requested.emit()
        self.accept()

    def _on_export_report(self) -> None:
        """Save the compatibility report as a JSON file."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox

        from core.report_export import save_report_json

        pkg_name = self._metadata.name if self._metadata else "package"
        default_name = f"pkgforge-report-{pkg_name}.json"
        path, _ = QFileDialog.getSaveFileName(
            self, tr("result.export_report"), default_name, "JSON (*.json)"
        )
        if not path:
            return
        try:
            save_report_json(
                path,
                self._report,
                metadata=self._metadata,
                sha256=self._sha256,
                signature=self._signature,
            )
            QMessageBox.information(
                self, tr("common.success"), tr("result.export_done", path=path)
            )
        except OSError as exc:
            QMessageBox.critical(self, tr("common.error"), str(exc))

    def _build_files_card(self) -> QWidget:
        """Collapsible preview of the files this package will install."""
        meta = self._metadata
        assert meta is not None
        files = [f for f in meta.file_list if not f.endswith("/")]

        card = QFrame()
        card.setObjectName("infoCard")
        layout = QVBoxLayout(card)
        layout.setSpacing(4)

        toggle_btn = QPushButton("▶ " + tr("result.files_title", count=len(files)))
        toggle_btn.setObjectName("logToggle")
        toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(toggle_btn)

        preview = QLabel("\n".join(files[:25]) + ("\n…" if len(files) > 25 else ""))
        preview.setStyleSheet("font-family: monospace; font-size: 11px; padding: 4px;")
        preview.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        preview.setVisible(False)
        layout.addWidget(preview)

        # NOTE: clicked() emits a bool (checked state). The leading _checked
        # parameter absorbs it so it cannot clobber the captured widget refs —
        # without it, pressing Enter/Space on this focused button crashed the
        # whole app (AttributeError inside Qt's event dispatch -> abort()).
        def toggle(_checked: bool = False, w=preview, b=toggle_btn) -> None:
            vis = not w.isVisible()
            w.setVisible(vis)
            b.setText(("▼ " if vis else "▶ ") + tr("result.files_title", count=len(files)))

        toggle_btn.clicked.connect(toggle)
        return card

    # ── Card builders ────────────────────────────────────────────

    def _build_info_card(self) -> QWidget:
        meta = self._metadata
        assert meta is not None

        card = QFrame()
        card.setObjectName("infoCard")
        layout = QVBoxLayout(card)
        layout.setSpacing(4)

        fields = [
            (tr("result.pkg_label"), meta.name),
            (tr("result.ver_label"), meta.version),
            (tr("result.arch_label"), f"{meta.arch} → {meta.arch_mapped}"),
            (tr("result.desc_label"), meta.description[:80] if meta.description else "—"),
        ]

        if meta.already_installed:
            fields.append((tr("result.installed_label"), f"✓ {meta.installed_version}"))

        for label_text, value_text in fields:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setObjectName("infoLabel")
            lbl.setFixedWidth(100)
            row.addWidget(lbl)

            val = QLabel(str(value_text))
            val.setObjectName("infoValue")
            val.setWordWrap(True)
            row.addWidget(val, stretch=1)
            layout.addLayout(row)

        return card

    def _build_security_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("infoCard")
        layout = QVBoxLayout(card)
        layout.setSpacing(4)

        sec_title = QLabel(tr("result.security_title"))
        sec_title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(sec_title)

        if self._sha256:
            row = QHBoxLayout()
            lbl = QLabel(tr("result.sha_label"))
            lbl.setObjectName("infoLabel")
            lbl.setFixedWidth(100)
            row.addWidget(lbl)
            val = QLabel(self._sha256[:32] + "...")
            val.setObjectName("infoValue")
            val.setStyleSheet("font-family: monospace; font-size: 11px;")
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row.addWidget(val, stretch=1)
            layout.addLayout(row)

        if self._signature:
            row = QHBoxLayout()
            lbl = QLabel(tr("result.sig_label"))
            lbl.setObjectName("infoLabel")
            lbl.setFixedWidth(100)
            row.addWidget(lbl)

            sig_color = Colors.TEAL if self._signature.has_signature else Colors.ORANGE
            val = QLabel(self._signature.detail)
            val.setObjectName("infoValue")
            val.setStyleSheet(f"color: {sig_color};")
            val.setWordWrap(True)
            row.addWidget(val, stretch=1)
            layout.addLayout(row)

        return card

    def _build_check_card(self, check: CheckResult) -> QWidget:
        card = QFrame()
        card.setObjectName("infoCard")
        layout = QVBoxLayout(card)
        layout.setSpacing(4)

        header = QHBoxLayout()
        severity_icons = {
            CheckSeverity.PASS: ("✅", Colors.TEAL),
            CheckSeverity.WARNING: ("⚠️", Colors.ORANGE),
            CheckSeverity.ERROR: ("❌", Colors.RED),
        }
        sev_icon, sev_color = severity_icons[check.severity]

        icon_lbl = QLabel(sev_icon)
        header.addWidget(icon_lbl)

        name_lbl = QLabel(check.name)
        name_lbl.setStyleSheet(f"font-weight: bold; color: {sev_color};")
        header.addWidget(name_lbl)
        header.addStretch()
        layout.addLayout(header)

        msg_lbl = QLabel(check.message)
        msg_lbl.setWordWrap(True)
        layout.addWidget(msg_lbl)

        if check.details:
            details_btn = QPushButton(tr("result.details_btn", count=len(check.details)))
            details_btn.setObjectName("logToggle")
            details_btn.setCursor(Qt.CursorShape.PointingHandCursor)

            details_widget = QLabel("\n".join(check.details[:15]))
            details_widget.setStyleSheet("font-family: monospace; font-size: 11px; padding: 8px;")
            details_widget.setWordWrap(True)
            details_widget.setVisible(False)

            # Leading _checked absorbs clicked(bool); see note on toggle() above.
            def toggle_details(_checked: bool = False, w=details_widget, b=details_btn, c=check) -> None:
                vis = not w.isVisible()
                w.setVisible(vis)
                prefix = "▼" if vis else "▶"
                b.setText(f"{prefix} " + tr("result.details_btn", count=len(c.details)))

            details_btn.clicked.connect(toggle_details)
            layout.addWidget(details_btn)
            layout.addWidget(details_widget)

        return card
