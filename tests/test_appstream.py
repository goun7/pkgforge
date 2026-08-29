"""Faz 5 (F5.21) — AppStream metainfo + flatpak manifesti."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from config import APP_ID, APP_VERSION

ROOT = Path(__file__).resolve().parent.parent
METAINFO = ROOT / "data" / "org.pkgforge.app.metainfo.xml"
FLATPAK = ROOT / "packaging" / "flatpak" / "org.pkgforge.app.yml"


def test_metainfo_is_well_formed_xml():
    root = ET.parse(METAINFO).getroot()
    assert root.tag == "component"
    assert root.get("type") == "desktop-application"


def test_metainfo_id_matches_app_id():
    root = ET.parse(METAINFO).getroot()
    assert root.find("id").text == APP_ID


def test_metainfo_has_required_fields():
    root = ET.parse(METAINFO).getroot()
    for tag in ("id", "name", "summary", "project_license",
                "metadata_license", "description", "launchable", "releases"):
        assert root.find(tag) is not None, f"eksik alan: {tag}"


def test_metainfo_release_version_matches_app_version():
    root = ET.parse(METAINFO).getroot()
    release = root.find("releases/release")
    assert release is not None
    assert release.get("version") == APP_VERSION


def test_metainfo_launchable_points_at_desktop_id():
    root = ET.parse(METAINFO).getroot()
    launchable = root.find("launchable")
    assert launchable.get("type") == "desktop-id"
    assert launchable.text == APP_ID + ".desktop"


def test_flatpak_manifest_app_id_matches():
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        import pytest

        pytest.skip("pyyaml yok")
    data = yaml.safe_load(FLATPAK.read_text(encoding="utf-8"))
    assert data["app-id"] == APP_ID
    assert data.get("modules"), "flatpak manifestinde modul yok"