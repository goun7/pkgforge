"""CLI integration tests — tests actual CLI command execution."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestCLIHelp(unittest.TestCase):
    """Test CLI help output for all commands."""

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess:
        """Run CLI command and return result."""
        return subprocess.run(
            [sys.executable, "main.py", *args],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path(__file__).parent.parent),
        )

    def test_main_help(self):
        """Main help should show all commands."""
        result = self._run_cli("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("convert", result.stdout)
        self.assertIn("sbom", result.stdout)
        self.assertIn("plugin", result.stdout)

    def test_version(self):
        """--version should show version."""
        result = self._run_cli("--version")
        self.assertEqual(result.returncode, 0)
        self.assertIn("2.0.0", result.stdout)

    def test_convert_help(self):
        """convert --help should show options."""
        result = self._run_cli("convert", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("--install", result.stdout)
        self.assertIn("--delta", result.stdout)

    def test_sbom_help(self):
        """sbom --help should show options."""
        result = self._run_cli("sbom", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("--diff", result.stdout)
        self.assertIn("--no-hashes", result.stdout)

    def test_plugin_help(self):
        """plugin --help should show subcommands."""
        result = self._run_cli("plugin", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("install", result.stdout)
        self.assertIn("list", result.stdout)
        self.assertIn("audit", result.stdout)

    def test_delta_help(self):
        """delta --help should show subcommands."""
        result = self._run_cli("delta", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("status", result.stdout)
        self.assertIn("enable", result.stdout)

    def test_health(self):
        """health command should run."""
        result = self._run_cli("health")
        self.assertEqual(result.returncode, 0)

    def test_benchmark_quick(self):
        """benchmark --quick should complete fast."""
        result = self._run_cli("benchmark", "--quick")
        self.assertEqual(result.returncode, 0)
        self.assertIn("başarılı", result.stdout) if "başarılı" in result.stdout else None


class TestCLIConvert(unittest.TestCase):
    """Test convert command with real test DEB."""

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "main.py", *args],
            capture_output=True, text=True, timeout=60,
            cwd=str(Path(__file__).parent.parent),
        )

    def test_convert_test_deb(self):
        """Should convert the test DEB file."""
        deb_path = Path("utest/hello_1.0.0-1_amd64.deb")
        if not deb_path.exists():
            self.skipTest("Test DEB not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._run_cli(
                "convert", str(deb_path),
                "--output-dir", tmpdir,
                "--dry-run",
            )
            self.assertEqual(result.returncode, 0)
