"""Integration test: ERROR compatibility report must wait for a user decision.

Regression for the flow where an ERROR (not recommended) report returned
immediately, finishing the worker and cleaning up the temp dir (deleting the
converted package) before the user could choose Install Anyway. The ERROR
branch now blocks in _wait_for_decision() exactly like WARNING, so:
  - Install Anyway -> approve_install() -> install proceeds
  - Close          -> dismiss_install() -> pipeline aborts cleanly
"""

import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import QCoreApplication

from core.compatibility_checker import (
    CheckResult,
    CheckSeverity,
    CompatibilityReport,
)
from core.package_analyzer import PackageMetadata
from core.pipeline import ConversionPipeline
from core.security import SignatureResult


def _ensure_app() -> QCoreApplication:
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


def _error_report() -> CompatibilityReport:
    return CompatibilityReport(
        checks=[
            CheckResult(
                name="broken",
                severity=CheckSeverity.ERROR,
                message="fatal problem",
                details=["detail"],
            )
        ]
    )


def _meta() -> PackageMetadata:
    return PackageMetadata(
        name="hello",
        version="1.0.0-1",
        arch="amd64",
        arch_mapped="x86_64",
        description="test",
        file_list=["usr/bin/hello"],
    )


def _fake_setting(key, default=None):
    # Skip optional network/scan steps; keep dry_run off so the install path
    # is exercised (we mock _do_install itself).
    if key in ("clamav_scan", "aur_check"):
        return False
    return default


class TestErrorReportWaitsForDecision(unittest.TestCase):
    """An ERROR report must block until the UI records a decision."""

    def setUp(self):
        self.app = _ensure_app()
        self.pipeline = ConversionPipeline()
        self.deb = Path("/tmp/hello_1.0.0-1_amd64.deb")
        # Universal intake dosyanin varligina bakar; sahte de olsa dosya olmali
        # ki sonek (.deb) siniflandirmasi DEB donsun ve deb/rpm akisi calissin.
        self.deb.write_bytes(b"!<arch>fake")
        self.converted = Path("/tmp/hello-1.0.0-1-x86_64.pkg.tar.zst")
        self.installed = []

    def tearDown(self):
        try:
            self.deb.unlink(missing_ok=True)
        except OSError:
            pass

    def _patch_common(self):
        """Patch every stage before compatibility so the run reaches it."""
        # Arch toolchain gate bypass: _run_pipeline returns early when
        # required tools are missing (ubuntu CI); tests exercise the
        # decision flow, so provide a complete toolset explicitly.
        from config import ToolPaths
        self.pipeline._tools = ToolPaths(
            pacman="/usr/bin/pacman", makepkg="/usr/bin/makepkg",
            fakeroot="/usr/bin/fakeroot", file_cmd="/usr/bin/file",
            pkexec="/usr/bin/pkexec", bsdtar="/usr/bin/bsdtar")

        def fake_convert(deb_path, output_dir):
            self.pipeline._async_success = True
            self.pipeline._async_message = ""
            self.pipeline._async_pkg_path = self.converted
            self.pipeline._async_success = True
            self.pipeline._async_message = ""
            self.pipeline._async_pkg_path = self.converted

        def fake_install(pkg_path, pkg_name):
            self.installed.append((pkg_path, pkg_name))
            self.pipeline._result.success = True
            self.pipeline._result.message = "installed"

        return [
            patch("core.pipeline.validate_mime_type", return_value="application/vnd.debian.binary-package"),
            patch("core.pipeline.validate_file_size", return_value=None),
            patch("core.pipeline.sha256_hash", return_value="a" * 64),
            patch("core.pipeline.verify_deb_signature", return_value=SignatureResult()),
            patch("core.security.check_compression_bomb", return_value=None),
            patch("core.pipeline.analyze_package", return_value=_meta()),
            patch("core.pipeline.check_path_traversal", return_value=None),
            patch("core.pipeline.run_compatibility_checks", return_value=_error_report()),
            patch("i18n.load_setting", side_effect=_fake_setting),
            patch.object(ConversionPipeline, "_convert_deb", side_effect=fake_convert),
            patch.object(ConversionPipeline, "_do_install", side_effect=fake_install),
            patch.object(ConversionPipeline, "_record_history", return_value=None),
        ]

    def test_error_approve_proceeds_to_install(self):
        """Install Anyway on an ERROR report must run the install step."""
        patches = self._patch_common()
        for p in patches:
            p.start()
        try:
            # Deterministic: approve the moment the report opens (no timer race
            # on slow runners — the decision latches until the worker arrives).
            self.pipeline.compatibility_ready.connect(
                lambda *a: self.pipeline.approve_install())
            self.pipeline.run(self.deb)
        finally:
            for p in patches:
                p.stop()
        self.assertEqual(self.installed, [(self.converted, "hello")])
        self.assertTrue(self.pipeline._result.success)

    def test_error_dismiss_aborts_without_install(self):
        """Close on an ERROR report must abort cleanly without installing."""
        patches = self._patch_common()
        for p in patches:
            p.start()
        try:
            self.pipeline.compatibility_ready.connect(
                lambda *a: self.pipeline.dismiss_install())
            self.pipeline.run(self.deb)
        finally:
            for p in patches:
                p.stop()
        self.assertEqual(self.installed, [])
        self.assertFalse(self.pipeline._result.success)


if __name__ == "__main__":
    unittest.main()
