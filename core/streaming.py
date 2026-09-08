"""PkgForge — Memory-Efficient File Processing.

Provides streaming utilities for processing large files without loading
entire contents into memory. Critical for 1GB+ packages.

Usage:
    from core.streaming import stream_hash, stream_copy, chunked_read

    sha256 = stream_hash(Path("large_package.deb"))
    stream_copy(src, dst, chunk_size=65536)
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Iterator
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 65536  # 64KB


def stream_hash(
    file_path: Path,
    algorithm: str = "sha256",
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> str:
    """Compute hash of a file using streaming (constant memory).

    Args:
        file_path: Path to the file.
        algorithm: Hash algorithm (sha256, md5, sha512, etc.).
        chunk_size: Read chunk size in bytes.

    Returns:
        Hex digest string.
    """
    hasher = hashlib.new(algorithm)
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def stream_copy(
    src: Path,
    dst: Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    progress_callback: Callable[[int, int], None] | None = None,
) -> int:
    """Copy a file using streaming (constant memory).

    Args:
        src: Source file path.
        dst: Destination file path.
        chunk_size: Read chunk size in bytes.
        progress_callback: Optional callback(bytes_copied, total_bytes).

    Returns:
        Total bytes copied.
    """
    total = src.stat().st_size
    copied = 0

    with open(src, "rb") as f_in, open(dst, "wb") as f_out:
        while True:
            chunk = f_in.read(chunk_size)
            if not chunk:
                break
            f_out.write(chunk)
            copied += len(chunk)
            if progress_callback and total > 0:
                progress_callback(copied, total)

    return copied


def chunked_read(
    file_path: Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> Iterator[bytes]:
    """Generator that yields chunks of a file.

    Args:
        file_path: Path to the file.
        chunk_size: Maximum chunk size in bytes.

    Yields:
        Bytes chunks.
    """
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk


def count_lines(file_path: Path, encoding: str = "utf-8") -> int:
    """Count lines in a file without loading it entirely.

    Args:
        file_path: Path to the text file.
        encoding: File encoding.

    Returns:
        Number of lines.
    """
    count = 0
    with open(file_path, "r", encoding=encoding, errors="ignore") as f:
        for _ in f:
            count += 1
    return count


def get_file_size_human(file_path: Path) -> str:
    """Get human-readable file size.

    Args:
        file_path: Path to the file.

    Returns:
        Size string like "1.5 GB", "256 KB", etc.
    """
    size = float(file_path.stat().st_size)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"
