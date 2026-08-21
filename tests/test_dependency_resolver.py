"""Unit tests for core/dependency_resolver.py (parsing + ELF detection)."""

import tempfile
import unittest
from pathlib import Path

from core.dep_resolver import (
    is_elf_file,
    parse_needed_sonames,
    parse_objdump_sonames,
)


class TestDependencyResolver(unittest.TestCase):

    def test_parse_needed_sonames(self):
        readelf_out = """
Dynamic section at offset 0x2d88 contains 27 entries:
  Tag        Type                         Name/Value
 0x0000000000000001 (NEEDED)             Shared library: [libncursesw.so.6]
 0x0000000000000001 (NEEDED)             Shared library: [libc.so.6]
 0x000000000000000c (INIT)               0x3000
"""
        sonames = parse_needed_sonames(readelf_out)
        self.assertIn("libncursesw.so.6", sonames)
        self.assertIn("libc.so.6", sonames)
        self.assertEqual(len(sonames), 2)

    def test_parse_objdump_sonames(self):
        objdump_out = """
Dynamic Section:
  NEEDED               libssl.so.3
  NEEDED               libc.so.6
  SONAME               libfoo.so.1
"""
        sonames = parse_objdump_sonames(objdump_out)
        self.assertIn("libssl.so.3", sonames)
        self.assertIn("libc.so.6", sonames)
        self.assertNotIn("libfoo.so.1", sonames)  # SONAME line is not NEEDED

    def test_is_elf_file(self):
        with tempfile.TemporaryDirectory(prefix="pkgforge_test_") as tmp:
            elf = Path(tmp) / "fake.bin"
            elf.write_bytes(b"\x7fELF\x02\x01\x01\x00rest")
            self.assertTrue(is_elf_file(elf))

            not_elf = Path(tmp) / "plain.txt"
            not_elf.write_text("hello")
            self.assertFalse(is_elf_file(not_elf))

            missing = Path(tmp) / "nope.bin"
            self.assertFalse(is_elf_file(missing))


if __name__ == "__main__":
    unittest.main()
