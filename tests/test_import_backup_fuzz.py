"""Faz 5 (F5.7) — hypothesis fuzz for import_backup path-safety.

Invariant under test: for ANY crafted bundle, import_backup either raises
SyncError or writes ONLY inside the isolated config root. We spy on every
filesystem mutation (Path.write_bytes and os.replace) and assert each target
resolves inside CONFIG_DIR, so a traversal that slipped past the name checks
would fail loudly even if it "succeeded".
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import zipfile
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import config
from core.cloud_sync import SyncError, import_backup

_MARKER = "pkgforge-backup.json"
_MANIFEST = "manifest.json"
_BUNDLE_FILES = ("settings.json", "history.db", "history.db-wal", "history.db-shm")


@pytest.fixture
def cfg_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "pkgforge-config"
    root.mkdir()
    monkeypatch.setattr(config, "CONFIG_DIR", root)
    return root


@pytest.fixture
def write_spy(monkeypatch: pytest.MonkeyPatch):
    """Record every absolute path that import_backup tries to write/replace."""
    recorded: list[Path] = []
    orig_replace = os.replace

    def spy_replace(src, dst):
        recorded.append(Path(dst).resolve())
        return orig_replace(src, dst)

    orig_wb = Path.write_bytes

    def spy_wb(self, data):
        recorded.append(Path(self).resolve())
        return orig_wb(self, data)

    monkeypatch.setattr("core.cloud_sync.os.replace", spy_replace)
    monkeypatch.setattr(Path, "write_bytes", spy_wb)
    return recorded


# --- adversarial member-name strategies ------------------------------------

_VALID_PROFILES = ["default", "work", "A1_b-2", "x" * 64]
_TRAVERSAL_NAMES = [
    "../evil/settings.json",
    "../../etc/passwd",
    "..\\..\\windows\\system32",
    "a/../../escape/settings.json",
    "/etc/passwd",
    "default/../../../tmp/pwned",
    "default/settings.json/../../x",
    "de..fault/settings.json",
    "default/settings.json\x00.png",
    "./default/settings.json",
    "default//settings.json",
    "a/b/c/settings.json",
    "onlyonepart",
    "",
    "default/" + "history.db",
    ("long" * 40) + "/settings.json",
]

member_name = st.one_of(
    # valid profile + valid file (should be accepted when hashes match)
    st.tuples(st.sampled_from(_VALID_PROFILES), st.sampled_from(_BUNDLE_FILES))
      .map(lambda t: t[0] + "/" + t[1]),
    # valid profile + arbitrary (often invalid) filename
    st.tuples(st.sampled_from(_VALID_PROFILES), st.text(min_size=0, max_size=20))
      .map(lambda t: t[0] + "/" + t[1]),
    # explicit traversal / absolute / malformed names
    st.sampled_from(_TRAVERSAL_NAMES),
    # fully random names (may contain slashes, dots, NUL, unicode)
    st.text(min_size=0, max_size=60),
)

member_content = st.one_of(
    st.just(b""),
    st.binary(min_size=0, max_size=256),
    # a "bomb-ish" blob that still stays fast (compresses well)
    st.just(b"\x00" * (1024 * 64)),
)


def _build_zip(entries: list[tuple[str, bytes]], include_marker: bool,
               include_manifest: bool, corrupt_hash: bool) -> bytes:
    buf = io.BytesIO()
    # Dedupe member names so zipfile does not warn about duplicates.
    unique: list[tuple[str, bytes]] = []
    seen: set[str] = set()
    for name, blob in entries:
        if name in (_MARKER, _MANIFEST) or not name or name in seen:
            continue
        seen.add(name)
        unique.append((name, blob))

    manifest_files: dict[str, str] = {}
    for name, blob in unique:
        if corrupt_hash:
            manifest_files[name] = "0" * 64
        else:
            manifest_files[name] = hashlib.sha256(blob).hexdigest()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if include_marker:
            zf.writestr(_MARKER, json.dumps({"app": "pkgforge"}))
        if include_manifest:
            zf.writestr(_MANIFEST, json.dumps({"files": manifest_files}))
        for name, blob in unique:
            try:
                zf.writestr(name, blob)
            except (ValueError, zipfile.BadZipFile):
                # zip itself rejects some pathological names; skip them
                continue
    return buf.getvalue()


@settings(max_examples=60, deadline=None,
          suppress_health_check=[HealthCheck.too_slow,
                                 HealthCheck.function_scoped_fixture])
@given(
    entries=st.lists(st.tuples(member_name, member_content),
                     min_size=0, max_size=6),
    include_marker=st.booleans(),
    include_manifest=st.booleans(),
    corrupt_hash=st.booleans(),
)
def test_import_backup_never_writes_outside_config(
    cfg_root: Path, write_spy: list[Path],
    entries, include_marker, include_manifest, corrupt_hash,
):
    bundle = _build_zip(entries, include_marker, include_manifest, corrupt_hash)
    zip_path = cfg_root / "fuzz.zip"
    zip_path.write_bytes(bundle)
    write_spy.clear()  # bundle dosyasinin kendisini kayitlardan dus

    try:
        result = import_backup(str(zip_path))
    except SyncError:
        result = None
    except zipfile.BadZipFile:
        result = None

    # Invariant 1: nothing was even attempted outside the config root.
    for target in write_spy:
        assert target.is_relative_to(cfg_root.resolve()), (
            f"import_backup yazdi: {target} (kok: {cfg_root})")

    # Invariant 2: on success, every reported restore lives inside the root.
    if result and result.get("ok"):
        for rel in result["restored"]:
            assert ".." not in rel
            prof, fname = rel.split("/", 1)
            assert fname in _BUNDLE_FILES
            assert config.PROFILE_NAME_RE.match(prof)


def test_absolute_path_member_is_rejected(cfg_root: Path, write_spy):
    bundle = _build_zip([("/etc/passwd", b"root:x:0:0")], True, True, False)
    zip_path = cfg_root / "abs.zip"
    zip_path.write_bytes(bundle)
    write_spy.clear()  # bundle dosyasinin kendisini kayitlardan dus
    with pytest.raises(SyncError):
        import_backup(str(zip_path))
    assert write_spy == []


def test_traversal_member_is_rejected(cfg_root: Path, write_spy):
    bundle = _build_zip([("../../escape/settings.json", b"{}")], True, True, False)
    zip_path = cfg_root / "trav.zip"
    zip_path.write_bytes(bundle)
    write_spy.clear()  # bundle dosyasinin kendisini kayitlardan dus
    with pytest.raises(SyncError):
        import_backup(str(zip_path))
    assert write_spy == []


def test_missing_marker_is_rejected(cfg_root: Path, write_spy):
    bundle = _build_zip([("default/settings.json", b"{}")], False, True, False)
    zip_path = cfg_root / "nomarker.zip"
    zip_path.write_bytes(bundle)
    write_spy.clear()  # bundle dosyasinin kendisini kayitlardan dus
    with pytest.raises(SyncError):
        import_backup(str(zip_path))
    assert write_spy == []


def test_tampered_hash_is_rejected(cfg_root: Path, write_spy):
    bundle = _build_zip([("default/settings.json", b'{"a":1}')], True, True, True)
    zip_path = cfg_root / "tamper.zip"
    zip_path.write_bytes(bundle)
    write_spy.clear()  # bundle dosyasinin kendisini kayitlardan dus
    with pytest.raises(SyncError):
        import_backup(str(zip_path))
    assert write_spy == []


def test_valid_bundle_restores_inside_root(cfg_root: Path, write_spy):
    payload = json.dumps({"theme": "dark"}).encode()
    bundle = _build_zip([("default/settings.json", payload)], True, True, False)
    zip_path = cfg_root / "good.zip"
    zip_path.write_bytes(bundle)
    write_spy.clear()  # bundle dosyasinin kendisini kayitlardan dus
    result = import_backup(str(zip_path))
    assert result["ok"] is True
    assert result["restored"] == ["default/settings.json"]
    restored_file = cfg_root / "settings.json"
    assert restored_file.read_bytes() == payload
    for target in write_spy:
        assert target.is_relative_to(cfg_root.resolve())
