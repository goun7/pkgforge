"""Unit tests for core/aur_checker.py."""

import unittest
from core.aur_checker import _version_compare, check_aur


class TestAurChecker(unittest.TestCase):

    def test_version_compare(self):
        self.assertEqual(_version_compare("1.0.0", "1.0.0"), 0)
        self.assertTrue(_version_compare("2.0.0", "1.0.0") > 0)
        self.assertTrue(_version_compare("1.0.0", "2.0.0") < 0)
        self.assertTrue(_version_compare("1.2.3-2", "1.2.3-1") >= 0)

    def test_check_aur_empty(self):
        res = check_aur("")
        self.assertEqual(res.status, "error")
        self.assertIn("Boş", res.detail)


if __name__ == "__main__":
    unittest.main()
