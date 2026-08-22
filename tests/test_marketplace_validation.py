"""Tests for marketplace plugin validation and compatibility file-conflicts.

All hermetic: name/scheme validation, sha256, offline mode, empty file list.
"""

import hashlib
import tempfile
import unittest
from pathlib import Path


class TestPluginNameValidation(unittest.TestCase):

    def test_valid_names(self):
        from core.plugins.marketplace import is_valid_plugin_name
        for name in ("myplugin", "my-plugin", "my_plugin", "plugin2", "a"):
            self.assertTrue(is_valid_plugin_name(name), name)

    def test_rejects_uppercase(self):
        from core.plugins.marketplace import is_valid_plugin_name
        self.assertFalse(is_valid_plugin_name("MyPlugin"))

    def test_rejects_leading_special(self):
        from core.plugins.marketplace import is_valid_plugin_name
        self.assertFalse(is_valid_plugin_name("-plugin"))
        self.assertFalse(is_valid_plugin_name("_plugin"))

    def test_rejects_empty_and_long(self):
        from core.plugins.marketplace import is_valid_plugin_name
        self.assertFalse(is_valid_plugin_name(""))
        self.assertFalse(is_valid_plugin_name("a" * 65))

    def test_rejects_path_traversal(self):
        from core.plugins.marketplace import is_valid_plugin_name
        self.assertFalse(is_valid_plugin_name("../evil"))
        self.assertFalse(is_valid_plugin_name("evil.py"))

    def test_validate_raises(self):
        from core.plugins.marketplace import _validate_plugin_name
        with self.assertRaises(ValueError):
            _validate_plugin_name("../evil")
        # valid name must not raise
        _validate_plugin_name("good-plugin")


class TestRequireHttps(unittest.TestCase):

    def test_https_ok(self):
        from core.plugins.marketplace import _require_https
        _require_https("https://example.com/plugin.py")  # must not raise

    def test_http_rejected(self):
        from core.plugins.marketplace import _require_https
        with self.assertRaises(ValueError):
            _require_https("http://example.com/plugin.py")

    def test_file_rejected(self):
        from core.plugins.marketplace import _require_https
        with self.assertRaises(ValueError):
            _require_https("file:///etc/passwd")


class TestSha256File(unittest.TestCase):

    def test_matches_hashlib(self):
        from core.plugins.marketplace import _sha256_file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"plugin content")
            path = Path(f.name)
        try:
            expected = hashlib.sha256(b"plugin content").hexdigest()
            self.assertEqual(_sha256_file(path), expected)
        finally:
            path.unlink(missing_ok=True)


class TestFetchAvailablePluginsOffline(unittest.TestCase):

    def test_offline_returns_empty(self):
        from core.plugins.marketplace import fetch_available_plugins
        self.assertEqual(fetch_available_plugins(offline=True), [])


class TestCheckFileConflicts(unittest.TestCase):

    def test_empty_list_passes(self):
        from config import discover_tools
        from core.compatibility_checker import (
            CheckSeverity,
            _check_file_conflicts,
        )
        result = _check_file_conflicts([], discover_tools())
        self.assertEqual(result.severity, CheckSeverity.PASS)


if __name__ == "__main__":
    unittest.main()
