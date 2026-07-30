"""Unit tests for installer scripts, completion files, and dialog classes."""

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestInstallerAndCompletions(unittest.TestCase):

    def test_install_script_exists_and_executable(self):
        install_script = PROJECT_ROOT / "scripts" / "install.sh"
        uninstall_script = PROJECT_ROOT / "scripts" / "uninstall.sh"
        self.assertTrue(install_script.is_file())
        self.assertTrue(uninstall_script.is_file())

    def test_completion_files_exist(self):
        bash_comp = PROJECT_ROOT / "data" / "completions" / "pkgforge.bash"
        zsh_comp = PROJECT_ROOT / "data" / "completions" / "_pkgforge"
        self.assertTrue(bash_comp.is_file())
        self.assertTrue(zsh_comp.is_file())

    def test_desktop_file_validity(self):
        desktop_file = PROJECT_ROOT / "data" / "pkgforge.desktop"
        self.assertTrue(desktop_file.is_file())
        content = desktop_file.read_text(encoding="utf-8")
        self.assertIn("Name=PkgForge", content)
        self.assertIn("Exec=pkgforge gui %f", content)


if __name__ == "__main__":
    unittest.main()
