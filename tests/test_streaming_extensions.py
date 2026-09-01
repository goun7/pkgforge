"""Tur-55 B8: Large-package streaming extensions."""
from __future__ import annotations

import io
import json
import os
import tarfile
from pathlib import Path

import pytest

from core.streaming_extensions import (
    IntegrityReport,
    stream_integrity,
    stream_join,
    stream_manifest_writer,
    stream_split,
    stream_tar_index,
)

# ---- stream_integrity ------------------------------------------------------

def test_stream_integrity_basic(tmp_path: Path) -> None:
    p = tmp_path / "data.bin"
    p.write_bytes(b"hello world" * 100)
    rep = stream_integrity(p)
    assert isinstance(rep, IntegrityReport)
    assert rep.size == p.stat().st_size
    assert len(rep.sha256) == 64
    assert len(rep.blake2b) == 128
    assert rep.chunks >= 1


def test_stream_integrity_empty(tmp_path: Path) -> None:
    p = tmp_path / "empty.bin"
    p.write_bytes(b"")
    rep = stream_integrity(p)
    assert rep.size == 0
    assert rep.chunks == 0
    assert rep.sha256  # still a valid hex digest of nothing


def test_stream_integrity_different_files_have_different_hashes(tmp_path: Path) -> None:
    a = tmp_path / "a.bin"; a.write_bytes(b"A" * 1000)
    b = tmp_path / "b.bin"; b.write_bytes(b"B" * 1000)
    ra = stream_integrity(a); rb = stream_integrity(b)
    assert ra.sha256 != rb.sha256
    assert ra.blake2b != rb.blake2b


# ---- stream_tar_index ------------------------------------------------------

def test_stream_tar_index_lists_entries(tmp_path: Path) -> None:
    """Index a tar with 3 files: names, sizes, types must all come back."""
    tar = tmp_path / "sample.tar"
    files = {"a.txt": 100, "b.txt": 200, "sub/c.txt": 300}
    with tarfile.open(tar, "w") as t:
        for name, size in files.items():
            data = b"\0" * size
            info = tarfile.TarInfo(name=name)
            info.size = size
            t.addfile(info, io.BytesIO(data))
    entries = list(stream_tar_index(tar))
    assert len(entries) == 3
    by_name = {e.name: e for e in entries}
    assert set(by_name.keys()) == set(files.keys())
    for name, size in files.items():
        assert by_name[name].size == size
        assert by_name[name].is_dir is False


def test_stream_tar_index_handles_empty(tmp_path: Path) -> None:
    """Empty tar yields no entries (just zero padding)."""
    tar = tmp_path / "empty.tar"
    with tarfile.open(tar, "w") as t:
        pass  # writes only end-of-archive block
    entries = list(stream_tar_index(tar))
    assert entries == []


def test_stream_tar_index_handles_non_tar(tmp_path: Path) -> None:
    """Non-tar file: empty generator, no crash."""
    p = tmp_path / "junk.bin"
    p.write_bytes(b"not a tar\n" * 10)
    entries = list(stream_tar_index(p))
    assert entries == []


# ---- stream_manifest_writer -----------------------------------------------

def test_stream_manifest_writer_round_trip(tmp_path: Path) -> None:
    out = tmp_path / "m.json"
    entries = [{"name": "x", "size": 1}, {"name": "y", "size": 2}]
    stream_manifest_writer(entries, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data == {"packages": entries}


def test_stream_manifest_writer_empty_list(tmp_path: Path) -> None:
    out = tmp_path / "m.json"
    stream_manifest_writer([], out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data == {"packages": []}


def test_stream_manifest_writer_creates_parent_dirs(tmp_path: Path) -> None:
    out = tmp_path / "deep" / "nested" / "m.json"
    stream_manifest_writer([{"name": "z", "size": 0}], out)
    assert out.is_file()


# ---- stream_split + stream_join -------------------------------------------

def test_stream_split_round_trip(tmp_path: Path) -> None:
    """Split a 2.5 MB file into 1 MB parts and rejoin — must match exactly."""
    src = tmp_path / "big.bin"
    src.write_bytes(os.urandom(2_500_000))
    out_dir = tmp_path / "parts"
    parts = stream_split(src, out_dir, part_size=1_000_000)
    sizes = [p.stat().st_size for p in parts]
    assert sizes == [1_000_000, 1_000_000, 500_000]
    manifest = json.loads((out_dir / "big.bin.manifest.json").read_text())
    assert manifest["total_size"] == 2_500_000
    assert len(manifest["parts"]) == 3
    assert sum(p["size"] for p in manifest["parts"]) == 2_500_000
    rejoined = tmp_path / "big.rejoined.bin"
    stream_join(parts, rejoined, expected_sha256=manifest["total_sha256"])
    assert rejoined.read_bytes() == src.read_bytes()


def test_stream_split_size_aligned(tmp_path: Path) -> None:
    """File exactly equal to N parts → N parts, no trailing smaller part."""
    src = tmp_path / "exact.bin"
    src.write_bytes(os.urandom(2_000_000))
    out_dir = tmp_path / "parts"
    parts = stream_split(src, out_dir, part_size=1_000_000)
    assert len(parts) == 2
    assert all(p.stat().st_size == 1_000_000 for p in parts)


def test_stream_join_sha256_mismatch_raises(tmp_path: Path) -> None:
    src = tmp_path / "src.bin"; src.write_bytes(os.urandom(500_000))
    out_dir = tmp_path / "parts"
    parts = stream_split(src, out_dir, part_size=300_000)
    dest = tmp_path / "rejoined.bin"
    with pytest.raises(ValueError, match="sha256 mismatch"):
        stream_join(parts, dest, expected_sha256="00" * 32)
    assert not dest.exists()  # partial output cleaned up


def test_stream_split_no_manifest_part_size_aligned_no_remainder(tmp_path: Path) -> None:
    """Source smaller than one part → single part, no manifest mismatch."""
    src = tmp_path / "small.bin"; src.write_bytes(b"hello")
    out_dir = tmp_path / "parts"
    parts = stream_split(src, out_dir, part_size=1024)
    assert len(parts) == 1
    assert parts[0].read_bytes() == b"hello"
