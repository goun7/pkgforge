"""Property-based tests using Hypothesis.

Tests core functions with randomly generated inputs to find edge cases.
"""

import hypothesis
from hypothesis import given, strategies as st, settings

from config import extract_package_name
from core.security import sha256_hash, check_path_traversal


class TestExtractPackageNameProperties:
    """Property-based tests for extract_package_name."""

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=200)
    def test_always_returns_string(self, filename):
        """Should always return a non-empty string."""
        result = extract_package_name(filename)
        assert isinstance(result, str)
        assert len(result) > 0

    @given(st.sampled_from([
        "firefox_91.0-1_amd64.deb",
        "libssl1.1_1.1.0-1_amd64.deb",
        "python3-pip_21.0-1_all.deb",
    ]))
    def test_deb_names_are_correct(self, filename):
        """Known DEB filenames should produce correct names."""
        result = extract_package_name(filename)
        assert "_" not in result or result.count("_") == 0
        assert result.isalpha() or "-" in result or "." in result

    @given(st.sampled_from([
        "openssl-1.1.1k-4-x86_64.rpm",
        "glibc-2.33-5.fc34.x86_64.rpm",
        "1:openssl-1.1.1k-4-x86_64.rpm",
    ]))
    def test_rpm_epoch_handled(self, filename):
        """Epoch prefix should be stripped."""
        result = extract_package_name(filename)
        assert ":" not in result

    @given(st.text(min_size=1, max_size=50).filter(lambda x: "." not in x and "/" not in x))
    def test_plain_name_unchanged(self, filename):
        """Names without extensions should pass through."""
        result = extract_package_name(filename)
        assert result == filename


class TestSha256Properties:
    """Property-based tests for sha256_hash."""

    @given(st.binary(min_size=0, max_size=10000))
    @settings(max_examples=100)
    def test_hash_length(self, data):
        """SHA-256 hash should always be 64 hex chars."""
        import tempfile
        from pathlib import Path
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
            f.write(data)
            f.flush()
            result = sha256_hash(Path(f.name))
            assert len(result) == 64
            assert all(c in "0123456789abcdef" for c in result)
            Path(f.name).unlink()


class TestPathTraversalProperties:
    """Property-based tests for check_path_traversal."""

    @given(st.lists(
        st.text(min_size=1, max_size=100).filter(lambda x: ".." not in x and "/" not in x),
        min_size=0, max_size=20
    ))
    def test_safe_paths_pass(self, paths):
        """Paths without '..' should never be flagged."""
        result = check_path_traversal(paths)
        assert result == []

    @given(st.text(min_size=1, max_size=50))
    def test_traversal_always_detected(self, name):
        """Paths containing '..' should always be flagged."""
        malicious = [f"usr/bin/../../{name}"]
        result = check_path_traversal(malicious)
        assert len(result) == 1
