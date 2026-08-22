"""Tests for cli_bridge.ConversionResult and cross_check dataclasses.

These are the last small hermetic units before the remaining coverage is
Qt-coupled UI / external-tool / network paths.
"""

import unittest


class TestConversionResult(unittest.TestCase):

    def test_defaults(self):
        from core.cli_bridge import ConversionResult
        r = ConversionResult()
        self.assertFalse(r.success)
        self.assertEqual(r.message, "")
        self.assertIsNone(r.output_pkg)

    def test_slots(self):
        from core.cli_bridge import ConversionResult
        r = ConversionResult()
        # __slots__ prevents arbitrary attribute assignment
        with self.assertRaises(AttributeError):
            r.nonexistent_attr = 1


class TestCrossCheckDataclasses(unittest.TestCase):

    def test_source_info(self):
        from core.cross_check import SourceInfo
        s = SourceInfo(channel="aur", version="1.0", available=True)
        self.assertEqual(s.channel, "aur")
        self.assertTrue(s.available)

    def test_cross_check_report(self):
        from core.cross_check import CrossCheckReport
        r = CrossCheckReport(
            package_name="hello", local_version="1.0",
            aur_version="1.1", flatpak_version="",
            recommended_source="aur",
            recommendation_reason="newer in AUR",
        )
        self.assertEqual(r.recommended_source, "aur")
        self.assertEqual(r.package_name, "hello")


if __name__ == "__main__":
    unittest.main()
