"""PkgForge - privileged helper assets (F4.7).

Single source of truth for the polkit action definitions behind pkexec
installs. packaging/polkit/org.pkgforge.helper.policy is generated from
this module so the shipped file cannot drift from what the code expects.
"""

from __future__ import annotations

import os
from pathlib import Path

# F5.1: polkit action listesi ve helper yolu tek kaynaktan (capabilities)
# turetilir; boylece policy uretimi ile HTTP/D-Bus kapsamlari kayamaz.
from core.capabilities import helper_system_path, polkit_actions

HELPER_SYSTEM_PATH = helper_system_path()
POLICY_SYSTEM_PATH = "/usr/share/polkit-1/actions/org.pkgforge.helper.policy"

Q = chr(34)
NL = chr(10)

ACTIONS = polkit_actions()


def _action_block(aid: str, title: str, desc: str) -> str:
    lines = [
        "  <action id=" + Q + aid + Q + ">",
        "    <description>" + title + "</description>",
        "    <message>" + desc + "</message>",
        "    <defaults>",
        "      <allow_any>auth_admin_keep</allow_any>",
        "      <allow_inactive>auth_admin_keep</allow_inactive>",
        "      <allow_active>auth_admin_keep</allow_active>",
        "    </defaults>",
        "    <annotate key=" + Q + "org.freedesktop.policy.exec.path" + Q
        + ">" + HELPER_SYSTEM_PATH + "</annotate>",
        "  </action>",
    ]
    return NL.join(lines)


def build_policy_text() -> str:
    blocks = [_action_block(a, t, d) for (a, t, d) in ACTIONS]
    parts = ["<?xml version=" + Q + "1.0" + Q + " encoding=" + Q + "UTF-8"
             + Q + "?>", "<policyconfig>", "", *blocks, "",
             "</policyconfig>", ""]
    return NL.join(parts)


def install_polkit_assets(dry_run=True):
    """Install policy + helper copy targets (root required).

    dry_run=True (default) returns the exact write plan without touching
    disk, so tests and previews never need privileges.
    """
    repo = Path(__file__).resolve().parent.parent
    helper_src = repo / "scripts" / "install_helper.sh"
    plan = {
        POLICY_SYSTEM_PATH: build_policy_text(),
        HELPER_SYSTEM_PATH: None,
    }
    if dry_run:
        out = {}
        for pth, txt in plan.items():
            label = "<copy of scripts/install_helper.sh>"
            out[pth] = label if txt is None else txt
        return {"installed": False, "dry_run": True, "units": out,
                "helper_source": str(helper_src)}
    if os.geteuid() != 0:
        raise PermissionError("polkit varliklarini kurmak root gerektirir "
                              "(sudo python -m core.privileged)")
    if not helper_src.is_file():
        raise FileNotFoundError(str(helper_src))
    Path(POLICY_SYSTEM_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(HELPER_SYSTEM_PATH).parent.mkdir(parents=True, exist_ok=True)
    tmp = POLICY_SYSTEM_PATH + ".tmp"
    Path(tmp).write_text(build_policy_text(), encoding="utf-8")
    os.replace(tmp, POLICY_SYSTEM_PATH)
    tmp2 = HELPER_SYSTEM_PATH + ".tmp"
    with open(tmp2, "wb") as fh:
        fh.write(helper_src.read_bytes())
    os.chmod(tmp2, 0o755)
    os.replace(tmp2, HELPER_SYSTEM_PATH)
    return {"installed": True, "dry_run": False, "units": list(plan)}


if __name__ == "__main__":  # pragma: no cover - sudo entry point
    import json as _json
    import sys as _sys

    try:
        result = install_polkit_assets(dry_run="--dry-run" in _sys.argv)
        print(_json.dumps(result, indent=2))
    except Exception as exc:
        print("hata:", exc, file=_sys.stderr)
        raise SystemExit(1) from exc
