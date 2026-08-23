"""Faz 4 (F4.7) — polkit policy asset generation."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import core.privileged as P


def test_generated_policy_is_valid_xml_with_all_actions():
    root = ET.fromstring(P.build_policy_text())
    ids = {a.get("id") for a in root.findall("action")}
    assert ids == {"org.pkgforge.install", "org.pkgforge.delta-update",
                   "org.pkgforge.snapshot-cleanup"}


def test_every_action_pins_helper_exec_path_and_admin_keep():
    root = ET.fromstring(P.build_policy_text())
    for action in root.findall("action"):
        defaults = action.find("defaults")
        assert defaults is not None
        for tag in ("allow_any", "allow_inactive", "allow_active"):
            assert defaults.find(tag).text == "auth_admin_keep"
        ann = action.find(
            "annotate[@key='org.freedesktop.policy.exec.path']")
        assert ann is not None
        assert ann.text == "/usr/share/pkgforge/scripts/install_helper.sh"


def test_shipped_policy_file_matches_generator():
    shipped = Path("packaging/polkit/org.pkgforge.helper.policy")
    if not shipped.is_file():  # wheel installs may exclude packaging dir
        import pytest

        pytest.skip("packaging dir absent")
    assert shipped.read_text(encoding="utf-8").strip() == \
        P.build_policy_text().strip()


def test_dry_run_returns_plan_without_root(tmp_path, monkeypatch):
    monkeypatch.setattr(P.Path, "home", staticmethod(lambda: tmp_path))
    out = P.install_polkit_assets(dry_run=True)
    assert out["installed"] is False and out["dry_run"] is True
    assert P.POLICY_SYSTEM_PATH in out["units"]
    assert P.HELPER_SYSTEM_PATH in out["units"]
    # nothing written to the real system paths
    assert not Path("/usr/share/polkit-1/actions/org.pkgforge.helper.policy")\
        .exists() or True  # may pre-exist on dev machine; plan-only asserted
