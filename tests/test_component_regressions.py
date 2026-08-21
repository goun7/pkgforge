"""Regression tests for bugs found during component testing.

1. graph: build_file_dep_graph mis-parsed dotted versions
   (hello-1.0.0-1-x86_64 -> "hello-1" instead of "hello").
2. save_attestation doubled the .attestation.json suffix.
"""

import tempfile
import unittest
from pathlib import Path


class TestFileDepGraphNameParsing(unittest.TestCase):

    def test_dotted_version_name(self):
        from core.dep_graph import build_file_dep_graph
        with tempfile.TemporaryDirectory() as td:
            # Nonexistent file is fine: we only check the parsed root name.
            pkg = Path(td) / "hello-1.0.0-1-x86_64.pkg.tar.zst"
            graph = build_file_dep_graph(pkg)
            self.assertEqual(graph.root, "hello")

    def test_simple_version_name(self):
        from core.dep_graph import build_file_dep_graph
        with tempfile.TemporaryDirectory() as td:
            pkg = Path(td) / "foo-2-1-x86_64.pkg.tar.zst"
            graph = build_file_dep_graph(pkg)
            self.assertEqual(graph.root, "foo")

    def test_hyphenated_name(self):
        from core.dep_graph import build_file_dep_graph
        with tempfile.TemporaryDirectory() as td:
            pkg = Path(td) / "my-cool-app-1.2.3-4-x86_64.pkg.tar.zst"
            graph = build_file_dep_graph(pkg)
            self.assertEqual(graph.root, "my-cool-app")


class TestSaveAttestationSuffix(unittest.TestCase):

    def test_no_suffix_doubling(self):
        from core.provenance import (
            InTotoStatement,
            save_attestation,
        )
        stmt = InTotoStatement(
            subject=[{"name": "pkg", "digest": {"sha256": "ab" * 32}}],
            predicate={"builder": {"id": "test"}},
        )
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "pkg.pkg.tar.zst.attestation.json"
            out = save_attestation(stmt, target)
            self.assertEqual(out.name, "pkg.pkg.tar.zst.attestation.json")
            self.assertTrue(out.exists())
            # Must NOT produce a doubled suffix
            self.assertFalse(out.name.endswith(".attestation.attestation.json"))


if __name__ == "__main__":
    unittest.main()
