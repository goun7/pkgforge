"""PkgForge — Conversion / compatibility report export.

Serializes a compatibility report (plus optional package metadata and security
info) into a shareable JSON document — useful for bug reports and auditing.
Kept free of any Qt dependency so it is easy to unit-test and reuse from CLI.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

from config import APP_NAME, APP_VERSION


def report_to_dict(
    report: Any,
    *,
    metadata: Any = None,
    sha256: str = "",
    signature: Any = None,
) -> dict[str, Any]:
    """Build a plain-dict representation of a conversion result."""
    data: dict[str, Any] = {
        "tool": APP_NAME,
        "tool_version": APP_VERSION,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
        "grade": getattr(report, "grade", "N/A") if report is not None else "N/A",
        "overall": report.overall.value if report is not None else "unknown",
        "sha256": sha256,
        "package": None,
        "signature": None,
        "checks": [],
    }

    if metadata is not None:
        data["package"] = {
            "name": metadata.name,
            "version": metadata.version,
            "arch": metadata.arch,
            "arch_mapped": metadata.arch_mapped,
            "type": metadata.package_type,
            "file_count": len(metadata.file_list),
        }

    if signature is not None:
        data["signature"] = {
            "has_signature": signature.has_signature,
            "detail": signature.detail,
        }

    if report is not None:
        for check in report.checks:
            data["checks"].append(
                {
                    "name": check.name,
                    "severity": check.severity.value,
                    "message": check.message,
                    "details": list(check.details),
                }
            )

    return data


def report_to_json(report: Any, **kwargs: Any) -> str:
    """Return the report as a pretty-printed JSON string."""
    return json.dumps(report_to_dict(report, **kwargs), indent=2, ensure_ascii=False)


def save_report_json(path: str | Path, report: Any, **kwargs: Any) -> Path:
    """Write the report JSON to *path* and return the written Path."""
    out = Path(path)
    out.write_text(report_to_json(report, **kwargs), encoding="utf-8")
    return out
