"""Pytest fixtures and configuration for PkgForge tests."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# ── Environment isolation ────────────────────────────────────────
# Tests must never touch the real user's ~/.config/pkgforge (history DB,
# settings, backups). Redirect HOME to a private temp dir BEFORE importing
# anything from the project, because config.py computes CONFIG_DIR from
# Path.home() at import time.
_TEST_HOME = tempfile.mkdtemp(prefix="pkgforge_test_home_")
os.environ["HOME"] = _TEST_HOME
os.environ.pop("XDG_CONFIG_HOME", None)

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import ToolPaths


def pytest_sessionfinish(session, exitstatus):
    """Remove the isolated HOME temp dir after the test session."""
    import shutil

    shutil.rmtree(_TEST_HOME, ignore_errors=True)


@pytest.fixture
def temp_dir():
    """Fixture providing a temporary directory."""
    with tempfile.TemporaryDirectory(prefix="pkgforge_test_") as tmp:
        yield Path(tmp)


@pytest.fixture
def mock_tools():
    """Fixture providing a ToolPaths instance."""
    return ToolPaths(
        pacman="/usr/bin/pacman",
        makepkg="/usr/bin/makepkg",
        fakeroot="/usr/bin/fakeroot",
        file_cmd="/usr/bin/file",
        pkexec="/usr/bin/pkexec",
        bsdtar="/usr/bin/bsdtar",
        bwrap="/usr/bin/bwrap",
    )


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        'slow: marks tests as slow (deselect with \'-m "not slow"\')',
    )
