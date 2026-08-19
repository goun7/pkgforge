"""PkgForge — Offline Mode Cache.

Provides local caching for network-dependent operations so PkgForge
can work without internet access. Caches:
- AUR RPC responses
- Package analysis results
- ClamAV database timestamps
- Upstream tracker ETags/Last-Modified

Usage:
    from core.offline_cache import OfflineCache

    cache = OfflineCache()
    # Try cache first, then network
    data = cache.get_or_fetch("aur", "firefox", fetch_func)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "pkgforge" / "offline"
DEFAULT_TTL = 86400  # 24 hours


class OfflineCache:
    """Local file-based cache for network operations."""

    def __init__(self, cache_dir: Path | None = None, ttl: int = DEFAULT_TTL):
        """Initialize the cache.

        Args:
            cache_dir: Directory to store cache files. Defaults to ~/.cache/pkgforge/offline
            ttl: Cache time-to-live in seconds. Default 24h.
        """
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.ttl = ttl
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Create cache directory if it doesn't exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key_path(self, namespace: str, key: str) -> Path:
        """Generate a file path for a cache key."""
        safe_key = hashlib.sha256(key.encode()).hexdigest()[:16]
        return self.cache_dir / namespace / f"{safe_key}.json"

    def get(self, namespace: str, key: str) -> dict | None:
        """Get a cached value if it exists and hasn't expired.

        Args:
            namespace: Cache namespace (e.g., "aur", "analysis", "tracker")
            key: Cache key (e.g., package name, URL)

        Returns:
            Cached dict or None if not found/expired.
        """
        path = self._key_path(namespace, key)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            # Check TTL
            if time.time() - data.get("_cached_at", 0) > self.ttl:
                log.debug("Cache expired: %s/%s", namespace, key)
                return None
            return data.get("value")
        except (json.JSONDecodeError, OSError) as exc:
            log.debug("Cache read error: %s", exc)
            return None

    def put(self, namespace: str, key: str, value: dict | list | str | int | float) -> None:
        """Store a value in the cache.

        Args:
            namespace: Cache namespace.
            key: Cache key.
            value: Value to cache (must be JSON-serializable).
        """
        path = self._key_path(namespace, key)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "_cached_at": time.time(),
            "_namespace": namespace,
            "_key": key[:100],
            "value": value,
        }

        try:
            import tempfile
            fd, tmp_path = tempfile.mkstemp(
                dir=str(path.parent), suffix=".tmp", prefix="cache_"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(tmp_path, str(path))  # Atomic rename
            except Exception:
                # Clean up temp file on failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except OSError as exc:
            log.warning("Cache write error: %s", exc)

    def get_or_fetch(
        self,
        namespace: str,
        key: str,
        fetch_func,
        force_refresh: bool = False,
    ):
        """Get from cache or fetch from network.

        Args:
            namespace: Cache namespace.
            key: Cache key.
            fetch_func: Callable that returns the value if not cached.
            force_refresh: If True, bypass cache and fetch fresh data.

        Returns:
            Cached or freshly fetched value.
        """
        if not force_refresh:
            cached = self.get(namespace, key)
            if cached is not None:
                log.debug("Cache hit: %s/%s", namespace, key)
                return cached

        log.debug("Cache miss: %s/%s — fetching", namespace, key)
        try:
            value = fetch_func()
            if value is not None:
                self.put(namespace, key, value)
            return value
        except Exception as exc:
            log.warning("Fetch failed for %s/%s: %s", namespace, key, exc)
            # Return stale cache if available
            return self.get(namespace, key)

    def invalidate(self, namespace: str, key: str) -> bool:
        """Remove a specific cache entry.

        Returns:
            True if entry was found and removed.
        """
        path = self._key_path(namespace, key)
        if path.exists():
            path.unlink()
            return True
        return False

    def clear_namespace(self, namespace: str) -> int:
        """Remove all entries in a namespace.

        Returns:
            Number of entries removed.
        """
        ns_dir = self.cache_dir / namespace
        if not ns_dir.exists():
            return 0

        count = 0
        for f in ns_dir.glob("*.json"):
            f.unlink()
            count += 1
        return count

    def clear_all(self) -> int:
        """Remove all cache entries.

        Returns:
            Number of entries removed.
        """
        count = 0
        for ns_dir in self.cache_dir.iterdir():
            if ns_dir.is_dir():
                for f in ns_dir.glob("*.json"):
                    f.unlink()
                    count += 1
        return count

    def stats(self) -> dict:
        """Get cache statistics."""
        total_entries = 0
        total_size = 0
        namespaces: dict[str, int] = {}

        for ns_dir in self.cache_dir.iterdir():
            if not ns_dir.is_dir():
                continue
            ns_count = 0
            for f in ns_dir.glob("*.json"):
                total_entries += 1
                ns_count += 1
                total_size += f.stat().st_size
            namespaces[ns_dir.name] = ns_count

        return {
            "total_entries": total_entries,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "namespaces": namespaces,
            "cache_dir": str(self.cache_dir),
            "ttl_hours": self.ttl // 3600,
        }

    def is_offline(self) -> bool:
        """Quick check if we're likely offline."""
        try:
            import urllib.request
            req = urllib.request.Request(
                "https://aur.archlinux.org",
                method="HEAD",
                headers={"User-Agent": "PkgForge/2.0"},
            )
            urllib.request.urlopen(req, timeout=3)
            return False
        except Exception:
            return True


# Global cache instance
_cache: OfflineCache | None = None


def get_cache() -> OfflineCache:
    """Get the global cache instance."""
    global _cache
    if _cache is None:
        _cache = OfflineCache()
    return _cache
