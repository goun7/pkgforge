"""Tur-55 C9: Monorepo workspace introspection.

Her üyeden (core, desktop, shared) başlık-bilgi döner; kapasite
ve yetenek sorusuna tek yerden cevap üretir.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import tomllib


@dataclass
class MemberInfo:
    name: str
    path: str
    language: str
    runtime: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "path": self.path,
                "language": self.language, "runtime": self.runtime}


WORKSPACE_FILE = Path(__file__).resolve().parent.parent / "workspace.toml"


class Workspace:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or WORKSPACE_FILE.parent
        self._members: dict[str, MemberInfo] = {}
        if WORKSPACE_FILE.is_file():
            try:
                data = tomllib.loads(WORKSPACE_FILE.read_text(encoding="utf-8"))
            except (OSError, tomllib.TOMLDecodeError):
                return
            for key in data.get("workspace", {}).get("members", []):
                m = data.get(key)
                if not isinstance(m, dict):
                    continue
                self._members[key] = MemberInfo(
                    name=key,
                    path=str(Path(self.root, m.get("path", key))),
                    language=m.get("language", ""),
                    runtime=m.get("runtime", ""),
                )

    def members(self) -> list[MemberInfo]:
        return list(self._members.values())

    def get(self, name: str) -> MemberInfo | None:
        return self._members.get(name)

    def to_dict(self) -> dict[str, dict[str, str]]:
        return {m.name: m.to_dict() for m in self.members()}

    def resolve_path(self, path: str | Path) -> Path:
        """Resolve a path relative to the workspace root if not absolute."""
        p = Path(path)
        if p.is_absolute():
            return p.resolve()
        cwd_candidate = (Path.cwd() / p).resolve()
        if cwd_candidate.exists():
            return cwd_candidate
        root_candidate = (self.root / p).resolve()
        if root_candidate.exists():
            return root_candidate
        return root_candidate


