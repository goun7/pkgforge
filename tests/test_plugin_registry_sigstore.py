"""Tests for the plugin registry and sigstore guard paths.

Plugin registry: registration, loading, extension-based lookup, priority.
Sigstore: dataclass summary + cosign availability status.
"""

import shutil
import unittest
from pathlib import Path


class TestPluginRegistry(unittest.TestCase):

    def test_load_plugins_finds_deb(self):
        from core.plugins import load_plugins
        loaded = load_plugins()
        self.assertIn("deb", loaded)

    def test_get_converter_by_name(self):
        from core.plugins import get_converter, load_plugins
        load_plugins()  # ensure registry populated
        plugin = get_converter("deb")
        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.name, "deb")

    def test_get_converter_unknown(self):
        from core.plugins import get_converter, load_plugins
        load_plugins()
        self.assertIsNone(get_converter("nonexistent-format"))

    def test_get_converter_for_deb_file(self):
        from core.plugins import get_converter_for_file, load_plugins
        load_plugins()
        plugin = get_converter_for_file(Path("hello_1.0.0-1_amd64.deb"))
        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.name, "deb")

    def test_get_converter_for_unknown_ext(self):
        from core.plugins import get_converter_for_file, load_plugins
        load_plugins()
        plugin = get_converter_for_file(Path("file.unknownext"))
        self.assertIsNone(plugin)

    def test_register_rejects_non_plugin(self):
        from core.plugins import register_plugin
        with self.assertRaises(TypeError):
            register_plugin(str)  # not a ConverterPlugin subclass

    def test_list_plugins(self):
        from core.plugins import list_plugins, load_plugins
        load_plugins()
        plugins = list_plugins()
        self.assertIsInstance(plugins, list)
        names = [p.get("name") for p in plugins]
        self.assertIn("deb", names)

    def test_deb_plugin_is_available(self):
        from config import discover_tools
        from core.plugins import get_converter, load_plugins
        load_plugins()
        plugin = get_converter("deb")
        self.assertIsNotNone(plugin)
        # makepkg + bsdtar are present on this Arch system
        self.assertIsInstance(plugin.is_available(discover_tools()), bool)


class TestSigstore(unittest.TestCase):

    def test_result_summary_success(self):
        from core.sigstore import SigstoreResult
        r = SigstoreResult(success=True, message="signed", log_index="42")
        s = r.summary()
        self.assertIn("signed", s)
        self.assertIn("42", s)

    def test_result_summary_failure(self):
        from core.sigstore import SigstoreResult
        r = SigstoreResult(success=False, message="cosign not found")
        s = r.summary()
        self.assertIn("cosign not found", s)

    def test_get_sigstore_status(self):
        from core.sigstore import get_sigstore_status
        status = get_sigstore_status()
        self.assertIn("cosign_available", status)
        # Must agree with actual cosign presence
        expected = shutil.which("cosign") is not None
        self.assertEqual(status["cosign_available"], expected)


if __name__ == "__main__":
    unittest.main()
