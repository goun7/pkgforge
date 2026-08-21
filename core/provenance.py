"""PkgForge — SLSA Provenance Tracking.

Records build metadata (source, timestamps, hashes, build environment)
for every converted package.  This enables verification of package
provenance and supply chain integrity.

Provenance records are stored as JSON alongside converted packages
and in the HistoryDB for audit purposes.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from config import APP_NAME, APP_VERSION, ToolPaths

log = logging.getLogger(__name__)


@dataclass
class BuildProvenance:
    """SLSA-style provenance record for a converted package."""

    # Identity
    tool_name: str = APP_NAME
    tool_version: str = APP_VERSION
    build_id: str = ""  # Unique build identifier

    # Source information
    source_file: str = ""
    source_type: str = ""  # "deb" | "rpm" | "flatpak" | "url"
    source_url: str = ""
    source_sha256: str = ""

    # Output information
    output_file: str = ""
    output_sha256: str = ""

    # Build environment
    build_host: str = ""
    build_user: str = ""
    build_os: str = ""
    build_arch: str = ""
    build_timestamp: str = ""
    build_duration_ms: int = 0

    # Package metadata
    package_name: str = ""
    package_version: str = ""
    package_arch: str = ""
    package_type: str = ""  # "deb" | "rpm" -> converted to arch

    # Security scan results
    clamav_scanned: bool = False
    clamav_result: str = ""  # "clean" | "infected" | "skipped"
    decompression_bomb_check: bool = False
    decompression_bomb_result: str = ""  # "safe" | "warning" | "skipped"

    # Verification
    signature_valid: bool = False
    signature_detail: str = ""

    # Integrity
    provenance_hash: str = ""  # SHA-256 of this record (self-referential)

    def compute_hash(self) -> str:
        """Compute SHA-256 of the provenance record (excluding provenance_hash)."""
        rec = asdict(self)
        rec["provenance_hash"] = ""
        content = json.dumps(rec, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content.encode()).hexdigest()

    def finalize(self) -> None:
        """Compute and set the self-referential hash."""
        self.provenance_hash = self.compute_hash()


def create_provenance(
    *,
    source_file: Path | str,
    source_type: str = "",
    source_url: str = "",
    source_sha256: str = "",
    output_file: Path | str = "",
    output_sha256: str = "",
    tools: ToolPaths | None = None,
    **kwargs,
) -> BuildProvenance:
    """Create a new BuildProvenance record with build environment info."""
    prov = BuildProvenance()

    # Build ID: timestamp + random suffix
    import random
    prov.build_id = f"build-{int(time.time())}-{random.randint(1000, 9999)}"

    # Source
    prov.source_file = str(source_file)
    prov.source_type = source_type or (Path(str(source_file)).suffix.lstrip(".").lower())
    prov.source_url = source_url
    prov.source_sha256 = source_sha256

    # Output
    prov.output_file = str(output_file)
    prov.output_sha256 = output_sha256

    # Build environment
    prov.build_host = platform.node()
    prov.build_user = os.getenv("USER", os.getenv("USERNAME", "unknown"))
    prov.build_os = f"{platform.system()} {platform.release()}"
    prov.build_arch = platform.machine()
    prov.build_timestamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    # Package metadata (from kwargs)
    prov.package_name = kwargs.get("package_name", "")
    prov.package_version = kwargs.get("package_version", "")
    prov.package_arch = kwargs.get("package_arch", "")
    prov.package_type = kwargs.get("package_type", "")

    # Security results
    prov.clamav_scanned = kwargs.get("clamav_scanned", False)
    prov.clamav_result = kwargs.get("clamav_result", "skipped")
    prov.decompression_bomb_check = kwargs.get("decompression_bomb_check", False)
    prov.decompression_bomb_result = kwargs.get("decompression_bomb_result", "skipped")
    prov.signature_valid = kwargs.get("signature_valid", False)
    prov.signature_detail = kwargs.get("signature_detail", "")

    # Compute hashes when the caller did not supply them.
    if not prov.source_sha256 and Path(prov.source_file).is_file():
        from core.security import sha256_hash
        try:
            prov.source_sha256 = sha256_hash(Path(prov.source_file))
        except Exception as exc:
            log.debug("Kaynak SHA256 hesaplanamadı: %s", exc)

    if not prov.output_sha256 and Path(prov.output_file).is_file():
        from core.security import sha256_hash
        try:
            prov.output_sha256 = sha256_hash(Path(prov.output_file))
        except Exception as exc:
            log.debug("Çıktı SHA256 hesaplanamadı: %s", exc)

    prov.finalize()
    return prov


def save_provenance(prov: BuildProvenance, path: Path | str) -> Path:
    """Save provenance record as JSON."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(prov)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Provenance kaydedildi: %s", out)
    return out


def load_provenance(path: Path | str) -> BuildProvenance | None:
    """Load a provenance record from JSON."""
    p = Path(path)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return BuildProvenance(**{k: v for k, v in data.items() if k in BuildProvenance.__dataclass_fields__})
    except (json.JSONDecodeError, TypeError) as exc:
        log.warning("Provenance yüklenemedi: %s", exc)
        return None


