"""Tests for converter sanitize/escape pure functions (security-relevant).

_escape_bash prevents command substitution in generated PKGBUILDs;
_sanitize_pkgname/_sanitize_version keep names pacman-safe.
"""

import unittest


class TestNativeDebSanitize(unittest.TestCase):

    def test_pkgname_lowercased(self):
        from core.native_deb_converter import _sanitize_pkgname
        self.assertEqual(_sanitize_pkgname("MyApp"), "myapp")

    def test_pkgname_special_chars(self):
        from core.native_deb_converter import _sanitize_pkgname
        self.assertEqual(_sanitize_pkgname("my app!"), "my-app-")

    def test_pkgname_empty_fallback(self):
        from core.native_deb_converter import _sanitize_pkgname
        self.assertEqual(_sanitize_pkgname(""), "unknown-deb-pkg")

    def test_version_epoch_stripped(self):
        from core.native_deb_converter import _sanitize_version
        self.assertEqual(_sanitize_version("1:2.0.0"), "2.0.0")

    def test_version_release_stripped(self):
        from core.native_deb_converter import _sanitize_version
        self.assertEqual(_sanitize_version("2.0.0-3"), "2.0.0")

    def test_version_empty_fallback(self):
        from core.native_deb_converter import _sanitize_version
        self.assertEqual(_sanitize_version(""), "1.0.0")


class TestRpmSanitize(unittest.TestCase):

    def test_pkgname(self):
        from core.rpm_converter import _sanitize_pkgname
        self.assertEqual(_sanitize_pkgname("Hello World"), "hello-world")

    def test_pkgname_empty_fallback(self):
        from core.rpm_converter import _sanitize_pkgname
        self.assertEqual(_sanitize_pkgname(""), "unknown-pkg")

    def test_version(self):
        from core.rpm_converter import _sanitize_version
        self.assertEqual(_sanitize_version("2:1.5-2.el9"), "1.5")


class TestEscapeBash(unittest.TestCase):

    def test_single_quote_escaped(self):
        from core.rpm_converter import _escape_bash
        # A single quote must become the 4-char sequence: quote, backslash,
        # quote, quote — the standard way to embed a quote in a bash
        # single-quoted string.
        result = _escape_bash("it" + chr(39) + "s")
        expected = "it" + chr(39) + chr(92) + chr(39) + chr(39) + "s"
        self.assertEqual(result, expected)

    def test_command_substitution_stripped(self):
        from core.rpm_converter import _escape_bash
        # backticks and $() must be removed to prevent command injection
        self.assertNotIn("`", _escape_bash("evil`rm -rf /`"))
        self.assertNotIn("$(", _escape_bash("evil$(rm -rf /)"))

    def test_plain_text_unchanged(self):
        from core.rpm_converter import _escape_bash
        self.assertEqual(_escape_bash("hello world"), "hello world")


if __name__ == "__main__":
    unittest.main()
