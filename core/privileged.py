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
from core.capabilities import action_exec_path, helper_system_path, polkit_actions

HELPER_SYSTEM_PATH = helper_system_path()
POLICY_SYSTEM_PATH = "/usr/share/polkit-1/actions/org.pkgforge.helper.policy"

Q = chr(34)
NL = chr(10)

ACTIONS = polkit_actions()


# --- F5.4: konsolide yetkili yardimci (pkgforge-privileged.sh) -------------

PRIVILEGED_HELPER_NAME = "pkgforge-privileged.sh"

# The helper only ever touches these roots (mirrors the script whitelist).
SYSTEMCTL_VERBS = frozenset(
    {"enable", "disable", "start", "stop", "daemon-reload"})


def find_privileged_helper() -> Path:
    """Locate pkgforge-privileged.sh (source tree, wheel, or system install)."""
    import sys

    candidates = [
        Path(__file__).resolve().parent.parent / "scripts"
        / PRIVILEGED_HELPER_NAME,
        Path(sys.prefix) / "share" / "pkgforge" / "scripts"
        / PRIVILEGED_HELPER_NAME,
        Path("/usr/share/pkgforge/scripts") / PRIVILEGED_HELPER_NAME,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


PRIVILEGED_HELPER = find_privileged_helper()


def privileged_argv(pkexec: str, subcommand: str, *args: str) -> list[str]:
    """Build ``[pkexec, helper, subcommand, *args]`` for a privileged op.

    Centralising construction keeps every caller on the same validated
    helper script and makes the command shape unit-testable.
    """
    return [pkexec, str(PRIVILEGED_HELPER), subcommand, *args]


def privileged_write_argv(pkexec: str, path: str) -> list[str]:
    return privileged_argv(pkexec, "write-file", path)


def privileged_chmod_argv(pkexec: str, mode: str, path: str) -> list[str]:
    return privileged_argv(pkexec, "chmod", mode, path)


def privileged_remove_argv(pkexec: str, path: str) -> list[str]:
    return privileged_argv(pkexec, "remove-file", path)


def privileged_systemctl_argv(pkexec: str, verb: str,
                              unit: str = "") -> list[str]:
    if verb not in SYSTEMCTL_VERBS:
        raise ValueError(f"Gecersiz systemctl fiili: {verb}")
    argv = privileged_argv(pkexec, "systemctl", verb)
    if unit:
        argv.append(unit)
    return argv


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
        + ">" + action_exec_path(aid) + "</annotate>",
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
