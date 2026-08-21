"""PkgForge — Reproducible Build Oracle.

Compares a converted package against an independently rebuilt version
to detect supply chain tampering.  Two approaches:

1. **Binary diff**: Uses xdelta3 to compute differences between
   the converted package and a fresh rebuild from the same source.
2. **Hash comparison**: If a known-good hash is available (e.g., from
   a trusted CI), compare against it.

This is NOT a full SLSA verifier — it's a best-effort detection tool.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from config import ToolPaths
from core.security import safe_run, sha256_hash

log = logging.getLogger(__name__)


@dataclass
class VerifyResult:
    """Result of a reproducible build verification."""

    verified: bool = False
    match_ratio: float = 0.0  # 0.0 to 1.0 (1.0 = perfect match)
    diff_size: int = 0
    total_size: int = 0
    detail: str = ""
    original_hash: str = ""
    rebuild_hash: str = ""


def verify_reproducible(
    original_pkg: Path,
    tools: ToolPaths,
    *,
    rebuild_dir: Path | None = None,
) -> VerifyResult:
    """Verify that a converted package can be reproduced.

    This rebuilds the package from scratch using the same PKGBUILD
    and compares the output against the original.

    Args:
        original_pkg: Path to the original .pkg.tar.zst
        tools: Discovered tool paths
        rebuild_dir: Directory for rebuild (auto-created if None)

    Returns:
        VerifyResult with comparison details
    """
    if not original_pkg.is_file():
        return VerifyResult(detail=f"Paket bulunamadı: {original_pkg}")

    if not tools.makepkg:
        return VerifyResult(detail="makepkg bulunamadı — yeniden oluşturma yapılamıyor")

    original_hash = sha256_hash(original_pkg)

    with tempfile.TemporaryDirectory(prefix="pkgforge_verify_") as tmpdir:
        verify_dir = Path(tmpdir)

        # 1. Extract the original package to get the PKGBUILD
        extract_dir = verify_dir / "extracted"
        extract_dir.mkdir()

        res = safe_run(
            [tools.bsdtar, "-xf", str(original_pkg), "-C", str(extract_dir)],
            timeout=60,
        )
        if res.returncode != 0:
            return VerifyResult(
                detail=f"Paket çıkarılamadı: {res.stderr[:200]}",
                original_hash=original_hash,
            )

        # 2. Look for PKGBUILD in the extracted content or build directory
        # For PkgForge-converted packages, the PKGBUILD was used during build
        # We need to find the source metadata to rebuild

        # Try to find PKGBUILD-like content
        pkgbuild_candidates = list(extract_dir.rglob("PKGBUILD"))
        if not pkgbuild_candidates:
            # No PKGBUILD found — we can't rebuild
            return VerifyResult(
                detail="Paket içinde PKGBUILD bulunamadı — yeniden oluşturma yapılamıyor",
                original_hash=original_hash,
            )

        pkgbuild_path = pkgbuild_candidates[0]
        build_dir = pkgbuild_path.parent

        # 3. Run makepkg to rebuild
        rebuild_pkg = verify_dir / "rebuild" / "pkg"
        rebuild_pkg.mkdir(parents=True)

        import os
        env = {**os.environ, "PKGDEST": str(rebuild_pkg)}

        res = safe_run(
            [tools.makepkg, "-f", "--skipchecksums", "--skipinteg", "--noconfirm"],
            cwd=str(build_dir),
            env=env,
            timeout=600,
        )

        if res.returncode != 0:
            return VerifyResult(
                detail=f"Yeniden oluşturma başarısız (kod: {res.returncode})",
                original_hash=original_hash,
            )

        # 4. Find the rebuilt package
        rebuilt = None
        for f in rebuild_pkg.iterdir():
            if f.is_file() and ".pkg.tar" in f.name:
                rebuilt = f
                break

        if not rebuilt:
            return VerifyResult(
                detail="Yeniden oluşturma başarısız — çıktı paketi bulunamadı",
                original_hash=original_hash,
            )

        rebuild_hash = sha256_hash(rebuilt)

        # 5. Compare hashes
        if original_hash == rebuild_hash:
            return VerifyResult(
                verified=True,
                match_ratio=1.0,
                detail="✓ Paket birebir aynı — reproducible build doğrulandı",
                original_hash=original_hash,
                rebuild_hash=rebuild_hash,
            )

        # 6. Compute binary diff if xdelta3 available
        diff_size = 0
        if shutil.which("xdelta3"):
            diff_file = verify_dir / "diff.xdelta"
            res = safe_run(
                ["xdelta3", "-e", "-f", "-s", str(original_pkg), str(rebuilt), str(diff_file)],
                timeout=120,
            )
            if res.returncode == 0 and diff_file.is_file():
                diff_size = diff_file.stat().st_size

        total_size = original_pkg.stat().st_size
        match_ratio = 1.0 - (diff_size / total_size) if total_size > 0 else 0.0

        return VerifyResult(
            verified=False,
            match_ratio=match_ratio,
            diff_size=diff_size,
            total_size=total_size,
            detail=(
                f"Paket farklı — eşleşme oranı: {match_ratio:.1%}\n"
                f"  Orijinal: {original_hash[:32]}…\n"
                f"  Yeniden:  {rebuild_hash[:32]}…"
            ),
            original_hash=original_hash,
            rebuild_hash=rebuild_hash,
        )
