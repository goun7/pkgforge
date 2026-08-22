"""Tests for core/from_source version/license/build-system detection.

All hermetic: temp dirs with synthetic project files.
"""

import tempfile
import unittest
from pathlib import Path


class TestExtractVersionCargo(unittest.TestCase):

    def test_cargo_version(self):
        from core.from_source import _extract_version_from_cargo
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "Cargo.toml").write_text(
                "[package]\nname = \"myapp\"\nversion = \"1.2.3\"\n",
                encoding="utf-8",
            )
            self.assertEqual(_extract_version_from_cargo(Path(td)), "1.2.3")

    def test_no_cargo(self):
        from core.from_source import _extract_version_from_cargo
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(_extract_version_from_cargo(Path(td)))

    def test_cargo_no_version(self):
        from core.from_source import _extract_version_from_cargo
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "Cargo.toml").write_text("[package]\nname = \"x\"\n", encoding="utf-8")
            self.assertIsNone(_extract_version_from_cargo(Path(td)))


class TestExtractVersionCmake(unittest.TestCase):

    def test_project_version(self):
        from core.from_source import _extract_version_from_cmake
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.10)\n"
                "project(myapp VERSION 2.5.1 LANGUAGES C)\n",
                encoding="utf-8",
            )
            self.assertEqual(_extract_version_from_cmake(Path(td)), "2.5.1")

    def test_set_version(self):
        from core.from_source import _extract_version_from_cmake
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "CMakeLists.txt").write_text(
                "set(PROJECT_VERSION \"3.0.0\")\n", encoding="utf-8"
            )
            self.assertEqual(_extract_version_from_cmake(Path(td)), "3.0.0")

    def test_no_cmake(self):
        from core.from_source import _extract_version_from_cmake
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(_extract_version_from_cmake(Path(td)))


class TestExtractVersionMeson(unittest.TestCase):

    def test_meson_version(self):
        from core.from_source import _extract_version_from_meson
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "meson.build").write_text(
                "project(\"myapp\", \"c\", version: \"4.1.0\")\n", encoding="utf-8"
            )
            self.assertEqual(_extract_version_from_meson(Path(td)), "4.1.0")

    def test_no_meson(self):
        from core.from_source import _extract_version_from_meson
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(_extract_version_from_meson(Path(td)))


class TestExtractVersionPyproject(unittest.TestCase):

    def test_pyproject_version(self):
        from core.from_source import _extract_version_from_pyproject
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "pyproject.toml").write_text(
                "[project]\nname = \"myapp\"\nversion = \"0.9.0\"\n", encoding="utf-8"
            )
            self.assertEqual(_extract_version_from_pyproject(Path(td)), "0.9.0")

    def test_no_pyproject(self):
        from core.from_source import _extract_version_from_pyproject
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(_extract_version_from_pyproject(Path(td)))


class TestExtractVersionFile(unittest.TestCase):

    def test_VERSION_file(self):
        from core.from_source import _extract_version_from_file
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "VERSION").write_text("5.6.7\n", encoding="utf-8")
            self.assertEqual(_extract_version_from_file(Path(td)), "5.6.7")

    def test_version_txt(self):
        from core.from_source import _extract_version_from_file
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "version.txt").write_text("1.0.0", encoding="utf-8")
            self.assertEqual(_extract_version_from_file(Path(td)), "1.0.0")

    def test_no_version_file(self):
        from core.from_source import _extract_version_from_file
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(_extract_version_from_file(Path(td)))


class TestDetectLicense(unittest.TestCase):

    def test_mit(self):
        from core.from_source import _detect_license
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "LICENSE").write_text(
                "MIT License\n\nPermission is hereby granted, free of charge...",
                encoding="utf-8",
            )
            self.assertEqual(_detect_license(Path(td)), "MIT")

    def test_gpl3(self):
        from core.from_source import _detect_license
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "COPYING").write_text(
                "GNU GENERAL PUBLIC LICENSE, Version 3...", encoding="utf-8"
            )
            self.assertEqual(_detect_license(Path(td)), "GPL-3.0-or-later")

    def test_apache(self):
        from core.from_source import _detect_license
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "LICENSE").write_text("Apache License, Version 2.0", encoding="utf-8")
            self.assertEqual(_detect_license(Path(td)), "Apache-2.0")

    def test_cargo_license(self):
        from core.from_source import _detect_license
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "Cargo.toml").write_text(
                "[package]\nlicense = \"BSD-3-Clause\"\n", encoding="utf-8"
            )
            self.assertEqual(_detect_license(Path(td)), "BSD-3-Clause")

    def test_package_json_license(self):
        from core.from_source import _detect_license
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "package.json").write_text(
                "{\"license\": \"ISC\"}", encoding="utf-8"
            )
            self.assertEqual(_detect_license(Path(td)), "ISC")

    def test_default_gpl(self):
        from core.from_source import _detect_license
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(_detect_license(Path(td)), "GPL-3.0-or-later")


class TestDetectPackageType(unittest.TestCase):

    def test_python_setup_py(self):
        from core.from_source import _detect_python_package
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "setup.py").write_text("", encoding="utf-8")
            self.assertTrue(_detect_python_package(Path(td)))

    def test_python_pyproject(self):
        from core.from_source import _detect_python_package
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "pyproject.toml").write_text("", encoding="utf-8")
            self.assertTrue(_detect_python_package(Path(td)))

    def test_not_python(self):
        from core.from_source import _detect_python_package
        with tempfile.TemporaryDirectory() as td:
            self.assertFalse(_detect_python_package(Path(td)))

    def test_node_with_bin(self):
        from core.from_source import _detect_node_package
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "package.json").write_text(
                "{\"bin\": {\"app\": \"cli.js\"}}", encoding="utf-8"
            )
            self.assertTrue(_detect_node_package(Path(td)))

    def test_node_plain_json(self):
        from core.from_source import _detect_node_package
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "package.json").write_text("{\"name\": \"x\"}", encoding="utf-8")
            self.assertFalse(_detect_node_package(Path(td)))

    def test_no_package_json(self):
        from core.from_source import _detect_node_package
        with tempfile.TemporaryDirectory() as td:
            self.assertFalse(_detect_node_package(Path(td)))


class TestDetectBinaryName(unittest.TestCase):

    def test_cargo_name(self):
        from core.from_source import _detect_binary_name
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "Cargo.toml").write_text(
                "[package]\nname = \"rustapp\"\n", encoding="utf-8"
            )
            self.assertEqual(_detect_binary_name(Path(td), "fallback"), "rustapp")

    def test_cmake_executable(self):
        from core.from_source import _detect_binary_name
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "CMakeLists.txt").write_text(
                "add_executable(capp main.c)\n", encoding="utf-8"
            )
            self.assertEqual(_detect_binary_name(Path(td), "fallback"), "capp")

    def test_package_json_bin_dict(self):
        from core.from_source import _detect_binary_name
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "package.json").write_text(
                "{\"bin\": {\"jsapp\": \"cli.js\"}}", encoding="utf-8"
            )
            self.assertEqual(_detect_binary_name(Path(td), "fallback"), "jsapp")

    def test_fallback(self):
        from core.from_source import _detect_binary_name
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(_detect_binary_name(Path(td), "projname"), "projname")


if __name__ == "__main__":
    unittest.main()
