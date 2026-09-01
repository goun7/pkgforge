"""Tur-55 C9: Package Manifest contract (Python).

JSON Schema: package_manifest.schema.json
Bu dataclass hem validasyon hem de serileştirme sağlar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PackageManifest:
    name: str = ""
    version: str = ""
    arch: str = ""
    size_bytes: int = 0
    sha256: str = ""
    dependencies: list[str] = field(default_factory=list)
    signed: bool = False
    signature_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "arch": self.arch,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "dependencies": list(self.dependencies),
            "signed": self.signed,
            "signature_path": self.signature_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PackageManifest:
        return cls(
            name=data.get("name", ""),
            version=data.get("version", ""),
            arch=data.get("arch", ""),
            size_bytes=int(data.get("size_bytes", 0)),
            sha256=data.get("sha256", ""),
            dependencies=list(data.get("dependencies", [])),
            signed=bool(data.get("signed", False)),
            signature_path=data.get("signature_path", ""),
        )
