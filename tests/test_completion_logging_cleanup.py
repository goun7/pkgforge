"""Tests for completion, structured_log, snapshot_cleanup generators, rollback_verify.

All hermetic: string generation and temp dirs only.
"""

import json
import logging
import unittest
from pathlib import Path


class TestGenerateCompletion(unittest.TestCase):

    def test_bash(self):
        from core.completion import generate_completion
        out = generate_completion("bash")
        self.assertIn("complete", out)
        self.assertIn("pkgforge", out)

    def test_zsh(self):
        from core.completion import generate_completion
        out = generate_completion("zsh")
        self.assertIn("#compdef", out)

    def test_fish(self):
        from core.completion import generate_completion
        out = generate_completion("fish")
        self.assertIn("complete", out)

    def test_unsupported_shell(self):
        from core.completion import generate_completion
        with self.assertRaises(ValueError):
            generate_completion("powershell")


class TestJSONFormatter(unittest.TestCase):

    def _record(self, msg="hello", level=logging.INFO, **extra):
        return logging.LogRecord(
            name="test.logger", level=level, pathname=__file__,
            lineno=1, msg=msg, args=None, exc_info=None,
        )

    def test_json_output(self):
        from core.structured_log import JSONFormatter
        fmt = JSONFormatter()
        out = fmt.format(self._record("test message"))
        data = json.loads(out)
        self.assertEqual(data["message"], "test message")
        self.assertEqual(data["level"], "INFO")
        self.assertEqual(data["logger"], "test.logger")
        self.assertIn("timestamp", data)

    def test_extra_fields(self):
        from core.structured_log import JSONFormatter
        fmt = JSONFormatter()
        rec = self._record()
        rec.package_name = "hello"
        rec.duration_ms = 42
        rec.success = True
        data = json.loads(fmt.format(rec))
        self.assertEqual(data["package_name"], "hello")
        self.assertEqual(data["duration_ms"], 42)
        self.assertTrue(data["success"])

    def test_exception_included(self):
        from core.structured_log import JSONFormatter
        fmt = JSONFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys
            rec = logging.LogRecord(
                name="t", level=logging.ERROR, pathname=__file__,
                lineno=1, msg="failed", args=None, exc_info=sys.exc_info(),
            )
        data = json.loads(fmt.format(rec))
        self.assertEqual(data["exception"]["type"], "ValueError")
        self.assertEqual(data["exception"]["message"], "boom")


class TestHumanFormatter(unittest.TestCase):

    def test_format_contains_message(self):
        from core.structured_log import HumanFormatter
        fmt = HumanFormatter(use_colors=False)
        rec = logging.LogRecord(
            name="core.pipeline", level=logging.INFO, pathname=__file__,
            lineno=1, msg="hello world", args=None, exc_info=None,
        )
        out = fmt.format(rec)
        self.assertIn("hello world", out)
        self.assertIn("pipeline", out)  # short logger name


class TestSnapshotCleanupGenerators(unittest.TestCase):

    def test_cleanup_script(self):
        from core.snapshot_cleanup import _generate_cleanup_script
        script = _generate_cleanup_script(7)
        self.assertIn("#!/bin/bash", script)
        self.assertIn("MAX_AGE_DAYS=7", script)
        self.assertIn("btrfs", script)
        self.assertIn("zfs", script)

    def test_service_unit(self):
        from core.snapshot_cleanup import _generate_service_unit
        unit = _generate_service_unit()
        self.assertIn("[Unit]", unit)
        self.assertIn("[Service]", unit)
        self.assertIn("Type=oneshot", unit)

    def test_timer_unit(self):
        from core.snapshot_cleanup import _generate_timer_unit
        unit = _generate_timer_unit(14)
        self.assertIn("[Timer]", unit)
        self.assertIn("OnCalendar", unit)
        self.assertIn("14", unit)


class TestHashFileTree(unittest.TestCase):

    def test_returns_hex_string(self):
        from core.rollback_verify import _hash_file_tree
        result = _hash_file_tree(Path("/"), max_files=5)
        self.assertIsInstance(result, str)
        self.assertEqual(len(result), 64)  # sha256 hex

    def test_deterministic(self):
        from core.rollback_verify import _hash_file_tree
        a = _hash_file_tree(Path("/"), max_files=5)
        b = _hash_file_tree(Path("/"), max_files=5)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