def verify_provenance(prov: BuildProvenance) -> tuple[bool, str]:
    """Verify a provenance record's integrity.

    Returns:
        (valid, message)
    """
    # 1. Check self-referential hash
    expected = prov.compute_hash()
    if expected != prov.provenance_hash:
        return False, f"Provenance hash uyuşmuyor: beklenen {expected[:16]}…, mevcut {prov.provenance_hash[:16]}…"

    # 2. Check source file exists and hash matches
    if prov.source_file and Path(prov.source_file).is_file() and prov.source_sha256:
        from core.security import sha256_hash
        actual = sha256_hash(Path(prov.source_file))
        if actual != prov.source_sha256:
            return False, f"Kaynak dosya hash uyuşmazlığı: {actual[:16]}… ≠ {prov.source_sha256[:16]}…"

    # 3. Check output file exists and hash matches
    if prov.output_file and Path(prov.output_file).is_file() and prov.output_sha256:
        from core.security import sha256_hash
        actual = sha256_hash(Path(prov.output_file))
        if actual != prov.output_sha256:
            return False, f"Çıktı dosyası hash uyuşmazlığı: {actual[:16]}… ≠ {prov.output_sha256[:16]}…"

    return True, "Provenance doğrulandı ✓"


def find_provenance(output_file: Path) -> Path | None:
    """Find the provenance JSON file for a given package file."""
    # Look in same directory with .provenance.json suffix
    prov_path = output_file.parent / f"{output_file.name}.provenance.json"
    if prov_path.is_file():
        return prov_path
    return None


# ── In-toto Attestation (SLSA Level 2) ──────────────────────────

@dataclass
class InTotoStatement:
    """In-toto attestation statement for supply chain integrity.

    Follows the in-toto attestation spec v1.0:
    https://in-toto.io/Statement/v1
    """
    _type: str = "https://in-toto.io/Statement/v1"
    predicate_type: str = "https://pkgforge.app/attestation/v1"
    subject: list[dict[str, Any]] = field(default_factory=list)
    predicate: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "_type": self._type,
            "predicateType": self.predicate_type,
            "subject": self.subject,
            "predicate": self.predicate,
        }


def create_attestation(
    prov: BuildProvenance,
    *,
    signer_key: str = "",
) -> InTotoStatement:
    """Create an in-toto attestation from a BuildProvenance record.

    The subject contains the output package identity and hash.
    The predicate contains the full build provenance.
    """
    # Subject: the output artifact
    subject = []
    if prov.output_file and prov.output_sha256:
        subject.append({
            "name": Path(prov.output_file).name,
            "digest": {"sha256": prov.output_sha256},
        })
    elif prov.output_file:
        subject.append({"name": Path(prov.output_file).name})

    # Predicate: full provenance metadata
    materials: list[dict[str, Any]] = []
    predicate: dict[str, Any] = {
        "builder": {
            "id": f"{prov.tool_name}@{prov.tool_version}",
        },
        "buildType": f"{prov.tool_name}/convert",
        "invocation": {
            "configSource": {
                "uri": prov.source_url or prov.source_file,
                "digest": {"sha256": prov.source_sha256} if prov.source_sha256 else {},
            },
        },
        "metadata": {
            "buildInvocationId": prov.build_id,
            "buildStartedOn": prov.build_timestamp,
            "buildFinishedOn": prov.build_timestamp,
            "completeness": {
                "environment": False,
                "materials": False,
                "reproducible": False,
            },
            "reproducible": False,
        },
        "materials": materials,
        "environment": {
            "arch": prov.build_arch,
            "os": prov.build_os,
            "host": prov.build_host,
        },
        "security": {
            "clamav": prov.clamav_result,
            "decompression_bomb": prov.decompression_bomb_result,
            "signature_valid": prov.signature_valid,
        },
    }

    # Source material
    if prov.source_file:
        material: dict[str, Any] = {"uri": prov.source_file}
        if prov.source_sha256:
            material["digest"] = {"sha256": prov.source_sha256}
        materials.append(material)

    statement = InTotoStatement(subject=subject, predicate=predicate)

    # Sign if key provided
    if signer_key:
        statement.predicate["signer"] = {
            "keyId": signer_key[:16],
        }

    return statement


def save_attestation(
    attestation: InTotoStatement,
    output_path: Path,
) -> Path:
    """Save in-toto attestation as JSON."""
    out = output_path.with_suffix(".attestation.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(attestation.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("Attestation kaydedildi: %s", out)
    return out


def verify_attestation(attestation: InTotoStatement) -> tuple[bool, str]:
    """Verify an in-toto attestation statement."""
    # Check statement type
    if attestation._type != "https://in-toto.io/Statement/v1":
        return False, f"Geçersiz statement tipi: {attestation._type}"

    # Check predicate type
    if not attestation.predicate_type.startswith("https://"):
        return False, f"Geçersiz predicate tipi: {attestation.predicate_type}"

    # Check subject exists
    if not attestation.subject:
        return False, "Attestation'da subject yok"

    # Check required predicate fields
    pred = attestation.predicate
    for key in ("builder", "buildType", "metadata"):
        if key not in pred:
            return False, f"Predicate'de '{key}' alanı eksik"

    return True, "Attestation doğrulandı ✓"
    return None
