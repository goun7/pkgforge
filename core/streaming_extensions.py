"""Tur-55 B8: Large-package streaming extensions.

core/streaming.py zaten chunk hash + copy sağlar. Buraya eklediklerimiz:
  - stream_integrity: tek geçişte sha256+blake2b+size+chunk_count
  - stream_tar_index: tar header'larını ayrıştırır, body'i atlar
    (1 GB+ .pkg.tar içinden dosya listesini < 1 MB bellekle çıkarır)
  - stream_manifest_writer: streaming JSON manifest writer (bellek sabit)
  - stream_split: büyük dosyayı parçalara böler (CD/DVD/USB dağıtımı)
  - stream_join: parçaları birleştirir, bütünlük doğrular

Tüm fonksiyonlar sabit bellek kullanır (chunk_size parametresine bağlı).
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

from core.streaming import DEFAULT_CHUNK_SIZE, chunked_read


@dataclass
class IntegrityReport:
    """Single-pass hash + size + chunk count report."""
    size: int = 0
    sha256: str = ""
    blake2b: str = ""
    chunks: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def stream_integrity(
    file_path: Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> IntegrityReport:
    """Single-pass sha256 + blake2b + size + chunk_count.

    Büyük dosyaları iki kez okumadan çoklu hash üretir; her iki hash
    aynı anda güncellenir (bellek = 2 × chunk_size).
    """
    sha = hashlib.sha256()
    blake = hashlib.blake2b()
    report = IntegrityReport()
    with open(file_path, "rb") as f:
        for chunk in chunked_read(file_path, chunk_size):
            sha.update(chunk)
            blake.update(chunk)
            report.chunks += 1
    report.size = file_path.stat().st_size
    report.sha256 = sha.hexdigest()
    report.blake2b = blake.hexdigest()
    return report


@dataclass
class TarEntry:
    """A single tar header (body not loaded)."""
    name: str = ""
    size: int = 0
    mode: int = 0
    mtime: int = 0
    typeflag: str = ""  # '0' regular, '5' dir, etc.
    is_dir: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _parse_tar_header(header: bytes) -> TarEntry | None:
    """Parse a single 512-byte POSIX tar header (ustar + old GNU).

    Returns None if the header is all-zero (EOF marker) or if it does
    not look like a tar header at all. No exception raised for invalid
    headers — caller treats them as 'end of archive'.
    """
    if len(header) < 512:
        return None
    if header == b"\x00" * 512:
        return None
    try:
        # Tar name is 0:100 bytes, null-terminated.
        name_raw = header[0:100].rstrip(b"\x00").decode("utf-8", errors="replace")
        if not name_raw:
            return None
        # Magic: 257:265. If we see 'ustar\0' or 'ustar  ' it's a ustar header.
        magic = header[257:265]
        if magic not in (b"ustar\x00", b"ustar  "):
            # Old-style tar (no magic). Still parse name/size.
            pass
        # size field is octal ASCII at 124:135, null/space terminated.
        size_raw = header[124:136].rstrip(b"\x00 ").decode("ascii", errors="ignore")
        size = int(size_raw, 8) if size_raw else 0
        mode_raw = header[100:108].rstrip(b"\x00 ").decode("ascii", errors="ignore")
        mode = int(mode_raw, 8) if mode_raw else 0
        mtime_raw = header[136:148].rstrip(b"\x00 ").decode("ascii", errors="ignore")
        mtime = int(mtime_raw, 8) if mtime_raw else 0
        typeflag = chr(header[156]) if header[156:157] else ""
        return TarEntry(
            name=name_raw,
            size=size,
            mode=mode,
            mtime=mtime,
            typeflag=typeflag,
            is_dir=(typeflag == "5"),
        )
    except (ValueError, IndexError):
        return None


def stream_tar_index(
    tar_path: Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> Iterator[TarEntry]:
    """Stream-parse a tar archive: yield header info, skip body bytes.

    Her entry için yalnızca 512-byte header bellekte tutulur; gövde
    (boyut + 512 padding) seek ile atlanır. 1 GB tar dosyası saniyeler
    içinde taranır, < 1 MB bellek.
    """
    with open(tar_path, "rb") as f:
        while True:
            header = f.read(512)
            if len(header) < 512:
                return
            entry = _parse_tar_header(header)
            if entry is None:
                return
            yield entry
            if entry.size > 0:
                body_skip = (entry.size + 511) & ~0x1FF
                f.seek(body_skip, os.SEEK_CUR)


def stream_manifest_writer(
    entries: list[dict],
    output: Path,
) -> int:
    """Stream-write a JSON manifest: bytes flushed as we go.

    Bellek: sadece tek satır + açma/kapama yükü.
    Returns: bytes written.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "wb") as f:
        f.write(b'{\n  "packages": [\n')
        for i, e in enumerate(entries):
            sep = b"," if i < len(entries) - 1 else b""
            line = b"    " + json.dumps(e, ensure_ascii=False).encode("utf-8") + sep + b"\n"
            f.write(line)
        f.write(b"  ]\n}\n")
    return output.stat().st_size


