"""PkgForge — Sigstore Integration.

Provides Sigstore-based signing and verification for supply chain security.
Uses cosign for signing and Rekor transparency log for auditability.

Usage:
    from core.sigstore import sign_with_sigstore, verify_with_sigstore
    result = sign_with_sigstore(prov, key_path=None)
    valid, msg = verify_with_sigstore(signed_path)
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from core.security import safe_run

log = logging.getLogger(__name__)


@dataclass
class SigstoreResult:
    """Result of a Sigstore signing or verification operation."""

    success: bool = False
    message: str = ""
    signature_path: Path | None = None
    certificate_path: Path | None = None
    log_index: str = ""  # Rekor log index
    bundle_path: Path | None = None  # Sigstore bundle

    def summary(self) -> str:
        if self.success:
            lines = [f"  ✅ {self.message}"]
            if self.log_index:
                lines.append(f"  📋 Rekor log index: {self.log_index}")
            if self.bundle_path:
                lines.append(f"  📦 Bundle: {self.bundle_path}")
        else:
            lines = [f"  ❌ {self.message}"]
        return "\n".join(lines)


def _find_cosign() -> str | None:
    """Find cosign binary."""
    return shutil.which("cosign")


def sign_with_sigstore(
    file_path: Path,
    *,
    key_path: str | None = None,
    output_dir: Path | None = None,
    oidc_issuer: str | None = None,
    certificate_identity: str | None = None,
) -> SigstoreResult:
    """Sign a file using Sigstore (cosign).

    Args:
        file_path: Path to the file to sign.
        key_path: Optional path to private key. If None, uses keyless signing.
        output_dir: Directory to write signature files. Defaults to file's parent.
        oidc_issuer: OIDC issuer URL for keyless signing (e.g., GitHub Actions).
        certificate_identity: Expected certificate identity for keyless signing.

    Returns:
        SigstoreResult with signing outcome.
    """
    cosign = _find_cosign()
    if not cosign:
        return SigstoreResult(
            success=False,
            message="cosign bulunamadı — Sigstore imzalama için gerekli. "
                    "Yükleme: go install github.com/sigstore/cosign/v2/cmd/cosign@latest",
        )

    if not file_path.is_file():
        return SigstoreResult(success=False, message=f"Dosya bulunamadı: {file_path}")

    out_dir = output_dir or file_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build cosign sign command
    cmd = [cosign, "sign-blob", "--output-signature", str(out_dir / f"{file_path.name}.sig")]

    if key_path:
        # Key-based signing
        cmd.extend(["--key", key_path])
    else:
        # Keyless signing (OIDC token)
        cmd.append("--yes")  # Skip confirmation
        if oidc_issuer:
            cmd.extend(["--oidc-issuer", oidc_issuer])
        if certificate_identity:
            cmd.extend(["--certificate-identity", certificate_identity])

    log.info("Sigstore imzalama: %s", file_path.name)
    result = safe_run(cmd, timeout=120)

    if result.returncode == 0:
        sig_path = out_dir / f"{file_path.name}.sig"
        sigstore_result = SigstoreResult(
            success=True,
            message=f"Dosya imzalandı: {file_path.name}",
            signature_path=sig_path if sig_path.exists() else None,
        )

        # Try to extract log index from output
        stdout = result.stdout if isinstance(result.stdout, str) else result.stdout.decode("utf-8", errors="replace")
        for line in stdout.splitlines():
            if "log index" in line.lower() or "rekor" in line.lower():
                sigstore_result.log_index = line.strip()
                break

        log.info("Sigstore imzalama başarılı: %s", file_path.name)
        return sigstore_result
    else:
        stderr = result.stderr if isinstance(result.stderr, str) else result.stderr.decode("utf-8", errors="replace")
        log.warning("Sigstore imzalama başarısız: %s", stderr[:200])
        return SigstoreResult(success=False, message=f"İmzalama başarısız: {stderr[:200]}")


def verify_with_sigstore(
    file_path: Path,
    *,
    key_path: str | None = None,
    certificate_identity: str | None = None,
    certificate_oidc_issuer: str | None = None,
) -> SigstoreResult:
    """Verify a file's Sigstore signature.

    Args:
        file_path: Path to the file to verify.
        key_path: Optional path to public key for key-based verification.
        certificate_identity: Expected certificate identity (exact match or regexp).
        certificate_oidc_issuer: Expected OIDC issuer URL (exact match or regexp).

    Returns:
        SigstoreResult with verification outcome.
    """
    cosign = _find_cosign()
    if not cosign:
        return SigstoreResult(
            success=False,
            message="cosign bulunamadı — Sigstore doğrulama için gerekli",
        )

    if not file_path.is_file():
        return SigstoreResult(success=False, message=f"Dosya bulunamadı: {file_path}")

    # Build cosign verify command
    sig_path = file_path.parent / f"{file_path.name}.sig"
    cmd = [cosign, "verify-blob"]

    if sig_path.exists():
        cmd.extend(["--signature", str(sig_path)])

    if key_path:
        cmd.extend(["--key", key_path])
    else:
        # Keyless verification — strict or permissive
        if certificate_identity:
            cmd.extend(["--certificate-identity", certificate_identity])
        else:
            cmd.append("--certificate-identity-regexp=.*")
        if certificate_oidc_issuer:
            cmd.extend(["--certificate-oidc-issuer", certificate_oidc_issuer])
        else:
            cmd.append("--certificate-oidc-issuer-regexp=.*")

    cmd.append(str(file_path))

    log.info("Sigstore doğrulama: %s", file_path.name)
    result = safe_run(cmd, timeout=60)

    if result.returncode == 0:
        log.info("Sigstore doğrulama başarılı: %s", file_path.name)
        return SigstoreResult(
            success=True,
            message=f"Doğrulama başarılı: {file_path.name}",
            signature_path=sig_path if sig_path.exists() else None,
        )
    else:
        stderr = result.stderr if isinstance(result.stderr, str) else result.stderr.decode("utf-8", errors="replace")
        log.warning("Sigstore doğrulama başarısız: %s", stderr[:200])
        return SigstoreResult(success=False, message=f"Doğrulama başarısız: {stderr[:200]}")


def get_sigstore_status() -> dict:
    """Check Sigstore tool availability.

    Returns:
        Dict with cosign availability and version.
    """
    cosign = _find_cosign()
    status = {
        "cosign_available": bool(cosign),
        "cosign_path": cosign or "",
        "cosign_version": "",
    }

    if cosign:
        result = safe_run([cosign, "version"], timeout=5)
        if result.returncode == 0:
            stdout = result.stdout if isinstance(result.stdout, str) else result.stdout.decode("utf-8", errors="replace")
            status["cosign_version"] = stdout.strip().split("\n")[0]

    return status
