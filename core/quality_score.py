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
from dataclasses import dataclass, field
from pathlib import Path

from config import ToolPaths
from core.security import safe_run
from i18n import tr

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
        res = safe_run(
            ["tar", "xf", str(pkg_path), "-O", ".PKGINFO"],
            timeout=10,
        )
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if " = " in line:
                    key, val = line.split(" = ", 1)
                    info[key.strip()] = val.strip()
    except Exception as exc:  # noqa: BLE001
        log.debug("Check failed: %s", exc)
    return info


def _name_from_filename(pkg_path: Path) -> str:
    """Derive a package name from a .pkg.tar.* filename.

    Strips the .pkg.tar.* suffix chain, then drops the trailing
    version-rel-arch components (e.g. lictest-1.0.0-1-any -> lictest).
    Mirrors the parsing used by core/dep_graph.py so both agree.
    """
    name = pkg_path.name
    for suffix in (".pkg.tar.zst", ".pkg.tar.xz", ".pkg.tar.gz", ".pkg.tar"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    parts = name.split("-")
    if len(parts) > 3:
        return "-".join(parts[:-3])  # Remove version-rel-arch
    return name


# ── Faz 18: kategori yardımcıları — score_package 341 satırdan
# ince orkestratöre bölündü; her kategori kendi fonksiyonunda test edilebilir.


def _security_checks(pkg_path: Path, tools: ToolPaths, report: QualityReport) -> None:
    """Güvenlik denetimleri (25 puan): ABI, ClamAV, path traversal."""
    # ABI compatibility (10 pts)
    try:
        from core.abi_scanner import check_abi_compatibility
        abi = check_abi_compatibility(pkg_path)
        if abi.passed:
            report.checks.append(QualityCheck(
                name="ABI Uyumluluğu", category="security",
                passed=True, score=10, max_score=10,
                detail=tr("quality.abi_binary_count_elf", abi_binary_count=abi.binary_count),
            ))
        else:
            report.checks.append(QualityCheck(
                name="ABI Uyumluluğu", category="security",
                passed=False, score=max(0, 10 - abi.error_count * 2), max_score=10,
                detail=f"{abi.error_count} uyumsuzluk tespit edildi",
            ))
    except Exception as exc:  # noqa: BLE001
        log.debug("Check fallback: %s", exc)
        report.checks.append(QualityCheck(
            name="ABI Uyumluluğu", category="security",
            passed=True, score=5, max_score=10,
            detail="Tarama yapılamadı (varsayılan puan)",
        ))

    # ClamAV scan (10 pts)
    try:
        from core.malware_scanner import is_clamav_available, scan_file
        if is_clamav_available():
            scan_result = scan_file(pkg_path, tools)
            ok = scan_result.clean
            msg = scan_result.detail
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
    except Exception as exc:  # noqa: BLE001
        log.debug("Check fallback: %s", exc)
        report.checks.append(QualityCheck(
            name="Malware Taraması", category="security",
            passed=True, score=5, max_score=10,
            detail="Tarama başarısız",
        ))

    # Path traversal (5 pts)
    try:
        from core.security import check_path_traversal
        # Extract file list for check
        res = safe_run(
            ["tar", "tf", str(pkg_path)],
            timeout=10,
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
    except Exception as exc:  # noqa: BLE001
        log.debug("Check fallback: %s", exc)
        report.checks.append(QualityCheck(
            name="Path Traversal", category="security",
            passed=True, score=3, max_score=5,
            detail="Kontrol başarısız",
        ))


def _compatibility_checks(pkginfo: dict[str, str], report: QualityReport) -> None:
    """Uyumluluk denetimleri (25 puan): bağımlılıklar, mimari."""
    # Dependencies resolved (15 pts)
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
                detail=tr("quality.resolve_report_resolved_count", resolve_report_resolved_count=resolve_report.resolved_count, resolve_report_total=resolve_report.total),
            ))
        else:
            report.checks.append(QualityCheck(
                name="Bağımlılık Çözümleme", category="compatibility",
                passed=True, score=10, max_score=15,
                detail="Bağımlılık yok veya okunamadı",
            ))
    except Exception as exc:  # noqa: BLE001
        log.debug("Check fallback: %s", exc)
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
    except Exception as exc:  # noqa: BLE001
        log.debug("Check fallback: %s", exc)
        report.checks.append(QualityCheck(
            name="Mimari Uyumluluğu", category="compatibility",
            passed=True, score=5, max_score=10,
            detail="Kontrol başarısız",
        ))


def _metadata_checks(pkginfo: dict[str, str], report: QualityReport) -> None:
    """Üstveri denetimleri (25 puan): ad, sürüm, açıklama, lisans, url."""
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
    except Exception as exc:  # noqa: BLE001
        log.debug("Check fallback: %s", exc)
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
    except Exception as exc:  # noqa: BLE001
        log.debug("Check fallback: %s", exc)
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
    except Exception as exc:  # noqa: BLE001
        log.debug("Check fallback: %s", exc)
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
    except Exception as exc:  # noqa: BLE001
        log.debug("Check fallback: %s", exc)
        report.checks.append(QualityCheck(
            name="Web Sitesi", category="metadata",
            passed=False, score=0, max_score=5,
            detail="Okunamadı",
        ))


def _size_checks(pkg_path: Path, report: QualityReport) -> None:
    """Boyut denetimleri (25 puan): paket boyutu, dosya sayısı, sıkıştırma."""
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
        res = safe_run(
            ["tar", "tf", str(pkg_path)],
            timeout=10,
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
    except Exception as exc:  # noqa: BLE001
        log.debug("Check fallback: %s", exc)
        report.checks.append(QualityCheck(
            name="Dosya Sayısı", category="size",
            passed=True, score=5, max_score=10,
            detail="Kontrol başarısız",
        ))

    # Compression ratio (5 pts)
    try:
        res = safe_run(
            ["tar", "tf", str(pkg_path)],
            timeout=10,
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
    except Exception as exc:  # noqa: BLE001
        log.debug("Check fallback: %s", exc)
        report.checks.append(QualityCheck(
            name="Sıkıştırma Oranı", category="size",
            passed=True, score=3, max_score=5,
            detail="Kontrol başarısız",
        ))


def _grade(total: int, maximum: int) -> str:
    """Toplam puandan harf notu üret."""
    pct = total / maximum * 100 if maximum else 0
    if pct >= 90:
        return "A"
    if pct >= 80:
        return "B"
    if pct >= 70:
        return "C"
    if pct >= 60:
        return "D"
    return "F"


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

    # Read .PKGINFO once up front: it carries the authoritative pkgname and is
    # reused by the compatibility/metadata checks below. Deriving the name from
    # the filename via stem.split(".")[0] mis-parses dotted versions
    # (lictest-1.0.0-1-any -> "lictest-1"), so prefer pkgname and fall back to
    # stripping the .pkg.tar.* suffix chain + version-rel-arch.
    pkginfo = _read_pkginfo(pkg_path)
    report.package_name = pkginfo.get("pkgname", "") or _name_from_filename(pkg_path)

    _security_checks(pkg_path, tools, report)
    _compatibility_checks(pkginfo, report)
    _metadata_checks(pkginfo, report)
    _size_checks(pkg_path, report)

    # Calculate total
    report.total_score = sum(c.score for c in report.checks)
    report.max_score = sum(c.max_score for c in report.checks)
    report.grade = _grade(report.total_score, report.max_score)

    return report
