"""PkgForge — Retry Utility with Exponential Backoff.

Provides retry logic with exponential backoff and jitter for network
operations (HTTP downloads, AUR RPC calls, etc.).

Usage:
    from core.retry import retry_with_backoff, RetryConfig

    result = retry_with_backoff(
        lambda: urllib.request.urlopen(url, timeout=10),
        config=RetryConfig(max_retries=3, base_delay=1.0),
    )
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

log = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay: float = 1.0       # Initial delay in seconds
    max_delay: float = 30.0       # Maximum delay cap
    backoff_factor: float = 2.0   # Multiplier per retry
    jitter: bool = True           # Add random jitter to prevent thundering herd
    retryable_exceptions: tuple[type[Exception], ...] = (ConnectionError, TimeoutError, OSError)

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number (0-indexed)."""
        delay = min(self.base_delay * (self.backoff_factor ** attempt), self.max_delay)
        if self.jitter:
            delay = delay * (0.5 + random.random() * 0.5)  # 50-100% of calculated delay
        return delay


def retry_with_backoff(
    func: Callable[[], T],
    config: RetryConfig | None = None,
    operation_name: str = "",
) -> T:
    """Execute a function with retry and exponential backoff.

    Args:
        func: Callable to execute. Should raise on failure.
        config: Retry configuration. Uses defaults if None.
        operation_name: Name for logging purposes.

    Returns:
        Result of func() on success.

    Raises:
        The last exception from func() after all retries exhausted.
    """
    if config is None:
        config = RetryConfig()

    last_exception: Exception | None = None

    for attempt in range(config.max_retries + 1):
        try:
            return func()
        except config.retryable_exceptions as exc:
            last_exception = exc
            if attempt < config.max_retries:
                delay = config.get_delay(attempt)
                log.warning(
                    "Deneme %d/%d başarısız (%s)%s: %s — %.1fs sonra tekrar denenecek",
                    attempt + 1,
                    config.max_retries + 1,
                    operation_name or "operasyon",
                    f" [{exc.__class__.__name__}]",
                    str(exc)[:100],
                    delay,
                )
                time.sleep(delay)
            else:
                log.error(
                    "Tüm denemeler başarısız (%s): %s",
                    operation_name or "operasyon",
                    str(exc)[:200],
                )

    raise last_exception  # type: ignore[misc]


def retry_download(
    url: str,
    max_retries: int = 3,
    timeout: int = 30,
) -> bytes:
    """Download URL content with retry and exponential backoff.

    Args:
        url: URL to download.
        max_retries: Maximum number of retry attempts.
        timeout: Request timeout in seconds.

    Returns:
        Response body as bytes.
    """
    import urllib.request
    import urllib.error

    def _do_download() -> bytes:
        from config import APP_VERSION
        req = urllib.request.Request(url, headers={"User-Agent": f"PkgForge/{APP_VERSION}"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            return resp.read()

    config = RetryConfig(
        max_retries=max_retries,
        base_delay=2.0,
        retryable_exceptions=(
            urllib.error.URLError,
            ConnectionError,
            TimeoutError,
            OSError,
        ),
    )

    return retry_with_backoff(_do_download, config=config, operation_name=f"download({url[:50]})")


def retry_aur_rpc(
    url: str,
    max_retries: int = 2,
    timeout: int = 15,
) -> dict:
    """Make an AUR RPC call with retry.

    Args:
        url: Full AUR RPC URL.
        max_retries: Maximum number of retry attempts.
        timeout: Request timeout in seconds.

    Returns:
        Parsed JSON response dict.
    """
    import json
    import urllib.request
    import urllib.error

    def _do_rpc() -> dict:
        from config import APP_VERSION
        req = urllib.request.Request(url, headers={"User-Agent": f"PkgForge/{APP_VERSION}"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            return json.loads(resp.read())

    config = RetryConfig(
        max_retries=max_retries,
        base_delay=1.0,
        retryable_exceptions=(
            urllib.error.URLError,
            ConnectionError,
            TimeoutError,
            OSError,
            json.JSONDecodeError,
        ),
    )

    return retry_with_backoff(_do_rpc, config=config, operation_name="aur-rpc")
