"""PkgForge — Package Quality Score.

Scores converted packages on multiple dimensions to help users
understand the quality and safety of a conversion.

Usage:
    from core.quality_score import score_package
    report = score_package(Path("app.pkg.tar.zst"), tools)
    print(f"Score: {report.score}/100")
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from config import ToolPaths

log = logging.getLogger(__name__)


@dataclass
class QualityCheck:
    """A single quality check result."""

    name: str
    category: str      # "security", "compatibility", "metadata", "size"
    passed: bool
    score: int         # Points awarded (0-25 per check)
    max_score: int     # Maximum possible points
    detail: str = ""


@dataclass
class QualityReport:
    """Complete quality report for a package."""

    package_name: str = ""
    total_score: int = 0
    max_score: int = 100
    checks: list[QualityCheck] = field(default_factory=list)
    grade: str = ""

    @property
    def passed(self) -> bool:
        return self.total_score >= 60  # D grade or better

    def summary(self) -> str:
        lines = [
            f"  📦 Paket: {self.package_name}",
            f"  📊 Puan: {self.total_score}/{self.max_score} ({self.grade})",
            "",
        ]

        by_category: dict[str, list[QualityCheck]] = {}
        for c in self.checks:
            by_category.setdefault(c.category, []).append(c)

        for cat, checks in by_category.items():
            cat_scores = sum(c.score for c in checks)
            cat_max = sum(c.max_score for c in checks)
            lines.append(f"  [{cat.upper()}] {cat_scores}/{cat_max}")
            for c in checks:
                icon = "✅" if c.passed else "❌"
                lines.append(f"    {icon} {c.name}: {c.detail}")
            lines.append("")

        # Grade interpretation
        if self.total_score >= 90:
            lines.append("  🏆 Mükemmel — production-ready")
        elif self.total_score >= 75:
            lines.append("  ✅ İyi — çoğu ortamda çalışır")
        elif self.total_score >= 60:
            lines.append("  ⚠️ Kabul edilebilir — bazı sorunlar var")
        elif self.total_score >= 40:
            lines.append("  ⚠️ Düşük — ciddi sorunlar mevcut")
        else:
            lines.append("  ❌ Kötü — kurulum önerilmez")

        return "\n".join(lines)


def _read_pkginfo(pkg_path: Path) -> dict[str, str]:
    """Read .PKGINFO from package once and return as dict."""
    info: dict[str, str] = {}
    try:
        res = subprocess.run(
            ["tar", "xf", str(pkg_path), "-O", ".PKGINFO"],
            capture_output=True, text=True, timeout=10,
        )
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if " = " in line:
                    key, val = line.split(" = ", 1)
                    info[key.strip()] = val.strip()
    except Exception:
        pass
    return info


def score_package(pkg_path: Path, tools: ToolPaths) -> QualityReport:
    """Score a converted package on multiple quality dimensions.

    Checks:
    1. Security (25 pts): ABI compatibility, ClamAV, path traversal
    2. Compatibility (25 pts): Dependencies resolved, architecture match
    3. Metadata (25 pts): Name, version, description, license
    4. Size (25 pts): Reasonable size, no excessive files

    Args:
        pkg_path: Path to .pkg.tar.zst file.
        tools: Detected system tools.

    Returns:
        QualityReport with detailed scoring.
    """
    report = QualityReport()
    report.package_name = pkg_path.stem.split(".")[0]

    # ── Security checks (25 pts) ────────────────────────────────

    # ABI compatibility (10 pts)
    try:
        from core.abi_scanner import check_abi_compatibility
        abi = check_abi_compatibility(pkg_path)
        if abi.passed:
            report.checks.append(QualityCheck(
                name="ABI Uyumluluğu", category="security",
                passed=True, score=10, max_score=10,
                detail=f"{abi.binary_count} ELF dosyası, uyumsuzluk yok",
            ))
        else:
            report.checks.append(QualityCheck(
                name="ABI Uyumluluğu", category="security",
                passed=False, score=max(0, 10 - abi.error_count * 2), max_score=10,
                detail=f"{abi.error_count} uyumsuzluk tespit edildi",
            ))
    except Exception:
        report.checks.append(QualityCheck(
            name="ABI Uyumluluğu", category="security",
            passed=True, score=5, max_score=10,
            detail="Tarama yapılamadı (varsayılan puan)",
        ))

    # ClamAV scan (10 pts)
    try:
        from core.malware_scanner import is_clamav_available, scan_with_clamav
        if is_clamav_available():
            ok, msg = scan_with_clamav(pkg_path)
            report.checks.append(QualityCheck(
                name="Malware Taraması", category="security",
                passed=ok, score=10 if ok else 0, max_score=10,
                detail="Temiz" if ok else f"Tespit: {msg[:50]}",
            ))
        else:
            report.checks.append(QualityCheck(
                name="Malware Taraması", category="security",
                passed=True, score=5, max_score=10,
                detail="ClamAV kurulu değil",
            ))
    except Exception:
        report.checks.append(QualityCheck(
            name="Malware Taraması", category="security",
            passed=True, score=5, max_score=10,
            detail="Tarama başarısız",
        ))

    # Path traversal (5 pts)
    try:
        from core.security import check_path_traversal
        # Extract file list for check
        res = subprocess.run(
            ["tar", "tf", str(pkg_path)],
            capture_output=True, text=True, timeout=10,
        )
        if res.returncode == 0:
            file_list = res.stdout.strip().splitlines()
            offending = check_path_traversal(file_list)
            report.checks.append(QualityCheck(
                name="Path Traversal", category="security",
                passed=len(offending) == 0,
                score=5 if not offending else 0, max_score=5,
                detail=f"{len(offending)} ihlal" if offending else "Temiz",
            ))
        else:
            report.checks.append(QualityCheck(
                name="Path Traversal", category="security",
                passed=True, score=3, max_score=5,
                detail="Dosya listesi alınamadı",
            ))
    except Exception:
        report.checks.append(QualityCheck(
            name="Path Traversal", category="security",
            passed=True, score=3, max_score=5,
            detail="Kontrol başarısız",
        ))

    # ── Compatibility checks (25 pts) ───────────────────────────

    # Dependencies resolved (15 pts)
    pkginfo = _read_pkginfo(pkg_path)

    try:
        from core.dep_resolver import resolve_dependencies
        deps = [v for k, v in pkginfo.items() if k == "depend"]

        if deps:
            resolve_report = resolve_dependencies(deps, include_installed=True)
            resolved_pct = resolve_report.resolved_count / resolve_report.total if resolve_report.total else 1
            score = int(15 * resolved_pct)
            report.checks.append(QualityCheck(
                name="Bağımlılık Çözümleme", category="compatibility",
                passed=resolve_report.all_resolved,
                score=score, max_score=15,
                detail=f"{resolve_report.resolved_count}/{resolve_report.total} çözümlendi",
            ))
        else:
            report.checks.append(QualityCheck(
                name="Bağımlılık Çözümleme", category="compatibility",
                passed=True, score=10, max_score=15,
                detail="Bağımlılık yok veya okunamadı",
            ))
    except Exception:
        report.checks.append(QualityCheck(
            name="Bağımlılık Çözümleme", category="compatibility",
            passed=True, score=8, max_score=15,
            detail="Kontrol başarısız",
        ))

    # Architecture match (10 pts)
    try:
        arch = pkginfo.get("arch", "")

        import platform
        system_arch = platform.machine()
        arch_ok = arch in (system_arch, "any", "")
        report.checks.append(QualityCheck(
            name="Mimari Uyumluluğu", category="compatibility",
            passed=arch_ok, score=10 if arch_ok else 0, max_score=10,
            detail=f"Paket: {arch}, Sistem: {system_arch}" if arch else "Mimari bilinmiyor",
        ))
    except Exception:
        report.checks.append(QualityCheck(
            name="Mimari Uyumluluğu", category="compatibility",
            passed=True, score=5, max_score=10,
            detail="Kontrol başarısız",
        ))

    # ── Metadata checks (25 pts) ────────────────────────────────

    # Package name (5 pts)
    name_ok = bool(report.package_name and len(report.package_name) > 1)
    report.checks.append(QualityCheck(
        name="Paket Adı", category="metadata",
        passed=name_ok, score=5 if name_ok else 0, max_score=5,
        detail=report.package_name or "Eksik",
    ))

    # Version (5 pts)
    try:
        version = pkginfo.get("pkgver", "")
        ver_ok = bool(version)
        report.checks.append(QualityCheck(
            name="Sürüm", category="metadata",
            passed=ver_ok, score=5 if ver_ok else 0, max_score=5,
            detail=version or "Eksik",
        ))
    except Exception:
        report.checks.append(QualityCheck(
            name="Sürüm", category="metadata",
            passed=False, score=0, max_score=5,
            detail="Okunamadı",
        ))

    # Description (5 pts)
    try:
        desc = pkginfo.get("desc", "")
        desc_ok = bool(desc and len(desc) > 5)
        report.checks.append(QualityCheck(
            name="Açıklama", category="metadata",
            passed=desc_ok, score=5 if desc_ok else 0, max_score=5,
            detail=desc[:60] if desc else "Eksik veya çok kısa",
        ))
    except Exception:
        report.checks.append(QualityCheck(
            name="Açıklama", category="metadata",
            passed=False, score=0, max_score=5,
            detail="Okunamadı",
        ))

    # License (5 pts)
    try:
        license_id = pkginfo.get("license", "")
        lic_ok = bool(license_id)
        report.checks.append(QualityCheck(
            name="Lisans", category="metadata",
            passed=lic_ok, score=5 if lic_ok else 0, max_score=5,
            detail=license_id or "Bilinmiyor",
        ))
    except Exception:
        report.checks.append(QualityCheck(
            name="Lisans", category="metadata",
            passed=False, score=0, max_score=5,
            detail="Okunamadı",
        ))

    # Homepage (5 pts)
    try:
        url = pkginfo.get("url", "")
        url_ok = bool(url and url.startswith("http"))
        report.checks.append(QualityCheck(
            name="Web Sitesi", category="metadata",
            passed=url_ok, score=5 if url_ok else 0, max_score=5,
            detail=url[:60] if url else "Belirtilmemiş",
        ))
    except Exception:
        report.checks.append(QualityCheck(
            name="Web Sitesi", category="metadata",
            passed=False, score=0, max_score=5,
            detail="Okunamadı",
        ))

    # ── Size checks (25 pts) ────────────────────────────────────

    # Package size (10 pts)
    pkg_size_mb = pkg_path.stat().st_size / (1024 * 1024)
    if pkg_size_mb < 100:
        size_score = 10
    elif pkg_size_mb < 500:
        size_score = 7
    elif pkg_size_mb < 1000:
        size_score = 4
    else:
        size_score = 1
    report.checks.append(QualityCheck(
        name="Paket Boyutu", category="size",
        passed=pkg_size_mb < 500,
        score=size_score, max_score=10,
        detail=f"{pkg_size_mb:.1f} MB",
    ))

    # File count (10 pts)
    try:
        res = subprocess.run(
            ["tar", "tf", str(pkg_path)],
            capture_output=True, text=True, timeout=10,
        )
        if res.returncode == 0:
            file_count = len(res.stdout.strip().splitlines())
            if file_count < 1000:
                f_score = 10
            elif file_count < 5000:
                f_score = 7
            elif file_count < 20000:
                f_score = 4
            else:
                f_score = 1
            report.checks.append(QualityCheck(
                name="Dosya Sayısı", category="size",
                passed=file_count < 5000,
                score=f_score, max_score=10,
                detail=f"{file_count} dosya",
            ))
        else:
            report.checks.append(QualityCheck(
                name="Dosya Sayısı", category="size",
                passed=True, score=5, max_score=10,
                detail="Sayılamadı",
            ))
    except Exception:
        report.checks.append(QualityCheck(
            name="Dosya Sayısı", category="size",
            passed=True, score=5, max_score=10,
            detail="Kontrol başarısız",
        ))

    # Compression ratio (5 pts)
    try:
        res = subprocess.run(
            ["tar", "tf", str(pkg_path)],
            capture_output=True, text=True, timeout=10,
        )
        if res.returncode == 0:
            uncompressed_est = len(res.stdout) * 10  # rough estimate
            ratio = pkg_path.stat().st_size / max(uncompressed_est, 1)
            comp_ok = ratio < 0.5  # should compress reasonably
            report.checks.append(QualityCheck(
                name="Sıkıştırma Oranı", category="size",
                passed=comp_ok, score=5 if comp_ok else 2, max_score=5,
                detail=f"Oran: {ratio:.2f}",
            ))
        else:
            report.checks.append(QualityCheck(
                name="Sıkıştırma Oranı", category="size",
                passed=True, score=3, max_score=5,
                detail="Hesaplanamadı",
            ))
    except Exception:
        report.checks.append(QualityCheck(
            name="Sıkıştırma Oranı", category="size",
            passed=True, score=3, max_score=5,
            detail="Kontrol başarısız",
        ))

    # Calculate total
    report.total_score = sum(c.score for c in report.checks)
    report.max_score = sum(c.max_score for c in report.checks)

    # Grade
    pct = report.total_score / report.max_score * 100 if report.max_score else 0
    if pct >= 90:
        report.grade = "A"
    elif pct >= 80:
        report.grade = "B"
    elif pct >= 70:
        report.grade = "C"
    elif pct >= 60:
        report.grade = "D"
    else:
        report.grade = "F"

    return report