def stream_split(
    src: Path,
    out_dir: Path,
    part_size: int = 700 * 1024 * 1024,  # 700 MB — CD/DVD default
    base_name: str | None = None,
) -> list[Path]:
    """Split a file into parts of `part_size` bytes.

    Returns the list of created part paths. Each part is named
    `<base>.part-NN` (NN = zero-padded 3 digits). The manifest file
    `<base>.manifest.json` records per-part sha256 + sizes for join.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    base = base_name or src.name
    parts: list[Path] = []
    sha256 = hashlib.sha256()
    part_hashes: list[dict] = []
    total = src.stat().st_size
    bytes_seen = 0

    with open(src, "rb") as f_in:
        idx = 1
        while bytes_seen < total:
            part_path = out_dir / f"{base}.part-{idx:03d}"
            hasher = hashlib.sha256()
            written = 0
            with open(part_path, "wb") as f_out:
                while written < part_size and bytes_seen < total:
                    remaining_file = total - bytes_seen
                    remaining_part = part_size - written
                    need = min(remaining_part, remaining_file, DEFAULT_CHUNK_SIZE)
                    if need <= 0:
                        break
                    chunk = f_in.read(need)
                    if not chunk:
                        break
                    take = len(chunk)
                    f_out.write(chunk)
                    hasher.update(chunk)
                    sha256.update(chunk)
                    written += take
                    bytes_seen += take
            if written == 0:
                part_path.unlink(missing_ok=True)
                break  # outer: no progress, EOF
            part_hashes.append({"part": part_path.name,
                                "size": written,
                                "sha256": hasher.hexdigest()})
            parts.append(part_path)
            idx += 1

    manifest = {
        "base": base,
        "total_size": total,
        "total_sha256": sha256.hexdigest(),
        "parts": part_hashes,
    }
    manifest_path = out_dir / f"{base}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2),
                             encoding="utf-8")
    return parts


def stream_join(
    parts: list[Path],
    dst: Path,
    expected_sha256: str | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> int:
    """Join parts into a single file, optionally verify sha256.

    Returns total bytes written. If expected_sha256 is given and
    mismatch occurs, raises ValueError after deleting partial output.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256()
    written = 0
    try:
        with open(dst, "wb") as f_out:
            for part in parts:
                for chunk in chunked_read(part):
                    f_out.write(chunk)
                    sha.update(chunk)
                    written += len(chunk)
                    if progress:
                        progress(written, 0)
        if expected_sha256 and sha.hexdigest() != expected_sha256:
            raise ValueError(
                f"sha256 mismatch: expected {expected_sha256}, "
                f"got {sha.hexdigest()}"
            )
    except Exception:
        dst.unlink(missing_ok=True)
        raise
    return written
