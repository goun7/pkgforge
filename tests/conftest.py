"""Pytest fixtures and configuration for PkgForge tests."""

from __future__ import annotations

import sys
from pathlib import Path
import tempfile
import pytest

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import ToolPaths


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
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
