"""PkgForge - privileged helper assets (F4.7).

Single source of truth for the polkit action definitions behind pkexec
installs. packaging/polkit/org.pkgforge.helper.policy is generated from
this module so the shipped file cannot drift from what the code expects.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

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
    """Locate pkgforge-privileged.sh (system install, wheel, or source tree).

    Siralama bilincli olarak SISTEM once: polkit politikasi yalnizca
    /usr/share/pkgforge/scripts/ yolunu yetkilendirir. Kaynak agactaki
    kopya once gelseydi kurulu sistemde bile policy eslesmez, pkexec her
    cagrida genel fallback ile parola isterdi.
    """
    import sys

    candidates = [
        Path("/usr/share/pkgforge/scripts") / PRIVILEGED_HELPER_NAME,
        Path(sys.prefix) / "share" / "pkgforge" / "scripts"
        / PRIVILEGED_HELPER_NAME,
        Path(__file__).resolve().parent.parent / "scripts"
        / PRIVILEGED_HELPER_NAME,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    # Bilinen kurulum konumlarinin hicbiri mevcut degil; ilk aday yine de
    # dondurulur (kurulum sirasinda olusturulabilir) ama uyari loglanir.
    log.warning(
        "Ayricalikli yardimci betik bulunamadi, ilk aday kullanilacak: %s",
        candidates[0],
    )
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


def build_write_batch_manifest(items: list[tuple[str, str, str]]) -> bytes:
    """Faz 14: write-batch manifest serileştiricisi.

    Her öge ``(mod, hedef_yol, içerik)``. Biçim: NUL-ayırıcılı üçlü;
    bash tarafı aynı sırayla okur, içerikte newline güvenlidir.
    """
    out = bytearray()
    for mod, path, content in items:
        out += mod.encode("ascii") + b"\x00"
        out += path.encode("utf-8") + b"\x00"
        out += content.encode("utf-8") + b"\x00"
    return bytes(out)


def privileged_write_batch_argv(pkexec: str) -> list[str]:
    """Tek pkexec diyaloğunda çoklu dosya yazımı (write-batch)."""
    return privileged_argv(pkexec, "write-batch")


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


def privileged_install_pkg_argv(pkexec: str, pkg: str,
                                snapshot: str = "") -> list[str]:
    """Tek diyalogda snapshot'li kurulum: install-pkg [--snapshot AD] <paket>."""
    argv = privileged_argv(pkexec, "install-pkg")
    if snapshot:
        argv += ["--snapshot", snapshot]
    argv.append(pkg)
    return argv


def privileged_service_deploy_argv(pkexec: str, unit: str) -> list[str]:
    """Servis kurulumunun TAMAMI tek diyalogda (manifest stdin'den)."""
    _check_unit_name(unit)
    return privileged_argv(pkexec, "service-deploy", unit)


def privileged_service_remove_argv(pkexec: str, unit: str,
                                   *files: str) -> list[str]:
    """Servis kaldirmanin TAMAMI tek diyalogda (stop+disable+sil+reload)."""
    _check_unit_name(unit)
    return privileged_argv(pkexec, "service-remove", unit, *files)


def privileged_service_enable_argv(pkexec: str, unit: str) -> list[str]:
    """enable + start tek diyalogda."""
    _check_unit_name(unit)
    return privileged_argv(pkexec, "service-enable", unit)


def privileged_service_disable_argv(pkexec: str, unit: str) -> list[str]:
    """stop + disable tek diyalogda."""
    _check_unit_name(unit)
    return privileged_argv(pkexec, "service-disable", unit)


_SNAPSHOT_OPS = frozenset(
    {"take-btrfs", "delete-btrfs", "take-zfs", "destroy-zfs"})


def _check_unit_name(unit: str) -> None:
    import re as _re

    if not unit or _re.search(r"[^A-Za-z0-9._-]", unit):
        raise ValueError(f"Gecersiz unit adi: {unit}")


def privileged_snapshot_argv(pkexec: str, op: str, target: str) -> list[str]:
    """Dosya-sistemi snapshot islemi tek diyalogda.

    op: take-btrfs | delete-btrfs | take-zfs | destroy-zfs.
    btrfs hedefleri mutlak yol, zfs hedefleri dataset@snap bicimindedir.
    Hedef adlar helper tarafinda da dogrulanir (pkgforge- one eki sart).
    """
    import re as _re

    if op not in _SNAPSHOT_OPS:
        raise ValueError(f"Gecersiz snapshot islemi: {op}")
    if not target or ".." in target:
        raise ValueError(f"Gecersiz snapshot hedefi: {target}")
    if op in ("take-zfs", "destroy-zfs"):
        if "@" not in target:
            raise ValueError(f"ZFS hedefi dataset@snap biciminde olmali: {target}")
        dataset, _, snap = target.partition("@")
        if not dataset or _re.search(r"[^A-Za-z0-9._/-]", dataset):
            raise ValueError(f"Gecersiz dataset: {target}")
        if not snap.startswith("pkgforge-"):
            raise ValueError(f"Snapshot adi pkgforge- ile baslamali: {target}")
    else:
        if not target.startswith("/"):
            raise ValueError(f"Gecersiz snapshot hedefi: {target}")
    return privileged_argv(pkexec, "snapshot", op, target)


def policy_installed() -> bool:
    """Polkit politikasi + sistem helper'i kurulu mu?

    Kurulu degilse pkexec HER cagrida genel fallback ile parola ister
    (kuruluysa auth_admin_keep sayesinde tek parola 5 dk yeter).
    """
    from core.capabilities import privileged_helper_system_path

    return (Path(POLICY_SYSTEM_PATH).is_file()
            and Path(privileged_helper_system_path()).is_file())


_SETUP_HINT_SHOWN = False


def privileged_setup_hint() -> str | None:
    """Kurulum eksikse tek seferlik uyari metni dondur (oturumda bir kez).

    pkexec bombardimanindan once cagrilir; None ise hersey kurulu demektir.
    """
    global _SETUP_HINT_SHOWN
    if _SETUP_HINT_SHOWN or policy_installed():
        return None
    _SETUP_HINT_SHOWN = True
    return ("Polkit politikasi kurulu degil — her yetkili islem ayri parola "
            "ister. Tek parola icin: sudo ./scripts/install.sh "
            "(ardindan policy + helper sisteme kurulur)")


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


def install_polkit_assets(dry_run: bool = True) -> dict[str, object]:
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
    # Kök sahibi yardımcı betik tüm kullanıcılarca çalıştırılmalı (0755 bilinçli).
    os.chmod(tmp2, 0o755)  # nosec B103
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
