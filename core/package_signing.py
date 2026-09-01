"""PkgForge — GPG Package Signing & Verification.

Signs converted packages with GPG to ensure integrity and authenticity.
Verification checks that the signature is valid and matches a trusted key.

Usage:
    pkgforge sign package.pkg.tar.zst --key ~/.gnupg/pkgforge.key
    pkgforge verify package.pkg.tar.zst
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from core.security import safe_run
from i18n import tr

log = logging.getLogger(__name__)

_GNUPGHOME = os.environ.get("GNUPGHOME", "")  


def _gpg_homedir_args() -> list[str]:
    """Return --homedir arg if a custom GNUPGHOME is set."""
    if _GNUPGHOME:
        return ["--homedir", _GNUPGHOME]
    return []


@dataclass
class SignatureInfo:
    """Information about a GPG signature."""

    signed: bool = False
    valid: bool = False
    key_id: str = ""
    key_fingerprint: str = ""
    signer: str = ""
    timestamp: str = ""
    detail: str = ""


def is_gpg_available() -> bool:
    """Check if GPG is installed."""
    return shutil.which("gpg") is not None


def sign_package(
    package_path: Path,
    key_path: Path | None = None,
    passphrase: str = "",
) -> tuple[bool, str]:
    """Sign a package file with GPG.

    Args:
        package_path: Path to the .pkg.tar.zst file.
        key_path: Path to GPG key (optional, uses default if None).
        passphrase: GPG passphrase (optional).

    Returns:
        (success, message)
    """
    if not is_gpg_available():
        return False, "gpg bulunamadı — kurulum: sudo pacman -S gnupg"

    if not package_path.is_file():
        return False, tr("signing.paket_bulunamadi_package_path", package_path=package_path)

    sig_path = Path(f"{package_path}.sig")

    cmd = ["gpg", "--batch", "--yes", "--detach-sign", *_gpg_homedir_args()]
    if key_path:
        cmd += ["--default-key", str(key_path)]
    if passphrase:
        cmd += ["--pinentry-mode", "loopback", "--passphrase", passphrase]

    cmd.append(str(package_path))

    res = safe_run(cmd, timeout=60)

    if res.returncode != 0:
        return False, tr("signing.gpg_imzalama_basarisiz_res", res_stderr=res.stderr)

    if not sig_path.is_file():
        return False, "İmza dosyası oluşturulamadı"

    log.info(tr("signing.paket_imzalandi_s_s"), package_path.name, sig_path.name)
    return True, tr("signing.mza_olusturuldu_sig_path", sig_path_name=sig_path.name)


def verify_signature(package_path: Path) -> SignatureInfo:
    """Verify the GPG signature of a package.

    Args:
        package_path: Path to the .pkg.tar.zst file.

    Returns:
        SignatureInfo with verification details.
    """
    if not is_gpg_available():
        return SignatureInfo(detail="gpg bulunamadı — imza doğrulanamıyor")

    sig_path = Path(f"{package_path}.sig")
    if not sig_path.is_file():
        return SignatureInfo(detail=tr("signing.mza_dosyasi_bulunamadi_sig", sig_path_name=sig_path.name))

    # Verify signature
    res = safe_run(
        ["gpg", "--verify", "--status-fd", "1", *_gpg_homedir_args(), str(sig_path), str(package_path)],
        timeout=30,
    )

    output = res.stdout + "\n" + res.stderr

    info = SignatureInfo()

    # Parse GPG status output.
    # Format: "[GNUPG:] GOODSIG <keyid> <signer>" — parts[0] is "[GNUPG:]",
    # parts[1] is the status keyword, so payload starts at parts[2].
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("[GNUPG:] GOODSIG"):
            parts = line.split()
            if len(parts) >= 4:
                info.key_id = parts[2]
                info.signer = " ".join(parts[3:])
            info.signed = True
        elif line.startswith("[GNUPG:] VALIDSIG"):
            info.valid = True
            parts = line.split()
            if len(parts) >= 3:
                info.key_fingerprint = parts[2]
        elif line.startswith("[GNUPG:] TRUST_"):
            if "FULL" in line or "ULTIMATE" in line:
                info.valid = True
        elif line.startswith("[GNUPG:] SIG_ID"):
            parts = line.split()
            if len(parts) >= 5:
                info.timestamp = parts[4]

    if info.valid:
        info.detail = tr("signing.mza_gecerli_var0", var0=info.signer or info.key_id)
    elif info.signed:
        info.detail = tr("signing.mza_mevcut_ama_dogrulanamadi", var0=info.signer or info.key_id)
    else:
        info.detail = "Geçerli imza bulunamadı"

    return info


def list_keys() -> list[dict[str, str]]:
    """List GPG keys available for signing."""
    if not is_gpg_available():
        return []

    res = safe_run(
        ["gpg", "--list-keys", "--with-colons", "--fingerprint"],
        timeout=10,
    )

    keys = []
    current_key = {}
    for line in res.stdout.splitlines():
        parts = line.split(":")
        if len(parts) >= 10:
            if parts[0] == "pub":
                current_key = {
                    "key_id": parts[4],
                    "algo": parts[2],
                    "created": parts[5],
                    "capabilities": parts[11] if len(parts) > 11 else "",
                }
            elif parts[0] == "uid":
                uid = parts[9]
                if current_key and uid:
                    current_key["uid"] = uid
                    keys.append(current_key)
                    current_key = {}

    return keys
